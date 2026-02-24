import threading
import time

from sensors.gyro.gyro import Gyro, run_gyro_loop
from simulators.gyro import run_gyro_simulator


def gyro_callback(name, reading, publisher=None, settings=None, event_handler=None):
    t = time.localtime()
    print("=" * 20)
    print(f"Timestamp: {time.strftime('%H:%M:%S', t)}")
    print(f"{name} reading: {reading}")

    if publisher and settings:
        publisher.enqueue_reading(
            sensor_type="GYRO",
            sensor_name=name,
            value=reading,
            simulated=settings.get("simulated", True),
            topic=settings.get("topic"),
        )
    if event_handler:
        event_handler(name, reading)


def run_gyro(name, settings, threads, stop_event, gyro_queue=None, publisher=None, event_handler=None):
    if settings.get("simulated", True):
        print(f"Starting {name} gyro simulator")
        gyro_thread = threading.Thread(
            target=run_gyro_simulator,
            args=(
                stop_event,
                gyro_queue,
                lambda reading: gyro_callback(name, reading, publisher, settings, event_handler),
                settings,
            ),
            daemon=True,
        )
        gyro_thread.start()
        threads.append(gyro_thread)
        print(f"{name} gyro simulator started")

    else:
        print(f"Starting {name} gyro hardware loop")

        gyro = Gyro(
            i2c_bus=settings.get("i2c_bus", 1),
            address=settings.get("address", 0x68),
            simulated=False,
        )

        poll_hz = settings.get("poll_hz", 10)
        interval = 1.0 / max(1, poll_hz)

        gyro_thread = threading.Thread(
            target=run_gyro_loop,
            args=(gyro, stop_event, lambda reading: gyro_callback(name, reading, publisher, settings, event_handler)),
            kwargs={"interval": interval},
            daemon=True,
        )
        gyro_thread.start()
        threads.append(gyro_thread)
        print(f"{name} gyro hardware loop started")
