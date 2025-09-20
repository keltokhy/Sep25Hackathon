# Autopilot Lab Book

> Append entries with `- YYYY-MM-DDTHH:MM:SSZ | action | observation | outcome | next`.
- 2025-09-20T07:59:46Z | run complete | Run 2025-09-20T075930Z (iteration 1) | metrics captured | 
- 2025-09-20T08:05:40Z | run complete | Run 2025-09-20T080324Z (iteration 1) | metrics captured | 
- 2025-09-20T08:08:00Z | run complete | Run 2025-09-20T080540Z (iteration 2) | metrics captured | 
- 2025-09-20T08:26:35Z | run complete | Run 2025-09-20T082502Z (iteration 1) | metrics captured | 
- 2025-09-20T08:27:49Z | run complete | Run 2025-09-20T082635Z (iteration 2) | metrics captured | 
- 2025-09-20T08:33:38Z | run complete | Run 2025-09-20T083214Z (iteration 1) | metrics captured | 
- 2025-09-20T08:41:21Z | run complete | Run 2025-09-20T083835Z (iteration 1) | metrics captured | 
- 2025-09-20T08:44:05Z | run complete | Run 2025-09-20T084231Z (iteration 1) | metrics captured | 
- 2025-09-20T08:50:32Z | autopilot harness | shifted override staging to post-run | docs/prompt aligned | next: dry-run loop to confirm agent updates
- 2025-09-20T08:54:21Z | run complete | Run 2025-09-20T085159Z (iteration 1) | metrics captured | 
- 2025-09-20T08:56:13Z | run complete | Run 2025-09-20T085421Z (iteration 2) | metrics captured | 
- 2025-09-20T09:00:44Z | automation wiring | training scripts now consume run config | throughput tuning documented | next: run quick loop to verify lr/entropy propagate
- 2025-09-20T10:15:00Z | troubleshooting heavy run | heavy MPS command appeared to hang after brief CPU spike | likely due to vec/env divisibility and MPS cold compile; moved to low‑demand probes
- 2025-09-20T10:18:00Z | probe serial (MPS) | 1 env, 1 drone, tiny batch | succeeded; dashboard printed within ~30–60s
- 2025-09-20T10:21:00Z | probe mp small | 2 workers, 2 vec envs (divisible), env.num_envs=1, num_drones=1 | succeeded; CPU ~10% overall (expected under‑utilization at this scale)
- 2025-09-20T10:25:00Z | hypothesis | low CPU due to low worker/env count; prior “stuck” came from invalid divisibility and/or MPS cold compile | next: stepwise scale workers/envs keeping vec.num_envs % vec.num_workers == 0 and batch_size % (vec.num_envs/vec.num_workers) == 0
- 2025-09-20T10:26:00Z | next steps | test 14 workers/28 envs then 28/56; maintain small train.batch-size initially; verify logs print within 60–90s; record SPS/CPU% per step | if idle persists, try CPU device to isolate MPS
- 2025-09-20T10:40:00Z | peak search | probe #1 (14/28, e1,d16,b=7168) stable ~50% CPU | probe #2 (28/56, e1,d16,b=14336) ~100% CPU | probe #3 (28/56, e4,d8,b=28672) ~100% CPU; adopting #3 as full baseline
- 2025-09-20T10:48:00Z | docs | codex prompt updated with allowed knobs + derivation rule (batch = agents×bptt); README/AGENTS emphasize constraints + baseline; scripts export mac perf env
- 2025-09-20T10:55:00Z | maintenance | cleared legacy logs, removed duplicate quick launcher, baseline full total_timesteps set to 5e6 (~2–3 min) | prompt/README/AGENTS updated with iteration-speed vs reward tradeoff guidance
- 2025-09-20T09:51:01Z | run complete | Run 2025-09-20T094724Z (iteration 1) | metrics captured | 
- 2025-09-20T09:52:42Z | run complete | Run 2025-09-20T095101Z (iteration 2) | metrics captured | 
- 2025-09-20T10:02:35Z | run complete | Run 2025-09-20T100046Z (iteration 1) | metrics captured | 
- 2025-09-20T10:03:13Z | run complete | Run 2025-09-20T100235Z (iteration 1) success 0.00, mean_reward 8.34, collision 0.0006, SPS 109k | stable; CPU about 190% with vec 12/24 | next: raise to 28/56, lr 3.2e-3, ent 0.10, 5e6 steps
- 2025-09-20T10:04:38Z | run complete | Run 2025-09-20T100235Z (iteration 2) | metrics captured | 
- 2025-09-20T10:05:57Z | run complete | Run 2025-09-20T100438Z (iteration 1) success 0.00, mean_reward 7.78, collision 5.5e-4, SPS 108k | metrics captured; CPU ~357%, GPU ~0% | next: ent_coef 0.05, total_timesteps 7e6
- 2025-09-20T10:07:29Z | run complete | Run 2025-09-20T100438Z (iteration 3) | metrics captured | 

- 2025-09-20T10:11:30Z | baseline update | Increased full baseline to 1e7 steps (~5–6 min) and reset checkpoint to 200 | logs/runs cleared for fresh cadence | next: run full iteration to confirm duration
- 2025-09-20T10:15:01Z | run complete | Run 2025-09-20T101314Z (iteration 1) success 0.00, mean_reward 8.38, collision 5.6e-4, SPS 114k | stable; CPU ~357%, GPU ~0% | next: drop ent_coef to 0.02 and extend to 1e7 steps for more exploitation
- 2025-09-20T10:16:04Z | run complete | Run 2025-09-20T101314Z (iteration 1) | metrics captured | 
