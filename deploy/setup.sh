#!/usr/bin/env bash
# One-time preparation of a fresh Ubuntu 24.04 cloud VM (scope §6.1: "initial git clone").
#
#   curl -fsSL <raw URL of this file> -o setup.sh && bash setup.sh <repository URL>
#
# Installs Docker Engine + Compose from Ubuntu's packages, clones the repository, creates
# deploy/.env with random secrets, and opens the firewall for SSH, HTTP(S) and MQTT over TLS.
# Java and Maven are NOT installed: deploy.sh builds the WARs inside a Maven container.
set -euo pipefail

REPO_URL="${1:?usage: setup.sh <git repository URL> [target directory]}"
TARGET="${2:-$HOME/Basilcare-AI}"

echo "== packages"
sudo apt-get update -y
sudo apt-get install -y docker.io docker-compose-v2 git openssl ufw python3 curl
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"   # takes effect at the next login

echo "== repository"
if [ ! -d "$TARGET/.git" ]; then
    git clone "$REPO_URL" "$TARGET"
fi
cd "$TARGET"

echo "== secrets (deploy/.env, never committed)"
if [ ! -f deploy/.env ]; then
    random() { openssl rand -base64 32 | tr -d '/+=' | cut -c1-40; }
    sed -e "s|^INGEST_KEY=.*|INGEST_KEY=$(random)|" \
        -e "s|^ADMIN_PASSWORD=.*|ADMIN_PASSWORD=$(random)|" \
        -e "s|^NODE_RED_CREDENTIAL_SECRET=.*|NODE_RED_CREDENTIAL_SECRET=$(random)|" \
        -e "s|^TLS_KEYSTORE_PASSWORD=.*|TLS_KEYSTORE_PASSWORD=$(random)|" \
        deploy/.env.example > deploy/.env
    chmod 600 deploy/.env
    echo "created deploy/.env; the IAM admin password is in it (ADMIN_PASSWORD)"
fi

echo "== firewall"
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 8883/tcp   # MQTT over TLS for the Raspberry Pi (contract §9)
sudo ufw --force enable

cat <<EOF

Done. Next:
  1. log out and in again (docker group), then:  cd $TARGET && bash deploy/deploy.sh
  2. set PUBLIC_ORIGIN and TLS_HOSTNAME in deploy/.env to the server's DNS name (WildFly serves HTTPS on 443)
  3. BEFORE exposing ports 1880 or 1883 publicly: Mosquitto TLS +
     per-device logins + ACL (docs/mqtt-contract.md §9), NODE_RED_ADMIN_HASH in deploy/.env.
EOF
