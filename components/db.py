import threading
import time
from sensors.db import Buzzer, run_buzzer_loop
from simulators.db import run_buzzer_simulator

def buzzer_callback(event, publisher, settings):
    t = time.localtime()
    print("="*20)
    print(f"Timestamp: {time.strftime('%H:%M:%S', t)}")
    print(f"Buzzer triggered: BZZzzzz")
    if publisher:
        publisher.enqueue_reading(
            sensor_type="DB",
            sensor_name="DB",
            value=event,
            simulated=settings["simulated"],
            topic=settings.get("topic"),
        )

def run_buzzer(settings, threads, stop_event, db_queue, publisher=None):
    if settings['simulated']:
        print("Starting Buzzer simulator")
        buzzer_thread = threading.Thread(
            target=run_buzzer_simulator,
            args=(lambda: buzzer_callback("buzz", publisher, settings), stop_event, db_queue),
        )
        buzzer_thread.start()
        threads.append(buzzer_thread)
        print("Buzzer simulator started")
    else:
        print("Starting Buzzer component")
        buzzer = Buzzer(settings['pin'])
        buzzer_thread = threading.Thread(
            target=run_buzzer_loop,
            args=(buzzer, stop_event, db_queue, lambda event: buzzer_callback(event, publisher, settings)),
        )
        buzzer_thread.start()
        threads.append(buzzer_thread)
        print("Buzzer component started")
