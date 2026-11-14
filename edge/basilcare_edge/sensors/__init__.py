"""Sensor drivers. build_sensors() turns the [sensors.*] config sections into objects.

Every driver has the same small interface (base.Sensor), so the gateway does not care
whether a value comes from a real probe or from the simulation: replacing a simulated
sensor by the real one is a one-line change in the config file.
"""
from .base import Sensor, SensorError
from .simulated import SimulatedSensor

__all__ = ["Sensor", "SensorError", "SimulatedSensor", "build_sensors"]


def build_sensors(sensor_configs, context):
    """context: shared state between drivers (e.g. EC compensation needs the water temperature)."""
    from . import hardware   # imported lazily: hardware libraries only exist on the Pi

    drivers = {
        "simulated": SimulatedSensor,
        "bme280": hardware.Bme280Sensor,
        "ds18b20": hardware.Ds18b20Sensor,
        "ads1115_ph": hardware.PhProbe,
        "ads1115_ec": hardware.EcProbe,
        "ads1115_level": hardware.LevelSensor,
    }
    sensors = []
    for cfg in sensor_configs:
        if cfg.driver not in drivers:
            raise ValueError(f"sensor {cfg.name}: unknown driver {cfg.driver!r} (one of {', '.join(drivers)})")
        sensors.append(drivers[cfg.driver](cfg.name, context=context, **cfg.options))
    return sensors
