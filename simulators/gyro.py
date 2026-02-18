import queue
import time
import random


def run_gyro_simulator(stop_event, gyro_queue, callback, settings=None):
    """
    Simulates gyro readings from queue input.

    Accepted commands:
        ax=100 ay=0 az=16384 gx=10 gy=0 gz=0
        random
    """

    print("Gyro simulator ready.")
    print("Type values like: ax=100 ay=0 az=16384 gx=10 gy=0 gz=0")
    print("Or type: random")

    while not stop_event.is_set():
        try:
            user_input = gyro_queue.get(timeout=1)
            cmd = str(user_input).strip().lower()

            if cmd == "random":
                reading = {
                    "ax": random.randint(-20000, 20000),
                    "ay": random.randint(-20000, 20000),
                    "az": random.randint(-20000, 20000),
                    "gx": random.randint(-500, 500),
                    "gy": random.randint(-500, 500),
                    "gz": random.randint(-500, 500),
                }
                callback(reading)

            else:
                reading = {
                    "ax": 0, "ay": 0, "az": 0,
                    "gx": 0, "gy": 0, "gz": 0,
                }

                parts = cmd.split()
                for part in parts:
                    if "=" in part:
                        key, value = part.split("=")
                        if key in reading:
                            try:
                                reading[key] = int(value)
                            except ValueError:
                                print(f"Invalid value for {key}")

                callback(reading)

        except queue.Empty:
            pass

        time.sleep(0.05)
