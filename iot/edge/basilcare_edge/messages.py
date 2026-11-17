"""Builders for the MQTT messages of docs/mqtt-contract.md (version 1).

Pure functions: they only build (topic, payload, retain) tuples, so they are easy to test
and every publisher in the gateway produces exactly the same shapes as the simulator.
"""
from datetime import datetime

PREFIX = "basilcare/v1"

# sensor -> (unit, plausible min, plausible max), contract section 3.1
SENSORS = {
    "air_temperature": ("degC", -10, 60),
    "air_humidity": ("%RH", 0, 100),
    "ph": ("pH", 0, 14),
    "ec": ("mS/cm", 0, 20),
    "water_temperature": ("degC", 0, 50),
    "water_level": ("%", 0, 100),
}


def iso(moment):
    """Contract timestamp: ISO 8601, second precision, explicit offset."""
    return moment.isoformat(timespec="seconds")


def parse_time(text):
    """Contract timestamp -> aware datetime, or None if missing, invalid or without offset."""
    try:
        moment = datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None
    return moment if moment.tzinfo else None


def local_now():
    return datetime.now().astimezone()


def topic(device_id, *parts):
    return "/".join((PREFIX, device_id) + parts)


def reading(device_id, sensor, value, measured_at, calibrated, seq, buffered=False):
    unit = SENSORS[sensor][0]
    return topic(device_id, "telemetry", sensor), {
        "device_id": device_id,
        "sensor": sensor,
        "value": round(float(value), 3),
        "unit": unit,
        "measured_at": iso(measured_at),
        "calibrated": bool(calibrated),
        "seq": int(seq),
        "buffered": bool(buffered),
    }, False


def status(device_id, online, started_at, interval_s, software, reported_at):
    """reported_at None = Last Will (the device cannot date its own disappearance)."""
    return topic(device_id, "status"), {
        "device_id": device_id,
        "online": online,
        "started_at": iso(started_at),
        "telemetry_interval_s": int(interval_s),
        "software": software,
        "reported_at": iso(reported_at) if reported_at else None,
    }, True


def pump_state(device_id, state, until, reported_at, command_id=None, result=None, reason=None):
    return topic(device_id, "pump", "state"), {
        "device_id": device_id,
        "state": state,
        "until": iso(until) if until else None,
        "command_id": command_id,
        "result": result,
        "reason": reason,
        "reported_at": iso(reported_at),
    }, True


def screening(device_id, image_id, captured_at, model_version, label, confidence, quality_issues,
              review_required):
    return topic(device_id, "screening"), {
        "device_id": device_id,
        "image_id": image_id,
        "captured_at": iso(captured_at),
        "model_version": model_version,
        "label": label,
        "confidence": round(float(confidence), 3),
        "quality_ok": not quality_issues,
        "quality_issues": list(quality_issues),
        "review_required": bool(review_required),
    }, False
