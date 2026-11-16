"""Local pump safety (contract section 5.2, scope sections 4.2 and 6.2).

The device re-checks every command, even though the API already did. This check works
when the cloud is down, and neither an API bug nor the AI assistant can bypass it.

Safety properties:
- the relay is OFF at start-up and at shutdown (safe default state);
- every "on" has a duration; the pump stops by itself when it runs out, even without network
  ("cloud disconnection must not cause unbounded pump operation", scope section 6.2);
- the pump stops by itself when the water level falls below the minimum (no dry running);
- a command is rejected when expired, malformed, addressed to another device, too long,
  when the pump is in fault, or when the water level is unknown or too low.
"""
import json
import threading
from datetime import timedelta

from . import messages


class FakeRelay:
    """Stands in for the relay when no hardware is attached (development, tests)."""

    def __init__(self):
        self.is_on = False

    def on(self):
        self.is_on = True

    def off(self):
        self.is_on = False


class GpioRelay:
    """Relay module on a GPIO pin (gpiozero). initial_value=False: off as soon as the program starts."""

    def __init__(self, pin, active_high=True):
        from gpiozero import OutputDevice   # only on the Pi
        self.device = OutputDevice(pin, active_high=active_high, initial_value=False)

    @property
    def is_on(self):
        return bool(self.device.value)

    def on(self):
        self.device.on()

    def off(self):
        self.device.off()


class PumpGuard:
    """Pure decision logic plus the relay. Methods return pump/state messages to publish."""

    def __init__(self, device_id, relay, max_duration_s=900, min_water_level=20.0, water_level_max_age_s=15,
                 clock=messages.local_now):
        self.device_id = device_id
        self.relay = relay
        self.max_duration_s = max_duration_s
        self.min_water_level = min_water_level
        # A reading older than this is as good as none: a probe that stopped answering must not
        # leave its last "safe" value in charge of the pump (review finding #4).
        self.water_level_max_age_s = water_level_max_age_s
        self.clock = clock
        self.state = "off"
        self.until = None
        self.water_level = None
        self.water_level_at = None
        self.handled = {}              # command_ids already processed (QoS 1 duplicates), oldest first
        self.lock = threading.Lock()   # commands arrive on the MQTT thread, the watchdog on another
        self.relay.off()

    def message(self, now=None, command_id=None, result=None, reason=None):
        return messages.pump_state(self.device_id, self.state, self.until, now or self.clock(),
                                   command_id, result, reason)

    def current(self):
        with self.lock:
            return self.message()

    def set_water_level(self, level):
        with self.lock:
            self.water_level = level
            self.water_level_at = self.clock()

    def _water_level_known(self, now):
        """True when a level was measured recently enough to be trusted."""
        if self.water_level is None or self.water_level_at is None:
            return False
        return (now - self.water_level_at).total_seconds() <= self.water_level_max_age_s

    def _switch(self, state, now, duration_s=None):
        self.state = state
        if state == "on":
            self.until = now + timedelta(seconds=duration_s)
            self.relay.on()
        else:
            self.until = None
            self.relay.off()

    def handle(self, raw):
        """Apply one pump/cmd payload. Returns the pump/state reply, or None for a duplicate."""
        with self.lock:
            now = self.clock()
            try:
                cmd = json.loads(raw)
            except (TypeError, ValueError):
                cmd = None
            if not isinstance(cmd, dict):
                cmd = {}
            command_id = cmd.get("command_id") if isinstance(cmd.get("command_id"), str) else None

            def reject(reason):
                return self.message(now, command_id, "rejected", reason)

            # 1. duplicate delivery
            if command_id and command_id in self.handled:
                return None
            if command_id:
                self.handled[command_id] = True
                if len(self.handled) > 10_000:   # bounded memory: forget the oldest half
                    self.handled = dict.fromkeys(list(self.handled)[-5_000:], True)
            # 2. malformed
            action, duration = cmd.get("action"), cmd.get("duration_s")
            valid_duration = type(duration) is int and duration > 0
            expires_at = messages.parse_time(cmd.get("expires_at"))
            if (cmd.get("device_id") != self.device_id or not command_id or action not in ("on", "off")
                    or expires_at is None or (action == "on" and not valid_duration)):
                return reject("invalid_command")
            # 3. expired
            if now > expires_at:
                return reject("expired")
            # 4. stopping is always allowed (a pump in fault stays in fault)
            if action == "off":
                if self.state != "fault":
                    self._switch("off", now)
                return self.message(now, command_id, "executed")
            # 5-8. starting
            if self.state == "fault":
                return reject("pump_fault")
            if duration > self.max_duration_s:
                return reject("duration_too_long")
            if not self._water_level_known(now):
                return reject("water_level_unknown")
            if self.water_level < self.min_water_level:
                return reject("low_water_level")
            self._switch("on", now, duration)
            return self.message(now, command_id, "executed")

    def watchdog(self):
        """Called about every second. Returns a pump/state message when the device acted by itself."""
        with self.lock:
            now = self.clock()
            if self.state == "on" and now >= self.until:
                self._switch("off", now)
                return self.message(now, reason="duration_elapsed")
            if self.state == "on" and not self._water_level_known(now):
                self._switch("off", now)   # the probe went silent: running dry cannot be excluded
                return self.message(now, reason="water_level_unknown")
            if self.state == "on" and self.water_level < self.min_water_level:
                self._switch("off", now)
                return self.message(now, reason="low_water_level")
            return None

    def fault(self):
        """A pump failure was detected (e.g. flow sensor, current sensor): stop and stay in fault."""
        with self.lock:
            now = self.clock()
            self._switch("off", now)
            self.state = "fault"
            return self.message(now, reason="pump_fault")

    def shutdown(self):
        with self.lock:
            self.relay.off()
