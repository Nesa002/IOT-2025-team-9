import json
import queue
import threading
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt


class MqttBatchPublisher:
    def __init__(self, mqtt_settings, device_info, stop_event):
        self._mqtt_settings = mqtt_settings
        self._device_info = device_info
        self._stop_event = stop_event
        self._queue = queue.Queue()
        self._batch_size = mqtt_settings.get("batch_size", 10)
        self._batch_interval = mqtt_settings.get("batch_interval_s", 5)
        self._topics = mqtt_settings.get("topics", {})
        self._default_topic = mqtt_settings.get("default_topic", "iot/sensors")
        self._qos = mqtt_settings.get("qos", 1)
        self._retain = mqtt_settings.get("retain", False)
        self._client = mqtt.Client(client_id=mqtt_settings.get("client_id")+"p")
        username = mqtt_settings.get("username")
        password = mqtt_settings.get("password")
        if username:
            self._client.username_pw_set(username, password)
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def enqueue_reading_pi(self, pi_id, sensor_name, value, topic):
        reading = {
            "pi_id": pi_id,
            "sensor_name": sensor_name,
            "value": value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        info = self._client.publish(topic, json.dumps(reading), qos=self._qos, retain=self._retain)
        info.wait_for_publish()
        print(info)

    def enqueue_reading(self, sensor_type, sensor_name, value, simulated, unit=None, topic=None, extra_tags=None):
        reading = {
            "sensor_type": sensor_type,
            "sensor_name": sensor_name,
            "value": value,
            "unit": unit,
            "simulated": simulated,
            "device": self._device_info,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if extra_tags:
            reading["tags"] = extra_tags
        self._queue.put(
            {
                "topic": topic or self._topics.get(sensor_type) or self._default_topic,
                "reading": reading,
            }
        )

    def _connect(self):
        host = self._mqtt_settings.get("host", "localhost")
        port = self._mqtt_settings.get("port", 1883)
        keepalive = self._mqtt_settings.get("keepalive", 60)
        self._client.connect(host, port, keepalive)
        self._client.loop_start()

    def _disconnect(self):
        self._client.loop_stop()
        self._client.disconnect()

    def _publish_batch(self, batch):
        grouped = {}
        for item in batch:
            print(item["topic"])
            grouped.setdefault(item["topic"], []).append(item["reading"])
        for topic, readings in grouped.items():
            payload = json.dumps({"readings": readings})
            self._client.publish(topic, payload, qos=self._qos, retain=self._retain)

    def _run(self):
        self._connect()
        batch = []
        last_flush = time.monotonic()
        try:
            while not self._stop_event.is_set():
                timeout = max(0.0, self._batch_interval - (time.monotonic() - last_flush))
                try:
                    item = self._queue.get(timeout=timeout)
                    batch.append(item)
                except queue.Empty:
                    pass

                should_flush = batch and (
                    len(batch) >= self._batch_size
                    or (time.monotonic() - last_flush) >= self._batch_interval
                )
                if should_flush:
                    self._publish_batch(batch)
                    batch = []
                    last_flush = time.monotonic()

            if batch:
                self._publish_batch(batch)
        finally:
            self._disconnect()
