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

APP_DIR="${APP_DIR:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"

cd "${APP_DIR}"

git pull --ff-only
docker compose down
docker compose up --build -d

echo "Redeploy complete."
