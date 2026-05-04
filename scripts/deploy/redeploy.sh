#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"

cd "${APP_DIR}"

git pull --ff-only
docker compose down
docker compose up --build -d

echo "Redeploy complete."
