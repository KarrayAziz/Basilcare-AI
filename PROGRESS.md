# Progress report: branch `leith`

**Author:** Leith BEN MABROUK · **Date:** 4 November 2026 · **For review by:** Aziz, Amir

This branch completes **step 7** of the Phase 0 build guide (MQTT contract + simulator) and the **Node-RED** part of step 8. You can now test the whole device → broker → Node-RED path without the Raspberry Pi.

---

## 1. Phase 0 status

| Checklist item (build guide §9) | Status |
|---|---|
| `iam/`: OAuth 2.0 + PKCE, registration, JWT signing | ✅ done by Amir (2 Nov) |
| `api/`: `/health`, `/me`, JWT verification, CORS | ✅ done by Amir (2 Nov) |
| `deploy/compose.yaml`: MongoDB, Mosquitto, WildFly | ✅ done by Amir; **Node-RED added in this branch** |
| `pwa-farmer/`, `pwa-admin/`: shell, router, PKCE sign-in | ✅ done by Amir (see §5 for two small issues) |
| `docs/mqtt-contract.md` | ✅ **this branch** |
| `simulator.py`: messages visible with `mosquitto_sub` | ✅ **this branch** |
| `nodered/flows.json` | ✅ **this branch** (does more than the guide's "MQTT in → debug", see §2.3) |
| No secret in Git (`git grep -i password`) | ✅ only placeholders |
| `postman/` collection | ⬜ to do (needs the full stack, so JDK 25 + Maven) |
| `deploy/`: `.env.example`, `setup.sh`, `deploy.sh`, WildFly pinned to 42 | ⬜ to do |
| `edge/`, `ai-service/`, `model/` skeletons; every folder README filled | ⬜ to do (done for `docs/`, `simulator/`, `nodered/`) |
| User stories in GitHub Issues | ⬜ to do |
| Design statement PDF (use case, class, deployment, 3 sequence diagrams) | ⬜ to do |

---

## 2. What this branch adds

### 2.1 MQTT contract: [`docs/mqtt-contract.md`](docs/mqtt-contract.md)

The agreement every component follows: edge, simulator, Node-RED, API and MCP tools.

- **Topics** `basilcare/v1/{device_id}/…`: `telemetry/{sensor}`, `status` (retained, with a Last Will), `pump/cmd`, `pump/state` (retained), `screening`.
- **Messages:** the JSON fields of each message, with units, timestamps carrying a UTC offset (scope §4.2), `calibrated`, a `seq` counter to detect lost readings, and `buffered` to keep late readings apart from live ones (scope §2.3).
- **Pump safety:**
  - a command is never retained, carries an id and an expiry time, and is addressed to one device;
  - the device checks it again before obeying (expired, too long, low water, pump fault, …), so neither the cloud nor the AI assistant can bypass it (scope §4.2, §5.3);
  - the pump always stops by itself after its duration.
- **Plausible ranges vs. alert thresholds:** the contract only says which values are physically possible. Basil alert thresholds stay in the API's configuration, to be checked against agronomic sources (scope §1.4).
- **Rules for consumers** (duplicates, stale detection, ordering), **versioning**, **security** for Internet exposure (TLS, one login per device, access control), and **open questions** (§10).

### 2.2 Simulator: [`simulator/`](simulator/)

A Python program that behaves like the Pi on MQTT, so backend work does not wait for the hardware (scope risk register: "hardware procurement delays").

- It publishes all the message types of the contract and **obeys pump commands** with the same safety rules as the real device.
- **Faults on demand** to test incident handling (FR-03): `ph-drift`, `low-water`, `stale`, `pump-failure`, `outage` (late, buffered readings), `crash` (triggers the Last Will).
- Usage, options and examples: [`simulator/README.md`](simulator/README.md).

### 2.3 Node-RED ingestion flow: [`nodered/`](nodered/), [`deploy/compose.yaml`](deploy/compose.yaml)

- New `nodered` service (`nodered/node-red:4.0.9`, editor at http://localhost:1880).
- Flow **"BasilCare ingestion"**: subscribes to `basilcare/v1/+/#`, then:
  - **checks every message against the contract**: topic, JSON, `device_id`, unit, plausible range, timestamp offset;
  - **routes** valid messages by type (telemetry, status, pump state, pump commands, screening);
  - sends invalid messages, with their reasons, to a separate output that is also written to the log.
- The debug outputs at the end are placeholders, to be replaced by calls to the Jakarta EE API.
- **No reading is lost while Node-RED restarts.** It uses a persistent MQTT session, so the broker keeps the messages until Node-RED is back.
- `nodered/` *is* Node-RED's data folder: pressing **Deploy** in the editor writes `flows.json` in the repository, so flow changes are reviewed and committed like code.
- Secrets (`NODE_RED_ADMIN_HASH` for the editor login, `NODE_RED_CREDENTIAL_SECRET`) come from environment variables, never from the repository.

---

## 3. Try it (5 minutes)

From the repository root (Docker Desktop running, Python 3.11+):

```bash
docker compose -f deploy/compose.yaml up -d mosquitto nodered
python -m venv simulator/.venv
simulator/.venv/Scripts/pip install -r simulator/requirements.txt       # Linux/macOS: simulator/.venv/bin/pip
simulator/.venv/Scripts/python simulator/simulator.py --fault ph-drift --interval 2
```

Open http://localhost:1880, then the debug sidebar (bug icon): the readings arrive and the pH rises. Ctrl+C stops the simulator. Other faults, pump commands and invalid messages: see the [simulator](simulator/README.md) and [Node-RED](nodered/README.md) READMEs.

---

## 4. Tests

| Test | Result |
|---|---|
| Simulator unit tests (`python -m unittest` in `simulator/`) | 21/21 |
| Node-RED unit tests of the checking code (`node --test "nodered/test/*.test.js"`) | 9/9 |
| Live end-to-end, 7 simulated devices (one per fault) + pump commands + broken messages, observed through Node-RED | 34/34 checks |
| No reading lost while Node-RED is restarted | 18/18 delivered |

Two bugs were found and fixed while testing:

1. **The contract was inconsistent:** pump commands had no `device_id`, although every other message has one. Commands now carry it, and a device rejects a command addressed to another device.
2. **The persistent session lost data:** Node-RED's default "unsubscribe on disconnect" cancelled the persistent session on every restart (0/18 readings delivered). Turning it off fixed it (18/18).

---

## 5. Points for the team

**Decisions needed** (contract §10):

- telemetry interval of the real Pi (5 s in the simulator);
- pump limits: maximum run 900 s, minimum water level 20 % (placeholders);
- EC unit (mS/cm or µS/cm), depending on the probe we buy;
- how `water_level` is calibrated to "% of full";
- screening classes and confidence threshold, after the dataset audit.

**Noticed while reading the repository** (not changed in this branch):

- **Swapped PWA names:**
  - `pwa-farmer/manifest.webmanifest` says "BasilCare Admin" and its service worker cache is `basilcare-admin-v1`;
  - `pwa-admin` has the farmer names;
  - the `clientId`s in `auth.js` are correct;
  - an installed app would show the wrong name.
- The `pwa-admin` pages are still a copy of the farmer pages.
- The build guide says it "lives outside the repository on purpose" because it mentions SmartHydro, but it is committed at the root. Should it stay?
- The scope statement says Java 21; the code targets Java 25 (`maven.compiler.release`). Both work on WildFly, but the design statement should match the code.

---

## 6. Next steps

1. **Phase 0 remainder:** Postman collection, deploy scripts, folder skeletons and READMEs, user stories, design statement PDF, PWA name fix.
2. **Telemetry storage:** Node-RED → API → database. The validation, duplicate and stale rules are already in contract §7. We need to choose the time-series store.
3. **Incidents and alerts** (FR-03, FR-04): the simulator faults already produce every case.
4. **Pump-control endpoint in the API:** role check, confirmation, safety policy, audit log, then `pump/cmd`. The simulator already answers it.
