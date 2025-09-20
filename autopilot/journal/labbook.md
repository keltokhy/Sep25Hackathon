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
