#!/usr/bin/env bash
set -euo pipefail

cd /Users/khaled/GitHub/Sep25Hackathon-master/PufferLib && source .venv/bin/activate && python -m pufferlib.pufferl train puffer_drone_pp \
    --train.device mps \
    --train.total-timesteps 1000000 \
    --train.bptt-horizon 16 \
    --train.batch-size 2048 \
    --train.minibatch-size 2048 \
    --train.max-minibatch-size 2048 \
    --vec.num-workers 4 \
    --vec.num-envs 4 \
    --env.num-envs 4 \
    --env.num-drones 8 \
    --train.checkpoint-interval 1000
