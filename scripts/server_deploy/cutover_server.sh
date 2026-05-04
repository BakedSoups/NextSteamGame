#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${ENV_FILE:-${SCRIPT_DIR}/.env}"

if [[ -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a
fi

APP_DIR="${APP_DIR:-/root/Steam_Reccomender}"
DOMAIN="${DOMAIN:-nextsteamgame.com}"
EMAIL="${EMAIL:-overbakedrice@gmail.com}"
SERVER_NAME="${SERVER_NAME:-nextsteamgame}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run this script as root or with sudo."
  exit 1
fi

cd "${APP_DIR}"

echo "[1/5] Stopping old gunicorn processes on port 5000 path"
pkill -f gunicorn || true
fuser -k 5000/tcp || true

echo "[2/5] Rewriting nginx proxy config"
INSTALL_BASE=0 RUN_CERTBOT=0 DOMAIN="${DOMAIN}" EMAIL="${EMAIL}" APP_DIR="${APP_DIR}" SERVER_NAME="${SERVER_NAME}" \
  bash "${SCRIPT_DIR}/setup_droplet.sh"

echo "[3/5] Stopping old docker stack"
docker compose down --remove-orphans || true

echo "[4/5] Building and starting docker stack"
docker compose up -d --build

echo "[5/5] Final nginx reload"
nginx -t
systemctl reload nginx

echo "Cutover complete."
