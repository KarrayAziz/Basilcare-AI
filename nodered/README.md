# nodered

The Node-RED flows between the MQTT broker and the rest of BasilCare. Today there is one flow, **BasilCare ingestion**. It receives every message from every device, checks it against the [MQTT contract](../docs/mqtt-contract.md), and routes it by type:

```
Mosquitto ──► All BasilCare devices ──► Check against MQTT contract ──► Route by message type ──► telemetry
              basilcare/v1/+/#           (valid / invalid)                (msg.kind)              device status
              QoS 1                            │                                                  pump state
                                               └──► invalid messages (also written to the log)   pump commands
                                                                                                  screening
```

| Output | Contains |
|---|---|
| valid | `msg.kind` (`telemetry`, `status`, `pump_state`, `pump_cmd`, `screening`), `msg.device_id`, `msg.payload` (the parsed JSON object), `msg.received_at` |
| invalid | `msg.errors` (what is wrong, e.g. `value outside the plausible range 0 to 14`), `msg.payload` (the raw text) |

The debug nodes at the end are placeholders. The next steps replace them with calls to the Jakarta EE API (store readings, raise incidents) and turn invalid messages into device incidents.

## Why it is organised this way

- **This folder is Node-RED's `/data` folder** (mounted in `deploy/compose.yaml`). Pressing *Deploy* in the editor writes `flows.json` here, so a flow change shows up in `git diff` like any other code. Node-RED's runtime files (`.config.*`, `node_modules/`, `lib/`, `flows_cred.json`, …) are ignored by [`.gitignore`](.gitignore).
- **[`settings.js`](settings.js)** contains only what differs from the defaults. `flows.json` is saved indented, so its diffs are readable. Secrets come from environment variables, never from the repository.
- **Broker address from environment variables.** The broker node uses `${MQTT_HOST}` and `${MQTT_PORT}`, so the same flow works on a laptop and on the server.
- **No reading is lost while Node-RED restarts.** The broker connection uses a fixed client id (`basilcare-nodered`), a persistent session (`cleansession: false`) and no unsubscribe on disconnect. While Node-RED is down, Mosquitto keeps the QoS 1 messages and delivers them when it comes back (tested: 18/18 readings). Consequences:
  - Run only one Node-RED per broker with this client id.
  - Messages arrive late but keep their `measured_at`, so always sort by `measured_at`.
  - The development broker keeps queued messages in memory, up to Mosquitto's default of 1000.
- **The checking code is tested.** [`test/check-contract.test.js`](test/check-contract.test.js) runs the function node's code, read straight from `flows.json`, against valid and broken messages.

## How to use it

### Start

```bash
export MSYS_NO_PATHCONV=1                                          # Git Bash only
docker compose -f deploy/compose.yaml up -d mosquitto nodered      # from the repository root
```

Open the editor at <http://localhost:1880> and open the debug sidebar (the bug icon, top right). Then start the [simulator](../simulator/README.md), with its virtual environment active:

```bash
python simulator/simulator.py --fault ph-drift
```

Readings appear in the sidebar, and each debug node shows a message counter. To see the *invalid* output, send a broken message:

```bash
docker exec basilcare-mosquitto-1 mosquitto_pub -t basilcare/v1/basil-sim-01/telemetry/ph \
  -m '{"device_id":"basil-sim-01","sensor":"ph","value":15.2,"unit":"pH","measured_at":"2026-11-04T10:00:00+01:00","calibrated":true,"seq":1,"buffered":false}'
docker compose -f deploy/compose.yaml logs nodered        # the invalid message is also in the log
```

### Change a flow

1. Edit in the editor, then press **Deploy**. `nodered/flows.json` is updated.
2. Run the tests and review the change: `git diff nodered/flows.json`.
3. Commit `flows.json` with a message that says what changed in the flow.

A changed `settings.js` takes effect after `docker compose -f deploy/compose.yaml restart nodered`.

### Tests

```bash
node --test "nodered/test/*.test.js"       # from the repository root; Node.js 22+, nothing to install
```

### Before exposing it on the Internet

| Variable | Why |
|---|---|
| `NODE_RED_ADMIN_HASH` | Turns on the editor login (user `admin`). Without it, anyone reaching port 1880 can change the flows and run code on the server. Make the hash with `docker compose -f deploy/compose.yaml exec nodered node-red admin hash-pw`. |
| `NODE_RED_CREDENTIAL_SECRET` | Key that encrypts `flows_cred.json` (broker or API passwords). Without it, Node-RED generates a key and warns at startup; that is fine in development. |

The broker side (TLS, one login per client, access control) is in contract §9. On a Linux server, the container runs as user id 1000, so this folder must be writable by that user (`sudo chown -R 1000:1000 nodered`).
