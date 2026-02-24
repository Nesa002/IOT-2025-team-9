import time
import queue
def run_dl_simulator(callback, stop_event, dl_queue):
    while not stop_event.is_set():
        try:
            user_input = dl_queue.get(timeout=1)
            if user_input == "dl on":
                callback("led_on")
                time.sleep(2)
                callback("led_off")
        except queue.Empty:
            pass 
        except KeyboardInterrupt:
            print('Stopping DL simulator...')
            stop_event.set()
            break
