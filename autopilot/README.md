# Autopilot Workspace

```
autopilot/
├─ configs/          # Baseline config templates consumed by loop.py
├─ scripts/          # Non-interactive entry points (training, Codex shim)
├─ prompts/          # Codex prompt templates
├─ journal/          # `labbook.md` and long-form notes
├─ proposals/        # `next_config.json` override queue
├─ logs/             # Tee'd stdout/stderr from training runs
├─ runs/             # One folder per run (config, summary, notes, diff, trainer_summary.json)
├─ schemas/          # Validation ranges (if extended)
├─ helpers.py        # Validation and journaling utilities
└─ loop.py           # Orchestrator driving Codex + training
```

Usage:
- Launch runs via `python3 autopilot/loop.py --runs N --mode {quick,full}`.
- Each iteration copies `configs/`->`runs/<run_id>/config.json`, clears `proposals/next_config.json`, then calls Codex to run the training script.
- Training scripts invoke `scripts/render_cli_args.py` so the merged config drives every launch—override the JSON to change batch sizes, worker counts, etc.
 - You can select the environment via a top-level `env_name` in the config (e.g., `"puffer_drone_pp"` or `"puffer_drone_pickplace"`). The training script reads this value and passes it as the positional environment argument.
- After the run, Codex (or a human) should review `runs/<run_id>/trainer_summary.json` or the mirrored log and write the **next** overrides back into `proposals/next_config.json` (stay within the whitelisted keys/ranges).
- Inspect results under `runs/<run_id>/` (look for `trainer_summary.json`, `summary.json`, `train.log`, `notes.txt`) and keep the journal up to date.
 - Warm start: set `autopilot.resume_mode: "continue"` and `autopilot.resume_from: "latest" | "best" | "/path/to/model.pt"` in the override to reuse a prior checkpoint. The orchestrator will inject `--load-model-path` for you and record the chosen source in the summary. Control artifact retention with `autopilot.save_strategy: "best" | "latest" | "all"` (default: `best`).

Baseline profiles (M3 Ultra):
- Quick: `vec 4/4`, `env 4×8`, `bptt 16`, `batch 2048`, `total_timesteps 1e6` (~1 minute smoke test).
- Full: `vec 28/56`, `env 4×8`, `bptt 16`, `batch 28672`, `total_timesteps 1e7`, checkpoint 200 (~5–6 minutes; see `autopilot/configs/baseline_full.json`).

Allowed knobs & constraints for the agent:
- Whitelisted keys (post‑run only):
  - Core PPO scalars: `train.learning_rate`, `train.ent_coef`, `train.seed`, `train.bptt_horizon`, `train.update_epochs`, `train.gae_lambda`, `train.gamma`, `train.clip_coef`, `train.vf_clip_coef`, `train.total_timesteps`.
  - Optimiser & stability: `train.optimizer` (`muon`/`adam`/`adamw`), `train.vf_coef`, `train.max_grad_norm`, `train.checkpoint_interval`, `train.adam_beta1`, `train.adam_beta2`, `train.adam_eps`.
  - Schedule & determinism: `train.anneal_lr`, `train.torch_deterministic`, `train.cpu_offload`, `train.compile`, `train.compile_fullgraph`, `train.precision`, `train.compile_mode` (pick documented values).
- Device & topology: `train.device`, `env.num_envs`, `env.num_drones`, `vec.num_workers`, `vec.num_envs`.
 - Autopilot policy (not CLI flags): `autopilot.resume_mode`, `autopilot.resume_from`, `autopilot.save_strategy`.
- Constraints to avoid stalls:
  - Divisibility: `vec.num_envs % vec.num_workers == 0`.
  - Segments rule: set `train.batch_size = (env.num_envs × env.num_drones × vec.num_envs) × train.bptt_horizon`.
  - Match: set `train.minibatch_size = train.batch_size = train.max_minibatch_size` (until gradient accumulation is introduced).
  - Device: prefer `mps`; `cpu` is allowed for diagnostics (expect slower wall-clock times) and log the rationale in the labbook.
 - The launcher normalizes the config at runtime to enforce the divisibility and batch-size rules above. If `vec.num_envs` is not divisible by `vec.num_workers`, it rounds `vec.num_envs` up to the nearest multiple, then derives `train.batch_size = train.minibatch_size = train.max_minibatch_size` from the product `(env.num_envs × env.num_drones × vec.num_envs × train.bptt_horizon)`.

Workflow expectations:
- The agent proposes changes by writing JSON to `proposals/next_config.json` after a run completes. Include the derived `train.batch_size` and `train.minibatch_size` per the rule above.
- The orchestrator clears this file before each launch so any content must come from the most recent run’s decision.
- Each run folder under `runs/<run_id>/` contains: `config.json` (applied), `override.json` (proposal used), `train.log`, `trainer_summary.json` (structured metrics incl. SPS/steps/epoch), `summary.json` (final snapshot), and `notes.txt`.
- Codex runs must start by executing `./scripts/run_training.sh` (from repo root with `bash -lc`) and grant at least 15 minutes before timeout; if no new log appears under `logs/`, treat that iteration as failed and rerun.
- Encourage the agent to review recent `runs/<run_id>/summary.json` and `notes.txt` files so proposals account for trends across iterations, not just the latest metrics.
 - Best/latest artifacts: the orchestrator maintains `autopilot/models/latest.pt` and (when improved) `autopilot/models/best.pt` plus `autopilot/runs/best.json`. Summaries stamp `resume_mode`/`resume_from` so you can audit warm starts.

Troubleshooting tips:
- If the trainer “sticks” after a brief CPU spike, check divisibility (`vec.num_envs % vec.num_workers`) and the batch rule above.
- First MPS use per process can appear idle for 30–60s during kernel compilation — tee logs and wait before assuming a hang.
- Use `scripts/peak_probe.sh <workers> <vec_envs> [env_envs] [drones] [batch] [minibatch] [timesteps] [device]` to sweep for stable, high‑util configs; results land in `logs/peak/`.
