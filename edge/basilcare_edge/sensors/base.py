"""The interface every sensor driver implements."""
from ..messages import SENSORS


class SensorError(Exception):
    """The sensor could not be read this cycle (disconnected, bus error...)."""


class Sensor:
    """One measured quantity of contract section 3.1.

    Subclasses implement read() and return the value in the contract unit.
    'calibrated' is published with every reading (contract section 3.2): False means the
    PWAs show "not calibrated" next to the value.
    """

    def __init__(self, name, context=None, calibrated=False):
        if name not in SENSORS:
            raise ValueError(f"unknown sensor {name!r}; contract sensors: {', '.join(SENSORS)}")
        self.name = name
        self.unit = SENSORS[name][0]
        self.context = context if context is not None else {}
        self.calibrated = bool(calibrated)

    def read(self):
        """Returns the measured value. Raises SensorError when no value is available."""
        raise NotImplementedError
