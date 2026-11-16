# ADR 0001: telemetry stored in MongoDB, one document per reading, deterministic id

**Status:** proposed (for team review) · **Date:** 2026-11-15

## Context

The scope (§3.2) leaves the time-series store open: "time-stamped telemetry store (final choice during design)". Needs:

- One reading per sensor every 5 s: 6 sensors means about 100 000 readings per device per day.
- The duplicate rule of contract §7: QoS 1 can deliver a message twice, and retained messages are replayed.
- Queries: the latest live value per sensor, the history of one sensor over a time window, and staleness.
- Readings arrive out of order: buffered readings come after an outage.

## Decision

- Store readings in the **MongoDB** we already run for the IAM and the device registry, in a `readings` collection with one document per reading.
- `_id = "{deviceId}:{sensor}:{measured_at in epoch ms}"`. A redelivered reading has the same id, so it cannot be stored twice. The same instant written with another offset (`+01:00` vs `Z`) is the same reading.
- Keep `measured_at` exactly as sent (with its offset) **and** `measuredAtEpoch` for sorting and ranges. Order is always by measurement time, never by arrival time.
- Indexes: `(deviceId, sensor, buffered, measuredAtEpoch desc)` for the latest live value, and `(deviceId, sensor, measuredAtEpoch)` for history. They are created at startup (`Startup.java`).

## Alternatives considered

| Option | Why not now |
|---|---|
| MongoDB **time-series collection** | Does not support unique indexes on custom keys, so duplicates would have to be filtered elsewhere. Worth revisiting if volume grows (compression, automatic bucketing). |
| InfluxDB / TimescaleDB | Another server to deploy, secure and back up on a student budget. No requirement needs it at prototype scale. |
| SQL database (scope §3.2 mentions SQL for users/controls) | The IAM and the registry are already on MongoDB through Jakarta NoSQL. One database is simpler to run. Revisit if relational reporting is needed. |

## Consequences

- At about 100 k documents per device per day, a laptop handles weeks of data. A retention job (for example a TTL index on old readings) is needed before long-term operation.
- FR-09 reports will use MongoDB aggregations (`$group` by day) rather than loading readings into Java.
