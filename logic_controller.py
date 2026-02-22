import json
import math
import threading
import time
from collections import deque

import paho.mqtt.client as mqtt


class LogicController:
    def __init__(self, settings, stop_event, publisher, queues):
        self.settings = settings
        self.stop_event = stop_event
        self.publisher = publisher
        self.queues = queues

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

        self.latest_dht = {}
        self.timer_remaining = 0
        self.timer_running = False
        self.timer_blinking = False
        self.timer_visible = True
        self.timer_add_step = 30
        self.last_lcd_rotation = 0
        self.last_lcd_index = 0

        self.rgb_on = False
        self.rgb_color = "white"

        self.lock = threading.Lock()

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
                topic=self.settings.get("mqtt", {}).get("default_topic", "iot/sensors"),
                extra_tags=tags or {},
            )

    def _set_alarm(self, active, reason="unknown"):
        with self.lock:
            if self.alarm_active == active:
                return
            self.alarm_active = active
            if active:
                self.queues["db"].put("buzz")
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
        if was_alarm:
            self._set_alarm(False, "pin")
        else:
            self._emit_logic_event("SECURITY", "disarmed")

    def _handle_pin_key(self, key):
        if key == "#":
            self.pin_buffer = ""
            return
        if key == "*":
            self._arm_security()
            return
        if key in {"A", "B", "C", "D"}:
            colors = {"B": "red", "C": "green", "D": "blue"}
            if key == "A":
                self.rgb_on = not self.rgb_on
            else:
                self.rgb_on = True
                self.rgb_color = colors[key]
            self.queues["rgb"].put(f"rgb {self.rgb_color if self.rgb_on else 'off'}")
            self._emit_logic_event("RGB", f"{self.rgb_on}:{self.rgb_color}")
            return

        if key.isdigit():
            self.pin_buffer += key
            self.pin_buffer = self.pin_buffer[-4:]
            if len(self.pin_buffer) == 4:
                if self.pin_buffer == self.pin_code:
                    self._disarm_by_pin()
                self.pin_buffer = ""

    def handle_sensor_event(self, name, value):
        now = time.time()
        with self.lock:
            if name in self.uds_history:
                try:
                    self.uds_history[name].append((now, float(value)))
                except Exception:
                    pass
                return

            if name.startswith("DHT") and isinstance(value, dict):
                self.latest_dht[name] = value
                return

            if name == "BTN" and value == "pressed":
                if self.timer_blinking:
                    self.timer_blinking = False
                    self.timer_visible = True
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
                self.queues["dl"].put("dl on")
                self._update_occupancy_from_motion(name)
                return

            if name in ("DPIR3", "RPIR1", "RPIR2", "RPIR3") and value == "motion_detected":
                if self.occupancy == 0:
                    self._set_alarm(True, "perimeter_motion_empty")
                return

            if name == "GYRO" and isinstance(value, dict):
                magnitude = math.sqrt(sum(float(value.get(k, 0)) ** 2 for k in ("gx", "gy", "gz")))
                if magnitude > 700:
                    self._set_alarm(True, "gsg_movement")

    def _update_occupancy_from_motion(self, pir_name):
        sensor = "DUS1" if pir_name == "DPIR1" else "DUS2"
        history = self.uds_history.get(sensor, deque())
        print(f"\n\n{history}\n\n")
        if len(history) < 2:
            return
        count = min(3, len(history))   # don’t over-pop
        recent = [history.popleft()[1] for _ in range(count)]
        if len(recent) < 2:
            return
        delta = recent[-1] - recent[0]
        entering = delta < 0
        self.occupancy = max(0, self.occupancy + (1 if entering else -1))
        print(f"Number of people: {self.occupancy}")
        self._emit_logic_event("OCCUPANCY", self.occupancy, {"trigger": pir_name, "direction": "in" if entering else "out"})

    def _tick_loop(self):
        last_timer_tick = time.time()
        while not self.stop_event.is_set():
            now = time.time()
            with self.lock:
                for ds_name, opened_at in self.door_open_since.items():
                    if opened_at and now - opened_at >= 5:
                        self._set_alarm(True, f"{ds_name}_unlocked")

                if self.pending_arm_at and now >= self.pending_arm_at:
                    self.security_armed = True
                    self.pending_arm_at = None
                    self._emit_logic_event("SECURITY", "armed")

                if self.pending_intrusion_at and now >= self.pending_intrusion_at:
                    self.pending_intrusion_at = None
                    self._set_alarm(True, "intrusion_no_pin")

                if self.timer_running and now - last_timer_tick >= 1:
                    elapsed = int(now - last_timer_tick)
                    self.timer_remaining = max(0, self.timer_remaining - elapsed)
                    last_timer_tick = now
                    if self.timer_remaining == 0:
                        self.timer_running = False
                        self.timer_blinking = True

                if self.timer_blinking:
                    self.timer_visible = not self.timer_visible

                self._push_timer_display()
                self._rotate_lcd(now)
            time.sleep(1)

    def _push_timer_display(self):
        shown = self.timer_remaining if self.timer_visible else 0
        minutes = shown // 60
        seconds = shown % 60
        self.queues["display"].put(f"disp {minutes:02d}:{seconds:02d}")

    def _rotate_lcd(self, now):
        if not self.latest_dht or now - self.last_lcd_rotation < 4:
            return
        names = sorted(self.latest_dht.keys())
        name = names[self.last_lcd_index % len(names)]
        val = self.latest_dht[name]
        self.last_lcd_index += 1
        self.last_lcd_rotation = now
        self.queues["lcd"].put(f"lcd {name} T:{val.get('temperature', '?')}C H:{val.get('humidity', '?')}%")

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
            self.queues["rgb"].put(f"rgb {color if state else 'off'}")
        elif action == "pin_entered":
            pin = str(payload.get("pin", ""))
            for digit in pin:
                self._handle_pin_key(digit)
