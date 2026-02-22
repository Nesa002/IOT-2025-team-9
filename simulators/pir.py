import time
import random

def run_pir_simulator(delay, callback, stop_event):
    while not stop_event.is_set():
        callback("motion_detected")
        time.sleep(2)
        callback("motion_stopped")

        time.sleep(delay)
