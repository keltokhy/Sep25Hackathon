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
- After the run, Codex (or a human) should review `runs/<run_id>/trainer_summary.json` or the mirrored log and write the **next** overrides back into `proposals/next_config.json` (stay within the whitelisted keys/ranges).
- Inspect results under `runs/<run_id>/` (look for `trainer_summary.json`, `summary.json`, `train.log`, `notes.txt`) and keep the journal up to date.

Baseline profiles (M3 Ultra):
- Quick: `vec 4/4`, `env 4×8`, `bptt 16`, `batch 2048`, `total_timesteps 1e6` (~1 minute smoke test).
- Full: `vec 28/56`, `env 4×8`, `bptt 16`, `batch 28672`, `total_timesteps 1e7`, checkpoint 200 (~5–6 minutes; see `autopilot/configs/baseline_full.json`).

Allowed knobs & constraints for the agent:
- Whitelisted keys (post‑run only):
  - train: `learning_rate`, `ent_coef`, `seed`, `bptt_horizon`, `update_epochs`, `gae_lambda`, `gamma`, `clip_coef`, `vf_clip_coef`, `device`.
  - env: `num_envs`, `num_drones`.
  - vec: `num_workers`, `num_envs`.
- Constraints to avoid stalls:
  - Divisibility: `vec.num_envs % vec.num_workers == 0`.
  - Segments rule: set `train.batch_size = (env.num_envs × env.num_drones × vec.num_envs) × train.bptt_horizon`.
  - Match: set `train.minibatch_size = train.batch_size = train.max_minibatch_size` (until gradient accumulation is introduced).
  - Device: prefer `mps`; `cpu` is allowed for diagnostics (expect slower wall-clock times) and log the rationale in the labbook.

Workflow expectations:
- The agent proposes changes by writing JSON to `proposals/next_config.json` after a run completes. Include the derived `train.batch_size` and `train.minibatch_size` per the rule above.
- The orchestrator clears this file before each launch so any content must come from the most recent run’s decision.
- Each run folder under `runs/<run_id>/` contains: `config.json` (applied), `override.json` (proposal used), `train.log`, `trainer_summary.json` (structured metrics incl. SPS/steps/epoch), `summary.json` (final snapshot), and `notes.txt`.
- Codex runs must start by executing `bash -lc './scripts/run_training.sh'`; if no new log appears under `logs/`, treat that iteration as failed and rerun.

Troubleshooting tips:
- If the trainer “sticks” after a brief CPU spike, check divisibility (`vec.num_envs % vec.num_workers`) and the batch rule above.
- First MPS use per process can appear idle for 30–60s during kernel compilation — tee logs and wait before assuming a hang.
- Use `scripts/peak_probe.sh <workers> <vec_envs> [env_envs] [drones] [batch] [minibatch] [timesteps] [device]` to sweep for stable, high‑util configs; results land in `logs/peak/`.
