import time
import queue
try:
    import RPi.GPIO as GPIO
except ImportError:
    pass

class DL:
    def __init__(self, pin):
        self.pin = pin
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(pin, GPIO.OUT)

    def turn_on(self):
        print("LED on")
        GPIO.output(self.pin, GPIO.HIGH)
        time.sleep(5)
        print("LED off")
        GPIO.output(self.pin, GPIO.LOW)

def run_dl_loop(dl, stop_event, dl_queue, callback=None):

    while not stop_event.is_set():
        try:
            user_input = dl_queue.get(timeout=1)
            if user_input == "dl on":
                if callback:
                    callback("led_on")
                dl.turn_on()
                if callback:
                    callback("led_off")
        except queue.Empty:
            pass 
