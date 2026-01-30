import threading
import time
from sensors.dl import DL, run_dl_loop
from simulators.dl import run_dl_simulator


def dl_callback(event, publisher, settings, name):
    """
    Callback function for DL events.

    :param name: Name identifier for the DL instance.
    :param event: The event detected by the DL.
    """
    t = time.localtime()
    print("=" * 20)
    print(f"Timestamp: {time.strftime('%H:%M:%S', t)}")
    if event == "led_on":
        print("LED on")
    elif event == "led_off":
        print("LED off")
    if publisher:
        publisher.enqueue_reading(
            sensor_type=name,
            sensor_name=name,
            value=event,
            simulated=settings["simulated"],
            topic=settings.get("topic"),
        )

def run_dl(name, settings, threads, stop_event, dl_queue, publisher=None):
    """
    Initializes and runs the DL in either simulated or real mode.

    :param name: Name identifier for the DL instance.
    :param settings: Configuration settings, including whether it's simulated.
    :param threads: A list to store running threads.
    :param stop_event: A threading.Event to signal thread termination.
    """
    if settings['simulated']:
        print("Starting DL simulator")
        dl_thread = threading.Thread(
            target=run_dl_simulator,
            args=(lambda event: dl_callback(event, publisher, settings, name), stop_event, dl_queue),
        )
        dl_thread.start()
        threads.append(dl_thread)
        print("DL simulator started")
    else:
        print("Starting DL sensor")
        dl = DL(settings['pin'])
        dl_thread = threading.Thread(
            target=run_dl_loop,
            args=(dl, stop_event, dl_queue, lambda event: dl_callback(event, publisher, settings, name)),
        )
        dl_thread.start()
        threads.append(dl_thread)
        print("DL loop started")
