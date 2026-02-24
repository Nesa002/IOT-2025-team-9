class LogicControllerPi:
    def __init__(self, this_pi, queues):
        self.queues = queues

        seld.this_pi = this_pi

    def start(self):

        mqtt_client = mqtt.Client(client_id=mqtt_settings.get("server_client_id", "mqtt-influx"))
        if mqtt_settings.get("username"):
            mqtt_client.username_pw_set(mqtt_settings.get("username"), mqtt_settings.get("password"))
        mqtt_client.on_message = on_message
        mqtt_client.connect(
            os.getenv("MQTT_HOST", mqtt_settings.get("host", "localhost")),
            int(os.getenv("MQTT_PORT", mqtt_settings.get("port", 1883))),
        )
        mqtt_client.subscribe(mqtt_settings.get("default_topic", "iot/pi"))

        mqtt_client.loop_start()

    def on_message(_client, _userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return

        if not isinstance(payload, dict):
            return

            # 1️ Check which Pi the message is for
        target_pi = payload.get("pi_id")

        if target_pi is None:
            return  # invalid message

        if this_pi is not None and str(target_pi) != str(this_pi):
            return  # not meant for this Pi

        sensor_name = payload.get("sensor_name")

        if sensor_name is None:
            return

        if(this_pi=="PI1"):

            if(sensor_name=="DL"):
                self.queues["dl"].put("dl on")
            if(sensor_name=="DB"):
                self.queues["db"].put("buzz")

        elif(this_pi=="PI2"):

            if (sensor_name == "4SD"):
                self.queues["display"].put(payload.get("value"))

        elif(this_pi=="PI3"):
            if (sensor_name == "LCD"):
                self.queues["lcd"].put(payload.get("value"))

            if (sensor_name == "BRGB"):
                self.queues["rgb"].put(payload.get("value"))
