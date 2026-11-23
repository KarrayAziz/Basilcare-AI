#!/usr/bin/env bash
set -euo pipefail

HOSTING_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
HOSTING_PROPERTIES="${BASILCARE_HOSTING_PROPERTIES:-$HOSTING_DIR/pwas-dev.properties}"
if [ ! -r "$HOSTING_PROPERTIES" ]; then
    echo "Missing WildFly hosting properties: $HOSTING_PROPERTIES" >&2
    exit 1
fi

# HTTPS: a self-signed certificate for TLS_HOSTNAME (plus localhost), created on first start
# in the certs volume and reused afterwards, so browsers only have to trust it once.
# A keystore supplied by an operator (no .generated-for marker) is never overwritten.
CERT_DIR="$JBOSS_HOME/certs"
KEYSTORE="$CERT_DIR/basilcare.p12"
MARKER="$CERT_DIR/.generated-for"
TLS_HOSTNAME="${TLS_HOSTNAME:-basilcare.test}"
CERT_NAMES="$TLS_HOSTNAME|four-domains-v1"
export TLS_KEYSTORE_PASSWORD="${TLS_KEYSTORE_PASSWORD:-changeit}"
regenerate=0
if [ ! -f "$KEYSTORE" ]; then
    regenerate=1
elif ! keytool -list -keystore "$KEYSTORE" -storepass "$TLS_KEYSTORE_PASSWORD" >/dev/null 2>&1; then
    if [ ! -f "$MARKER" ]; then
        echo "TLS keystore $KEYSTORE does not open with TLS_KEYSTORE_PASSWORD" >&2
        exit 1
    fi
    echo "TLS_KEYSTORE_PASSWORD changed: replacing the self-signed certificate (trust the new one again)"
    regenerate=1
elif [ -f "$MARKER" ] && [ "$(cat "$MARKER")" != "$CERT_NAMES" ]; then
    regenerate=1
fi
if [ "$regenerate" = 1 ]; then
    echo "Generating a self-signed TLS certificate for $TLS_HOSTNAME"
    rm -f "$KEYSTORE" "$CERT_DIR/basilcare.crt"
    keytool -genkeypair -noprompt -alias basilcare -keyalg RSA -keysize 2048 -validity 397 \
        -storetype PKCS12 -keystore "$KEYSTORE" -storepass "$TLS_KEYSTORE_PASSWORD" \
        -dname "CN=$TLS_HOSTNAME, O=BasilCare" \
        -ext "SAN=dns:$TLS_HOSTNAME,dns:www.$TLS_HOSTNAME,dns:admin.$TLS_HOSTNAME,dns:api.$TLS_HOSTNAME,dns:iam.$TLS_HOSTNAME,dns:localhost,ip:127.0.0.1" -ext "EKU=serverAuth"
    keytool -exportcert -rfc -alias basilcare -keystore "$KEYSTORE" \
        -storepass "$TLS_KEYSTORE_PASSWORD" -file "$CERT_DIR/basilcare.crt"
    echo "$CERT_NAMES" > "$MARKER"
fi

# Embedded administration configures the on-disk server before it starts listening.
# No public management port or administrator password is needed for provisioning.
"$JBOSS_HOME/bin/jboss-cli.sh" --file="$HOSTING_DIR/configure.cli" --properties="$HOSTING_PROPERTIES"
exec "$JBOSS_HOME/bin/standalone.sh" -b 0.0.0.0 "$@"
