#!/usr/bin/env bash
set -euo pipefail

# Usage: peak_probe.sh <workers> <vec_envs> [env_envs=1] [drones=16] [batch=8192] [minibatch=8192] [timesteps=200000] [device=mps]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUTOPILOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_DIR="$(cd "${AUTOPILOT_DIR}/.." && pwd)"
PUFFER_DIR="${REPO_DIR}/PufferLib"

WORKERS=${1:?"workers required"}
VEC_ENVS=${2:?"vec_envs required"}
ENV_ENVS=${3:-1}
DRONES=${4:-16}
BATCH=${5:-8192}
MINIBATCH=${6:-8192}
TIMESTEPS=${7:-200000}
DEVICE=${8:-mps}

TMP_DIR="${AUTOPILOT_DIR}/logs/peak"
mkdir -p "${TMP_DIR}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
RUN_TAG="w${WORKERS}_ve${VEC_ENVS}_ee${ENV_ENVS}_d${DRONES}_b${BATCH}_m${MINIBATCH}_${STAMP}"
SUMMARY_PATH="${TMP_DIR}/summary_${RUN_TAG}.json"
LOG_PATH="${TMP_DIR}/probe_${RUN_TAG}.log"

cat >"${TMP_DIR}/config_${RUN_TAG}.json" <<JSON
{
  "train": {
    "device": "${DEVICE}",
    "total_timesteps": ${TIMESTEPS},
    "bptt_horizon": 16,
    "batch_size": ${BATCH},
    "minibatch_size": ${MINIBATCH},
    "max_minibatch_size": ${MINIBATCH},
    "learning_rate": 0.003,
    "ent_coef": 0.08,
    "seed": 42,
    "checkpoint_interval": 1000
  },
  "env": {
    "num_envs": ${ENV_ENVS},
    "num_drones": ${DRONES}
  },
  "vec": {
    "num_workers": ${WORKERS},
    "num_envs": ${VEC_ENVS}
  }
}
JSON

cd "${PUFFER_DIR}"
source .venv/bin/activate

# macOS system bash is 3.2 (no mapfile); use portable array capture
TRAIN_ARGS=( $(python3 "${SCRIPT_DIR}/render_cli_args.py" "${TMP_DIR}/config_${RUN_TAG}.json") )

echo "[peak_probe] writing summary to: ${SUMMARY_PATH}" >&2
PUFFER_AUTOPILOT_SUMMARY="${SUMMARY_PATH}" \
python -m pufferlib.pufferl train puffer_drone_pp \
    "${TRAIN_ARGS[@]}" \
    2>&1 | tee "${LOG_PATH}"

echo "--- RESULT ${RUN_TAG} ---"
if [[ -f "${SUMMARY_PATH}" ]]; then
  # Extract SPS and a few key fields if present
  python - <<'PY'
import json,sys
path=sys.argv[1]
with open(path,'r') as f:
    j=json.load(f)
print("sps=", j.get("metrics",{}).get("sps"))
print("agent_steps=", j.get("metrics",{}).get("agent_steps"))
print("epoch=", j.get("metrics",{}).get("epoch"))
PY
  "${SUMMARY_PATH}"
else
  echo "No summary written. See log: ${LOG_PATH}" >&2
fi
