import threading
import time
from simulators.uds import run_uds_simulator
from sensors.uds import run_uds_loop, UDS


def uds_callback(name, distance, publisher, settings):
    t = time.localtime()
    print("="*20)
    print(f"Timestamp: {time.strftime('%H:%M:%S', t)}")
    print(f"{name}: Distance: {distance} cm")
    if publisher:
        publisher.enqueue_reading(
            sensor_type=name,
            sensor_name=name,
            value=distance,
            unit="cm",
            simulated=settings["simulated"],
            topic=settings.get("topic"),
        )

def run_uds(name, settings, threads, stop_event, publisher=None):
    if settings['simulated']:
        print("Starting UDS simulator")
        uds_thread = threading.Thread(
            target=run_uds_simulator,
            args=(lambda distance: uds_callback(name, distance, publisher, settings), stop_event),
        )
        uds_thread.start()
        threads.append(uds_thread)
        print(f"UDS simulator for {name} started")
    else:
        print(f"Starting UDS sensor loop for {name}")
        uds = UDS(settings['trig_pin'], settings['echo_pin'])
        uds_thread = threading.Thread(
            target=run_uds_loop,
            args=(uds, lambda distance: uds_callback(name, distance, publisher, settings), stop_event),
        )
        uds_thread.start()
        threads.append(uds_thread)
        print(f"UDS sensor loop for {name} started")
