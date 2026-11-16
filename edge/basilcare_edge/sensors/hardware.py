"""Drivers for the probes of the scope's bill of materials (section 3.1).

STATUS: written against the libraries' documentation, NOT yet tested on hardware (the
sensors are not delivered). Each driver imports its library only when it is created, so the
rest of the gateway runs and is tested on any computer.

Wiring assumed (change in config.toml):
- BME280 on I2C bus 1, address 0x76            -> air_temperature, air_humidity
- DS18B20 on the 1-Wire bus (GPIO 4)           -> water_temperature
- ADS1115 on I2C bus 1, address 0x48: the Pi has no analog input, so the analog pH, EC and
  water-level boards go through this 16-bit converter (channels A0..A3).

Calibration (contract section 3.2, scope risk "poor pH/EC calibration"):
- pH: two-point calibration with pH 7 and pH 4 buffer solutions -> v_ph7, v_ph4 in volts
- EC: one-point calibration with a reference solution -> k (mS/cm per volt at 25 degC),
      with temperature compensation (2 %/degC) using the water-temperature reading
- water level: voltages at empty and full reservoir -> v_empty, v_full
A driver without its calibration values publishes calibrated = false.
"""
import glob
import time
from pathlib import Path

from .base import Sensor, SensorError


class Bme280Sensor(Sensor):
    """Air temperature or humidity from one BME280. Two sensors share one chip and one sample per cycle."""

    _shared = {}

    def __init__(self, name, context=None, calibrated=True, bus=1, address=0x76):
        super().__init__(name, context, calibrated)
        if name not in ("air_temperature", "air_humidity"):
            raise ValueError("the bme280 driver measures air_temperature or air_humidity")
        key = (bus, address)
        if key not in self._shared:
            import bme280   # pip install RPi.bme280
            import smbus2   # pip install smbus2
            i2c = smbus2.SMBus(bus)
            params = bme280.load_calibration_params(i2c, address)
            self._shared[key] = {"bus": i2c, "params": params, "module": bme280, "sample": None, "at": 0.0}
        self.chip = self._shared[key]
        self.address = address

    def read(self):
        chip = self.chip
        try:
            if chip["sample"] is None or time.monotonic() - chip["at"] > 1.0:
                chip["sample"] = chip["module"].sample(chip["bus"], self.address, chip["params"])
                chip["at"] = time.monotonic()
        except OSError as error:
            raise SensorError(f"BME280 not answering: {error}") from error
        sample = chip["sample"]
        return round(sample.temperature if self.name == "air_temperature" else sample.humidity, 2)


class Ds18b20Sensor(Sensor):
    """Water temperature from a DS18B20 through the kernel's 1-Wire driver (dtoverlay=w1-gpio)."""

    def __init__(self, name, context=None, calibrated=True, device=""):
        super().__init__(name, context, calibrated)
        self.device = device   # e.g. "28-0123456789ab"; empty = the first one found

    def _path(self):
        pattern = f"/sys/bus/w1/devices/{self.device or '28-*'}"
        found = sorted(glob.glob(pattern))
        if not found:
            raise SensorError("no DS18B20 on the 1-Wire bus (is dtoverlay=w1-gpio enabled?)")
        return Path(found[0])

    def read(self):
        path = self._path()
        try:
            text = (path / "w1_slave").read_text()
        except OSError as error:
            raise SensorError(f"cannot read {path}: {error}") from error
        lines = text.strip().splitlines()
        if len(lines) < 2 or not lines[0].endswith("YES") or "t=" not in lines[1]:
            raise SensorError("DS18B20 CRC error")
        value = int(lines[1].split("t=")[1]) / 1000.0
        if value == 85.0:   # power-on reset value: the conversion did not happen
            raise SensorError("DS18B20 returned its reset value 85 degC")
        self.context["water_temperature"] = value
        return round(value, 2)


class _AnalogInput:
    """One ADS1115 channel, in volts (adafruit-circuitpython-ads1x15 2.x)."""

    _chips = {}

    def __init__(self, channel, address=0x48, gain=1):
        import board                                   # adafruit-blinka
        import busio
        from adafruit_ads1x15 import ads1115 as ads
        from adafruit_ads1x15.analog_in import AnalogIn
        if address not in self._chips:
            chip = ads.ADS1115(busio.I2C(board.SCL, board.SDA), address=address)
            chip.gain = gain                           # gain 1 = +/-4.096 V full scale
            self._chips[address] = chip
        pins = [ads.P0, ads.P1, ads.P2, ads.P3]
        self.input = AnalogIn(self._chips[address], pins[int(channel)])

    def volts(self, samples=5):
        try:
            values = sorted(self.input.voltage for _ in range(samples))
        except OSError as error:
            raise SensorError(f"ADS1115 not answering: {error}") from error
        return values[len(values) // 2]   # median: robust to a single noisy sample


class PhProbe(Sensor):
    def __init__(self, name, context=None, channel=0, address=0x48, v_ph7=None, v_ph4=None, calibrated=None):
        super().__init__(name, context, calibrated=v_ph7 is not None and v_ph4 is not None)
        if v_ph7 is not None and v_ph4 is not None and abs(v_ph7 - v_ph4) < 0.05:
            raise ValueError("v_ph7 and v_ph4 are too close: redo the calibration")
        self.v_ph7, self.v_ph4 = v_ph7, v_ph4
        self.adc = _AnalogInput(channel, address)

    def read(self):
        return round(ph_from_volts(self.adc.volts(), self.v_ph7, self.v_ph4), 2)


class EcProbe(Sensor):
    def __init__(self, name, context=None, channel=1, address=0x48, k=None, calibrated=None):
        super().__init__(name, context, calibrated=k is not None)
        self.k = 1.0 if k is None else float(k)
        self.adc = _AnalogInput(channel, address)

    def read(self):
        temperature = self.context.get("water_temperature", 25.0)
        return round(ec_from_volts(self.adc.volts(), self.k, temperature), 3)


class LevelSensor(Sensor):
    def __init__(self, name, context=None, channel=2, address=0x48, v_empty=None, v_full=None, calibrated=None):
        super().__init__(name, context, calibrated=v_empty is not None and v_full is not None)
        self.v_empty = 0.0 if v_empty is None else float(v_empty)
        self.v_full = 3.3 if v_full is None else float(v_full)
        self.adc = _AnalogInput(channel, address)

    def read(self):
        return round(level_from_volts(self.adc.volts(), self.v_empty, self.v_full), 1)


# ---- conversions: pure functions, unit-tested ------------------------------------

def ph_from_volts(volts, v_ph7=None, v_ph4=None):
    """Two-point linear calibration. Uncalibrated: typical analog board (2.5 V at pH 7, -0.18 V/pH)."""
    if v_ph7 is None or v_ph4 is None:
        v_ph7, v_ph4 = 2.5, 2.5 + 3 * 0.18
    slope = (7.0 - 4.0) / (v_ph7 - v_ph4)   # pH per volt
    return 7.0 + (volts - v_ph7) * slope


def ec_from_volts(volts, k, water_temperature):
    """Conductivity at 25 degC: raw = k * V, compensated by 2 % per degC."""
    raw = k * volts
    return max(0.0, raw / (1.0 + 0.02 * (water_temperature - 25.0)))


def level_from_volts(volts, v_empty, v_full):
    if v_full == v_empty:
        raise SensorError("water level calibration has v_full == v_empty")
    percent = (volts - v_empty) / (v_full - v_empty) * 100.0
    return min(max(percent, 0.0), 100.0)
