#!/usr/bin/env bash
# Stop BasilCare.  bash stop.sh          keeps the data (database, broker, certificate)
#                  bash stop.sh --reset  also deletes all data volumes
set -euo pipefail
cd "$(dirname "$0")"
case "${1:-}" in
    "") docker compose -f deploy/compose.yaml --profile demo down ;;
    --reset) docker compose -f deploy/compose.yaml --profile demo down --volumes ;;
    *) echo "usage: bash stop.sh [--reset]"; exit 2 ;;
esac
