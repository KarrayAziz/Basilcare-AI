# deploy

Everything needed to run BasilCare: the Docker Compose stack, the broker configuration, the secrets template, the server scripts and the end-to-end smoke test.

| File | Role |
|---|---|
| [`compose.yaml`](compose.yaml) | production stack: MongoDB, Mosquitto, Node-RED, the published WildFly image over HTTPS, optional simulator (`--profile demo`) |
| [`compose.dev.yaml`](compose.dev.yaml) | development override: mounts your local WARs and frontend folders into WildFly |
| [`wildfly/`](wildfly/README.md) | `Dockerfile` of the image, repeatable CLI configuration (PWAs + HTTPS) and hosting properties |
| [`wait_ready.sh`](wait_ready.sh) | waits until WildFly serves the API and the IAM keys (used by `start.sh` and CI) |
| [`mosquitto/mosquitto.conf`](mosquitto/mosquitto.conf) | development broker: anonymous on 1883, **persistence on**, so sessions and queued messages survive a restart |
| [`.env.example`](.env.example) | the secrets to set in `deploy/.env` (git-ignored): `INGEST_KEY`, `ADMIN_PASSWORD`, Node-RED keys |
| [`setup.sh`](setup.sh) | one-time preparation of an Ubuntu VM: Docker, `git clone`, random secrets, firewall |
| [`deploy.sh`](deploy.sh) | `git pull` → build and test both WARs (in a Maven container) → `docker compose up` → health check |
| [`smoke_test.py`](smoke_test.py) | end-to-end acceptance test of the demo path (scope §8.4), standard library only |
| [`hosting_smoke_test.py`](hosting_smoke_test.py) | static assets and PKCE redirects for both PWAs; requires only WildFly + MongoDB |

## Why it is organised this way

- **Secrets only in `deploy/.env`.** The compose file has development defaults after `:-`, and `setup.sh` generates random production values. `git grep -i password` finds only placeholders.
- **One image, built by CI or from Git.** `release.yml` tests and publishes the WildFly image (WARs + PWAs + configuration) for amd64 and arm64, so a laptop needs only Docker (`bash start.sh` at the repository root). A server can still build from its own checkout (`deploy.sh`, scope §6.1: clone once, then pull); no WAR is copied by hand.
- **HTTPS by default.** WildFly serves `https://basilcare.test` (`TLS_HOSTNAME`) with a self-signed certificate it creates on first start and keeps in a volume; plain HTTP 8080 is bound to 127.0.0.1 for health checks only.
- **Broker persistence.** Without it, a broker restart forgets Node-RED's persistent session, and the readings a Pi sends right after the restart (its offline backlog) are dropped. The edge outage test measured 8 lost readings without persistence and none with it.

## How to use it

### Demo / evaluation (any laptop with Docker)

```bash
bash start.sh            # from the repository root; see the root README
```

### Development (laptop)

```bash
(cd middleware/iam && mvn -q package) && (cd middleware/api && mvn -q package)
export MSYS_NO_PATHCONV=1                                  # Git Bash only
docker compose -f deploy/compose.yaml -f deploy/compose.dev.yaml --profile demo up -d --build
bash deploy/wait_ready.sh
mkdir -p deploy/certs && docker compose -f deploy/compose.yaml cp wildfly:/opt/jboss/wildfly/certs/basilcare.crt deploy/certs/
python deploy/hosting_smoke_test.py                       # HTTPS, assets and both login flows
python deploy/smoke_test.py                                # full demo path (simulator runs in the demo profile)
```

Both tests default to base domain `basilcare.test`, derive the four application names,
and trust `deploy/certs/basilcare.crt`. Add all names to your hosts file first; see the
[four-domain setup and migration](../docs/four-local-domains.md). For a custom base domain
or HTTPS port pass `--base https://your-domain.test:8443` to the hosting test or
`--api https://api.your-domain.test:8443` to the full smoke test.
If a local MongoDB already uses port 27017, set `MONGO_PORT=27018`.

Expected end of the smoke test:

```
[ok] pump command executed by the device and audited (state now on)
[ok] unsafe pump command rejected by the safety policy and audited (duration_too_long)
[ok] pump stopped

SMOKE TEST PASSED
```

After changing Java code, rebuild the WAR and run `docker compose -f deploy/compose.yaml restart wildfly`.

Open <https://www.basilcare.test/> and <https://admin.basilcare.test/>. With the dev override,
WildFly serves the frontend folders through read-only mounts. CLI configuration is reapplied on every start,
including a new container; no manual server edits are required. Authentication returns to
the app's own origin. Frontend file edits are available immediately; refresh/update the service
worker when testing an already installed app.

### Server

```bash
bash setup.sh https://github.com/KarrayAziz/Basilcare-AI.git   # once
bash deploy/deploy.sh                                          # every update
```

WildFly serves HTTPS on port 443. Set `PUBLIC_ORIGIN=https://your-domain.example` (no trailing
slash) and `TLS_HOSTNAME=your-domain.example`, `FARMER_ORIGIN=https://www.your-domain.example`
and `ADMIN_ORIGIN=https://admin.your-domain.example` in `deploy/.env` before recreating the WildFly
container. The generated certificate is self-signed; for a public server, place a CA-issued
PKCS12 keystore at `/opt/jboss/wildfly/certs/basilcare.p12` in the `wildfly-certs` volume (it is
never overwritten), or put a TLS proxy in front as described in the
[hosting deployment notes](wildfly/README.md).

Ports 1880 (Node-RED editor) and 1883 (MQTT without TLS) are for development only. Before exposing the server, configure Mosquitto TLS with per-device logins and the ACL of contract §9, and set `NODE_RED_ADMIN_HASH`.
