# sensors/gyro.py
import time

try:
    import MPU6050  # your MPU6050.py file
except ImportError:
    MPU6050 = None


class Gyro:
    def __init__(self, i2c_bus=1, address=0x68, simulated=False):
        self.simulated = simulated
        self.i2c_bus = i2c_bus
        self.address = address
        self.mpu = None

        # Only initialize real hardware if not simulated and library is available
        if not simulated and MPU6050:
            # This is where the Pi connection effectively happens:
            # MPU6050.MPU6050(...) internally does smbus.SMBus(i2c_bus)
            self.mpu = MPU6050.MPU6050(a_bus=i2c_bus, a_address=address)
            self.mpu.dmp_initialize()

    def read(self):
        """
        Returns a dict similar to what you'd publish.
        accel units: raw counts (you can scale if you want)
        gyro units: raw counts
        """
        if self.simulated:
            # In your architecture, simulated mode should be handled by simulator code,
            # but keeping a safe fallback here avoids crashes.
            return {"ax": 0, "ay": 0, "az": 0, "gx": 0, "gy": 0, "gz": 0}

        if not self.mpu:
            raise RuntimeError("Gyro hardware not initialized (MPU6050 import failed or simulated=False on non-Pi).")

        accel = self.mpu.get_acceleration()
        gyro = self.mpu.get_rotation()

        return {
            "ax": accel[0], "ay": accel[1], "az": accel[2],
            "gx": gyro[0],  "gy": gyro[1],  "gz": gyro[2],
        }


def run_gyro_loop(gyro: Gyro, stop_event, callback, interval=0.1):
    """
    Polls the gyro at a fixed interval and calls callback(reading).
    Matches the style of run_button_loop(button, stop_event, callback, cooldown=...)
    """
    while not stop_event.is_set():
        reading = gyro.read()
        callback(reading)
        time.sleep(interval)

