#!/usr/bin/env bash
# Start the whole BasilCare platform on this computer (macOS, Linux or Windows Git Bash).
# Only Docker Desktop is required: Java, Maven, Node and Python are NOT needed.
#
#   bash start.sh                  # download the published images and start everything
#   bash start.sh --build          # build the WildFly image from this checkout instead
#   bash start.sh --no-simulator   # without the virtual Raspberry Pi
#   bash stop.sh                   # stop (bash stop.sh --reset also deletes the data)
#
# The first run creates deploy/.env with random secrets, asks to add the site's name to the
# hosts file, and offers to trust the self-signed HTTPS certificate (each step needs your password).
set -euo pipefail
cd "$(dirname "$0")"

BUILD=0
SIMULATOR=1
for arg in "$@"; do
    case "$arg" in
        --build) BUILD=1 ;;
        --no-simulator) SIMULATOR=0 ;;
        -h|--help) sed -n '2,11p' "$0"; exit 0 ;;
        *) echo "unknown option $arg (see: bash start.sh --help)"; exit 2 ;;
    esac
done

say() { printf '\n== %s\n' "$*"; }
ask() {   # yes/no question; "no" when there is no terminal (scripts, CI)
    local answer
    (exec </dev/tty) 2>/dev/null || return 1
    read -r -p "$1 [y/N] " answer </dev/tty || return 1
    [ "$answer" = y ] || [ "$answer" = Y ]
}
random() { LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 32; }
env_value() { sed -n "s/^$1=//p" deploy/.env | tail -n 1; }

case "$(uname -s)" in
    Darwin) OS=mac ;;
    MINGW*|MSYS*|CYGWIN*) OS=windows; export MSYS_NO_PATHCONV=1 ;;
    *) OS=linux ;;
esac

say "Docker"
if ! docker info >/dev/null 2>&1; then
    echo "Docker is not running. Install/start Docker Desktop (https://www.docker.com/products/docker-desktop/) and retry."
    exit 1
fi
docker compose version

say "Configuration (deploy/.env)"
if [ ! -f deploy/.env ]; then
    sed -e "s|^INGEST_KEY=.*|INGEST_KEY=$(random)|" \
        -e "s|^ADMIN_PASSWORD=.*|ADMIN_PASSWORD=$(random)|" \
        -e "s|^NODE_RED_CREDENTIAL_SECRET=.*|NODE_RED_CREDENTIAL_SECRET=$(random)|" \
        -e "s|^TLS_KEYSTORE_PASSWORD=.*|TLS_KEYSTORE_PASSWORD=$(random)|" \
        deploy/.env.example > deploy/.env
    chmod 600 deploy/.env
    echo "created deploy/.env with random secrets"
else
    echo "using the existing deploy/.env"
fi
HOST="$(env_value TLS_HOSTNAME)"; HOST="${HOST:-basilcare.test}"
PORT="$(env_value HTTPS_PORT)"; PORT="${PORT:-443}"
ORIGIN="https://$HOST"; [ "$PORT" = 443 ] || ORIGIN="$ORIGIN:$PORT"
PORT_SUFFIX=""; [ "$PORT" = 443 ] || PORT_SUFFIX=":$PORT"
for pair in "FARMER_ORIGIN:www" "ADMIN_ORIGIN:admin"; do
    key="${pair%%:*}"; prefix="${pair#*:}"
    expected="https://$prefix.$HOST$PORT_SUFFIX"
    if ! grep -q "^$key=" deploy/.env; then
        printf '\n%s=%s\n' "$key" "$expected" >> deploy/.env
    elif [ "$(env_value "$key")" != "$expected" ]; then
        echo "Set $key=$expected in deploy/.env before starting (login must match the hostname)." >&2
        exit 1
    fi
done
if [ "$(env_value PUBLIC_ORIGIN)" != "$ORIGIN" ]; then
    echo "WARNING: PUBLIC_ORIGIN in deploy/.env is '$(env_value PUBLIC_ORIGIN)', expected '$ORIGIN'."
    echo "         PUBLIC_ORIGIN is the legacy chooser address; frontend redirects use FARMER_ORIGIN and ADMIN_ORIGIN."
fi

say "Hosts file (application names -> 127.0.0.1)"
if [ "$OS" = windows ]; then HOSTS_FILE=/c/Windows/System32/drivers/etc/hosts; else HOSTS_FILE=/etc/hosts; fi
MISSING=""
for name in "$HOST" "www.$HOST" "admin.$HOST" "api.$HOST" "iam.$HOST"; do
    if ! awk -v host="$name" '$1 == "127.0.0.1" {for (i=2;i<=NF;i++) if ($i == host) found=1} END {exit !found}' "$HOSTS_FILE"; then
        MISSING="$MISSING $name"
    fi
