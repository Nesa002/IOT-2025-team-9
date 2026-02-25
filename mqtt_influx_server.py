import os
import json
import queue
import threading
from datetime import datetime

from flask import Flask, jsonify, render_template, request, Response
import requests
import paho.mqtt.client as mqtt

from influxdb_client import InfluxDBClient, Point, WritePrecision

from settings import load_settings
from mqtt_publisher import MqttBatchPublisher
from logic_controller import LogicController



def _coerce_point(reading):
    point = (
        Point(reading.get("sensor_type", "sensor"))
        .tag("sensor", reading.get("sensor_name", "unknown"))
        .tag("device", reading.get("device", {}).get("device_name", "unknown"))
        .tag("pi_id", reading.get("device", {}).get("pi_id", "unknown"))
        .tag("simulated", str(reading.get("simulated", False)).lower())
    )

    timestamp = reading.get("timestamp")
    if timestamp:
        try:
            point.time(
                datetime.fromisoformat(timestamp.replace("Z", "+00:00")),
                WritePrecision.NS,
            )
        except ValueError:
            pass

    value = reading.get("value")
    if isinstance(value, (int, float)):
        point.field("value", value)
    else:
        point.field("state", str(value))

    unit = reading.get("unit")
    if unit:
        point.tag("unit", unit)

    tags = reading.get("tags", {})
    if isinstance(tags, dict):
        for key, tag_value in tags.items():
            point.tag(str(key), str(tag_value))

    return point


def create_app(settings_path=None):
    settings = load_settings(settings_path or "settings.json")

    mqtt_settings = settings.get("mqtt", {})
    influx_settings = settings.get("influxdb", {})
    grafana_settings = settings.get("grafana", {})

    grafana_url = grafana_settings.get("url", "http://localhost:3000")
    dashboard_uid = grafana_settings.get("dashboard_uid", "")

    stop_event = threading.Event()
    write_queue = queue.Queue()

    app = Flask(__name__)

    influx_client = InfluxDBClient(
        url=os.getenv("INFLUX_URL", influx_settings.get("url")),
        token=os.getenv("INFLUX_TOKEN", influx_settings.get("token")),
        org=os.getenv("INFLUX_ORG", influx_settings.get("org")),
    )
    write_api = influx_client.write_api()

    def influx_worker():
        while not stop_event.is_set():
            try:
                reading = write_queue.get(timeout=1)
            except queue.Empty:
                continue

            point = _coerce_point(reading)

            write_api.write(
                bucket=os.getenv("INFLUX_BUCKET", influx_settings.get("bucket")),
                org=os.getenv("INFLUX_ORG", influx_settings.get("org")),
                record=point,
            )

    threading.Thread(target=influx_worker, daemon=True).start()

    publisher = MqttBatchPublisher(mqtt_settings, None, stop_event)
    publisher.start()

    controller = LogicController(
        settings=settings,
        stop_event=stop_event,
        publisher=publisher,
    )
    controller.start()

    def on_message(_client, _userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return

        readings = payload.get("readings", [])
        if isinstance(readings, dict):
            readings = [readings]

        for reading in readings:
            if not isinstance(reading, dict):
                continue

            write_queue.put(reading)

            name = (
                reading.get("sensor_name")
                or reading.get("sensor_type")
                or reading.get("name")
            )

            value = (
                reading.get("value")
                if "value" in reading
                else reading.get("event")
            )

            if name is not None and value is not None:
                controller.handle_sensor_event(name, value)

    mqtt_client = mqtt.Client(
        client_id=mqtt_settings.get("server_client_id", "mqtt-influx")
    )

    if mqtt_settings.get("username"):
        mqtt_client.username_pw_set(
            mqtt_settings.get("username"),
            mqtt_settings.get("password"),
        )

    mqtt_client.on_message = on_message
    mqtt_client.connect(
        os.getenv("MQTT_HOST", mqtt_settings.get("host", "localhost")),
        int(os.getenv("MQTT_PORT", mqtt_settings.get("port", 1883))),
    )

    mqtt_client.subscribe(mqtt_settings.get("default_topic", "iot/sensors"))
    for topic in mqtt_settings.get("topics", {}).values():
        mqtt_client.subscribe(topic)

    mqtt_client.loop_start()

    @app.route("/")
    def index():
        return render_template(
            "index.html",
            grafana_url=grafana_url,
            dashboard_uid=dashboard_uid,
        )

    @app.route("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.route("/api/states")
    def states():
        query_api = influx_client.query_api()

        query = f'''
        from(bucket: "{influx_settings.get("bucket")}")
          |> range(start: -24h)
          |> filter(fn: (r) => r._field == "value" or r._field == "state")
          |> group(columns: ["sensor", "_field"])
          |> last()
        '''

        try:
            tables = query_api.query(
                query=query,
                org=os.getenv("INFLUX_ORG", influx_settings.get("org")),
            )
        except Exception:
            return jsonify({"states": [], "warning": "InfluxDB unavailable"}), 503

        latest = {}

        for table in tables:
            for record in table.records:
                sensor = record.values.get("sensor", "unknown")

                entry = latest.setdefault(
                    sensor,
                    {
                        "sensor": sensor,
                        "sensor_type": record.get_measurement(),
                        "device": record.values.get("device", "unknown"),
                        "pi_id": record.values.get("pi_id", "unknown"),
                        "unit": record.values.get("unit"),
                        "timestamp": record.get_time().isoformat()
                        if record.get_time()
                        else None,
                    },
                )

                if record.get_field() == "value":
                    entry["value"] = record.get_value()
                if record.get_field() == "state":
                    entry["state"] = record.get_value()

        return jsonify({"states": sorted(latest.values(), key=lambda x: x["sensor"])})

    @app.route("/proxy/grafana/<path:path>")
    def proxy_grafana(path):
        params = request.args.to_dict()
        target_url = f"{grafana_url}/{path}"

        r = requests.get(target_url, params=params, stream=True)

        def generate():
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    yield chunk

        resp = Response(
            generate(),
            status=r.status_code,
            content_type=r.headers.get("content-type"),
        )

        for k, v in r.headers.items():
            if k.lower() not in [
                "x-frame-options",
                "transfer-encoding",
                "content-encoding",
                "content-length",
            ]:
                resp.headers[k] = v

        return resp

    return app


if __name__ == "__main__":
    application = create_app()
    application.run(host="0.0.0.0", port=5000)