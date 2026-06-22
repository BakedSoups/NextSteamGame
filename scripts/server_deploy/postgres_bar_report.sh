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

REMOTE_HOST="${REMOTE_HOST:-}"
REMOTE_DIR="${REMOTE_DIR:-/root/steamrec2}"
LOCAL_DIR="${LOCAL_DIR:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/id_ed25519}"
REPORT_LIMIT="${REPORT_LIMIT:-20}"

if [[ -z "${REMOTE_HOST}" ]]; then
  echo "REMOTE_HOST is not set. Configure scripts/server_deploy/.env or export REMOTE_HOST before running." >&2
  exit 1
fi

echo "Syncing repo to ${REMOTE_HOST}:${REMOTE_DIR} ..."
bash "${SCRIPT_DIR}/rsync_push.sh"

echo "Generating Postgres bar report on server ..."
ssh -i "${SSH_KEY}" -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new "${REMOTE_HOST}" \
  "cd '${REMOTE_DIR}' && docker compose up -d postgres && docker compose run --rm --no-deps -v \"\${PWD}/scripts:/app/scripts:ro\" api python /app/scripts/postgres_bar_report.py --limit '${REPORT_LIMIT}'"

mkdir -p "${LOCAL_DIR}/data"

echo "Pulling report artifacts back to ${LOCAL_DIR}/data ..."
rsync -az \
  -e "ssh -i ${SSH_KEY} -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new" \
  "${REMOTE_HOST}:${REMOTE_DIR}/data/postgres_bar_report.html" \
  "${REMOTE_HOST}:${REMOTE_DIR}/data/postgres_bar_report.json" \
  "${LOCAL_DIR}/data/"

echo "Done."
echo "HTML: ${LOCAL_DIR}/data/postgres_bar_report.html"
echo "JSON: ${LOCAL_DIR}/data/postgres_bar_report.json"
