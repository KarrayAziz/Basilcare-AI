# Repository structure and migration

The professor requested three application areas: `middleware/`, `frontends/` and `iot/`.
AI components are grouped under `iot/ai/`.

| Previous directory | Current directory |
|---|---|
| `api/` | `middleware/api/` |
| `iam/` | `middleware/iam/` |
| `pwa-farmer/` | `frontends/frontoffice/` |
| `pwa-admin/` | `frontends/backoffice/` |
| `nodered/` | `iot/node-red/` |
| `edge/` | `iot/edge/` |
| `simulator/` | `iot/simulator/` |
| `model/` | `iot/ai/model/` |
| `ai-service/` | `iot/ai/service/` |

`middleware/core/` is reserved for shared code. It is documented but has no Java
implementation or build module yet. The API and IAM still build independently.
Deployment, documentation and Postman files remain at the root alongside the README
and attribution declaration.

## Updating an existing checkout

1. Keep local configuration, camera data and trained models before switching branches.
   Git does not relocate ignored files in another teammate's checkout. Copy any such
   files from the previous paths to the corresponding current paths.
2. Recreate Python virtual environments at their new locations; executable paths in
   existing environments may still point to the previous directory.
3. Rebuild both WARs using the commands in [middleware](../middleware/README.md).
4. Recreate Compose services using `docker compose -f deploy/compose.yaml up -d` from
   the root. Use `bash deploy/deploy.sh --no-pull` for the normal build, deployment and
   health checks. A container restart alone cannot change its bind mounts. Existing
   named MongoDB and broker volumes are retained; do not delete them for this migration.
5. On a Raspberry Pi, install the updated `iot/edge/systemd/basilcare-edge.service`
   after recreating the edge environment and copying `config.toml`. Run
   `sudo systemctl daemon-reload` before restarting the gateway at a suitable time.

The URLs `/farmer/`, `/admin/`, `/api/` and `/iam/`, OAuth client IDs, MQTT topics,
database names and Compose service names remain unchanged. Existing installed PWAs
do not need a new identity solely because repository directories moved.

This reorganization was assisted by OpenAI Codex: file moves, reference updates,
documentation and execution of the existing tests. It adds no new application feature.
