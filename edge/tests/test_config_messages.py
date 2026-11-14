import os
import sys
import unittest
from pathlib import Path
from unittest import mock

from basilcare_edge import config, messages
from tests.helpers import Clock

EDGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EDGE.parent / "simulator"))


class ConfigTest(unittest.TestCase):
    def test_the_example_file_loads(self):
        cfg = config.load(EDGE / "config.example.toml")
        self.assertEqual("basil-pi-01", cfg.device_id)
        self.assertEqual(6, len(cfg.sensors))
        self.assertTrue(Path(cfg.outbox_path).is_absolute(), "relative to the config file")

    def test_rejects_an_invalid_device_id_and_unknown_keys(self):
        with self.assertRaises(ValueError):
            config.from_dict({"device": {"id": "Basil_Pi"}})
        with self.assertRaises(ValueError):
            config.from_dict({"device": {"id": "basil-pi-01"}, "pump": {"max_duration": 10}})

    def test_password_from_the_environment(self):
        with mock.patch.dict(os.environ, {"BASILCARE_MQTT_PASSWORD": "s3cret"}):
            cfg = config.from_dict({"device": {"id": "basil-pi-01"}})
        self.assertEqual("s3cret", cfg.mqtt.password)


class MessagesTest(unittest.TestCase):
    """The gateway must produce exactly the shapes of the simulator (both follow the contract)."""

    def test_same_fields_as_the_simulator(self):
        try:
            import simulator
        except ImportError:
            self.skipTest("simulator dependencies not installed")
        clock = Clock()
        device = simulator.Device("basil-pi-01", clock=clock)
        sim_messages = {topic.split("/", 3)[3]: payload for topic, payload, _ in device.step()}
        _, reading, retain = messages.reading("basil-pi-01", "ph", 6.0, clock(), True, 1)
        self.assertFalse(retain)
        self.assertEqual(set(sim_messages["telemetry/ph"]), set(reading))
        _, status, retain = messages.status("basil-pi-01", True, clock(), 5, "edge", clock())
        self.assertTrue(retain)
        self.assertEqual(set(device.status(True)[1]), set(status))
        _, pump, _ = messages.pump_state("basil-pi-01", "off", None, clock())
        self.assertEqual(set(device.pump_state()[1]), set(pump))
        _, screening, _ = messages.screening("basil-pi-01", "img", clock(), "v", "healthy", 0.9, [], False)
        self.assertEqual(set(device._screening(clock())[1]), set(screening))

    def test_timestamps_carry_an_offset(self):
        _, payload, _ = messages.reading("basil-pi-01", "ph", 6.0, Clock()(), True, 1)
        self.assertEqual("2026-11-04T14:00:00+01:00", payload["measured_at"])
        _, will, _ = messages.status("basil-pi-01", False, Clock()(), 5, "edge", None)
        self.assertIsNone(will["reported_at"])


if __name__ == "__main__":
    unittest.main()
