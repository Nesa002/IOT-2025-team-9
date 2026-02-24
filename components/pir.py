import threading
import time
from simulators.pir import run_pir_simulator
from sensors.pir import run_pir_loop, PIR

def pir_callback(name, event, publisher, settings, event_handler=None):
    t = time.localtime()
    print("="*20)
    print(f"Timestamp: {time.strftime('%H:%M:%S', t)}")
    print(f"{name}: {event}")
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

def run_pir(name, settings, threads, stop_event, publisher=None, event_handler=None):
    if settings['simulated']:
        print("Starting PIR simulator")
        pir_thread = threading.Thread(
            target=run_pir_simulator,
            args=(2, lambda event: pir_callback(name, event, publisher, settings, event_handler), stop_event),
        )
        pir_thread.start()
        threads.append(pir_thread)
        print("PIR simulator started")
    else:
        print("Starting PIR sensor loop")
        pir = PIR(settings['pin'])
        pir_thread = threading.Thread(
            target=run_pir_loop,
            args=(pir, lambda event: pir_callback(name, event, publisher, settings, event_handler), stop_event),
        )
        pir_thread.start()
        threads.append(pir_thread)
        print("PIR sensor loop started")
