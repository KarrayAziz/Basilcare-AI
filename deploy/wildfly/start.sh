#!/usr/bin/env bash
set -euo pipefail

HOSTING_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
HOSTING_PROPERTIES="${BASILCARE_HOSTING_PROPERTIES:-$HOSTING_DIR/pwas-dev.properties}"
if [ ! -r "$HOSTING_PROPERTIES" ]; then
    echo "Missing WildFly hosting properties: $HOSTING_PROPERTIES" >&2
    exit 1
fi

# Embedded administration configures the on-disk server before it starts listening.
# No public management port or administrator password is needed for provisioning.
"$JBOSS_HOME/bin/jboss-cli.sh" --file="$HOSTING_DIR/configure.cli" --properties="$HOSTING_PROPERTIES"
exec "$JBOSS_HOME/bin/standalone.sh" -b 0.0.0.0 "$@"
