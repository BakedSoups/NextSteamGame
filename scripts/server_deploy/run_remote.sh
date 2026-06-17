#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ "$#" -eq 0 ]]; then
  echo "Usage: bash scripts/server_deploy/run_remote.sh <remote command>" >&2
  exit 1
fi

bash "${SCRIPT_DIR}/ssh_remote.sh" "$@"
