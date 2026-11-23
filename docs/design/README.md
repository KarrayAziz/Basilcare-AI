# Design statement (draft)

The working draft of the design statement PDF: use case, class, deployment and three sequence diagrams, plus the design choices behind them. The diagrams are PlantUML text files, so they are reviewed in `git diff` like code. The `.svg` files next to them are rendered from them.

Render after a change (Docker, nothing to install):

```bash
export MSYS_NO_PATHCONV=1      # Git Bash only
docker run --rm -v "$PWD/docs/design:/data" plantuml/plantuml:1.2025.2 -tsvg "/data/*.puml"
```

Or open a `.puml` file in VS Code with the "PlantUML" extension (Alt+D previews it).

## Diagrams

| Diagram | Shows |
|---|---|
| [Use cases](use-cases.svg) ([source](use-cases.puml)) | actors (farmer, administrator, agronomist, the Pi, the AI assistant) and what each one does; planned use cases are marked |
| [Domain classes](domain-classes.svg) ([source](domain-classes.puml)) | the API's entities and how they map to the IoT Thing / Sensor / Actuator abstractions (scope §7.3) |
| [Deployment](deployment.svg) ([source](deployment.puml)) | the Pi, the cloud VM (proxy, Mosquitto, Node-RED, WildFly, MongoDB), the phones, and the protocols between them |
| [Sequence 1: telemetry and incident](seq-telemetry-incident.svg) ([source](seq-telemetry-incident.puml)) | a reading from the sensor to the dashboard; duplicate handling; incident raised, cleared, acknowledged, resolved |
| [Sequence 2: safe pump control](seq-pump-command.svg) ([source](seq-pump-command.puml)) | confirmation, API safety policy, audit before sending, device re-check, automatic stop; includes the rejection case required by the demo (scope §8.4) |
| [Sequence 3: sign-in](seq-sign-in.svg) ([source](seq-sign-in.puml)) | OAuth 2.0 authorization code + PKCE, then a protected API call |

## Main design choices

Each choice has a short decision record in [`../decisions/`](../decisions/).

1. **The MQTT contract is the single interface between devices and cloud** ([`../mqtt-contract.md`](../mqtt-contract.md)). The simulator and the edge gateway are interchangeable, and a unit test checks that their messages have the same fields.
2. **Validation happens three times: device, Node-RED, API.** Node-RED rejects malformed messages early, and the API re-checks before storing (defence in depth). An invalid message is never stored as data. It raises a device incident instead.
3. **Readings are stored in MongoDB with a deterministic id** (`device:sensor:epoch`). The duplicate rule of contract §7 then holds by construction ([ADR 0001](../decisions/0001-telemetry-store.md)).
4. **Live and late data are kept apart.** A reading sent from the Pi's queue after an outage is flagged `buffered`. It is stored and charted, but it never becomes the live value, and it never opens or clears an incident (scope §2.3).
5. **Incidents need a person to close them.** A cleared condition marks the incident inactive but keeps it open until someone resolves it with a note, so the resolution is recorded (FR-04). There is at most one unresolved incident per (device, type, sensor).
6. **Two independent pump safety barriers** ([ADR 0003](../decisions/0003-pump-command-path.md)). The API's deterministic `PumpSafetyPolicy`, then the Pi's `PumpGuard`, which also works without network. Every request is audited *before* it is sent, including rejected ones. Only the API publishes `pump/cmd`, and the command is never retained.
7. **Machine-to-machine ingestion uses a service key, not user tokens** ([ADR 0002](../decisions/0002-ingest-authentication.md)).
8. **The edge model is MobileNetV3-Small minimalistic, int8** ([ADR 0004](../decisions/0004-edge-model.md)). It is chosen because it survives quantization. A result is always flagged "review required" when the model is unsure or the picture is poor, and it is never presented as a diagnosis.

## Design patterns (scope §7.3)

| Pattern | Where | Why |
|---|---|---|
| **Command** | `PumpCommand` (API) and the `pump/cmd` message | each control request is an object with an id, an author, a role, a client, an expiry and two recorded decisions. It can be audited, expired, de-duplicated and answered (`pump/state` refers to its `command_id`). |
| **Strategy** | `Notifier` (`LogNotifier`, later Web Push), `CommandPublisher` (MQTT, fake in tests), edge `Sensor` drivers (`simulated`, `bme280`, `ads1115_ph`, ...), edge relay (`GpioRelay` / `FakeRelay`) | the behaviour is chosen by configuration without touching the logic that uses it. Swapping a simulated sensor for the real probe is a config change. |
| **Observer** | `IncidentService.onLiveReading / onDeviceStatus / onPumpStatus / onScreening`, called by the ingestion services; the PWAs poll incidents and notify | the ingestion does not know which rules exist. New incident rules subscribe to the same events. |
| **Repository** | `TelemetryStore`, `IncidentStore`, `PumpStore` interfaces with MongoDB implementations | the services are unit-tested against in-memory stores. Only the `Mongo*Store` classes know the database. |
| **Pure function for safety decisions** | `PumpSafetyPolicy.evaluate`, `PumpGuard.handle` | same facts give the same answer, which can be tested rule by rule. No AI and no I/O in a safety decision. |

## Still to design

- `iot/ai/service/`: the cited CLI knowledge base, local Ollama adapter and initial traces/regression cases now exist. PWA integration, real-model evaluation and the MCP server remain pending (tools must call the API with the user's token and preserve the same role/pump safety rules).
- FR-09 reports: water consumption, uptime and alert frequency, computed with MongoDB aggregations.
- Production deployment: TLS proxy, Mosquitto TLS + per-device logins + ACL (contract §9), Web Push notifications.
