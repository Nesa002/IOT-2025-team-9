import time
import queue
try:
    import RPi.GPIO as GPIO
except ImportError:
    pass

class RGB:
    def __init__(self, pins=None):
        self.RED_PIN = pins.get("red", 12)
        self.GREEN_PIN = pins.get("green", 13)
        self.BLUE_PIN = pins.get("blue", 19)
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(self.RED_PIN, GPIO.OUT)
        GPIO.setup(self.GREEN_PIN, GPIO.OUT)
        GPIO.setup(self.BLUE_PIN, GPIO.OUT)

    def turn_off(self):
        GPIO.output(self.RED_PIN, GPIO.LOW)
        GPIO.output(self.GREEN_PIN, GPIO.LOW)
        GPIO.output(self.BLUE_PIN, GPIO.LOW)

    def set_color(self, color):
        if color == "white":
            GPIO.output(self.RED_PIN, GPIO.HIGH)
            GPIO.output(self.GREEN_PIN, GPIO.HIGH)
            GPIO.output(self.BLUE_PIN, GPIO.HIGH)
        elif color == "red":
            GPIO.output(self.RED_PIN, GPIO.HIGH)
            GPIO.output(self.GREEN_PIN, GPIO.LOW)
            GPIO.output(self.BLUE_PIN, GPIO.LOW)
        elif color == "green":
            GPIO.output(self.RED_PIN, GPIO.LOW)
            GPIO.output(self.GREEN_PIN, GPIO.HIGH)
            GPIO.output(self.BLUE_PIN, GPIO.LOW)
        elif color == "blue":
            GPIO.output(self.RED_PIN, GPIO.LOW)
            GPIO.output(self.GREEN_PIN, GPIO.LOW)
            GPIO.output(self.BLUE_PIN, GPIO.HIGH)
        elif color == "yellow":
            GPIO.output(self.RED_PIN, GPIO.HIGH)
            GPIO.output(self.GREEN_PIN, GPIO.HIGH)
            GPIO.output(self.BLUE_PIN, GPIO.LOW)
        elif color == "purple":
            GPIO.output(self.RED_PIN, GPIO.HIGH)
            GPIO.output(self.GREEN_PIN, GPIO.LOW)
            GPIO.output(self.BLUE_PIN, GPIO.HIGH)
        elif color == "lightBlue":
            GPIO.output(self.RED_PIN, GPIO.LOW)
            GPIO.output(self.GREEN_PIN, GPIO.HIGH)
            GPIO.output(self.BLUE_PIN, GPIO.HIGH)

def run_rgb_loop(rgb, stop_event, rgb_queue, callback=None):
    while not stop_event.is_set():
        try:
            user_input = rgb_queue.get(timeout=1)
            if user_input.startswith("rgb "):
                color = user_input.split(" ", 1)[1]
                if callback:
                    callback(color)
                rgb.set_color(color)
        except queue.Empty:
            pass
