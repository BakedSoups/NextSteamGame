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

APP_DIR="${APP_DIR:-/root/steamrec2}"
DOMAIN="${DOMAIN:-nextsteamgame.com}"
EMAIL="${EMAIL:-overbakedrice@gmail.com}"
SERVER_NAME="${SERVER_NAME:-steamrec2}"
PRECOMPUTE_PER_GAME="${PRECOMPUTE_PER_GAME:-500}"
PRECOMPUTE_BATCH_SIZE="${PRECOMPUTE_BATCH_SIZE:-64}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run this script as root or with sudo."
  exit 1
fi

cd "${APP_DIR}"

echo "[1/8] Stopping old gunicorn processes on port 5000 path"
pkill -f gunicorn || true
fuser -k 5000/tcp || true

echo "[2/8] Rewriting nginx proxy config"
INSTALL_BASE=0 RUN_CERTBOT=0 DOMAIN="${DOMAIN}" EMAIL="${EMAIL}" APP_DIR="${APP_DIR}" SERVER_NAME="${SERVER_NAME}" \
  bash "${SCRIPT_DIR}/setup_droplet.sh"

echo "[3/8] Stopping old docker stack"
docker compose down --remove-orphans || true

echo "[4/8] Building and starting docker stack"
docker compose up -d --build

echo "[5/8] Rebuilding final canonical SQLite DB from canon_groups_v6.csv"
docker compose exec api python -m db_creation.final_db --skip-canon

echo "[6/8] Refreshing Postgres from final canonical SQLite DB"
docker compose exec api python -m db_creation.postgres.load_from_sqlite

echo "[7/8] Rebuilding Chroma and precomputed candidate cache"
docker compose exec api python -m db_creation.chroma_db_migration
docker compose exec api python -m db_creation.precompute_candidates --per-game "${PRECOMPUTE_PER_GAME}" --batch-size "${PRECOMPUTE_BATCH_SIZE}"

echo "[8/8] Final nginx reload"
nginx -t
systemctl reload nginx

echo "Cutover complete."
