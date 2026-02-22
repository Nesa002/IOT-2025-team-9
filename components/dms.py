import threading
import time
from simulators.dms import run_dms_simulator
from sensors.dms import run_dms_loop, DMS

def dms_callback(name, event, publisher, settings, event_handler=None):
    t = time.localtime()
    print("="*20)
    print(f"Timestamp: {time.strftime('%H:%M:%S', t)}")
    print(f"{name}:Key pressed: {event}")
    if publisher:
        publisher.enqueue_reading(
            sensor_type=name,
            sensor_name=name,
            value=event,
            simulated=settings["simulated"],
            topic=settings.get("topic"),
        )
    if event_handler:
        event_handler(name, event)

def run_dms(name, settings, threads, stop_event, dms_queue, publisher=None, event_handler=None):
    if settings['simulated']:
        print("Starting DMS simulator")
        dms_thread = threading.Thread(
            target=run_dms_simulator,
            args=(lambda event: dms_callback(name, event, publisher, settings, event_handler), stop_event, dms_queue),
        )
        dms_thread.start()
        threads.append(dms_thread)
        print("DMS simulator started")
    else:
        print("Starting DMS sensor loop")
        dms = DMS(settings['pins'])
        dms_thread = threading.Thread(
            target=run_dms_loop,
            args=(dms, lambda event: dms_callback(name, event, publisher, settings, event_handler), stop_event),
        )
        dms_thread.start()
        threads.append(dms_thread)
        print("DMS sensor loop started")
