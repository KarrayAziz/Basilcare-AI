#!/usr/bin/env bash
# Wait until WildFly serves the API and the IAM keys.
#   bash deploy/wait_ready.sh [base URL, default https://localhost] [attempts, 3 s apart, default 60]
# -k: readiness only; certificate checks are done by the smoke tests (--cafile).
set -euo pipefail
BASE="${1:-https://localhost}"
TRIES="${2:-60}"
for _ in $(seq 1 "$TRIES"); do
    if curl -kfsS "$BASE/api/health" >/dev/null 2>&1 && curl -kfsS "$BASE/iam/jwk" >/dev/null 2>&1; then
        echo "WildFly ready at $BASE"
        exit 0
    fi
    sleep 3
done
echo "WildFly did not become ready at $BASE" >&2
exit 1
