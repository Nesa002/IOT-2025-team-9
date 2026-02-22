import random
import time

def run_uds_simulator(callback, stop_event, delay=7):
    while not stop_event.is_set():
        if random.choice([True, False]):
            sequence = [100, 50, 10]
        else:
            sequence = [10, 50, 100]
        for value in sequence:
            callback(value)

        time.sleep(delay)