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
INSTALL_BASE="${INSTALL_BASE:-1}"
RUN_CERTBOT="${RUN_CERTBOT:-1}"
PRECOMPUTE_PER_GAME="${PRECOMPUTE_PER_GAME:-300}"
PRECOMPUTE_BATCH_SIZE="${PRECOMPUTE_BATCH_SIZE:-64}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run this script as root or with sudo."
  exit 1
fi

cd "${APP_DIR}"

echo "[1/7] Server bootstrap"
INSTALL_BASE="${INSTALL_BASE}" RUN_CERTBOT="${RUN_CERTBOT}" \
  bash "${SCRIPT_DIR}/setup_server.sh"

echo "[2/7] Starting Postgres"
docker compose up -d postgres

echo "[3/7] Loading Postgres from SQLite"
docker compose --profile loader run --rm postgres_loader

echo "[4/7] Starting API and frontend"
docker compose up -d --build api frontend

echo "[5/7] Rebuilding Chroma"
docker compose run --rm api python -m db_creation.chroma_db_migration

echo "[6/7] Precomputing default candidates"
docker compose run --rm api python -m db_creation.precompute_candidates \
  --per-game "${PRECOMPUTE_PER_GAME}" \
  --batch-size "${PRECOMPUTE_BATCH_SIZE}"

echo "[7/7] Final status"
docker compose ps

cat <<EOF

Initial server setup complete.

Recommended smoke tests:
  curl -I https://nextsteamgame.com
  curl "https://nextsteamgame.com/api/search?q=hades"
EOF
