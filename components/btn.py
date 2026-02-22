import threading
import time
from sensors.btn import Button, run_button_loop
from simulators.btn import run_button_simulator

def button_callback(name, publisher=None, settings=None, event_handler=None):
    t = time.localtime()
    print("="*20)
    print(f"Timestamp: {time.strftime('%H:%M:%S', t)}")
    print(f"Button pressed!")
    if publisher and settings:
        publisher.enqueue_reading(
            sensor_type="BTN",
            sensor_name=name,
            value="pressed",
            simulated=settings.get("simulated", True),
            topic=settings.get("topic"),
        )
    if event_handler:
        event_handler(name, "pressed")

def run_button(name, settings, threads, stop_event, btn_queue=None, publisher=None, event_handler=None):
    """
    Runs the Button either in simulation mode or real hardware mode.
    """
    if settings.get("simulated", True):
        print(f"Starting {name} simulator")
        button_thread = threading.Thread(
            target=run_button_simulator,
            args=(lambda: button_callback(name, publisher, settings, event_handler), stop_event, btn_queue),
            daemon=True
        )
        button_thread.start()
        threads.append(button_thread)
        print(f"{name} simulator started")
    else:
        print(f"Starting {name} hardware loop")
        button = Button(pin=settings["pin"], simulated=False)
        button_thread = threading.Thread(
            target=run_button_loop,
            args=(button, stop_event, lambda: button_callback(name, publisher, settings, event_handler)),
            daemon=True
        )
        button_thread.start()
        threads.append(button_thread)
        print(f"{name} hardware loop started")
