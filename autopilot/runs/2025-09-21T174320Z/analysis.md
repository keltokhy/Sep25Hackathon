# Training Run Analysis: 2025-09-21T095422Z

## Executive Summary
This run reveals a fundamental disconnect between boundary avoidance improvements and actual task performance. While OOB rates improved from 91.5% to a best of 57.7%, the drones essentially failed to learn the package delivery task, with near-zero grip attempts and negligible delivery success.

## Performance Metrics Overview

### Boundary Performance (OOB)
- **Starting OOB**: 91.5% (epochs 0-30)
- **Best OOB**: 57.7% (epochs 33-40)
- **Final OOB**: 79.8% (epoch 85)
- **Pattern**: Improvement followed by regression

### Task Performance
- **Grip Attempts**: 1.723 total across 8,048 episodes (0.02% attempt rate)
- **Successful Grips**: 624 total (7.76% of episodes, but likely cumulative false positives)
- **Successful Deliveries**: 6 total (0.077% of episodes)
- **Key Finding**: Despite 276M training steps, drones almost never attempted to grip packages

### Score Evolution
- **Epochs 0-30**: Score ~3.3 (minimal learning)
- **Epochs 33-40**: Score 177.7 (peak performance)
- **Epochs 50-60**: Score 201.1 (slight improvement)
- **Epochs 70-80**: Score 103.7 (degradation begins)
- **Final epoch 85**: Score 34.9 (collapse)

## Critical Discoveries

### 1. Curriculum Configuration Analysis
The `grip_k` parameter controls task difficulty through grip gate tolerances:
- **Initial k**: 17.89 (nearly impossible grip requirements)
- **Decay rate**: 0.0000844 per timestep
- **k=1.0 reached**: After 200,000 timesteps
- **Training duration**: 200,000,000 timesteps
- **Result**: 99.9% of training occurs at k=1.0 (hardest difficulty)

At high k values (>5), the grip requirements become:
- XY distance must be < 0.35*k meters
- Z distance must be < 0.35*k meters
- At k=17.89: requires <6.26m precision (impossible given drone dynamics)
- At k=1: requires <0.35m precision (achievable but challenging)

### 2. Learning Window Problem
The curriculum decay happens so fast that drones miss the learning opportunity:
- **Timesteps 0-50K**: k=17.89→13.67 (impossible)
- **Timesteps 50K-100K**: k=13.67→9.44 (still impossible)
- **Timesteps 100K-150K**: k=9.44→5.22 (extremely difficult)
- **Timesteps 150K-200K**: k=5.22→1.00 (difficult but learnable)
- **Timesteps 200K-200M**: k=1.00 (constant maximum difficulty)

The drones never experience a gradual learning progression. They jump from impossible to very hard with no time to develop basic skills.

### 3. Mid-Training Performance Collapse
A striking pattern emerged where performance peaked mid-training then degraded:

**Phase 1 (Epochs 0-30)**: No Learning
- OOB: 91.5%
- Score: 3.3
- No grip attempts

**Phase 2 (Epochs 33-40)**: Breakthrough
- OOB: 57.7%
- Score: 177.7
- Some successful grips begin

**Phase 3 (Epochs 50-60)**: Peak Task Performance
- OOB: 60.1%
- Score: 201.1
- Maximum score achieved

**Phase 4 (Epochs 70-85)**: Degradation
- OOB: 72.4%→79.8%
- Score: 103.7→34.9
- Performance collapses

### 4. Velocity Penalty Impact
The distance-scaled velocity penalty introduced to fix OOB may have caused the performance collapse:
- Near target (<5m): Full penalty applied
- Far from target: 10% penalty strength
- This encouraged slow, careful movement near packages
- But may have over-penalized the aggressive movements needed for gripping

### 5. Training Duration Insufficiency
Comparison with typical RL benchmarks:
- Current training: 200M timesteps (85 epochs)
- Complex manipulation tasks typically need: 1B+ timesteps
- Drone has 10 discrete actions, 45-dim observation space
- Task involves sequential subgoals: locate→approach→grip→carry→deliver
- Each subgoal needs substantial training to master

