#!/usr/bin/env bash
# Update and (re)start the stack from the repository (scope §6.1: "subsequent git pull").
#
#   bash deploy/deploy.sh            # pull, build, start, check health
#   bash deploy/deploy.sh --no-pull  # build and restart the current checkout
#   bash deploy/deploy.sh --smoke    # also run deploy/smoke_test.py (needs a running simulator)
#
# The WARs are built with Maven inside a container (no Java on the server), with the same
# JDK 25 as CI. Runs from any directory.
set -euo pipefail
cd "$(dirname "$0")/.."

PULL=1
SMOKE=0
for arg in "$@"; do
    case "$arg" in
        --no-pull) PULL=0 ;;
        --smoke) SMOKE=1 ;;
        *) echo "unknown option $arg"; exit 2 ;;
    esac
done

if [ ! -f deploy/.env ]; then
    echo "deploy/.env is missing: cp deploy/.env.example deploy/.env and set the secrets (or run setup.sh)"
    exit 1
fi

if [ "$PULL" = 1 ]; then
    echo "== git pull"
    git pull --ff-only
fi
echo "== deploying $(git rev-parse --short HEAD): $(git log -1 --pretty=%s)"

echo "== build iam.war and api.war (tests included)"
if command -v mvn >/dev/null 2>&1 && mvn -v 2>/dev/null | grep -q "Java version: 25"; then
    # Two separate statements on purpose: under "set -e" a failure inside an "a && b" list does
    # NOT stop the script, so a broken IAM build used to deploy the old iam.war (review finding #7).
    (cd middleware/iam && mvn -B -q verify) || { echo "IAM build failed: nothing deployed"; exit 1; }
    (cd middleware/api && mvn -B -q verify) || { echo "API build failed: nothing deployed"; exit 1; }
else
    docker run --rm -v "$PWD":/src -v basilcare-m2:/root/.m2 -w /src maven:3.9-eclipse-temurin-25 \
        bash -c "cd middleware/iam && mvn -B -q verify && cd ../api && mvn -B -q verify" \
        || { echo "build failed: nothing deployed"; exit 1; }
fi

echo "== build the WildFly image (WARs, PWAs and HTTPS configuration)"
docker compose -f deploy/compose.yaml build wildfly

echo "== start the stack"
docker compose -f deploy/compose.yaml up -d --no-build --remove-orphans   # recreates WildFly if its image changed

echo "== wait for the API"
for _ in $(seq 1 60); do
    if curl -fsS http://localhost:8080/api/health >/dev/null 2>&1; then
        curl -fsS http://localhost:8080/api/health; echo
        break
    fi
    sleep 3
done
curl -fsS http://localhost:8080/api/health >/dev/null || { echo "API not healthy"; docker compose -f deploy/compose.yaml logs --tail 80 wildfly; exit 1; }

# The release is incomplete if Java is up but either frontend or the IAM is unavailable.
for _ in $(seq 1 30); do
    if curl -fsS http://localhost:8080/iam/jwk >/dev/null 2>&1; then break; fi
    sleep 2
done
python3 deploy/hosting_smoke_test.py --base http://localhost:8080 --static-only
mkdir -p deploy/certs
docker compose -f deploy/compose.yaml cp wildfly:/opt/jboss/wildfly/certs/basilcare.crt deploy/certs/basilcare.crt

if [ "$SMOKE" = 1 ]; then
    set -a; . deploy/.env; set +a
    python3 deploy/smoke_test.py --password "$ADMIN_PASSWORD" \
        --api "${PUBLIC_ORIGIN:-https://basilcare.test}" \
        --redirect-uri "${ADMIN_ORIGIN:-https://admin.basilcare.test}/"
fi
echo "== deployed"
