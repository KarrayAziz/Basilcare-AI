# BasilCare API

Jakarta EE 11 REST API deployed as `api.war` on WildFly. It stores device data, raises incidents, controls the pump safely, and serves the PWAs.

## Endpoints

Protected endpoints require `Authorization: Bearer <access-token>` with a token issued by the BasilCare IAM. The ingest endpoints use the `X-Ingest-Key` service key instead (Node-RED only, [ADR 0002](../docs/decisions/0002-ingest-authentication.md)).

| Method | Path | Roles | Purpose |
|---|---|---|---|
| `GET` | `/api/health` | Public | Service liveness |
| `GET` | `/api/me` | Farmer, Admin | Current authenticated user |
| `GET` | `/api/devices` | Farmer, Admin | List registered IoT gateways |
| `GET` | `/api/devices/{deviceId}` | Farmer, Admin | Read one gateway |
| `POST` | `/api/devices` | Admin | Register a gateway (409 if it exists) |
| `PUT` | `/api/devices/{deviceId}` | Admin | Update gateway metadata or availability |
| `DELETE` | `/api/devices/{deviceId}` | Admin | Remove a gateway |
| `GET` | `/api/device-states[/{deviceId}]` | Farmer, Admin | Online/offline state reported by the devices |
| `GET` | `/api/telemetry/latest?deviceId=` | Farmer, Admin | Live value of each sensor, with `stale`, `calibrated`, `ageSeconds`; never a buffered reading |
| `GET` | `/api/telemetry/history?deviceId=&sensor=&from=&to=&limit=` | Farmer, Admin | Readings ordered by `measured_at` (default: last 24 h, at most 10 000) |
| `GET` | `/api/screenings?deviceId=&limit=` | Farmer, Admin | Edge leaf-screening results, newest first |
| `GET` | `/api/incidents?status=&deviceId=&limit=` | Farmer, Admin | `status` = unresolved (default), open, acknowledged, resolved, all |
| `GET` | `/api/incidents/{id}` | Farmer, Admin | One incident |
| `POST` | `/api/incidents/{id}/acknowledge` | Farmer, Admin | Records who saw it, and when |
| `POST` | `/api/incidents/{id}/resolve` | Farmer, Admin | Body `{"note": "what was done"}` (3 to 500 characters) |
| `GET` | `/api/thresholds` | Farmer, Admin | Alert range of each sensor |
| `PUT` | `/api/thresholds/{sensor}` | Admin | `{"min", "max", "enabled", "severity", "verified", "source"}` |
| `GET` | `/api/pump/{deviceId}` | Farmer, Admin | Last pump state reported by the device, plus the API's limits |
| `POST` | `/api/pump/{deviceId}/commands` | Farmer, Admin | `{"action": "on", "duration_s": 120, "confirm": true}`: 202 sent, 409 refused (with the reason), 428 not confirmed, 503 broker down |
| `GET` | `/api/pump/commands?deviceId=&limit=` | Farmer, Admin | Pump audit log, newest first |
| `POST` | `/api/ingest/{telemetry,status,pump-state,screening}` | Service key | MQTT payloads of [the contract](../docs/mqtt-contract.md), unchanged: 201 stored, 200 duplicate, 422 invalid |
| `POST` | `/api/ingest/invalid` | Service key | `{"topic", "errors"}` of a message Node-RED rejected: raises a device incident |

Timestamps in query parameters are ISO 8601 with an offset, URL-encoded (`2026-11-04T14:05:00%2B01:00`).

## How it works

```
boundaries/    REST resources (thin: parse, call a service, map the answer to HTTP)
services/      TelemetryService, IncidentService, PumpService, ThresholdService,
               PumpSafetyPolicy (pure), ContractValidator (pure), StaleWatcher (timer, every 15 s)
repositories/  TelemetryStore, IncidentStore, PumpStore interfaces + MongoDB implementations
entities/      Device, DeviceState, Reading, ScreeningResult, Incident, Threshold, PumpStatus, PumpCommand
security/      SecurityFilter (user JWT, roles), IngestKeyFilter (service key)
```

- **Readings**: `_id = device:sensor:epoch`, so a QoS 1 duplicate cannot be stored twice ([ADR 0001](../docs/decisions/0001-telemetry-store.md)). Buffered readings are history. They never become the live value and never open or clear an incident.
- **Incidents**: at most one unresolved incident per (device, type, sensor). A condition that disappears marks it inactive. A person resolves it with a note. Types: `threshold`, `stale`, `offline`, `pump_fault`, `invalid_message`, `leaf_anomaly`.
- **Alert ranges** are seeded at the first start with typical basil values, flagged `verified: false` until an administrator checks them against a source.
- **Pump**: confirmation, then the deterministic safety policy, then the audit record (written *before* sending), then MQTT `pump/cmd` (QoS 1, never retained, expires after 60 s). The device's `pump/state` answer completes the record ([ADR 0003](../docs/decisions/0003-pump-command-path.md)).

## Configuration

`src/main/resources/META-INF/microprofile-config.properties`. Each key can be overridden by an environment variable (dots become underscores, upper case):

| Key | Default | Environment |
|---|---|---|
| `jnosql.mongodb.host` | `localhost:27017` | `JNOSQL_MONGODB_HOST` |
| `mqtt.broker.url` | `tcp://localhost:1883` | `MQTT_BROKER_URL` (`mqtt.username` and `mqtt.password` optional) |
| `ingest.key` | *(none: ingestion disabled)* | `INGEST_KEY` |
| `pump.max.duration.s` / `pump.min.water.level` / `pump.command.ttl.s` | 900 / 20 / 60 | `PUMP_MAX_DURATION_S`, ... |

## Build and test

Requires JDK 25 and Maven 3.9+:

```bash
mvn clean verify     # 41 unit tests: services against in-memory stores, endpoint security
```

The whole data path is tested against the running stack by [`deploy/smoke_test.py`](../deploy/smoke_test.py).
