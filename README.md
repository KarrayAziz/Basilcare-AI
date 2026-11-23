# BasilCare AI

An intelligent Cloud of Things platform for a small hydroponic sweet-basil farm. Cloud of Things project, SUP'COM 2026-2027: Leith Ben Mabrouk, Aziz Karray, Amir Triki. The scope is in [`docs/BasilCare_Scope_Statement.pdf`](docs/BasilCare_Scope_Statement.pdf).

```
Raspberry Pi 4 (iot/edge/)                        Cloud (deploy/compose.yaml)                         Phones
sensors ─► gateway ─► SQLite queue ─► MQTT ─► Mosquitto ─► Node-RED ─► Jakarta EE API ─► MongoDB
camera ─► quality + TFLite model ─┘            (persistence)  (contract   (WildFly 42)        ▲
pump relay ◄─ local safety rules ◄─ pump/cmd ◄──────────────── checks)    │  ▲ IAM (OAuth+PKCE)
                                                                          └──┴── Farmer PWA, Admin PWA
```

## Repository

The application is organised into three areas:

```text
middleware/             server applications
  core/                 reserved for shared code (no implementation yet)
  api/                  REST API
  iam/                  accounts and login
frontends/
  frontoffice/          Farmer PWA, served at www.basilcare.test/
  backoffice/           Admin PWA, served at admin.basilcare.test/
iot/
  node-red/             MQTT ingestion flows
  edge/                 Raspberry Pi gateway
  simulator/            simulated gateway
  ai/
    model/              leaf-model training and evaluation
    service/            planned AI assistant
```

Deployment scripts, documentation and Postman collections remain in `deploy/`, `docs/`
and `postman/`. The team's `ATTRIBUTION.md` stays at the repository root.
Folder moves do not change HTTP addresses, MQTT topics or OAuth client IDs.
See the [migration notes](docs/repository-structure.md) when updating an existing checkout.

| Folder | What | Status |
|---|---|---|
| [`docs/`](docs/README.md) | scope, [MQTT contract](docs/mqtt-contract.md), [design statement draft and UML](docs/design/README.md), [decisions](docs/decisions/), [user stories](docs/user-stories.md) | ✅ |
| [`middleware/iam/`](middleware/iam/README.md) | identity service: registration, OAuth 2.0 authorization code + PKCE, Ed25519 JWTs | ✅ |
| [`middleware/api/`](middleware/api/README.md) | REST API: devices, telemetry, incidents, alert ranges, safe pump control, ingestion | ✅ 41 tests |
| [`iot/node-red/`](iot/node-red/README.md) | ingestion flow: checks every message against the contract, forwards it to the API, retries | ✅ 17 tests |
| [`iot/simulator/`](iot/simulator/README.md) | simulated Pi with fault injection | ✅ 21 tests |
| [`iot/edge/`](iot/edge/README.md) | Raspberry Pi gateway: sensors (simulated or real), offline queue, local pump safety, leaf screening | ✅ 37 tests; real probes not yet tested |
| [`iot/ai/model/`](iot/ai/model/README.md) | leaf-screening model: dataset split, training, int8 export, evaluation | ✅ pipeline; no real dataset yet |
| [`frontends/frontoffice/`](frontends/frontoffice/README.md), [`frontends/backoffice/`](frontends/backoffice/README.md) | installable PWAs: live dashboard, alerts, pump, screening / registry, alert ranges, audit | 🟡 needs a browser check |
| [`deploy/`](deploy/README.md) | Compose stack, broker config, `.env.example`, `setup.sh`, `deploy.sh`, [end-to-end smoke test](deploy/smoke_test.py) | ✅ smoke test passes |
| [`postman/`](postman/README.md) | API collection (28 requests, OAuth 2.0 PKCE) | 🟡 not yet run in Postman |
| [`iot/ai/service/`](iot/ai/service/README.md) | RAG assistant, MCP tools, LLMOps | ⬜ next |

## Quick start (macOS, Linux or Windows; only Docker Desktop needed)

```bash
git clone https://github.com/KarrayAziz/Basilcare-AI.git && cd Basilcare-AI
bash start.sh
```

`start.sh` downloads the tested images that CI publishes for Intel and Apple Silicon, creates
`deploy/.env` with random secrets, and starts MongoDB, Mosquitto, Node-RED, WildFly and a
virtual Raspberry Pi. On the first run it asks (each needs your password):

1. to add the four application names and the chooser name to the hosts file (`/etc/hosts` on Linux/macOS,
   `C:\Windows\System32\drivers\etc\hosts` on Windows), so the site has a real name;
2. to trust the self-signed HTTPS certificate WildFly generated (`deploy/certs/basilcare.crt`),
   so the browser shows no warning and the PWAs can be installed and used offline.

Then open:

- Farmer: <https://www.basilcare.test/>
- Admin: <https://admin.basilcare.test/>
- API: <https://api.basilcare.test/api/health>
- IAM: <https://iam.basilcare.test/iam/jwk>
- Application chooser: <https://basilcare.test/>

Sign in as `admin` with the password `start.sh` prints (`ADMIN_PASSWORD` in `deploy/.env`).
`bash stop.sh` stops everything; `bash stop.sh --reset` also deletes the data.

### Developing (JDK 25, Maven, Python 3.11+)

```bash
(cd middleware/iam && mvn -q package) && (cd middleware/api && mvn -q package)
export MSYS_NO_PATHCONV=1                                   # Git Bash only
docker compose -f deploy/compose.yaml -f deploy/compose.dev.yaml up -d --build   # local WARs and frontends, live
python deploy/smoke_test.py --password change-me-now        # end-to-end check, prints SMOKE TEST PASSED
```

The dev override mounts your locally built WARs and the frontend folders, so frontend edits
are live and a Java change needs only `docker compose -f deploy/compose.yaml restart wildfly`.
See [four local domains and migration](docs/four-local-domains.md) and [WildFly hosting](deploy/wildfly/README.md) for the CLI configuration, HTTPS and
offline/login isolation.

## Tests

| What | Command |
|---|---|
| API | `cd middleware/api && mvn verify` |
| Edge gateway | `cd iot/edge && python -m unittest discover -s tests -t .` |
| Simulator | `cd iot/simulator && python -m unittest` |
| Node-RED and PWAs | `node --test "iot/node-red/test/*.test.js" "frontends/frontoffice/test/*.mjs" "frontends/backoffice/test/*.js"` |
| Whole stack | `python deploy/smoke_test.py` |
| WildFly hosting and both PKCE redirects | `python deploy/hosting_smoke_test.py` |
| Model dataset audit, provenance and quality checks | `python -m unittest discover -s iot/ai/model/tests -v` (install `iot/ai/model/requirements-mlops.txt`) |

See the [MLOps run guide](iot/ai/model/MLOPS.md) for dataset checks and an explicit training
pipeline around the existing YOLO scripts. Model CI uses artificial fixtures; it does not
train a detector or replace the model on the Pi.

CI runs the first four on every pull request (`.github/workflows/`). The hosting CI builds the
production image and checks HTTPS, the PWAs and sign-in. On every push to `main`,
[`release.yml`](.github/workflows/release.yml) tests everything, publishes the WildFly image to
GitHub Container Registry (`ghcr.io/karrayaziz/basilcare-wildfly`, `latest` and `sha-<commit>`),
then starts the published image and checks it again. A `v*` tag also creates a GitHub Release.
