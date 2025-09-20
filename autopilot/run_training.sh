#!/usr/bin/env bash
set -euo pipefail

cd /Users/khaled/GitHub/Sep25Hackathon-master/PufferLib && source .venv/bin/activate && python -m pufferlib.pufferl train puffer_drone_pp \
    --train.device mps \
    --train.total-timesteps 200000000 \
    --train.bptt-horizon 16 \
    --vec.num-workers 20 \
    --vec.num-envs 20 \
    --env.num-envs 32 \
    --env.num-drones 32 \
    --train.checkpoint-interval 100 \
    --wandb
