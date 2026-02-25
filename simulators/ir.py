
import time
import random

BUTTONS = ["LEFT","RIGHT","UP","DOWN","OK","1","2","3","4","5"]

def run_ir_simulator(callback, stop_event):
    while not stop_event.is_set():
        time.sleep(random.randint(3, 8))
        callback(random.choice(BUTTONS))

