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
LOCAL_FRONTEND_DIR="${LOCAL_FRONTEND_DIR:-${LOCAL_DIR}/frontend}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/id_ed25519}"

if [[ -z "${REMOTE_HOST}" ]]; then
  echo "REMOTE_HOST is not set. Configure scripts/server_deploy/.env or export REMOTE_HOST before running." >&2
  exit 1
fi

if [[ ! -d "${LOCAL_FRONTEND_DIR}" ]]; then
  echo "Frontend directory not found: ${LOCAL_FRONTEND_DIR}" >&2
  exit 1
fi

RSYNC_ARGS=(
  -az
  --delete
  --info=progress2
  --exclude "node_modules/"
  --exclude ".next/"
  -e "ssh -i ${SSH_KEY} -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"
)

rsync "${RSYNC_ARGS[@]}" "${LOCAL_FRONTEND_DIR}/" "${REMOTE_HOST}:${REMOTE_DIR}/frontend/"

bash "${SCRIPT_DIR}/run_remote.sh" "cd ${REMOTE_DIR} && docker compose up -d --build frontend"

echo "Frontend deploy complete: ${LOCAL_FRONTEND_DIR} -> ${REMOTE_HOST}:${REMOTE_DIR}/frontend"
