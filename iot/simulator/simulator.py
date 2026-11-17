"""BasilCare device simulator.

Behaves like the Raspberry Pi gateway on MQTT: it publishes sensor readings,
device status, pump state and image-screening results, and it obeys pump
commands with the same local safety rules. Every message follows
docs/mqtt-contract.md.

It lets the team build Node-RED flows, the API and the PWAs before the
hardware is ready, and inject faults on demand (pH drift, low water, ...).

    python simulator.py --help
"""
import argparse
import json
import os
import random
import re
import sys
import threading
import time
from datetime import datetime, timedelta

import paho.mqtt.client as mqtt

PREFIX = "basilcare/v1"
SOFTWARE = "simulator 0.1.0"

# sensor -> (unit, nominal value, noise, plausible min, plausible max)
# Nominal values are realistic for hydroponic basil but are only test data:
# they are NOT validated alert thresholds (contract section 3.1).
SENSORS = {
    "air_temperature":   ("degC",  24.0, 0.3,  -10, 60),
    "air_humidity":      ("%RH",   60.0, 1.5,    0, 100),
    "ph":                ("pH",     6.0, 0.03,   0, 14),
    "ec":                ("mS/cm",  1.4, 0.03,   0, 20),
    "water_temperature": ("degC",  21.0, 0.2,    0, 50),
    "water_level":       ("%",     80.0, 0.5,    0, 100),
}

FAULTS = {
    "none":         "normal readings",
    "ph-drift":     "pH rises by 0.08 per cycle",
    "low-water":    "water level falls by 8 points per cycle (below 20 % from cycle 8)",
    "stale":        "the pH sensor stops reporting from cycle 3; the rest keeps going",
    "pump-failure": "the pump goes into fault at cycle 2",
    "outage":       "readings of cycles 3-5 are queued, then sent late with buffered=true",
    "crash":        "the process dies at cycle 3 without disconnecting (tests the Last Will)",
}

# Device-side safety limits (contract section 5.2). Placeholders to agree on.
PUMP_MAX_DURATION_S = 900
PUMP_MIN_WATER_LEVEL = 20.0
REVIEW_CONFIDENCE = 0.7       # screening below this confidence needs a human


def iso(moment):
    """Timestamp format of the contract: ISO 8601, seconds, explicit offset."""
    return moment.isoformat(timespec="seconds")


def parse_time(text):
    """Contract timestamp -> aware datetime, or None if missing, invalid or without offset."""
    try:
        moment = datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None
    return moment if moment.tzinfo else None


def local_now():
    return datetime.now().astimezone()   # astimezone() attaches the local offset, e.g. +01:00


