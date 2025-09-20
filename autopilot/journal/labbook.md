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

- 2025-09-20T10:19:52Z | hyperparameter surface | Added PPO knobs (update_epochs, gae_lambda, gamma, clip_coef, vf_clip_coef, device toggle) to autopilot + docs | schema & configs patched | next: verify loop accepts new overrides
- 2025-09-20T10:23:02Z | run complete | Run 2025-09-20T102056Z (iteration 1) success 0.00, mean_reward 9.42, collision 5.8e-4, SPS 105.8k | stable; CPU ~357%, GPU ~0% | next: ent_coef 0.01, total_timesteps 2e7, keep 28/56 vec and batch 28672 for longer exploitation
- 2025-09-20T10:24:01Z | run complete | Run 2025-09-20T102109Z (iteration 1) | metrics captured | 
- 2025-09-20T10:24:16Z | run failed | 2025-09-20T102401Z: Codex run did not produce a new log in autopilot/logs/ | halt | 
- 2025-09-20T10:27:18Z | run failed | 2025-09-20T102706Z: Codex run did not produce a new log in autopilot/logs/ | halt | 

- 2025-09-20T10:28:25Z | prompt guardrail | Strengthened Codex instructions to execute training script via bash and documented fallback | prevents missing-log failures | next: rerun quick loop to confirm
- 2025-09-20T10:31:12Z | run complete | Run 2025-09-20T102907Z success 0.00, mean_reward 7.53, collision 5.5e-4, SPS 98k | baseline stable; CPU ~357%, vec 28/56, batch 28672 | next: drop ent_coef to 0.08 and raise update_epochs to 2 for more exploitation
- 2025-09-20T10:32:43Z | run complete | Run 2025-09-20T102907Z (iteration 1) | metrics captured | 
- 2025-09-20T10:32:44Z | run complete | Run 2025-09-20T102914Z success 0.00, mean_reward 5.46, collision 5.1e-4, SPS 17.5k | quick baseline vec 4/4, env 4x8, batch 2048; CPU ~95%, GPU ~0% | next: 2e6 steps, lr 5e-3, ent 0.12, update_epochs 2

- 2025-09-20T10:36:16Z | timeout guardrail | Prompt/docs now require `timeout 900` wrapper around training script to avoid 2-min CLI limit | ready to rerun multi-iter loop | next: verify Codex obeys timeout
- 2025-09-20T10:37:13Z | run complete | Run 2025-09-20T103243Z success 0.00, mean_reward 9.50, collision 6.1e-4, SPS 109k | CPU ~357%, GPU ~0% | next: ent 0.05, lr 2.5e-3, update_epochs 3, gamma 0.995, total_timesteps 15M
- 2025-09-20T10:39:25Z | run complete | Run 2025-09-20T103243Z (iteration 2) | metrics captured | 

- 2025-09-20T10:40:22Z | timeout policy tweak | Relaxed wording: agent must allow ≥15 min timeout when launching training script | ready to test loop again | next: rerun quick mode

- 2025-09-20T10:42:26Z | prompt nudge | Added guidance for Codex to read prior run summaries before proposing changes | reinforces trend-aware adjustments | next: observe behaviour in next loop run
- 2025-09-20T10:43:28Z | run complete | Run 2025-09-20T104111Z (iteration 1) success 0.00, mean_reward 8.70, collision 7.3e-4, SPS 10.4k | CPU ~357%, GPU ~0%; vec 4/4, env 4x8, batch 2048 | next: switch to full baseline (28/56) with lr 3e-3, ent 0.12, 1e7 steps
- 2025-09-20T10:38:30Z | tooling fix | host missing coreutils timeout; dropped python shim at /tmp/timeout to satisfy guardrail | monitor for early termination message
- 2025-09-20T10:43:48Z | run complete | Run 2025-09-20T103925Z success 0.00, mean_reward 11.73, collision 5.4e-4, SPS 115k | CPU ~357%, GPU ~0%; fallback timeout tripped at ~214s but logs show full 15M steps | next: drop ent_coef to 0.02 and extend to 2e7 steps to push exploitation
- 2025-09-20T10:45:40Z | run complete | Run 2025-09-20T103925Z (iteration 3) | metrics captured | 
- 2025-09-20T10:50:46Z | run complete | Run 2025-09-20T104540Z success 0.00, mean_reward 13.51, collision 5.4e-4, SPS 104k | stable; CPU ~357%, GPU ~0%; vec 28/56, env 4x8, batch 28672 | next: extend total_timesteps to 3e7 and drop lr to 2e-3 to consolidate gains
- 2025-09-20T10:52:49Z | run complete | Run 2025-09-20T104540Z (iteration 4) | metrics captured | 
- 2025-09-20T10:59:30Z | todo | Prompt still references {script}/{notes_path} without defaults | document explicit defaults and make placeholders configurable in next revision | autopilot prompt
- 2025-09-20T11:02:40Z | run complete | Run 2025-09-20T110240Z success 0.00, mean_reward 6.76, collision 6.4e-4, SPS 112k | CPU ~357%, GPU ~0%; oob ~0.96, rings 0 | next: ent 0.05, lr 2.5e-3, update_epochs 3, gamma 0.995, total_timesteps 15M
- 2025-09-20T11:06:19Z | run complete | Run 2025-09-20T110240Z (iteration 1) | metrics captured | 

- 2025-09-20T11:12:00Z | knob audit | Listed non-hyperparam levers (curriculum seeds, env randomization, wrappers, reward shaping, eval cadence, debugging hooks) | captured plan to log per-run rationale in labbook with dedicated checklist | next: extend prompt/schema so agent can pilot these safely
- 2025-09-20T11:18:00Z | resume wiring | Added autopilot resume knobs (resume_mode/resume_from/save_strategy); orchestrator now injects load_model_path & manages best/latest symlinks | ready to trial warm-start loops | next: gate adoption via A/B eval vs best
- 2025-09-20T11:13:00Z | run complete | Run 2025-09-20T110619Z (iteration 2) success 0.00, mean_reward 10.78, collision 6.2e-4, SPS 110.9k | reward recovered +4 vs prior but OOB 0.97 persists; clipfrac ~0 indicates conservative updates | next: ent 0.02, update_epochs 4, total_timesteps 20M to push on-track success
- 2025-09-20T11:13:04Z | run complete | Run 2025-09-20T110619Z (iteration 2) | metrics captured | 
- 2025-09-20T11:18:30Z | run complete | Run 2025-09-20T111304Z (iteration 3) success 0.00, mean_reward 13.92, collision 5.9e-4, SPS 104.5k, CPU ~357% | clipfrac≈0 with annealed lr; next: keep ent 0.02/update_epochs 4/20M steps but set lr 2.5e-3 and anneal_lr false to keep updates active
- 2025-09-20T11:21:22Z | run complete | Run 2025-09-20T111304Z (iteration 3) | metrics captured | 
- 2025-09-20T11:29:57Z | run complete | Run 2025-09-20T112722Z (iteration 1) | metrics captured | 
