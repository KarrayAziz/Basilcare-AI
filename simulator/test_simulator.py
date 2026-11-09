"""Unit tests of the simulated device. No MQTT broker needed.

    python -m unittest -v        (inside simulator/, with the virtual environment active)
"""
import json
import unittest
from datetime import datetime, timedelta, timezone

from simulator import PUMP_MAX_DURATION_S, SENSORS, Device, iso, parse_time

TUNIS = timezone(timedelta(hours=1))
READING_FIELDS = {"device_id", "sensor", "value", "unit", "measured_at", "calibrated", "seq", "buffered"}


class FakeClock:
    """Time that only moves when a test says so."""

    def __init__(self):
        self.now = datetime(2026, 11, 4, 14, 0, 0, tzinfo=TUNIS)

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += timedelta(seconds=seconds)


def make_device(fault="none", screening_every=0):
    clock = FakeClock()
    return Device("basil-test-01", fault, interval=5, screening_every=screening_every,
                  seed=42, clock=clock), clock


def run(device, clock, cycles):
    """Run some cycles, 5 s apart, and return every message published."""
    messages = []
    for _ in range(cycles):
        messages += device.step()
        clock.advance(5)
    return messages


def readings(messages, sensor=None):
    return [payload for topic, payload, _ in messages
            if "/telemetry/" in topic and sensor in (None, payload["sensor"])]


def pump_states(messages):
    return [payload for topic, payload, _ in messages if topic.endswith("/pump/state")]


def command(clock, **fields):
    cmd = {
        "device_id": "basil-test-01",
        "command_id": "cmd-1",
        "action": "on",
        "duration_s": 60,
        "requested_by": "farmer1",
        "requested_at": iso(clock()),
        "expires_at": iso(clock() + timedelta(seconds=60)),
    }
    cmd.update(fields)
    return json.dumps(cmd).encode()


class TelemetryTest(unittest.TestCase):

    def test_reading_follows_the_contract(self):
        device, clock = make_device()
        messages = device.step()
        self.assertEqual(len(readings(messages)), len(SENSORS))
        for topic, payload, retain in messages:
            sensor = payload["sensor"]
            unit, _, _, low, high = SENSORS[sensor]
            self.assertEqual(topic, f"basilcare/v1/basil-test-01/telemetry/{sensor}")
            self.assertFalse(retain)
            self.assertEqual(set(payload), READING_FIELDS)
            self.assertEqual(payload["unit"], unit)
            self.assertIsInstance(payload["value"], float)
            self.assertTrue(low <= payload["value"] <= high)
            self.assertEqual(payload["measured_at"], "2026-11-04T14:00:00+01:00")
            json.dumps(payload)   # must be serialisable

    def test_seq_counts_per_sensor(self):
        device, clock = make_device()
        messages = run(device, clock, 3)
        for sensor in SENSORS:
            self.assertEqual([r["seq"] for r in readings(messages, sensor)], [1, 2, 3])

    def test_values_stay_near_nominal_without_fault(self):
        device, clock = make_device()
        for reading in readings(run(device, clock, 20), "ph"):
            self.assertAlmostEqual(reading["value"], 6.0, delta=0.15)

    def test_ph_drift(self):
        device, clock = make_device("ph-drift")
        ph = [r["value"] for r in readings(run(device, clock, 10), "ph")]
        self.assertGreater(ph[-1], 6.5)
        self.assertGreater(ph[-1], ph[0])

    def test_stale_silences_only_ph(self):
        device, clock = make_device("stale")
        messages = run(device, clock, 6)
        self.assertEqual(len(readings(messages, "ph")), 3)
        self.assertEqual(len(readings(messages, "ec")), 6)

    def test_outage_buffers_then_sends_oldest_first(self):
        device, clock = make_device("outage")
        for cycle in range(6):
            sent = readings(device.step())
            clock.advance(5)
            self.assertEqual(len(sent), 0 if cycle >= 3 else len(SENSORS), f"cycle {cycle}")
        sent = readings(device.step())                # cycle 6: connection is back
        late, live = sent[:3 * len(SENSORS)], sent[3 * len(SENSORS):]
        self.assertTrue(all(r["buffered"] for r in late))
        self.assertFalse(any(r["buffered"] for r in live))
        self.assertEqual(len(live), len(SENSORS))
        self.assertEqual([r["seq"] for r in late if r["sensor"] == "ph"], [4, 5, 6])
        self.assertEqual(late[0]["measured_at"], "2026-11-04T14:00:15+01:00")   # cycle 3 time
        self.assertEqual(live[0]["measured_at"], "2026-11-04T14:00:30+01:00")

    def test_low_water_falls_below_minimum(self):
        device, clock = make_device("low-water")
        level = [r["value"] for r in readings(run(device, clock, 10), "water_level")]
        self.assertGreater(level[0], 75)
        self.assertLess(level[8], 20)


class StatusTest(unittest.TestCase):

    def test_online_status(self):
        device, clock = make_device()
        topic, payload, retain = device.status(online=True)
        self.assertEqual(topic, "basilcare/v1/basil-test-01/status")
        self.assertTrue(retain)
        self.assertTrue(payload["online"])
        self.assertEqual(payload["telemetry_interval_s"], 5)
        self.assertEqual(payload["reported_at"], "2026-11-04T14:00:00+01:00")

    def test_last_will_has_no_report_time(self):
        device, clock = make_device()
        _, payload, retain = device.status(online=False, will=True)
        self.assertTrue(retain)
        self.assertFalse(payload["online"])
        self.assertIsNone(payload["reported_at"])
        self.assertEqual(payload["started_at"], "2026-11-04T14:00:00+01:00")


