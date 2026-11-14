# deploy

Everything needed to run BasilCare: the Docker Compose stack, the broker configuration, the secrets template, the server scripts and the end-to-end smoke test.

| File | Role |
|---|---|
| [`compose.yaml`](compose.yaml) | MongoDB, Mosquitto, Node-RED, WildFly (with `iam.war` and `api.war`) |
| [`mosquitto/mosquitto.conf`](mosquitto/mosquitto.conf) | development broker: anonymous on 1883, **persistence on**, so sessions and queued messages survive a restart |
| [`.env.example`](.env.example) | the secrets to set in `deploy/.env` (git-ignored): `INGEST_KEY`, `ADMIN_PASSWORD`, Node-RED keys |
| [`setup.sh`](setup.sh) | one-time preparation of an Ubuntu VM: Docker, `git clone`, random secrets, firewall |
| [`deploy.sh`](deploy.sh) | `git pull` → build and test both WARs (in a Maven container) → `docker compose up` → health check |
| [`smoke_test.py`](smoke_test.py) | end-to-end acceptance test of the demo path (scope §8.4), standard library only |

## Why it is organised this way

- **Secrets only in `deploy/.env`.** The compose file has development defaults after `:-`, and `setup.sh` generates random production values. `git grep -i password` finds only placeholders.
- **Builds happen on the server, from Git.** The professor's rule (scope §6.1) is clone once, then pull. No WAR is copied by hand, and the tests run during every deployment.
- **Broker persistence.** Without it, a broker restart forgets Node-RED's persistent session, and the readings a Pi sends right after the restart (its offline backlog) are dropped. The edge outage test measured 8 lost readings without persistence and none with it.

## How to use it

### Development (laptop)

```bash
(cd iam && mvn -q package) && (cd api && mvn -q package)
export MSYS_NO_PATHCONV=1                                  # Git Bash only
docker compose -f deploy/compose.yaml up -d
curl localhost:8080/api/health
python simulator/simulator.py --fault ph-drift             # in its venv, see simulator/README.md
python deploy/smoke_test.py                                # signs in as admin / change-me-now
```

Expected end of the smoke test:

```
[ok] pump command executed by the device and audited (state now on)
[ok] unsafe pump command rejected by the safety policy and audited (duration_too_long)
[ok] pump stopped

SMOKE TEST PASSED
```

After changing Java code, rebuild the WAR and run `docker compose -f deploy/compose.yaml restart wildfly`.

### Server

```bash
bash setup.sh https://github.com/KarrayAziz/Basilcare-AI.git   # once
bash deploy/deploy.sh                                          # every update
```

Ports 1880 (Node-RED editor), 1883 (MQTT without TLS) and 8080 (WildFly) are for development only. Before exposing the server, put a TLS reverse proxy in front of WildFly, configure Mosquitto TLS with per-device logins and the ACL of contract §9, and set `NODE_RED_ADMIN_HASH`.
