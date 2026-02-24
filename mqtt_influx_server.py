import json
import os
import queue
import threading
from datetime import datetime

from flask import Flask, jsonify
import paho.mqtt.client as mqtt
from influxdb_client import InfluxDBClient, Point, WritePrecision
from mqtt_publisher import MqttBatchPublisher
from logic_controller import LogicController


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
    stop_event = threading.Event()

    publisher = MqttBatchPublisher(settings.get("mqtt", {}), None, stop_event)
    publisher.start()

    controller = LogicController(
        settings=settings,
        stop_event=stop_event,
        publisher=publisher,
        queues={
            "dl": queue.Queue(),
            "db": queue.Queue(),
            "display": queue.Queue(),
            "lcd": queue.Queue(),
            "rgb": queue.Queue(),
        },
    )
    controller.start()

    mqtt_settings = settings.get("mqtt", {})
    influx_settings = settings.get("influxdb", {})

    app = Flask(__name__)
    write_queue = queue.Queue()

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

    worker_thread = threading.Thread(target=influx_worker, daemon=True)
    worker_thread.start()

    def on_message(_client, _userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return

        readings = payload.get("readings", [])
        if isinstance(readings, dict):
            readings = [readings]
        if not isinstance(readings, list):
            return

        for reading in readings:
            if not isinstance(reading, dict):
                continue

            write_queue.put(reading)
            # Your enqueue_reading(...) produces fields like these:
            # sensor_type, sensor_name, value, simulated, topic
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

            if name is None or value is None:
                continue

            # Call your handler with extracted parameters
            controller.handle_sensor_event(name, value)

    mqtt_client = mqtt.Client(client_id=mqtt_settings.get("server_client_id", "mqtt-influx"))
    if mqtt_settings.get("username"):
        mqtt_client.username_pw_set(mqtt_settings.get("username"), mqtt_settings.get("password"))
    mqtt_client.on_message = on_message
    mqtt_client.connect(
        os.getenv("MQTT_HOST", mqtt_settings.get("host", "localhost")),
        int(os.getenv("MQTT_PORT", mqtt_settings.get("port", 1883))),
    )
    mqtt_client.subscribe(mqtt_settings.get("default_topic", "iot/sensors"))
    for topic in mqtt_settings.get("topics", {}).values():
        mqtt_client.subscribe(topic)
    mqtt_client.loop_start()

    @app.route("/health")
    def health():
        return jsonify({"status": "ok"})


    return app


if __name__ == "__main__":
    application = create_app()
    application.run(host="0.0.0.0", port=5000)