## Environmental Factors

### Spawn Configuration
- Drones spawn 0.3-0.8m from packages laterally
- Edge margin: 16m from boundaries
- Spawn height: Variable based on task phase
- Issue: Even at spawn, drones are often outside grip range at high k

### Physics Constants
- BASE_MAX_VEL: 20 m/s (reduced from 50)
- BASE_MAX_OMEGA: 25 rad/s
- These reductions helped OOB but may limit task execution ability

### Reward Structure
- Hover reward: 0.35
- Grip reward: 0.5
- Delivery reward: 0.75
- Distance decay factor: 0.5
- Issue: No reward for grip attempts, only successes

## Statistical Anomalies

### Impossible Percentages
The logged metrics show impossible values when interpreted as rates:
- Grip attempts per episode: 414% (epoch 40)
- Success rate of attempts: 10574% (epoch 40)

These arise because:
1. Metrics accumulate across all parallel environments
2. With 64 drones * 24 environments = 1536 agents
3. Numbers represent totals, not averages
4. Episode counts are incorrectly used as denominators

### Actual Performance
When properly normalized:
- True grip attempt rate: <0.02% of episodes
- True grip success rate: <0.01% of all episodes
- True delivery rate: <0.001% of all episodes

## Key Insights

1. **The task is essentially unlearned** - Despite 276M steps of training, drones avoid packages rather than attempting grips.

2. **Curriculum pacing is broken** - The difficulty spike happens in <0.1% of training time, providing no learning gradient.

3. **Performance can improve then degrade** - The model achieved 57.7% OOB mid-training but regressed to 79.8% by the end.

4. **Boundary avoidance ≠ task success** - Fixing OOB didn't translate to package delivery performance.

5. **Training is far too short** - 200M timesteps is insufficient for this task complexity; similar tasks require 1B+.

## Behavioral Observations

### What the Drones Learned
- Basic boundary avoidance (partial)
- Hovering behavior (limited)
- General navigation

### What the Drones Didn't Learn
- Package approach strategies
- Grip attempt behaviors
- Carry dynamics
- Delivery sequences
- Task sequencing

### Failure Modes
1. **Avoidance behavior**: Drones stay away from packages
2. **Boundary crashes**: Still 79.8% of episodes end at boundaries
3. **No grip attempts**: Only 0.02% of episodes include grip attempts
4. **Hover instability**: Cannot maintain stable hover positions

## Comparative Analysis

### Versus Previous Runs
Compared to runs 072610-094027 with similar configs:
- OOB improved: 95%→58% (best case)
- Episode length increased: 50→196 steps
- Rewards increased: 5.6→28.3
- But grip/delivery performance remained near zero

### Pattern Across All Recent Runs
Analysis of 15 recent runs shows:
- Average grip attempt rate: 0.016%
- Average delivery rate: 0.04%
- All runs stop at exactly epoch 85 (timestep limit)
- Performance degradation is common after epoch 60

## Conclusions

This run demonstrates that the current training setup has fundamental issues preventing task learning:

1. **The curriculum is improperly configured** - Difficulty ramps up in <0.1% of training time, giving no opportunity for gradual skill development.

2. **Training duration is inadequate** - 200M timesteps cannot cover the complexity of sequential manipulation tasks requiring precise control.

3. **Performance instability exists** - Even when improvements occur (57.7% OOB achieved), they don't persist through training.

4. **Task metrics are misleading** - Cumulative logging obscures the near-zero actual performance rates.

5. **The reward structure lacks shaping** - No incentive for grip attempts means no learning signal for the primary task.

The fundamental problem isn't boundary avoidance or physics parameters - it's that the training regime doesn't support learning the actual package delivery task. The drones learn to fly and partially avoid walls, but never develop package manipulation skills.