class Device:
    """The simulated Raspberry Pi.

    Pure logic: methods build messages as (topic, payload, retain) tuples and
    never touch the network, so the behaviour can be unit-tested without a broker.
    """

    def __init__(self, device_id, fault="none", interval=5, screening_every=12,
                 seed=None, clock=local_now):
        self.device_id = device_id
        self.fault = fault
        self.interval = interval
        self.screening_every = screening_every
        self.rng = random.Random(seed)
        self.clock = clock
        self.started_at = clock()
        self.cycle = 0
        self.seq = dict.fromkeys(SENSORS, 0)
        self.backlog = []             # readings held back during a simulated outage
        self.water_level = None       # last measured level, used by the pump safety rules
        self.pump = "off"
        self.pump_until = None
        self.handled = set()          # command_ids already processed (QoS 1 duplicates)
        self.lock = threading.Lock()  # commands arrive on paho's network thread

    def topic(self, *parts):
        return "/".join((PREFIX, self.device_id) + parts)

    # ---- status -------------------------------------------------------------

    def status(self, online, will=False):
        """Status message. With will=True it is the Last Will: written at connection
        time, so it cannot know when the device will be lost (reported_at null)."""
        return self.topic("status"), {
            "device_id": self.device_id,
            "online": online,
            "started_at": iso(self.started_at),
            "telemetry_interval_s": self.interval,
            "software": SOFTWARE,
            "reported_at": None if will else iso(self.clock()),
        }, True

    # ---- one measurement cycle ----------------------------------------------

    def step(self):
        """Run one measurement cycle and return the messages to publish, in order."""
        with self.lock:
            now = self.clock()
            readings = [self._read(sensor, now) for sensor in SENSORS if not self._silent(sensor)]

            if self.fault == "outage" and 3 <= self.cycle <= 5:
                for reading in readings:          # no connection: keep them locally
                    reading["buffered"] = True
                self.backlog += readings
                readings = []
            elif self.backlog:                     # connection back: oldest first
                readings = self.backlog + readings
                self.backlog = []

            messages = [(self.topic("telemetry", r["sensor"]), r, False) for r in readings]
            messages += self._pump_watchdog(now)
            if self.screening_every and self.cycle % self.screening_every == 0:
                messages.append(self._screening(now))
            self.cycle += 1
            return messages

    def _silent(self, sensor):
        return self.fault == "stale" and sensor == "ph" and self.cycle >= 3

    def _read(self, sensor, now):
        unit, nominal, noise, low, high = SENSORS[sensor]
        value = nominal + self.rng.gauss(0, noise)
        if sensor == "ph" and self.fault == "ph-drift":
            value += 0.08 * self.cycle
        if sensor == "water_level" and self.fault == "low-water":
            value -= 8 * self.cycle
        value = round(min(max(value, low), high), 2)   # a real sensor cannot leave its range
        if sensor == "water_level":
            self.water_level = value
        self.seq[sensor] += 1
        return {
            "device_id": self.device_id,
            "sensor": sensor,
            "value": value,
            "unit": unit,
            "measured_at": iso(now),
            "calibrated": True,
            "seq": self.seq[sensor],
            "buffered": False,
        }

    def _screening(self, now):
        label = "healthy" if self.rng.random() < 0.8 else "abnormal"
        confidence = round(self.rng.uniform(0.55, 0.99), 2)
        issues = ["too_dark"] if self.rng.random() < 0.1 else []
        return self.topic("screening"), {
            "device_id": self.device_id,
            "image_id": f"{self.device_id}-{now:%Y%m%dT%H%M%S}",
            "captured_at": iso(now),
            "model_version": "simulated",
            "label": label,
            "confidence": confidence,
            "quality_ok": not issues,
            "quality_issues": issues,
            "review_required": confidence < REVIEW_CONFIDENCE or bool(issues),
        }, False

    # ---- pump -----------------------------------------------------------------

    def pump_state(self, now=None, command_id=None, result=None, reason=None):
        return self.topic("pump", "state"), {
            "device_id": self.device_id,
            "state": self.pump,
            "until": iso(self.pump_until) if self.pump_until else None,
            "command_id": command_id,
            "result": result,
            "reason": reason,
            "reported_at": iso(now or self.clock()),
        }, True

    def _set_pump(self, state, now, duration_s=None):
        self.pump = state
        self.pump_until = now + timedelta(seconds=duration_s) if state == "on" else None

    def _pump_watchdog(self, now):
        """Changes the device makes by itself, without waiting for the cloud."""
        if self.fault == "pump-failure" and self.cycle >= 2 and self.pump != "fault":
            self._set_pump("fault", now)
            return [self.pump_state(now, reason="pump_fault")]
        if self.pump == "on" and now >= self.pump_until:
            self._set_pump("off", now)
            return [self.pump_state(now, reason="duration_elapsed")]
        if self.pump == "on" and self.water_level < PUMP_MIN_WATER_LEVEL:
            self._set_pump("off", now)
            return [self.pump_state(now, reason="low_water_level")]
        return []

    def handle_command(self, raw):
        """Apply one pump/cmd payload with the rules of contract section 5.2.
        Returns the pump/state reply, or None for a duplicate."""
        with self.lock:
            now = self.clock()
            try:
                cmd = json.loads(raw)
            except ValueError:
                cmd = None
            if not isinstance(cmd, dict):
                cmd = {}
            command_id = cmd.get("command_id")
            if not isinstance(command_id, str):
                command_id = None

            def reject(reason):
                return self.pump_state(now, command_id, "rejected", reason)

            # 1. duplicate delivery of a command already handled
            if command_id in self.handled:
                return None
            if command_id:
                self.handled.add(command_id)
            # 2. malformed command
            action, duration = cmd.get("action"), cmd.get("duration_s")
            valid_duration = type(duration) is int and duration > 0   # rejects true/false and 1.5
            expires_at = parse_time(cmd.get("expires_at"))
            if (cmd.get("device_id") != self.device_id or not command_id
                    or action not in ("on", "off") or expires_at is None
                    or (action == "on" and not valid_duration)):
                return reject("invalid_command")
            # 3. too old, e.g. it waited during an outage
            if now > expires_at:
                return reject("expired")
            # 4. stopping is always allowed (a pump in fault stays in fault)
            if action == "off":
                if self.pump != "fault":
                    self._set_pump("off", now)
                return self.pump_state(now, command_id, "executed")
            # 5-8. starting
            if self.pump == "fault":
                return reject("pump_fault")
            if duration > PUMP_MAX_DURATION_S:
                return reject("duration_too_long")
            if self.water_level is None:
                return reject("water_level_unknown")
            if self.water_level < PUMP_MIN_WATER_LEVEL:
                return reject("low_water_level")
            self._set_pump("on", now, duration)
            return self.pump_state(now, command_id, "executed")


