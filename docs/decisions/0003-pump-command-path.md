# ADR 0003: pump commands go PWA/MCP → API → MQTT, with two safety barriers

**Status:** proposed · **Date:** 2026-11-15

## Context

Scope §4.2, §5.3 and §6.2: control actions must be confirmed, checked by a deterministic safety policy, attributable to a role and a timestamp, and impossible to bypass by the AI assistant. Pump cutoffs must work when the cloud is down.

## Decision

1. **Single entry point:** `POST /api/pump/{deviceId}/commands`. The PWAs and, later, the MCP server use it. Nobody else publishes on `pump/cmd`, and the production broker ACL enforces this (contract §9).
2. **Confirmation:** the request must carry `"confirm": true`, otherwise it gets 428 with nothing recorded and nothing sent. The PWA shows a confirmation dialog. The MCP server must ask the user before setting it.
3. **API safety policy** (`PumpSafetyPolicy`, a pure function). In order: registered, enabled, `off` always allowed, online, no pump fault, duration ≤ maximum, a *recent* water-level reading exists, level ≥ minimum.
4. **Audit before action:** the `PumpCommand` record (who, role, OAuth client, when, expiry, decision, reason) is written **before** publishing. Rejections are recorded too. The device's answer on `pump/state` completes the same record.
5. **The API publishes directly to Mosquitto** (Paho, QoS 1, **never retained**, expires after 60 s), not through Node-RED: one hop less between the policy and the device.
6. **Device safety** (`PumpGuard` on the Pi) re-applies the contract §5.2 rules and stops the pump by itself when the duration ends or the water is low, with or without network. The relay is off at start and at shutdown.

## Consequences

- An API bug or a compromised AI assistant still meets the Pi's own rules.
- A command sent while the device is offline is lost (not retained, by design). The user sees "waiting…" in the audit log and can retry.
- The simulator and the edge gateway implement the same rules, and both are unit-tested rule by rule.
