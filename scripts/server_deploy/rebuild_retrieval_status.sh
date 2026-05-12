#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/root/steamrec2}"
LOG_DIR="${APP_DIR}/logs"
PID_FILE="${LOG_DIR}/retrieval_rebuild.pid"

if [[ -t 1 ]]; then
  C_RESET="$(printf '\033[0m')"
  C_RED="$(printf '\033[31m')"
  C_GREEN="$(printf '\033[32m')"
  C_YELLOW="$(printf '\033[33m')"
  C_BLUE="$(printf '\033[34m')"
  C_MAGENTA="$(printf '\033[35m')"
  C_CYAN="$(printf '\033[36m')"
  C_DIM="$(printf '\033[2m')"
  C_BOLD="$(printf '\033[1m')"
else
  C_RESET=""
  C_RED=""
  C_GREEN=""
  C_YELLOW=""
  C_BLUE=""
  C_MAGENTA=""
  C_CYAN=""
  C_DIM=""
  C_BOLD=""
fi

print_bar() {
  local current="$1"
  local total="$2"
  local width="${3:-28}"
  local color="${4:-$C_CYAN}"
  local filled=0
  local empty=0
  local percent=0
  local bar=""

  if [[ "${total}" -gt 0 ]]; then
    percent=$(( current * 100 / total ))
    filled=$(( current * width / total ))
  fi
  if [[ "${filled}" -gt "${width}" ]]; then
    filled="${width}"
  fi
  empty=$(( width - filled ))

  if [[ "${filled}" -gt 0 ]]; then
    bar="$(printf '%*s' "${filled}" '' | tr ' ' '#')"
  fi
  if [[ "${empty}" -gt 0 ]]; then
    bar="${bar}$(printf '%*s' "${empty}" '' | tr ' ' '-')"
  fi

  printf '%b[%s]%b %3d%%' "${color}" "${bar}" "${C_RESET}" "${percent}"
}

print_stage() {
  local label="$1"
  local state="$2"
  local color="$3"
  printf '%b%-12s%b %s\n' "${color}${C_BOLD}" "${label}" "${C_RESET}" "${state}"
}

show_recent_logs() {
  local file="$1"
  local lines="${2:-25}"
  echo
  printf '%bRecent Log Output%b\n' "${C_DIM}" "${C_RESET}"
  tail -n "${lines}" "${file}"
}

