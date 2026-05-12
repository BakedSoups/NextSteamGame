#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/root/steamrec2}"
LOG_DIR="${APP_DIR}/logs"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="${LOG_DIR}/retrieval_rebuild_${TIMESTAMP}.log"
PID_FILE="${LOG_DIR}/retrieval_rebuild.pid"

mkdir -p "${LOG_DIR}"
cd "${APP_DIR}"

if [[ -f "${PID_FILE}" ]]; then
  EXISTING_PID="$(cat "${PID_FILE}" 2>/dev/null || true)"
  if [[ -n "${EXISTING_PID}" ]] && kill -0 "${EXISTING_PID}" 2>/dev/null; then
    echo "A retrieval rebuild is already running with PID ${EXISTING_PID}."
    echo "Check status with:"
    echo "  bash scripts/server_deploy/rebuild_retrieval_status.sh"
    exit 1
  fi
fi

nohup bash -lc '
  set -euo pipefail
  cd "'"${APP_DIR}"'"
  echo "[0/3] Stopping live API so Chroma can be rebuilt safely"
  docker compose stop api
  echo
  echo "[1/2] Rebuilding Chroma"
  docker compose run --rm api python -m db_creation.chroma_db_migration
  echo
  echo "[2/2] Precomputing candidates"
  docker compose run --rm api python -m db_creation.precompute_candidates
  echo
  echo "[3/3] Starting live API again"
  docker compose up -d api
  echo
  echo "Retrieval rebuild complete"
' > "${LOG_FILE}" 2>&1 &

JOB_PID="$!"
echo "${JOB_PID}" > "${PID_FILE}"

echo "Started retrieval rebuild in background."
echo "PID: ${JOB_PID}"
echo "Log: ${LOG_FILE}"
echo
echo "Check status with:"
echo "  bash scripts/server_deploy/rebuild_retrieval_status.sh"
echo
echo "Follow logs with:"
echo "  tail -f ${LOG_FILE}"
