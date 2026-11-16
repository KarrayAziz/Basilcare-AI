import json
import unittest

from basilcare_edge import config
from basilcare_edge.gateway import Gateway
from basilcare_edge.outbox import Outbox
from basilcare_edge.pump import FakeRelay, PumpGuard
from basilcare_edge.sensors import SimulatedSensor
from tests.helpers import Clock, FakeMqttClient

DEVICE = "basil-pi-01"


class FailingSensor(SimulatedSensor):
    def read(self):
        raise OSError("probe unplugged")


class GatewayTest(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.cfg = config.from_dict({"device": {"id": DEVICE, "interval_s": 5}})
        self.client = FakeMqttClient()
        self.guard = PumpGuard(DEVICE, FakeRelay(), clock=self.clock)
        self.sensors = [SimulatedSensor("ph", seed=1), SimulatedSensor("water_level", seed=1)]
        self.gateway = Gateway(self.cfg, self.sensors, self.guard, Outbox(":memory:"), client=self.client,
                               clock=self.clock)

    def telemetry(self):
        return [p for t, p, _, _ in self.client.published if "/telemetry/" in t]

    def test_readings_go_through_the_queue_and_leave_it_when_acknowledged(self):
        self.gateway.measure()
        self.gateway.flush()
        self.assertEqual(["ph", "water_level"], [p["sensor"] for p in self.telemetry()])
        self.assertEqual(2, self.gateway.outbox.pending(), "kept until the broker acknowledges")
        self.client.ack_all(self.gateway)
        self.assertEqual(0, self.gateway.outbox.pending())

    def test_seq_counts_per_sensor_from_one(self):
        for _ in range(3):
            self.gateway.measure()
        self.gateway.flush()
        self.assertEqual([1, 1, 2, 2, 3, 3], [p["seq"] for p in self.telemetry()])

    def test_readings_queued_during_an_outage_are_sent_late_as_buffered(self):
        self.client.connected = False
        self.gateway.measure()
        self.gateway.flush()
        self.assertEqual([], self.client.published)
        self.clock.advance(60)
        self.client.connected = True
        self.gateway.measure()
        self.gateway.flush()
        flags = [(p["seq"], p["buffered"]) for p in self.telemetry() if p["sensor"] == "ph"]
        self.assertEqual([(1, True), (2, False)], flags, "oldest first; only the late one is buffered")

    def test_acknowledgement_faster_than_flush_is_not_lost(self):
        self.gateway.on_publish(self.client, None, 1)    # PUBACK for mid 1 before flush records it
        self.gateway.measure()
        self.gateway.flush()
        self.assertEqual(1, self.gateway.outbox.pending(), "mid 1 done at once, mid 2 still in flight")

    def test_disconnection_resends_what_was_in_flight(self):
        self.gateway.measure()
        self.gateway.flush()
        self.gateway.on_disconnect(self.client, None, None, "lost")
        self.gateway.flush()
        self.assertEqual(4, len(self.telemetry()), "the 2 unacknowledged readings are sent again")

    def test_water_level_feeds_the_pump_guard_and_commands_get_an_answer(self):
        self.gateway.measure()
        command = {"device_id": DEVICE, "command_id": "c-1", "action": "on", "duration_s": 30,
                   "requested_by": "farmer1", "requested_at": "2026-11-04T14:00:00+01:00",
                   "expires_at": "2026-11-04T14:01:00+01:00"}
        msg = type("Msg", (), {"payload": json.dumps(command).encode()})()
        self.gateway.on_message(self.client, None, msg)
        topic, state, retain, _ = self.client.published[-1]
        self.assertEqual(f"basilcare/v1/{DEVICE}/pump/state", topic)
        self.assertEqual(("on", "executed", True), (state["state"], state["result"], retain))

    def test_a_broken_probe_does_not_stop_the_other_sensors(self):
        self.gateway.sensors = [FailingSensor("ec"), SimulatedSensor("ph")]
        self.gateway.measure()
        self.gateway.flush()
        self.assertEqual(["ph"], [p["sensor"] for p in self.telemetry()])

    def test_a_crash_in_the_loop_still_switches_the_pump_off(self):
        """Review finding #2: an exception (e.g. SD card full while saving a reading) used to exit
        the loop with the relay still on and without telling the broker."""
        self.gateway.measure()
        self.guard.handle(json.dumps({"device_id": DEVICE, "command_id": "c-1", "action": "on", "duration_s": 600,
                                      "requested_by": "farmer1", "requested_at": "2026-11-04T14:00:00+01:00",
                                      "expires_at": "2026-11-04T14:01:00+01:00"}))
        self.assertTrue(self.guard.relay.is_on)
        self.gateway.outbox.add = lambda topic, payload: (_ for _ in ()).throw(OSError("No space left on device"))

        with self.assertRaises(OSError):
            self.gateway.run()

        self.assertFalse(self.guard.relay.is_on)
        topic, status, retain, _ = self.client.published[-1]
        self.assertTrue(topic.endswith("/status") and retain)
        self.assertFalse(status["online"])

    def test_clean_shutdown_switches_the_pump_off_and_says_offline(self):
        self.guard.relay.on()
        self.gateway.shutdown()
        self.assertFalse(self.guard.relay.is_on)
        topic, status, retain, _ = self.client.published[-1]
        self.assertTrue(topic.endswith("/status") and retain)
        self.assertFalse(status["online"])
        self.assertIsNotNone(status["reported_at"])


if __name__ == "__main__":
    unittest.main()