# ---- MQTT -------------------------------------------------------------------

def publish(client, message):
    topic, payload, retain = message
    text = json.dumps(payload)
    info = client.publish(topic, text, qos=1, retain=retain)
    print(f"{topic} {text}", flush=True)
    return info


def device_id(text):
    if not re.fullmatch(r"[a-z0-9-]{3,32}", text):
        raise argparse.ArgumentTypeError("3 to 32 characters: a-z, 0-9 and '-'")
    return text


def positive_int(text):
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return value


def parse_args(argv=None):
    faults = "\n".join(f"  {name:<13} {text}" for name, text in FAULTS.items())
    parser = argparse.ArgumentParser(
        description="Simulated BasilCare device (messages follow docs/mqtt-contract.md).",
        epilog="faults:\n" + faults,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default="localhost", help="MQTT broker host (default: localhost)")
    parser.add_argument("--port", type=int, default=1883, help="MQTT broker port (default: 1883)")
    parser.add_argument("--device", type=device_id, default="basil-sim-01",
                        help="device_id used in topics and payloads (default: basil-sim-01)")
    parser.add_argument("--interval", type=positive_int, default=5,
                        help="seconds between two measurement cycles (default: 5)")
    parser.add_argument("--count", type=int, default=0,
                        help="number of cycles, 0 = run until Ctrl+C (default: 0)")
    parser.add_argument("--fault", choices=FAULTS, default="none", help="fault to inject (see below)")
    parser.add_argument("--screening-every", type=int, default=12, metavar="N",
                        help="publish a screening result every N cycles, 0 = never (default: 12)")
    parser.add_argument("--seed", type=int, help="random seed, for repeatable runs")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    device = Device(args.device, args.fault, args.interval, args.screening_every, args.seed)
    connected = threading.Event()

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"{args.device}-simulator")
    will_topic, will, _ = device.status(online=False, will=True)
    client.will_set(will_topic, json.dumps(will), qos=1, retain=True)

    def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            print(f"broker refused the connection: {reason_code}", file=sys.stderr)
            return
        client.subscribe(device.topic("pump", "cmd"), qos=1)
        publish(client, device.status(online=True))   # replaces the retained Last Will
        with device.lock:
            publish(client, device.pump_state())
        connected.set()

    def on_message(client, userdata, msg):
        reply = device.handle_command(msg.payload)
        if reply:
            publish(client, reply)

    client.on_connect = on_connect
    client.on_message = on_message
    try:
        client.connect(args.host, args.port, keepalive=30)
    except OSError as error:
        sys.exit(f"cannot reach the MQTT broker at {args.host}:{args.port} ({error}).\n"
                 "Start it with: docker compose -f deploy/compose.yaml up -d mosquitto")
    client.loop_start()   # network thread: sends, receives, reconnects
    if not connected.wait(timeout=10):
        client.loop_stop()
        sys.exit("no answer from the MQTT broker within 10 s")

    try:
        while True:
            if args.fault == "crash" and device.cycle == 3:
                print("crash: exiting without DISCONNECT, the broker will publish the Last Will",
                      file=sys.stderr, flush=True)
                os._exit(1)   # skips the clean shutdown below on purpose
            for message in device.step():
                publish(client, message)
            if args.count and device.cycle >= args.count:
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        pass
    finally:
        # Clean shutdown: the broker does not send the Last Will, so say it ourselves.
        if client.is_connected():
            publish(client, device.status(online=False)).wait_for_publish(timeout=5)
        client.disconnect()
        client.loop_stop()


if __name__ == "__main__":
    main()
