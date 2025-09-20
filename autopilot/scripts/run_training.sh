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
LOG_FILE="${LOG_DIR}/train_full_${LOG_SUFFIX}.log"

CONFIG_PATH="${AUTOPILOT_DIR}/configs/baseline_full.json"
if [[ -n "${PUFFER_AUTOPILOT_RUN_DIR:-}" && -f "${PUFFER_AUTOPILOT_RUN_DIR}/config.json" ]]; then
  CONFIG_PATH="${PUFFER_AUTOPILOT_RUN_DIR}/config.json"
fi

echo "Logging output to ${LOG_FILE}"
echo "Using config ${CONFIG_PATH}"

cd "${PUFFER_DIR}"
source .venv/bin/activate

# macOS performance env (override by exporting before calling script)
export PYTORCH_MPS_HIGH_WATERMARK_RATIO=${PYTORCH_MPS_HIGH_WATERMARK_RATIO:-0.0}
export OMP_NUM_THREADS=${OMP_NUM_THREADS:-28}
export MKL_NUM_THREADS=${MKL_NUM_THREADS:-28}

# Normalize config: enforce divisibility and batch sizing, and allow env selection
# This edits the config in-place so the applied values are recorded alongside the run.
ENV_NAME=$(python3 - "$CONFIG_PATH" <<'PYCONF'
import json, math, sys
from pathlib import Path

cfg_path = Path(sys.argv[1])
cfg = json.loads(cfg_path.read_text())

# Default env name if not provided
env_name = cfg.get('env_name') or cfg.get('base', {}).get('env_name') or 'puffer_drone_pp'

train = cfg.setdefault('train', {})
env = cfg.setdefault('env', {})
vec = cfg.setdefault('vec', {})

num_envs_env = int(env.get('num_envs', 1))
num_drones = int(env.get('num_drones', 1))
num_envs_vec = int(vec.get('num_envs', 1))
num_workers = int(vec.get('num_workers', 1))
bptt = int(train.get('bptt_horizon', 16))

# Enforce vec.num_envs divisible by vec.num_workers
if num_workers > 0 and num_envs_vec % num_workers != 0:
    num_envs_vec = ( (num_envs_vec + num_workers - 1) // num_workers ) * num_workers
    vec['num_envs'] = num_envs_vec

# Derive batch sizes per guidelines
expected_batch = num_envs_env * num_drones * num_envs_vec * bptt
train['batch_size'] = expected_batch
train['minibatch_size'] = expected_batch
train['max_minibatch_size'] = expected_batch

# Persist env name to config for traceability
cfg['env_name'] = env_name

cfg_path.write_text(json.dumps(cfg, indent=2))

# Emit the env name so the shell can capture it
print(env_name)
PYCONF
)

# macOS system bash is 3.2 (no mapfile); use portable array capture
TRAIN_ARGS=( $(python3 "${SCRIPT_DIR}/render_cli_args.py" "${CONFIG_PATH}") )

python -m pufferlib.pufferl train "${ENV_NAME}" \
    "${TRAIN_ARGS[@]}" \
    2>&1 | tee "${LOG_FILE}"
