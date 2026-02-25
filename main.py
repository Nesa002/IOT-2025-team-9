
import threading
import queue
from components.dl import run_dl
from components.dms import run_dms
from components.ds import run_ds
from logic_controller_pi import LogicControllerPi
from settings import load_settings
from mqtt_publisher import MqttBatchPublisher
from components.pir import run_pir
from components.uds import run_uds
from components.db import run_buzzer
from components.dht import run_dht
from components.four_segment import run_display
from components.lcd import run_lcd
from components.btn import run_button
from components.rgb import run_rgb
from components.gyro import run_gyro
from components.ir import run_ir

import os
import time

try:
    import RPi.GPIO as GPIO
    GPIO.setmode(GPIO.BCM)
except:
    pass

if __name__ == "__main__":
    print('Starting app')

    pi_id = os.getenv("PI_ID", "PI1").upper()
    settings_file = f"settings_{pi_id.lower()}.json"
    print(f"Loading settings for {pi_id} from {settings_file}")

    settings = load_settings(settings_file)
    threads = []
    stop_event = threading.Event()

    dl_queue = queue.Queue()
    dms_queue = queue.Queue()
    db_queue = queue.Queue()
    display_queue = queue.Queue()
    lcd_queue = queue.Queue()
    btn_queue = queue.Queue()
    rgb_queue = queue.Queue()
    gyro_queue = queue.Queue()


    try:
        device_info = settings.get("device", {"pi_id": "PI1", "device_name": "unknown"})
        publisher = MqttBatchPublisher(settings.get("mqtt", {}), device_info, stop_event)
        publisher.start()

        controller = LogicControllerPi(
            settings=settings,
            this_pi=pi_id,
            queues={
                "dl": queue.Queue(),
                "db": queue.Queue(),
                "display": queue.Queue(),
                "lcd": queue.Queue(),
                "rgb": queue.Queue(),
            },
        )
        controller.start()

        for sensor_name, sensor_cfg in settings.items():
            if sensor_name in ("DPIR1", "DPIR2", "DPIR3"):
                run_pir(sensor_name, sensor_cfg, threads, stop_event, publisher)
            elif sensor_name in ("DUS1", "DUS2"):
                run_uds(sensor_name, sensor_cfg, threads, stop_event, publisher)
            elif sensor_name in ("DS1", "DS2"):
                run_ds(sensor_name, sensor_cfg, threads, stop_event, publisher)
            elif sensor_name == "DMS":
                run_dms(sensor_name, sensor_cfg, threads, stop_event, dms_queue, publisher)
            elif sensor_name == "DB":
                run_buzzer(sensor_cfg, threads, stop_event, db_queue, publisher)
            elif sensor_name == "DL":
                run_dl(sensor_name, sensor_cfg, threads, stop_event, dl_queue, publisher)
            elif sensor_name in ("DHT1", "DHT2", "DHT3"):
                run_dht(sensor_name, sensor_cfg, threads, stop_event, publisher)
            elif sensor_name == "4SD":
                run_display(sensor_name, sensor_cfg, threads, stop_event, display_queue, publisher)
            elif sensor_name == "LCD":
                run_lcd(sensor_name, sensor_cfg, threads, stop_event, lcd_queue, publisher)
            elif sensor_name == "BTN":
                run_button(sensor_name, sensor_cfg, threads, stop_event, btn_queue, publisher)
            elif sensor_name == "BRGB":
                run_rgb(sensor_name, sensor_cfg, threads, stop_event, rgb_queue, publisher)
            elif sensor_name == "GYRO":
                run_gyro(sensor_name, sensor_cfg, threads, stop_event, gyro_queue, publisher)
            elif sensor_name == "IR":
                run_ir(sensor_name, sensor_cfg, threads, stop_event, publisher)
            else:
                pass

        while True:
            try:
                user_input = input().strip()  # Blocking input
                if user_input.startswith("dms "):
                    dms_queue.put(user_input)
                elif user_input.startswith("dl "):
                    dl_queue.put(user_input)
                elif user_input.startswith("buzz"):
                    db_queue.put(user_input)
                elif user_input.startswith("disp "):
                    display_queue.put(user_input)
                elif user_input.startswith("lcd "):
                    lcd_queue.put(user_input)
                elif user_input.startswith("press"):
                    btn_queue.put(user_input)
                elif user_input.startswith("rgb "):
                    rgb_queue.put(user_input)
                elif user_input.startswith("gyro "):
                    gyro_queue.put(user_input[len("gyro "):])
                time.sleep(1)
            except KeyboardInterrupt:
                print('Stopping app')
                stop_event.set()  # Set stop_event to signal all threads to stop
                break

    except KeyboardInterrupt:
        print('Stopping app')
        for t in threads:
            stop_event.set()
