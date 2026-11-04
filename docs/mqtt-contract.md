# MQTT contract, version 1

This document fixes the MQTT topics and JSON messages exchanged between a BasilCare **device** (the Raspberry Pi gateway, or [`simulator/simulator.py`](../simulator/simulator.py) standing in for it) and the **cloud** (Mosquitto → Node-RED → Jakarta EE API).

Every component that publishes or subscribes follows it: `edge/`, `simulator/`, the Node-RED flows, the API, and, through the API, the MCP tools. A change to a topic or a field starts with a change to this file.

---

## 1. Conventions

| Item | Rule |
|---|---|
| Topic root | `basilcare/v1/`. `v1` is the version of this contract (see §8). |
| `device_id` | 3 to 32 characters: lower-case letters, digits and `-`, e.g. `basil-pi-01`. Never contains `/`, `+` or `#`. The `device_id` inside a payload always equals the one in the topic. Simulated devices use `basil-sim-NN`. |
| Payload | One JSON object, UTF-8, field names in `snake_case`. |
| Timestamps | ISO 8601 **with an explicit UTC offset**, second precision: `2026-11-04T14:05:00+01:00`. Never a time without offset, never an epoch number. A timestamp says when the event happened on the device, not when it was received. Devices keep their clock synchronised with NTP. |
| Numbers | Measured values are JSON numbers in the unit of §3, never strings. |
| QoS | **1** on every topic (at-least-once delivery, so a consumer can receive the same message twice, see §7). |
| Retained | Only `status` and `pump/state`. |
| Unknown fields | Consumers ignore fields they do not know. This lets us add fields without breaking anyone. |

---

## 2. Topics

| Topic | Direction | Retained | Content |
|---|---|---|---|
| `basilcare/v1/{device_id}/telemetry/{sensor}` | device → cloud | no | one sensor reading (§3) |
| `basilcare/v1/{device_id}/status` | device → cloud | **yes** | device online or offline, with a Last Will (§4) |
| `basilcare/v1/{device_id}/pump/cmd` | cloud → device | **no** | request to start or stop the pump (§5) |
| `basilcare/v1/{device_id}/pump/state` | device → cloud | **yes** | pump state, and the result of the last command (§5) |
| `basilcare/v1/{device_id}/screening` | device → cloud | no | result of one edge image screening (§6) |

Useful subscriptions:

| Subscription | Receives |
|---|---|
| `basilcare/v1/#` | everything (debugging) |
| `basilcare/v1/+/telemetry/#` | every reading of every device |
| `basilcare/v1/+/telemetry/ph` | pH readings only |
| `basilcare/v1/+/status` | online/offline of every device |
| `basilcare/v1/+/pump/state` | pump states and command results |

---

## 3. Telemetry

### 3.1 Sensors

| `sensor` | Quantity | `unit` | Plausible range | Hardware (scope §3.1) |
|---|---|---|---|---|
| `air_temperature` | ambient air temperature | `degC` | −10 to 60 | BME280 or similar |
| `air_humidity` | ambient relative humidity | `%RH` | 0 to 100 | BME280 or similar |
| `ph` | nutrient-solution pH | `pH` | 0 to 14 | pH probe + interface |
| `ec` | nutrient-solution electrical conductivity | `mS/cm` | 0 to 20 | EC probe + interface |
| `water_temperature` | nutrient-solution temperature | `degC` | 0 to 50 | water-temperature probe |
| `water_level` | reservoir level, percent of full | `%` | 0 to 100 | level sensor |

**The plausible range is not an alert threshold.** It only says whether a reading can be physically real. A value outside it means a sensor or wiring fault and becomes a *device* incident.

Agronomic thresholds (for example "pH too high for basil") are configured by an administrator in the API and checked against agronomic sources before activation (scope §1.4). They are deliberately not part of this contract.

EC is a proxy for dissolved ions, not a sodium-specific measurement.

### 3.2 Reading payload

Topic: `basilcare/v1/basil-pi-01/telemetry/ph`

```json
{
  "device_id": "basil-pi-01",
  "sensor": "ph",
  "value": 6.04,
  "unit": "pH",
  "measured_at": "2026-11-04T14:05:00+01:00",
  "calibrated": true,
  "seq": 128,
  "buffered": false
}
```

| Field | Type | Meaning |
|---|---|---|
| `device_id` | string | same as in the topic |
| `sensor` | string | same as in the topic, one of §3.1 |
| `value` | number | the measurement, in `unit` |
| `unit` | string | the unit of §3.1 for this sensor |
| `measured_at` | timestamp | when the sensor was read |
| `calibrated` | boolean | `false` when the probe has no valid calibration. The PWAs must show it (scope §4.2). |
| `seq` | integer | counter per device **and** sensor: +1 for each reading, back to 1 when the device software restarts (`status.started_at` changes). A gap means lost readings. |
| `buffered` | boolean | `true` when the reading waited in the device's local queue during a connection loss and is sent late. Buffered readings are **history**: store them, but never display them as live values (scope §2.3). |

A device publishes one reading per sensor every `telemetry_interval_s` seconds (announced in `status`), and never more than one reading per sensor per second.

