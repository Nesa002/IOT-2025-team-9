import threading
import time
from sensors.ir import IR, run_ir_loop
from simulators.ir import run_ir_simulator

def ir_callback(event, publisher, settings, name):
    t = time.localtime()
    print("=" * 20, flush=True)
    print(f"Timestamp: {time.strftime('%H:%M:%S', t)}", flush=True)
    print(f"IR Event: {event}", flush=True)

    if publisher:
        publisher.enqueue_reading(
            sensor_type=name,
            sensor_name=name,
            value=event,
            simulated=settings["simulated"],
            topic=settings.get("topic"),
        )

def run_ir(name, settings, threads, stop_event, publisher=None):
    if settings.get("simulated", False):
        print("Starting IR simulator")
        ir_thread = threading.Thread(
            target=run_ir_simulator,
            args=(lambda event: ir_callback(event, publisher, settings, name), stop_event),
        )
    else:
        print("Starting IR sensor")
        ir = IR(settings.get("pin", 17))
        ir_thread = threading.Thread(
            target=run_ir_loop,
            args=(ir, stop_event, lambda event: ir_callback(event, publisher, settings, name)),
        )

    ir_thread.start()
    threads.append(ir_thread)
