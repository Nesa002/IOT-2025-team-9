import threading
import time
from sensors.rgb import RGB, run_rgb_loop
from simulators.rgb import run_rgb_simulator

def rgb_callback(event, publisher, settings, name):
    t = time.localtime()
    print("=" * 20)
    print(f"Timestamp: {time.strftime('%H:%M:%S', t)}")
    print(f"RGB Event: {event}")
    if publisher:
        publisher.enqueue_reading(
            sensor_type=name,
            sensor_name=name,
            value=event,
            simulated=settings["simulated"],
            topic=settings.get("topic"),
        )

def run_rgb(name, settings, threads, stop_event, rgb_queue, publisher=None):
    if settings['simulated']:
        print("Starting RGB simulator")
        rgb_thread = threading.Thread(
            target=run_rgb_simulator,
            args=(lambda event: rgb_callback(event, publisher, settings, name), stop_event, rgb_queue),
        )
        rgb_thread.start()
        threads.append(rgb_thread)
        print("RGB simulator started")
    else:
        print("Starting RGB hardware")
        rgb = RGB(settings.get("pins", {}))
        rgb_thread = threading.Thread(
            target=run_rgb_loop,
            args=(rgb, stop_event, rgb_queue, lambda event: rgb_callback(event, publisher, settings, name)),
        )
        rgb_thread.start()
        threads.append(rgb_thread)
        print("RGB loop started")