---

## 4. Device status and Last Will

Topic: `basilcare/v1/basil-pi-01/status` (retained)

```json
{
  "device_id": "basil-pi-01",
  "online": true,
  "started_at": "2026-11-04T08:00:12+01:00",
  "telemetry_interval_s": 5,
  "software": "edge 0.1.0",
  "reported_at": "2026-11-04T08:00:13+01:00"
}
```

| Field | Type | Meaning |
|---|---|---|
| `device_id` | string | same as in the topic |
| `online` | boolean | `true` when connected, `false` when disconnected |
| `started_at` | timestamp | when the device software started; a new value means a restart |
| `telemetry_interval_s` | integer | seconds between two readings of the same sensor; used to detect stale readings (§7) |
| `software` | string | name and version of the publishing program |
| `reported_at` | timestamp or `null` | when the message was produced. `null` in the Last Will (see below). |

Lifecycle:

1. Before connecting, the device registers a **Last Will** on `status`: the same payload with `"online": false` and `"reported_at": null`, QoS 1, retained.
2. After every connection or reconnection, it publishes `"online": true` (retained). This replaces the previous Last Will.
3. On a clean shutdown, it publishes `"online": false` itself and then disconnects. The broker does **not** send the Last Will after a clean disconnection.
4. If the device crashes or loses the network, the broker publishes the Last Will once the keep-alive expires (keep-alive 30 s, so within about 45 s).

The Last Will is written at connection time, so it cannot know when the device will be lost. That is why its `reported_at` is `null`, and consumers use the time they received it.

Because `status` is retained, a consumer that starts later immediately learns the last known state of every device.

---

## 5. Pump control

```
PWA or AI assistant (MCP)
   → Jakarta EE API: role check, user confirmation, safety policy, audit record
   → pump/cmd → device: local safety check, then relay
   → pump/state → API: result added to the audit record
```

Only the backend publishes on `pump/cmd`, never a PWA or the AI service directly. The production broker enforces this with access control (§9).

### 5.1 Command: `pump/cmd` (not retained)

Topic: `basilcare/v1/basil-pi-01/pump/cmd`

```json
{
  "device_id": "basil-pi-01",
  "command_id": "4f6a1c2e-8d0b-4c56-9a51-0c3e7a9b2d10",
  "action": "on",
  "duration_s": 120,
  "requested_by": "farmer1",
  "requested_at": "2026-11-04T14:06:00+01:00",
  "expires_at": "2026-11-04T14:07:00+01:00"
}
```

| Field | Type | Meaning |
|---|---|---|
| `device_id` | string | the device that must execute the command, same as in the topic. A device rejects a command addressed to another device. |
| `command_id` | string | unique id (a UUID) created by the API; links the command to its audit record |
| `action` | `"on"` or `"off"` | start or stop the pump |
| `duration_s` | integer > 0 | required for `"on"`: the device stops the pump by itself after this many seconds. Ignored for `"off"`. |
| `requested_by` | string | the user who asked, for the audit trail |
| `requested_at` | timestamp | when the user asked |
| `expires_at` | timestamp | the device rejects the command if it is handled after this time (e.g. it waited during an outage) |

`pump/cmd` is **never retained**. A retained command would be delivered again after every reconnection or restart of the device, and could start the pump without anyone asking.

### 5.2 Safety rules applied by the device

The device checks every command again, even though the API already did. The local check still works when the cloud is down, and neither an API bug nor the AI assistant can bypass it (scope §4.2, §5.3). The device applies these rules in order and stops at the first that matches:

| # | Condition | Outcome (`result` / `reason`) |
|---|---|---|
| 1 | `command_id` already handled (QoS 1 duplicate) | ignored: nothing is published |
| 2 | not JSON, `device_id` not the device's own, missing `command_id`, unknown `action`, `"on"` without a positive integer `duration_s`, missing or invalid `expires_at` | `rejected` / `invalid_command` |
| 3 | current time after `expires_at` | `rejected` / `expired` |
| 4 | `action` is `"off"` | `executed`: stopping is always allowed |
| 5 | pump is in `fault` | `rejected` / `pump_fault` |
| 6 | `duration_s` above the device maximum | `rejected` / `duration_too_long` |
| 7 | no water-level reading yet | `rejected` / `water_level_unknown` |
| 8 | last water level below the device minimum | `rejected` / `low_water_level` |
| 9 | otherwise | `executed` |

An `"on"` while the pump is already running restarts its timer with the new `duration_s`.

The device also changes the pump state **by itself**, without a command (`command_id` and `result` are then `null`):

| `reason` | When |
|---|---|
| `duration_elapsed` | the `duration_s` of the last `"on"` ran out |
| `low_water_level` | the water level fell below the minimum while the pump was running |
| `pump_fault` | the device detected a pump failure; state becomes `fault` until maintenance on the device |

Default device limits: maximum run **900 s**, minimum water level **20 %**. These are placeholders to agree on (§10).

### 5.3 State: `pump/state` (retained)

Topic: `basilcare/v1/basil-pi-01/pump/state`