render_status() {
  local latest_log="$1"
  local is_running="$2"
  local chroma_processed=0
  local chroma_total=0
  local chroma_batch=0
  local precompute_processed=0
  local precompute_total=0
  local stage="bootstrap"
  local completed="0"

  if grep -q '\[3/3\] Starting live API again' "${latest_log}"; then
    stage="starting_api"
  elif grep -q '\[2/2\] Precomputing candidates' "${latest_log}"; then
    stage="precompute"
  elif grep -q '\[1/2\] Rebuilding Chroma' "${latest_log}"; then
    stage="chroma"
  elif grep -q '\[0/3\] Stopping live API' "${latest_log}"; then
    stage="stop_api"
  fi

  if grep -q 'Retrieval rebuild complete' "${latest_log}"; then
    completed="1"
  fi

  local chroma_line
  chroma_line="$(grep 'Chroma batch ' "${latest_log}" | tail -n 1 || true)"
  if [[ -n "${chroma_line}" ]]; then
    chroma_batch="$(printf '%s\n' "${chroma_line}" | sed -E 's/.*Chroma batch ([0-9]+):.*/\1/')"
    chroma_processed="$(printf '%s\n' "${chroma_line}" | sed -E 's/.*: ([0-9]+)\/([0-9]+).*/\1/')"
    chroma_total="$(printf '%s\n' "${chroma_line}" | sed -E 's/.*: ([0-9]+)\/([0-9]+).*/\2/')"
  fi

  local precompute_line
  precompute_line="$(grep -E 'processed=[0-9]+/[0-9]+|completed processed=' "${latest_log}" | tail -n 1 || true)"
  if [[ -n "${precompute_line}" ]]; then
    precompute_processed="$(printf '%s\n' "${precompute_line}" | sed -E 's/.*processed=([0-9]+)\/([0-9]+).*/\1/')"
    precompute_total="$(printf '%s\n' "${precompute_line}" | sed -E 's/.*processed=([0-9]+)\/([0-9]+).*/\2/')"
    if [[ "${precompute_line}" == completed* ]]; then
      precompute_processed="${precompute_total}"
    fi
  fi

  if [[ "${is_running}" == "1" ]]; then
    printf '%bRetrieval Rebuild Running%b\n' "${C_GREEN}${C_BOLD}" "${C_RESET}"
  elif [[ "${completed}" == "1" ]]; then
    printf '%bRetrieval Rebuild Complete%b\n' "${C_GREEN}${C_BOLD}" "${C_RESET}"
  else
    printf '%bRetrieval Rebuild Not Running%b\n' "${C_YELLOW}${C_BOLD}" "${C_RESET}"
  fi

  echo
  printf '%bStages%b\n' "${C_DIM}" "${C_RESET}"
  case "${stage}" in
    stop_api)
      print_stage "API Stop" "in progress" "${C_YELLOW}"
      print_stage "Chroma" "waiting" "${C_DIM}"
      print_stage "Candidates" "waiting" "${C_DIM}"
      print_stage "API Start" "waiting" "${C_DIM}"
      ;;
    chroma)
      print_stage "API Stop" "done" "${C_GREEN}"
      print_stage "Chroma" "in progress" "${C_YELLOW}"
      print_stage "Candidates" "waiting" "${C_DIM}"
      print_stage "API Start" "waiting" "${C_DIM}"
      ;;
    precompute)
      print_stage "API Stop" "done" "${C_GREEN}"
      print_stage "Chroma" "done" "${C_GREEN}"
      print_stage "Candidates" "in progress" "${C_YELLOW}"
      print_stage "API Start" "waiting" "${C_DIM}"
      ;;
    starting_api)
      print_stage "API Stop" "done" "${C_GREEN}"
      print_stage "Chroma" "done" "${C_GREEN}"
      print_stage "Candidates" "done" "${C_GREEN}"
      print_stage "API Start" "in progress" "${C_YELLOW}"
      ;;
    *)
      if [[ "${completed}" == "1" ]]; then
        print_stage "API Stop" "done" "${C_GREEN}"
        print_stage "Chroma" "done" "${C_GREEN}"
        print_stage "Candidates" "done" "${C_GREEN}"
        print_stage "API Start" "done" "${C_GREEN}"
      else
        print_stage "API Stop" "pending" "${C_DIM}"
        print_stage "Chroma" "pending" "${C_DIM}"
        print_stage "Candidates" "pending" "${C_DIM}"
        print_stage "API Start" "pending" "${C_DIM}"
      fi
      ;;
  esac

  if [[ "${chroma_total}" -gt 0 ]]; then
    echo
    printf '%bChroma Progress%b\n' "${C_DIM}" "${C_RESET}"
    printf 'Batch %s  ' "${chroma_batch}"
    print_bar "${chroma_processed}" "${chroma_total}" 30 "${C_CYAN}"
    printf '  %s/%s\n' "${chroma_processed}" "${chroma_total}"
  fi

  if [[ "${precompute_total}" -gt 0 ]]; then
    echo
    printf '%bCandidate Precompute%b\n' "${C_DIM}" "${C_RESET}"
    print_bar "${precompute_processed}" "${precompute_total}" 30 "${C_MAGENTA}"
    printf '  %s/%s\n' "${precompute_processed}" "${precompute_total}"
  fi
}

if [[ ! -f "${PID_FILE}" ]]; then
  printf '%bNo retrieval rebuild PID file found.%b\n' "${C_YELLOW}" "${C_RESET}"
  if ls "${LOG_DIR}"/retrieval_rebuild_*.log >/dev/null 2>&1; then
    echo
    printf '%bRecent logs:%b\n' "${C_DIM}" "${C_RESET}"
    ls -1t "${LOG_DIR}"/retrieval_rebuild_*.log | head -n 3
  fi
  exit 0
fi

JOB_PID="$(cat "${PID_FILE}")"

LATEST_LOG="$(ls -1t "${LOG_DIR}"/retrieval_rebuild_*.log 2>/dev/null | head -n 1 || true)"

if [[ -n "${JOB_PID}" ]] && kill -0 "${JOB_PID}" 2>/dev/null; then
  render_status "${LATEST_LOG}" "1"
  echo
  printf '%bPID:%b %s\n' "${C_DIM}" "${C_RESET}" "${JOB_PID}"
  if [[ -n "${LATEST_LOG}" ]]; then
    printf '%bLog:%b %s\n' "${C_DIM}" "${C_RESET}" "${LATEST_LOG}"
    show_recent_logs "${LATEST_LOG}" 20
  fi
  exit 0
fi

render_status "${LATEST_LOG}" "0"
echo
printf '%bPID file:%b %s\n' "${C_DIM}" "${C_RESET}" "${PID_FILE}"
if [[ -n "${LATEST_LOG}" ]]; then
  printf '%bLast log:%b %s\n' "${C_DIM}" "${C_RESET}" "${LATEST_LOG}"
  show_recent_logs "${LATEST_LOG}" 30
fi
