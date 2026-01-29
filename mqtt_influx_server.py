import json
import queue
import threading
from datetime import datetime

from flask import Flask, jsonify
import paho.mqtt.client as mqtt
from influxdb_client import InfluxDBClient, Point, WritePrecision

from settings import load_settings


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
            point.time(datetime.fromisoformat(timestamp.replace("Z", "+00:00")), WritePrecision.NS)
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

    app = Flask(__name__)
    write_queue = queue.Queue()
    stop_event = threading.Event()

    influx_client = InfluxDBClient(
        url=influx_settings.get("url"),
        token=influx_settings.get("token"),
        org=influx_settings.get("org"),
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
                bucket=influx_settings.get("bucket"),
                org=influx_settings.get("org"),
                record=point,
            )

    worker_thread = threading.Thread(target=influx_worker, daemon=True)
    worker_thread.start()

    def on_message(_client, _userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except json.JSONDecodeError:
            return
        readings = payload.get("readings", [])
        if isinstance(readings, dict):
            readings = [readings]
        for reading in readings:
            write_queue.put(reading)

    mqtt_client = mqtt.Client(client_id=mqtt_settings.get("server_client_id", "mqtt-influx"))
    if mqtt_settings.get("username"):
        mqtt_client.username_pw_set(mqtt_settings.get("username"), mqtt_settings.get("password"))
    mqtt_client.on_message = on_message
    mqtt_client.connect(mqtt_settings.get("host", "localhost"), mqtt_settings.get("port", 1883))
    mqtt_client.subscribe(mqtt_settings.get("default_topic", "iot/sensors"))
    for topic in mqtt_settings.get("topics", {}).values():
        mqtt_client.subscribe(topic)
    mqtt_client.loop_start()

    @app.route("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.teardown_appcontext
    def shutdown(_exception=None):
        stop_event.set()
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
        influx_client.close()

    return app


if __name__ == "__main__":
    application = create_app()
    application.run(host="0.0.0.0", port=5000)