```json
{
  "device_id": "basil-pi-01",
  "state": "on",
  "until": "2026-11-04T14:08:01+01:00",
  "command_id": "4f6a1c2e-8d0b-4c56-9a51-0c3e7a9b2d10",
  "result": "executed",
  "reason": null,
  "reported_at": "2026-11-04T14:06:01+01:00"
}
```

| Field | Type | Meaning |
|---|---|---|
| `device_id` | string | same as in the topic |
| `state` | `"on"`, `"off"` or `"fault"` | what the pump is doing now (`fault`: stopped because of a detected failure) |
| `until` | timestamp or `null` | while `on`: when the device will stop it by itself |
| `command_id` | string or `null` | the command this message answers; `null` when the device acted by itself |
| `result` | `"executed"`, `"rejected"` or `null` | outcome of that command |
| `reason` | string or `null` | why (tables of §5.2) |
| `reported_at` | timestamp | when the message was produced |

The device publishes `pump/state` after each connection (current state), after each command it handles, and after each change it makes by itself.

---

## 6. Image screening

Images stay on the Pi. Only the derived result is sent (scope §4.1).

Topic: `basilcare/v1/basil-pi-01/screening`

```json
{
  "device_id": "basil-pi-01",
  "image_id": "basil-pi-01-20261104T140500",
  "captured_at": "2026-11-04T14:05:00+01:00",
  "model_version": "leafscreen-0.1-int8",
  "label": "healthy",
  "confidence": 0.62,
  "quality_ok": true,
  "quality_issues": [],
  "review_required": true
}
```

| Field | Type | Meaning |
|---|---|---|
| `device_id` | string | same as in the topic |
| `image_id` | string | identifies the image kept on the device, for later human review |
| `captured_at` | timestamp | when the picture was taken |
| `model_version` | string | which model produced the result (traceability, scope §5.4) |
| `label` | string | predicted class. The class list depends on the labelled basil data available (scope §5.1), so consumers accept any label. `"unknown"` when the model cannot decide. |
| `confidence` | number, 0 to 1 | model confidence |
| `quality_ok` | boolean | result of the image-quality checks |
| `quality_issues` | list of strings | e.g. `"too_dark"`, `"blurry"`, `"out_of_frame"`; empty when `quality_ok` is `true` |
| `review_required` | boolean | `true` when the confidence is below the device threshold or the quality check failed. The PWA then shows "review required". It never presents the result as a diagnosis. |

---

## 7. Rules for consumers (Node-RED, API)

- **Duplicates.** QoS 1 can deliver a message twice. Ignore a reading whose (`device_id`, `sensor`, `measured_at`) is already stored, and a `pump/state` whose `command_id` is already in the audit trail.
- **Retained replays.** On every (re)subscription the broker sends the retained `status` and `pump/state` again. The duplicate rule above makes this harmless.
- **Validation before storage.** The topic and payload agree on `device_id` and `sensor`, `unit` matches §3.1, `value` is a number inside the plausible range, and the timestamps carry an offset. A message that fails is logged and raises a device incident. It is never stored as a valid reading.
- **Stale readings.** A sensor is stale when its last `measured_at` is older than 3 × `telemetry_interval_s` (from the retained `status`) while the device is `online`. A device whose `status` says `online: false` is *offline*, which is a separate incident.
- **Order.** Messages can arrive out of order (buffered readings arrive after an outage). Sort by `measured_at`, never by arrival time.
- **Buffered readings.** Store them with their flag. Show them as history and not as the current value.

---

## 8. Versioning

- **Allowed in v1:** adding an optional field or a new sensor name. Document it here first.
- **Breaking:** renaming or removing a field, or changing a unit or a type. That needs a new root `basilcare/v2/`, and both versions run side by side during the migration.

---

## 9. Security

**Development** (`deploy/compose.yaml`): Mosquitto accepts anonymous clients on port 1883. Use it only on your own machine.

**Before any Internet exposure** (scope §4.2, §6.1):

- TLS on port 8883;
- one identity per device and per backend service (username/password or client certificate), with the device username equal to its `device_id`;
- an access-control list so that a device only uses its own topics:

| Client | May publish | May subscribe |
|---|---|---|
| device `basil-pi-01` | `basilcare/v1/basil-pi-01/telemetry/#`, `.../status`, `.../pump/state`, `.../screening` | `basilcare/v1/basil-pi-01/pump/cmd` |
| backend (Node-RED, API) | `basilcare/v1/+/pump/cmd` | `basilcare/v1/#` |

In Mosquitto, `%u` stands for the username, so one rule covers all devices, for example `pattern write basilcare/v1/%u/telemetry/#`.

---

## 10. Open questions for the team

| Question | Current placeholder |
|---|---|
| Telemetry interval of the real Pi | 5 s in the simulator |
| Pump limits (maximum run, minimum water level) | 900 s, 20 % |
| EC unit: mS/cm or µS/cm? Depends on the EC interface we buy. | mS/cm |
| How `water_level` is calibrated to "% of full" (empty and full marks) | to define with the hardware |
| Screening classes | to decide after the dataset audit (scope §5.1) |
| Screening confidence threshold for `review_required` | 0.7 in the simulator |
