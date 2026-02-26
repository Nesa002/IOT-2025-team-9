import queue

def run_rgb_simulator(callback, stop_event, rgb_queue):
    while not stop_event.is_set():
        try:
            user_input = rgb_queue.get(timeout=1)
            if user_input.startswith("rgb "):
                color = user_input.split(" ", 1)[1]
                callback(color)
                print("rgb "+color)
        except queue.Empty:
            pass
        except KeyboardInterrupt:
            print("Stopping RGB simulator...")
            stop_event.set()
            break