class PumpTest(unittest.TestCase):

    def ready_device(self, fault="none"):
        device, clock = make_device(fault)
        run(device, clock, 1)               # one cycle so the water level is known
        return device, clock

    def test_on_then_stops_by_itself(self):
        device, clock = self.ready_device()
        topic, state, retain = device.handle_command(command(clock, duration_s=10))
        self.assertEqual(topic, "basilcare/v1/basil-test-01/pump/state")
        self.assertTrue(retain)
        self.assertEqual((state["state"], state["result"], state["command_id"]), ("on", "executed", "cmd-1"))
        self.assertEqual(state["until"], iso(clock() + timedelta(seconds=10)))
        self.assertEqual(pump_states(run(device, clock, 2)), [])     # 0 s and 5 s: still on
        stopped = pump_states(device.step())                          # 10 s: time is up
        self.assertEqual(len(stopped), 1)
        self.assertEqual((stopped[0]["state"], stopped[0]["reason"]), ("off", "duration_elapsed"))
        self.assertIsNone(stopped[0]["command_id"])
        self.assertIsNone(stopped[0]["until"])

    def test_off_is_always_executed(self):
        device, clock = self.ready_device()
        device.handle_command(command(clock, command_id="a"))
        _, state, _ = device.handle_command(command(clock, command_id="b", action="off"))
        self.assertEqual((state["state"], state["result"]), ("off", "executed"))

    def test_duplicate_is_ignored(self):
        device, clock = self.ready_device()
        self.assertIsNotNone(device.handle_command(command(clock)))
        self.assertIsNone(device.handle_command(command(clock)))

    def assertRejected(self, device, raw, reason):
        _, state, _ = device.handle_command(raw)
        self.assertEqual((state["result"], state["reason"]), ("rejected", reason))
        self.assertNotEqual(state["state"], "on")

    def test_invalid_commands(self):
        device, clock = self.ready_device()
        self.assertRejected(device, b"not json", "invalid_command")
        self.assertRejected(device, b"[1, 2]", "invalid_command")
        self.assertRejected(device, command(clock, command_id="c1", action="start"), "invalid_command")
        self.assertRejected(device, command(clock, command_id="c2", duration_s=None), "invalid_command")
        self.assertRejected(device, command(clock, command_id="c3", duration_s=0), "invalid_command")
        self.assertRejected(device, command(clock, command_id="c4", duration_s=True), "invalid_command")
        self.assertRejected(device, command(clock, command_id="c5", duration_s=1.5), "invalid_command")
        self.assertRejected(device, command(clock, command_id="c6", expires_at="2026-11-04T15:00:00"),
                            "invalid_command")   # no UTC offset
        self.assertRejected(device, command(clock, command_id=None), "invalid_command")
        self.assertRejected(device, command(clock, command_id="c7", device_id="basil-other-01"),
                            "invalid_command")   # addressed to another device
        self.assertRejected(device, command(clock, command_id="c8", device_id=None), "invalid_command")

    def test_expired_command(self):
        device, clock = self.ready_device()
        old = command(clock)
        clock.advance(61)
        self.assertRejected(device, old, "expired")

    def test_duration_too_long(self):
        device, clock = self.ready_device()
        self.assertRejected(device, command(clock, duration_s=PUMP_MAX_DURATION_S + 1), "duration_too_long")

    def test_water_level_unknown_before_first_reading(self):
        device, clock = make_device()
        self.assertRejected(device, command(clock), "water_level_unknown")

    def test_low_water_rejects_start(self):
        device, clock = make_device("low-water")
        run(device, clock, 9)                              # level now below 20 %
        self.assertRejected(device, command(clock), "low_water_level")

    def test_low_water_stops_running_pump(self):
        device, clock = self.ready_device("low-water")
        device.handle_command(command(clock, duration_s=PUMP_MAX_DURATION_S))
        states = pump_states(run(device, clock, 10))
        self.assertEqual(len(states), 1)
        self.assertEqual((states[0]["state"], states[0]["reason"]), ("off", "low_water_level"))

    def test_pump_failure(self):
        device, clock = make_device("pump-failure")
        states = pump_states(run(device, clock, 3))
        self.assertEqual(len(states), 1)
        self.assertEqual((states[0]["state"], states[0]["reason"]), ("fault", "pump_fault"))
        self.assertRejected(device, command(clock, command_id="x"), "pump_fault")
        _, state, _ = device.handle_command(command(clock, command_id="y", action="off"))
        self.assertEqual((state["result"], state["state"]), ("executed", "fault"))   # off never clears a fault


class ScreeningTest(unittest.TestCase):

    def test_screening_message(self):
        device, clock = make_device(screening_every=1)
        results = [p for t, p, _ in run(device, clock, 30) if t.endswith("/screening")]
        self.assertEqual(len(results), 30)
        for result in results:
            self.assertTrue(0 <= result["confidence"] <= 1)
            self.assertEqual(result["quality_ok"], not result["quality_issues"])
            expected = result["confidence"] < 0.7 or not result["quality_ok"]
            self.assertEqual(result["review_required"], expected)
        self.assertTrue(any(r["review_required"] for r in results))


class TimeTest(unittest.TestCase):

    def test_parse_time(self):
        self.assertEqual(parse_time("2026-11-04T14:00:00+01:00"), datetime(2026, 11, 4, 14, tzinfo=TUNIS))
        self.assertIsNotNone(parse_time("2026-11-04T13:00:00Z"))
        self.assertIsNone(parse_time("2026-11-04T14:00:00"))   # no offset
        self.assertIsNone(parse_time("yesterday"))
        self.assertIsNone(parse_time(None))


if __name__ == "__main__":
    unittest.main()
