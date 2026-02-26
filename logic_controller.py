import json
import math
import threading
import time
from collections import deque

import paho.mqtt.client as mqtt


class LogicController:
    def __init__(self, settings, stop_event, publisher):
        self.settings = settings
        self.stop_event = stop_event
        self.publisher = publisher

        self.pin_code = str(settings.get("logic", {}).get("pin_code", "1234"))
        self.pin_buffer = ""

        self.alarm_active = False
        self.security_armed = False
        self.pending_arm_at = None
        self.pending_intrusion_at = None

        self.occupancy = 0
        self.uds_history = {
            "DUS1": deque(maxlen=15),
            "DUS2": deque(maxlen=15),
        }
        self.door_open_since = {"DS1": None, "DS2": None}

        self.ir="OFF"

        self.latest_dht = {}
        self.timer_remaining = 0
        self.timer_running = False
        self.timer_blinking = False
        self.timer_visible = True

        self.timer_add_step = 10
        self.last_lcd_rotation = 0
        self.last_lcd_index = 0

        self.rgb_on = False
        self.rgb_color = "white"


        self.lock = threading.RLock()

    def start(self):
        self.tick_thread = threading.Thread(target=self._tick_loop, daemon=True)
        self.tick_thread.start()
        self.command_thread = threading.Thread(target=self._command_listener, daemon=True)
        self.command_thread.start()

    def _emit_logic_event(self, name, value, tags=None):
        if self.publisher:
            self.publisher.enqueue_reading(
                sensor_type="LOGIC",
                sensor_name=name,
                value=value,
                simulated=True,
                topic="iot/logic/event",
                extra_tags=tags or {},
            )

    def handle_timer_add(self, seconds: int):
        with self.lock:
            self.timer_remaining += max(0, seconds)
            self.timer_running = True
        print(f"[LogicController] Added {seconds} seconds to timer, new value: {self.timer_remaining}")

    def handle_timer_step(self, seconds: int):
        with self.lock:
            self.timer_add_step = max(1, seconds)
        print(f"[LogicController] Timer add step set to {self.timer_add_step} seconds")
            
    def get_alarm_state(self):
        with self.lock:
            return {
                "active": self.alarm_active,
                "armed": self.security_armed,
            }
        
    def _set_alarm(self, active, reason="unknown"):

        print("ALARM!!!")
        self._send_mqtt_message("PI1","DL","dl on")

        if self.alarm_active == active:
            return
        self.alarm_active = active
        if active:
            self._send_mqtt_message("PI1","DB","buzz")
            # self.queues["db"].put("buzz")
        else:
            self.security_armed = False
            self.pending_intrusion_at = None
        state = "entered" if active else "cleared"
        self._emit_logic_event("ALARM", state, {"reason": reason})

    def _arm_security(self):
        with self.lock:
            self.pending_arm_at = time.time() + 10
        self._emit_logic_event("SECURITY", "arming")

    def _disarm_by_pin(self):
        with self.lock:
            self.pin_buffer = ""
            self.pending_arm_at = None
            self.pending_intrusion_at = None
            was_alarm = self.alarm_active
            self.security_armed = False

            print("DISARMED")
        if was_alarm:
            self._set_alarm(False, "pin")
        else:
            self._emit_logic_event("SECURITY", "disarmed")

    def _handle_pin_key(self, key):
        if key == "#":
            self.pin_buffer = ""
            return

        if key == "*":
            if(self.security_armed):
                if self.pin_buffer == self.pin_code:
                    self._disarm_by_pin()
                    return
            if len(self.pin_buffer)<4:
                return
            self._arm_security()
            self.pin_code=self.pin_buffer
            return

        if key.isdigit():
            #if entered number instead of star
            if len(self.pin_buffer) == 4:
                self.pin_buffer = ""
                return
            self.pin_buffer += key


    def _send_mqtt_message(self, pi_id, sensor_name, value):
        self.publisher.enqueue_reading_pi(
            pi_id=pi_id,
            sensor_name=sensor_name,
            value=value,
            topic="iot/pi"
        )

    def handle_sensor_event(self, name, value):
        print(f"NAME {name}, VALUE {value}")

        now = time.time()
        with self.lock:
            if name in self.uds_history:
                try:
                    self.uds_history[name].append((now, float(value)))
                except Exception:
                    pass
                return

            if name.startswith("DHT"):

                self.latest_dht[name] = value
                return

            if name == "BTN" and value == "pressed":
                if self.timer_blinking:
                    self.timer_blinking = False
                    self.timer_visible = True

                    return
                self.timer_remaining += self.timer_add_step
                self.timer_running = True
                return

            if name == "DMS":
                self._handle_pin_key(str(value))
                return

            if name in ("DS1", "DS2"):
                state = str(value).lower()
                if state == "open":
                    if self.door_open_since[name] is None:
                        self.door_open_since[name] = now
                    if self.security_armed and self.pending_intrusion_at is None:
                        self.pending_intrusion_at = now + 10
                        self._emit_logic_event("SECURITY", "pin_grace_started", {"sensor": name})
                else:
                    self.door_open_since[name] = None
                return

            if name in ("DPIR1", "DPIR2") and value == "motion_detected":
                self._send_mqtt_message("PI1","DL","dl on")
                #self.queues["dl"].put("dl on")
                self._update_occupancy_from_motion(name)


            if name in ("DPIR1", "DPIR2", "DPIR3") and value == "motion_detected":
                print(self.occupancy)
                if self.occupancy == 0:
                    self._set_alarm(True, "perimeter_motion_empty")
                return

            if name == "IR":

                if value=="ON":
                    self._send_mqtt_message("PI3", "BRGB", "rgb on")
                    print("sent")
                    self.ir = "ON"
                elif value=="OFF":
                    self._send_mqtt_message("PI3", "BRGB", "rgb off")
                    self.ir = "OFF"
                elif(self.ir == "OFF"):print("IR IS OFF")
                elif value=="RED": self._send_mqtt_message("PI3", "BRGB", "rgb red")
                elif value=="GREEN": self._send_mqtt_message("PI3", "BRGB", "rgb green")
                elif value=="BLUE": self._send_mqtt_message("PI3", "BRGB", "rgb blue")


            if name == "GYRO" and isinstance(value, dict):
                magnitude = math.sqrt(
                    value["gx"] ** 2 +
                    value["gy"] ** 2 +
                    value["gz"] ** 2
                )
                if magnitude > 700:
                    self._set_alarm(True, "gsg_movement")

    def _update_occupancy_from_motion(self, pir_name):
        sensor = "DUS1" if pir_name == "DPIR1" else "DUS2"

        history = self.uds_history.get(sensor, deque())
        if len(history) < 2:
            return
        count = min(3, len(history))   # don’t over-pop
        recent = [history.popleft()[1] for _ in range(count)]
        if len(recent) < 2:
            return
        delta = recent[-1] - recent[0]
        entering = delta < 0
        self.occupancy = max(0, self.occupancy + (1 if entering else -1))
        self._emit_logic_event("OCCUPANCY", str(self.occupancy), {"trigger": pir_name, "direction": "in" if entering else "out"})

    def _tick_loop(self):
        last_timer_tick = time.time()
        acc = 0.0
        while not self.stop_event.is_set():

            now = time.time()
            with self.lock:
                elapsed = now - last_timer_tick
                last_timer_tick = now
                acc += elapsed
                while acc >= 1.0:
                    if self.timer_running and self.timer_remaining > 0:
                        self.timer_remaining -= 1
                        if self.timer_remaining == 0:
                            self.timer_running = False
                            self.timer_blinking = False
                            print("Timer ran out")
                    acc -= 1.0
                for ds_name, opened_at in self.door_open_since.items():
                    if opened_at and now - opened_at >= 5:

                        print(now - opened_at)
                        self._set_alarm(True, f"{ds_name}_unlocked")

                if self.pending_arm_at and now >= self.pending_arm_at:
                    self.security_armed = True
                    self.pending_arm_at = None

                    print("ARMED!!!")
                    self._emit_logic_event("SECURITY", "armed")

                if self.pending_intrusion_at and now >= self.pending_intrusion_at:
                    self.pending_intrusion_at = None
                    self._set_alarm(True, "intrusion_no_pin")

                if self.timer_blinking:
                    self.timer_visible = not self.timer_visible

                self._push_timer_display()
                self._rotate_lcd(now)
            time.sleep(0.1)

    def _push_timer_display(self):
        shown = self.timer_remaining if self.timer_visible else 0
        minutes = shown // 60
        seconds = shown % 60
        # self._send_mqtt_message("PI2", "4SD", f"disp {minutes:02d}:{seconds:02d}")
       # self.queues["display"].put(f"disp {minutes:02d}:{seconds:02d}")

    def _rotate_lcd(self, now):
        if not self.latest_dht or now - self.last_lcd_rotation < 4:
            return
        names = sorted(self.latest_dht.keys())
        name = names[self.last_lcd_index % len(names)]
        val = self.latest_dht[name]
        self.last_lcd_index += 1
        self.last_lcd_rotation = now

        self._send_mqtt_message("PI3", "LCD", f"lcd {name} T:{val.get('temperature', '?')}C H:{val.get('humidity', '?')}%")
       # self.queues["lcd"].put(f"lcd {name} T:{val.get('temperature', '?')}C H:{val.get('humidity', '?')}%")

    def _command_listener(self):
        mqtt_settings = self.settings.get("mqtt", {})
        client = mqtt.Client(client_id=f"logic-{int(time.time())}")
        if mqtt_settings.get("username"):
            client.username_pw_set(mqtt_settings.get("username"), mqtt_settings.get("password"))

        def on_message(_client, _userdata, msg):
            try:
                payload = json.loads(msg.payload.decode("utf-8"))
            except Exception:
                return
            self.handle_command(payload)

        client.on_message = on_message
        client.connect(mqtt_settings.get("host", "localhost"), mqtt_settings.get("port", 1883))
        client.subscribe("iot/commands/#")
        client.loop_start()
        while not self.stop_event.is_set():
            time.sleep(0.5)
        client.loop_stop()
        client.disconnect()

    def handle_command(self, payload):
        action = payload.get("action")
        if action == "alarm_off":
            self._set_alarm(False, "web")
        elif action == "arm":
            self._arm_security()
        elif action == "timer_set":
            seconds = int(payload.get("seconds", 0))
            with self.lock:
                self.timer_remaining = max(0, seconds)
                self.timer_running = self.timer_remaining > 0
                self.timer_blinking = False
        elif action == "timer_add_step":
            with self.lock:
                self.timer_add_step = int(payload.get("seconds", self.timer_add_step))
        elif action == "rgb":
            color = payload.get("color", "white")
            state = bool(payload.get("on", True))
            self.rgb_on = state
            self.rgb_color = color

            self._send_mqtt_message("PI3", "BRGB",f"rgb {color if state else 'off'}")
            #self.queues["rgb"].put(f"rgb {color if state else 'off'}")
        elif action == "pin_entered":
            pin = str(payload.get("pin", ""))
            for digit in pin:
                self._handle_pin_key(digit)
