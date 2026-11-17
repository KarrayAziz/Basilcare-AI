# BasilCare AI

An intelligent Cloud of Things platform for a small hydroponic sweet-basil farm. Cloud of Things project, SUP'COM 2026-2027: Leith Ben Mabrouk, Aziz Karray, Amir Triki. The scope is in [`docs/BasilCare_Scope_Statement.pdf`](docs/BasilCare_Scope_Statement.pdf).

```
Raspberry Pi 4 (edge/)                        Cloud (deploy/compose.yaml)                         Phones
sensors ─► gateway ─► SQLite queue ─► MQTT ─► Mosquitto ─► Node-RED ─► Jakarta EE API ─► MongoDB
camera ─► quality + TFLite model ─┘            (persistence)  (contract   (WildFly 42)        ▲
pump relay ◄─ local safety rules ◄─ pump/cmd ◄──────────────── checks)    │  ▲ IAM (OAuth+PKCE)
                                                                          └──┴── Farmer PWA, Admin PWA
```

## Repository

| Folder | What | Status |
|---|---|---|
| [`docs/`](docs/README.md) | scope, [MQTT contract](docs/mqtt-contract.md), [design statement draft and UML](docs/design/README.md), [decisions](docs/decisions/), [user stories](docs/user-stories.md) | ✅ |
| [`iam/`](iam/README.md) | identity service: registration, OAuth 2.0 authorization code + PKCE, Ed25519 JWTs | ✅ |
| [`api/`](api/README.md) | REST API: devices, telemetry, incidents, alert ranges, safe pump control, ingestion | ✅ 41 tests |
| [`nodered/`](nodered/README.md) | ingestion flow: checks every message against the contract, forwards it to the API, retries | ✅ 17 tests |
| [`simulator/`](simulator/README.md) | simulated Pi with fault injection | ✅ 21 tests |
| [`edge/`](edge/README.md) | Raspberry Pi gateway: sensors (simulated or real), offline queue, local pump safety, leaf screening | ✅ 37 tests; real probes not yet tested |
| [`model/`](model/README.md) | leaf-screening model: dataset split, training, int8 export, evaluation | ✅ pipeline; no real dataset yet |
| [`pwa-farmer/`](pwa-farmer/README.md), [`pwa-admin/`](pwa-admin/README.md) | installable PWAs: live dashboard, alerts, pump, screening / registry, alert ranges, audit | 🟡 needs a browser check |
| [`deploy/`](deploy/README.md) | Compose stack, broker config, `.env.example`, `setup.sh`, `deploy.sh`, [end-to-end smoke test](deploy/smoke_test.py) | ✅ smoke test passes |
| [`postman/`](postman/README.md) | API collection (28 requests, OAuth 2.0 PKCE) | 🟡 not yet run in Postman |
| [`ai-service/`](ai-service/README.md) | RAG assistant, MCP tools, LLMOps | ⬜ next |

## Quick start (laptop, Docker Desktop, JDK 25, Maven, Python 3.11+)

```bash
(cd iam && mvn -q package) && (cd api && mvn -q package)
export MSYS_NO_PATHCONV=1                                   # Git Bash only
docker compose -f deploy/compose.yaml up -d                 # MongoDB, Mosquitto, Node-RED, WildFly
python -m venv simulator/.venv && simulator/.venv/Scripts/pip install -r simulator/requirements.txt
simulator/.venv/Scripts/python simulator/simulator.py --fault ph-drift &
python deploy/smoke_test.py                                 # end-to-end check, prints SMOKE TEST PASSED
```

WildFly serves both PWAs directly; no Live Server is required:

- Farmer: <http://localhost:8080/farmer/>
- Admin: <http://localhost:8080/admin/>
- Application chooser: <http://localhost:8080/>

Sign in as `admin` / `change-me-now` on a fresh development database (or use the password
configured in `deploy/.env`). See [WildFly hosting](deploy/wildfly/README.md) for the CLI
configuration, production settings and offline/login isolation.

## Tests

| What | Command |
|---|---|
| API | `cd api && mvn verify` |
| Edge gateway | `cd edge && python -m unittest discover -s tests -t .` |
| Simulator | `cd simulator && python -m unittest` |
| Node-RED and PWAs | `node --test "nodered/test/*.test.js" "pwa-farmer/test/*.test.mjs" "pwa-admin/test/*.test.js"` |
| Whole stack | `python deploy/smoke_test.py` |
| WildFly hosting and both PKCE redirects | `python deploy/hosting_smoke_test.py` |

CI runs the first four on every pull request (`.github/workflows/`).
