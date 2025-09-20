#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUTOPILOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_DIR="$(cd "${AUTOPILOT_DIR}/.." && pwd)"
PUFFER_DIR="${REPO_DIR}/PufferLib"
LOG_DIR="${AUTOPILOT_DIR}/logs"
mkdir -p "${LOG_DIR}"

RUN_ID="${PUFFER_AUTOPILOT_RUN_ID:-}" 
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG_SUFFIX="${RUN_ID:-${STAMP}}"
LOG_FILE="${LOG_DIR}/train_quick_${LOG_SUFFIX}.log"

CONFIG_PATH="${AUTOPILOT_DIR}/configs/baseline_quick.json"
if [[ -n "${PUFFER_AUTOPILOT_RUN_DIR:-}" && -f "${PUFFER_AUTOPILOT_RUN_DIR}/config.json" ]]; then
  CONFIG_PATH="${PUFFER_AUTOPILOT_RUN_DIR}/config.json"
fi

echo "Logging output to ${LOG_FILE}"
echo "Using config ${CONFIG_PATH}"

cd "${PUFFER_DIR}"
source .venv/bin/activate

# macOS system bash is 3.2 (no mapfile); use portable array capture
TRAIN_ARGS=( $(python3 "${SCRIPT_DIR}/render_cli_args.py" "${CONFIG_PATH}") )

python -m pufferlib.pufferl train puffer_drone_pp \
    "${TRAIN_ARGS[@]}" \
    2>&1 | tee "${LOG_FILE}"
