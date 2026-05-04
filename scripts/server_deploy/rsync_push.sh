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

REMOTE_HOST="${REMOTE_HOST:-root@134.209.35.2}"
REMOTE_DIR="${REMOTE_DIR:-/root/Steam_Reccomender}"
LOCAL_DIR="${LOCAL_DIR:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/id_ed25519}"

rsync -az --delete \
  -e "ssh -i ${SSH_KEY}" \
  "${LOCAL_DIR}/" "${REMOTE_HOST}:${REMOTE_DIR}/"

echo "Rsync complete: ${LOCAL_DIR} -> ${REMOTE_HOST}:${REMOTE_DIR}"
