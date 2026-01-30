try:
    import RPi.GPIO as GPIO
except ImportError:
    pass
import time
import queue
class Buzzer:
    def __init__(self, pin):
        self.pin = pin
        GPIO.setup(pin, GPIO.OUT)

    def buzz(self, pitch, duration):
        period = 1.0 / pitch
        delay = period / 2
        cycles = int(duration * pitch)
        for _ in range(cycles):
            GPIO.output(self.pin, True)
            time.sleep(delay)
            GPIO.output(self.pin, False)
            time.sleep(delay)

def run_buzzer_loop(buzzer, stop_event, db_queue, callback=None):

    while not stop_event.is_set():
        try:
            user_input = db_queue.get(timeout=1)
            if user_input == "buzz":
                pitch = 440 
                duration = 0.5
                if callback:
                    callback("buzz")
                buzzer.buzz(pitch, duration)
        except queue.Empty:
            pass 
