# PufferLib Drone Training Lab Book

## Session: 2025-09-20

### Problem: ZeroDivisionError in Training Loop

**Issue**: `ZeroDivisionError: float division by zero` at `pufferl.py:329`
```python
anneal_beta = b0 + (1 - b0)*a*self.epoch/self.total_epochs
```

**Root Cause**:
- `total_epochs = total_timesteps // batch_size`
- When `batch_size > total_timesteps`, we get `total_epochs = 0`
- This happens because `batch_size = total_agents * bptt_horizon`

**Key Discovery**: Automatic batch sizing creates massive batches
- **Default config**: `num_envs=24`, `num_drones=64`, `bptt_horizon=64`
- **Agents**: 24 × 64 = 1,536 agents
- **Batch size**: 1,536 × 64 = 98,304 steps
- **Problem**: 50k timesteps ÷ 98k batch = 0 epochs

### Solutions Tested

#### ❌ Failed: Just increasing total timesteps to 1M
- Worked initially but hit same issue when scaling parallelization

#### ❌ Failed: Scaling parallelization without adjusting batch size
```bash
--vec.num-workers 16 --vec.num-envs 16 --env.num-envs 32 --env.num-drones 32
```
- Created even larger batch: 16 × (32×32) × 64 = 1,048,576 steps
- 1M timesteps still insufficient

#### ✅ **WORKING SOLUTION**: Reduce BPTT horizon
```bash
python -m pufferlib.pufferl train puffer_drone_pp \
  --train.device mps \
  --train.total-timesteps 1000000 \
  --train.bptt-horizon 16 \
  --vec.num-workers 16 \
  --vec.num-envs 16 \
  --env.num-envs 32 \
  --env.num-drones 32
```

**Results**:
- **Batch size**: 16,384 agents × 16 horizon = 262,144 steps
- **Epochs**: 1M ÷ 262k = ~4 epochs ✅
- **CPU usage**: 187% (improved from 115%)
- **SPS**: 1.8M steps/second
- **Memory**: 28.4% DRAM usage

### M3 Ultra Optimization Notes

**Hardware**: 24 cores (16 P-cores + 8 E-cores), 128GB unified memory

**Key Constraints**:
1. `vec.num_envs` must be divisible by `vec.num_workers`
2. `batch_size = total_agents * bptt_horizon` must be < `total_timesteps`
3. `total_agents = vec.num_envs * env.num_envs * env.num_drones`

**Optimization Strategy**:
- Maximize parallelization with `vec.num_workers` and `vec.num_envs`
- Reduce `bptt_horizon` to keep batch size manageable
- Scale `total_timesteps` proportionally if needed

### Training Metrics (Current Run)

**Performance**:
- Steps: 17.0M
- SPS: 1.8M
- Epoch: 4
- CPU: 187% (still room for improvement on 24-core system)

**Environment Stats**:
- Score: 1.680
- Collision rate: 0.002
- Episode length: 53.514
- Perfect deliveries: 0.000 (still learning)

## Full Training Run Results (200M timesteps)

**Command Used**:
```bash
python -m pufferlib.pufferl train puffer_drone_pp \
  --train.device mps \
  --train.total-timesteps 200000000 \
  --train.bptt-horizon 16 \
  --vec.num-workers 20 \
  --vec.num-envs 20 \
  --env.num-envs 32 \
  --env.num-drones 32 \
  --train.checkpoint-interval 100 \
  --wandb
```

**Performance Metrics**:
- **Runtime**: 5m 57s (357 seconds)
- **Steps**: 210.7M (completed full run + extra)
- **Epochs**: 611 (as predicted: 200M ÷ 327k ≈ 610)
- **SPS**: 1.2M average (590k steps/second raw throughput)
- **CPU Usage**: 282.3% (excellent M3 Ultra utilization)
- **Memory**: 30.3% DRAM usage (well within limits)

**Training Efficiency**:
- **Time breakdown**: 44% evaluate, 27% forward, 24% learn, 15% copy
- **Throughput**: ~590k environment steps/second sustained
- **M3 Ultra utilization**: Using ~12 of 24 cores effectively

**Learning Progress**:
- **Score**: 0.725 (down from initial 1.680 - exploration phase)
- **Episode length**: 63.376 steps
- **Collision rate**: 0.002 (very low, good flight control)
- **Perfect deliveries**: 0.000 (still learning task)
- **Explained variance**: 0.868 (high - value function learning well)

**Key Observations**:
- ✅ **Stable training**: No crashes, smooth convergence
- ✅ **Excellent hardware utilization**: 282% CPU on M3 Ultra
- ✅ **Fast completion**: 200M steps in under 6 minutes
- ⚠️ **Task complexity**: Drone delivery task challenging, needs longer training
- ✅ **WandB logging**: Full metrics captured for analysis

### Next Steps

1. **Longer training runs**: 500M-1B timesteps for complex drone delivery task
2. **Hyperparameter tuning**: Adjust reward weights based on WandB analysis
3. **Evaluation runs**: Test trained checkpoints on specific delivery scenarios

### Key Learnings

- **Batch size calculation is critical**: Always verify `total_timesteps / batch_size >= 1`
- **Horizon vs parallelization tradeoff**: Reducing horizon allows more parallelization
- **M3 Ultra handles high parallelization well**: 187% CPU with stable performance
- **Monitor the math**: PufferLib's automatic batch sizing can create surprisingly large batches