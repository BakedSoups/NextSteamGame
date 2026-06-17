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
SEND_EVERYTHING="${SEND_EVERYTHING:-0}"

if [[ -z "${REMOTE_HOST}" ]]; then
  echo "REMOTE_HOST is not set. Configure scripts/server_deploy/.env or export REMOTE_HOST before running." >&2
  exit 1
fi

RSYNC_ARGS=(
  -az
  --delete
  --info=progress2
  -e "ssh -i ${SSH_KEY} -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"
)

if [[ "${SEND_EVERYTHING}" != "1" ]]; then
  RSYNC_ARGS+=(
    --exclude ".git/"
    --exclude "venv/"
    --exclude ".venv/"
    --exclude "frontend/node_modules/"
    --exclude "frontend/.next/"
    --exclude "__pycache__/"
    --exclude ".mypy_cache/"
    --exclude ".pytest_cache/"
    --exclude "scripts/server_deploy/.env"
  )
fi

rsync "${RSYNC_ARGS[@]}" "${LOCAL_DIR}/" "${REMOTE_HOST}:${REMOTE_DIR}/"

echo "Rsync complete: ${LOCAL_DIR} -> ${REMOTE_HOST}:${REMOTE_DIR}"