done
if [ -z "$MISSING" ]; then
    echo "all names already present in $HOSTS_FILE"
elif [ "$OS" = windows ]; then
    echo "Missing. Add this line to C:\\Windows\\System32\\drivers\\etc\\hosts (as administrator):"
    echo "    127.0.0.1$MISSING"
    if ask "Open an administrator prompt that adds it now?"; then
        powershell.exe -NoProfile -Command "Start-Process powershell -Verb RunAs -Wait -ArgumentList '-NoProfile -Command Add-Content -Path C:\Windows\System32\drivers\etc\hosts -Value ''127.0.0.1$MISSING'''"
    fi
else
    echo "Missing. It is needed so the browser can open $ORIGIN."
    if ask "Add '127.0.0.1$MISSING' to $HOSTS_FILE now (sudo)?"; then
        printf '127.0.0.1%s\n' "$MISSING" | sudo tee -a "$HOSTS_FILE" >/dev/null
        [ "$OS" = mac ] && sudo dscacheutil -flushcache && sudo killall -HUP mDNSResponder 2>/dev/null || true
    fi
fi

COMPOSE=(docker compose -f deploy/compose.yaml)
[ "$SIMULATOR" = 1 ] && COMPOSE+=(--profile demo)

if [ "$BUILD" = 1 ]; then
    say "Building the WildFly image from this checkout (a few minutes the first time)"
    "${COMPOSE[@]}" build wildfly
else
    say "Downloading the published images"
    "${COMPOSE[@]}" pull || true
    IMAGE="$("${COMPOSE[@]}" config --images | grep basilcare-wildfly | head -n 1)"
    if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
        echo "Could not download $IMAGE; building it from this checkout instead."
        "${COMPOSE[@]}" build wildfly
    fi
fi

say "Starting the stack"
"${COMPOSE[@]}" up -d --no-build --remove-orphans

say "Waiting for WildFly (first start takes about a minute)"
if ! bash deploy/wait_ready.sh "https://localhost:$PORT" 60; then
    echo "Last log lines:"
    "${COMPOSE[@]}" logs --tail 60 wildfly
    exit 1
fi
curl -kfsS "https://localhost:$PORT/api/health"; echo

say "HTTPS certificate"
mkdir -p deploy/certs
"${COMPOSE[@]}" cp wildfly:/opt/jboss/wildfly/certs/basilcare.crt deploy/certs/basilcare.crt >/dev/null
echo "self-signed certificate for $HOST saved to deploy/certs/basilcare.crt"
case "$OS" in
    mac)
        if security verify-cert -q -c deploy/certs/basilcare.crt -p ssl -s "$HOST" >/dev/null 2>&1; then
            echo "already trusted by macOS"
        elif ask "Trust it in the macOS keychain, so browsers show no warning and the PWAs can be installed (sudo)?"; then
            sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain deploy/certs/basilcare.crt
            echo "trusted; restart the browser if it was open"
        fi ;;
    windows)
        if ask "Trust it for your Windows user, so browsers show no warning (a confirmation dialog opens)?"; then
            certutil -user -addstore Root "$(cygpath -w deploy/certs/basilcare.crt 2>/dev/null || echo deploy\\certs\\basilcare.crt)" >/dev/null
            echo "trusted; restart the browser if it was open"
        fi ;;
    *)
        echo "To remove browser warnings, import deploy/certs/basilcare.crt as a trusted authority in your browser." ;;
esac
echo "(Without trusting it the site still works after accepting the browser warning, but the PWAs cannot be installed or used offline.)"

cat <<EOF

BasilCare is running.

  Farmer app         https://www.$HOST$PORT_SUFFIX/
  Administrator app  https://admin.$HOST$PORT_SUFFIX/
  Start page         $ORIGIN/
  API health         https://api.$HOST$PORT_SUFFIX/api/health
  IAM keys           https://iam.$HOST$PORT_SUFFIX/iam/jwk
  Node-RED editor    http://localhost:1880

  Administrator login:  admin / $(env_value ADMIN_PASSWORD)
  (set when the database is first created; after "bash stop.sh --reset" a new start uses it again)
EOF
if [ "$SIMULATOR" = 1 ]; then
    cat <<EOF
  Virtual Raspberry Pi "basil-sim-01" is publishing (pH drift fault). Register it once in the
  admin app (Devices) to see its readings and incidents, or run the full acceptance test:
    python3 deploy/smoke_test.py --api "https://api.$HOST$PORT_SUFFIX" --password "\$(sed -n 's/^ADMIN_PASSWORD=//p' deploy/.env)"
EOF
fi
echo
echo "Stop with: bash stop.sh"
