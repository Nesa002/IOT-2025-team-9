
import time
import random

BUTTONS = ["ON","OFF","RED","GREEN","BLUE"]

def run_ir_simulator(callback, stop_event):
    while not stop_event.is_set():
        time.sleep(random.randint(3, 8))
        callback(random.choice(BUTTONS))

