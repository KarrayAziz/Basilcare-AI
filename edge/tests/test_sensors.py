import unittest

from basilcare_edge.config import SensorConfig
from basilcare_edge.sensors import SimulatedSensor, build_sensors
from basilcare_edge.sensors.hardware import ec_from_volts, level_from_volts, ph_from_volts


class ConversionTest(unittest.TestCase):
    def test_ph_two_point_calibration(self):
        self.assertAlmostEqual(7.0, ph_from_volts(2.51, v_ph7=2.51, v_ph4=3.04))
        self.assertAlmostEqual(4.0, ph_from_volts(3.04, v_ph7=2.51, v_ph4=3.04))
        self.assertAlmostEqual(5.5, ph_from_volts(2.775, v_ph7=2.51, v_ph4=3.04))

    def test_ec_is_compensated_to_25_degrees(self):
        self.assertAlmostEqual(1.4, ec_from_volts(1.0, 1.4, 25.0))
        self.assertLess(ec_from_volts(1.0, 1.4, 30.0), 1.4, "warmer solution conducts more")

    def test_level_is_clamped_to_0_100(self):
        self.assertAlmostEqual(50.0, level_from_volts(1.5, 1.0, 2.0))
        self.assertEqual(100.0, level_from_volts(2.5, 1.0, 2.0))
        self.assertEqual(0.0, level_from_volts(0.2, 1.0, 2.0))


class SimulatedSensorTest(unittest.TestCase):
    def test_built_from_config_and_marked_uncalibrated(self):
        sensors = build_sensors([SensorConfig("ph", "simulated", {"seed": 1})], {})
        self.assertEqual("pH", sensors[0].unit)
        self.assertFalse(sensors[0].calibrated)
        self.assertAlmostEqual(6.0, sensors[0].read(), delta=0.2)

    def test_drift_and_plausible_clamp(self):
        sensor = SimulatedSensor("water_level", noise=0, drift_per_read=-30)
        self.assertEqual([80, 50, 20, 0, 0], [sensor.read() for _ in range(5)])

    def test_unknown_driver_or_sensor(self):
        with self.assertRaises(ValueError):
            build_sensors([SensorConfig("ph", "magic")], {})
        with self.assertRaises(ValueError):
            SimulatedSensor("co2")


if __name__ == "__main__":
    unittest.main()
