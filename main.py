
import threading
import queue
from components.dl import run_dl
from components.dms import run_dms
from components.ds import run_ds
from settings import load_settings
from mqtt_publisher import MqttBatchPublisher
from components.pir import run_pir
from components.uds import run_uds
from components.db import run_buzzer

import time

try:
    import RPi.GPIO as GPIO
    GPIO.setmode(GPIO.BCM)
except:
    pass

if __name__ == "__main__":
    print('Starting app')
    settings = load_settings()
    threads = []
    stop_event = threading.Event()

    dl_queue = queue.Queue()
    dms_queue = queue.Queue()
    db_queue = queue.Queue()

    try:


        dpir1_setting = settings['DPIR1']

        dus1_settings = settings['DUS1']

        db_setting = settings['DB']

        dms_setting=settings['DMS']

        ds_setting=settings['DS']

        dl_setting=settings['DL']


        device_info = settings.get("device", {"pi_id": "PI1", "device_name": "unknown"})
        publisher = MqttBatchPublisher(settings.get("mqtt", {}), device_info, stop_event)
        publisher.start()

        run_pir('DPIR1', dpir1_setting, threads, stop_event, publisher)

        run_uds('DUS1', dus1_settings, threads, stop_event, publisher)

        run_buzzer(db_setting, threads, stop_event, db_queue, publisher)

        run_dms("DMS", dms_setting, threads, stop_event, dms_queue, publisher)

        run_ds("DS", ds_setting, threads, stop_event, publisher)

        run_dl("DL", dl_setting, threads, stop_event, dl_queue, publisher)


        while True:
            try:
                user_input = input().strip()  # Blocking input
                if user_input.startswith("dms "):
                    dms_queue.put(user_input)
                elif user_input.startswith("dl "):
                    dl_queue.put(user_input)
                elif user_input.startswith("buzz"):
                    db_queue.put(user_input)
                time.sleep(1)
            except KeyboardInterrupt:
                print('Stopping app')
                stop_event.set()  # Set stop_event to signal all threads to stop
                break

    except KeyboardInterrupt:
        print('Stopping app')
        for t in threads:
            stop_event.set()
