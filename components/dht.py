import time
import threading
from sensors.dht import run_dht_loop, DHT
from simulators.dht import run_dht_simulator

def dht_callback(name, humidity, temperature, publisher=None, settings=None):
    t = time.localtime()
    print("="*20)
    print(f"Timestamp: {time.strftime('%H:%M:%S', t)}")
    print(f"Humidity: {humidity}%")
    print(f"Temperature: {temperature}°C")

    if publisher and settings:
        publisher.enqueue_reading(
            sensor_type="DHT",
            sensor_name=f"{name}_humidity",
            value=humidity,
            simulated=settings.get("simulated", True),
            topic=settings.get("humidity_topic"),
        )
        publisher.enqueue_reading(
            sensor_type="DHT",
            sensor_name=f"{name}_temperature",
            value=temperature,
            simulated=settings.get("simulated", True),
            topic=settings.get("temperature_topic"),
        )


def run_dht(name, settings, threads, stop_event, publisher=None):
    if settings['simulated']:
        print(f"Starting {name} simulator")
        dht_thread = threading.Thread(
            target=run_dht_simulator,
            args=(2, lambda h, temp: dht_callback(name, h, temp, publisher, settings), stop_event)
        )
        dht_thread.start()
        threads.append(dht_thread)
        print(f"{name} simulator started")
    else:
        print(f"Starting {name} sensor loop")
        dht = DHT(settings['pin'])
        dht_thread = threading.Thread(
            target=run_dht_loop,
            args=(dht, 2, lambda h, temp: dht_callback(name, h, temp, publisher, settings), stop_event)
        )
        dht_thread.start()
        threads.append(dht_thread)
        print(f"{name} sensor loop started")
