import json
import os
import queue
import paho.mqtt.client as mqtt

class LogicControllerPi:
    def __init__(self, settings, this_pi, queues):
        self.queues = queues
        self.this_pi = str(this_pi) if this_pi is not None else None
        self.settings = settings
        self.client = None

    def start(self):
        mqtt_settings = self.settings.get("mqtt", {})
        host = os.getenv("MQTT_HOST", mqtt_settings.get("host", "localhost"))
        port = int(os.getenv("MQTT_PORT", mqtt_settings.get("port", 1883)))
        topic = mqtt_settings.get("default_topic", "iot/pi")
        client_id = mqtt_settings.get("client_id", "mqtt-influx")

        self.client = mqtt.Client(
            client_id=client_id,
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        )

        self.client.on_connect = lambda c, u, f, rc, p=None: self._on_connect(c, u, f, rc, topic)
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect

        self.client.connect(host, port, keepalive=60)
        self.client.loop_start()

    def _on_connect(self, client, userdata, flags, reason_code, topic):
        client.subscribe(topic)

    def on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties=None):
        pass


    def on_message(self, client, userdata, msg):

        try:
            text = msg.payload.decode("utf-8")
        except UnicodeDecodeError as e:
            return

        try:
            payload = json.loads(text)
        except json.JSONDecodeError as e:
            return

        if not isinstance(payload, dict):
            return

        target_pi = payload.get("pi_id")
        if target_pi is None:
            return

        if self.this_pi is not None and str(target_pi) != self.this_pi:
            # Not for this Pi
            return

        sensor_name = payload.get("sensor_name")
        if sensor_name is None:
            return

        value = payload.get("value")

        # --- routing ---
        if self.this_pi == "PI1":
            if sensor_name == "DL":
                self.queues["dl"].put("dl on")
            elif sensor_name == "DB":
                self.queues["db"].put("buzz")

        elif self.this_pi == "PI2":
            if sensor_name == "4SD":
                self.queues["display"].put(value)

        elif self.this_pi == "PI3":
            if sensor_name == "LCD":
                self.queues["lcd"].put(value)
            elif sensor_name == "BRGB":
                self.queues["rgb"].put(value)
