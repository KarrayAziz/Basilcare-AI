import json
import unittest

from basilcare_edge import messages
from basilcare_edge.pump import FakeRelay, PumpGuard
from tests.helpers import Clock

DEVICE = "basil-pi-01"


def command(clock, **fields):
    cmd = {"device_id": DEVICE, "command_id": "c-1", "action": "on", "duration_s": 60,
           "requested_by": "farmer1", "requested_at": messages.iso(clock()),
           "expires_at": messages.iso(clock.now.replace(minute=clock.now.minute + 1))}
    cmd.update(fields)
    return json.dumps({k: v for k, v in cmd.items() if v is not None})


class PumpGuardTest(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.relay = FakeRelay()
        self.relay.is_on = True                  # whatever state the GPIO had before
        self.guard = PumpGuard(DEVICE, self.relay, 900, 20.0, clock=self.clock)

    def reply(self, **fields):
        result = self.guard.handle(command(self.clock, **fields))
        return result and result[1]

    def test_relay_is_off_at_start(self):
        self.assertFalse(self.relay.is_on)

    def test_start_needs_a_known_and_sufficient_water_level(self):
        self.assertEqual("water_level_unknown", self.reply(command_id="a")["reason"])
        self.guard.set_water_level(12)
        self.assertEqual("low_water_level", self.reply(command_id="b")["reason"])
        self.guard.set_water_level(80)
        state = self.reply(command_id="c")
        self.assertEqual(("on", "executed"), (state["state"], state["result"]))
        self.assertTrue(self.relay.is_on)

    def test_rules_in_contract_order(self):
        self.guard.set_water_level(80)
        self.assertEqual("invalid_command", self.reply(command_id="a", device_id="basil-pi-02")["reason"])
        self.assertEqual("invalid_command", self.reply(command_id="b", duration_s=1.5)["reason"])
        self.assertEqual("invalid_command", self.reply(command_id="c", duration_s=True)["reason"])
        self.assertEqual("expired", self.reply(command_id="d", expires_at="2026-11-04T13:59:00+01:00")["reason"])
        self.assertEqual("duration_too_long", self.reply(command_id="e", duration_s=901)["reason"])
        self.assertIsNone(self.guard.handle("not json")[1]["command_id"])

    def test_duplicate_command_is_ignored(self):
        self.guard.set_water_level(80)
        self.assertIsNotNone(self.reply())
        self.assertIsNone(self.reply())

    def test_pump_stops_by_itself_without_any_network(self):
        self.guard.set_water_level(80)
        self.reply(duration_s=30)
        self.clock.advance(29)
        self.assertIsNone(self.guard.watchdog())
        self.clock.advance(1)
        state = self.guard.watchdog()[1]
        self.assertEqual(("off", "duration_elapsed", None), (state["state"], state["reason"], state["command_id"]))
        self.assertFalse(self.relay.is_on)

    def test_pump_stops_when_the_water_runs_low(self):
        self.guard.set_water_level(80)
        self.reply()
        self.guard.set_water_level(15)
        self.assertEqual("low_water_level", self.guard.watchdog()[1]["reason"])
        self.assertFalse(self.relay.is_on)

    def test_stop_always_works_and_fault_stays(self):
        self.guard.set_water_level(80)
        self.reply(command_id="a")
        self.guard.fault()
        self.assertEqual("pump_fault", self.reply(command_id="b")["reason"])
        stop = self.reply(command_id="c", action="off", duration_s=None)
        self.assertEqual(("executed", "fault"), (stop["result"], stop["state"]))
        self.assertFalse(self.relay.is_on)


if __name__ == "__main__":
    unittest.main()
