"""Simulated sensor, used on the Pi until the real probes arrive.

Values are realistic for hydroponic basil but are only test data. They are published with
calibrated = false by default, so nobody mistakes them for real measurements.
"""
import random

from ..messages import SENSORS
from .base import Sensor

# sensor -> (nominal value, noise standard deviation)
DEFAULTS = {
    "air_temperature": (24.0, 0.3),
    "air_humidity": (60.0, 1.5),
    "ph": (6.0, 0.03),
    "ec": (1.4, 0.03),
    "water_temperature": (21.0, 0.2),
    "water_level": (80.0, 0.5),
}


class SimulatedSensor(Sensor):
    def __init__(self, name, context=None, calibrated=False, nominal=None, noise=None, drift_per_read=0.0,
                 seed=None):
        super().__init__(name, context, calibrated)
        default_nominal, default_noise = DEFAULTS[name]
        self.nominal = default_nominal if nominal is None else float(nominal)
        self.noise = default_noise if noise is None else float(noise)
        self.drift_per_read = float(drift_per_read)   # e.g. -0.5 on water_level to test the pump lock-out
        self.rng = random.Random(seed)
        self.reads = 0

    def read(self):
        _, low, high = SENSORS[self.name]
        value = self.nominal + self.drift_per_read * self.reads + self.rng.gauss(0, self.noise)
        self.reads += 1
        return round(min(max(value, low), high), 2)
