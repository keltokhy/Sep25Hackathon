# DREX - Drone Research Explorer

An intelligent autopilot system that understands drone behavior and selects appropriate experiments based on what's actually failing.

```
autopilot/
├─ configs/          # Baseline config templates consumed by loop.py
├─ scripts/          # Non-interactive entry points (training, Codex shim)
├─ prompts/          # Codex prompt templates
├─ journal/          # `labbook.md` and long-form notes
├─ proposals/        # `next_config.json` override queue
├─ logs/             # Live training stdout/stderr (tee target during run)
├─ runs/             # One folder per run (config, summary, notes, diff, trainer_summary.json)
├─ schemas/          # Validation ranges (if extended)
├─ helpers.py        # Validation and journaling utilities
└─ loop.py           # Orchestrator driving Codex + training
```

## Key Features

### Behavioral Analysis
DREX analyzes training metrics to understand what the drone is actually doing:
- **Grip Detection**: Is the drone attempting to grip objects?
- **Delivery Chain**: Can it grip but not deliver? Navigation issue?
- **Stability Issues**: High collision rate? Control problems?
- **Performance Ready**: Everything working? Ready for optimization?

### Intelligent Experiment Selection
Based on behavioral analysis, DREX selects appropriate experiments:
- `diagnostic_grip` → Quick 100K-500K timestep runs to debug grip issues
- `improve_carrying` → Medium 1-5M runs to fix navigation/carrying
- `optimize_performance` → Full 10M+ runs when basics work

### No‑HParam Changes Policy
- DREX does not modify any training hyperparameters or topology (`train.*`, `env.*`, `vec.*`).
- Baselines in `autopilot/configs/` (reflecting upstream defaults) are treated as canonical.
- Only `autopilot.*` fields (`resume_mode`, `resume_from`, `save_strategy`) may be set in `proposals/next_config.json`; otherwise leave `{}`.
- The orchestrator enforces this by ignoring non‑autopilot keys in overrides.

### Metrics Tracking
- **Grip Success Rate** (`perfect_grip`)
- **Delivery Success Rate** (`perfect_deliv`)
- **End-to-End Success** (`perfect_now`)
- **Behavioral Diagnostics** (attempts, hovering, collisions)

Usage:
- Launch runs via `python3 autopilot/loop.py --runs N --mode {quick,full}`.
- Each iteration copies `configs/`->`runs/<run_id>/config.json`, clears `proposals/next_config.json`, then calls the training script.
- The training script reads the top‑level `env_name` (e.g., `"puffer_drone_pp"`) and passes it as the positional environment argument.
- After the run, review `runs/<run_id>/trainer_summary.json` or the mirrored log and write the **next** overrides back into `proposals/next_config.json`.
  - With no‑hparam policy enabled, only `autopilot.*` keys are honored; all other keys are ignored.
- Inspect results under `runs/<run_id>/` (look for `trainer_summary.json`, `summary.json`, `train.log`, `notes.txt`) and keep the journal up to date.
 - Warm start: set `autopilot.resume_mode: "continue"` and `autopilot.resume_from: "latest" | "best" | "/path/to/model.pt"` in the override to reuse a prior checkpoint. The orchestrator will inject `--load-model-path` for you and record the chosen source in the summary. Control artifact retention with `autopilot.save_strategy: "best" | "latest" | "all"` (default: `best`).

Baseline profiles:
- Quick (default for iteration): `vec 4/4`, `env 4×8`, `bptt 64`, `batch 2048`, `total_timesteps 1e6`. Intended as a ~1 minute smoke test to collect behavioral evidence.
- Full (Dan’s defaults; heavy): `vec 28/56`, `env 4×8`, `bptt 64`, `batch 28672`, `total_timesteps 2e8`, checkpoint 200 (see `autopilot/configs/baseline_full.json`). Use sparingly; most loops should stay on quick until behavior is correct.

Allowed knobs & constraints for the agent:
- With the no‑hparam policy enabled, only `autopilot.*` keys are honored (`resume_mode`, `resume_from`, `save_strategy`). Other keys will be ignored by the orchestrator and logged to the labbook.
- Constraints for baseline configs:
  - Divisibility: `vec.num_envs % vec.num_workers == 0`.
  - Segments rule: set `train.batch_size = (env.num_envs × env.num_drones × vec.num_envs) × train.bptt_horizon`.
  - Match: set `train.minibatch_size = train.batch_size = train.max_minibatch_size` (until gradient accumulation is introduced).
  - Device: prefer `mps`; `cpu` is allowed for diagnostics (expect slower wall-clock times) and log the rationale in the labbook.
 - EXACT_CONFIG: By default the orchestrator exports `EXACT_CONFIG=1`, so the training script passes the config through unchanged (no normalization). Unset this env var during manual experiments to let the script normalize batch sizes and divisibility.

Workflow expectations:
- The agent proposes changes by writing JSON to `proposals/next_config.json` after a run completes. Do not include hparams; only `autopilot.*` is honored.
- The orchestrator clears this file before each launch so any content must come from the most recent run’s decision.
- Each run folder under `runs/<run_id>/` contains: `config.json` (applied), `override.json` (proposal used), `train.log` (mirrored), `trainer_summary.json`, `summary.json`, and `notes.txt`.
- Codex runs must start by executing `./scripts/run_training.sh` (from repo root with `bash -lc`) and grant at least 15 minutes before timeout; if no new log appears under `autopilot/logs/`, treat that iteration as failed and rerun.
- Encourage reviewing recent `runs/<run_id>/summary.json` and `notes.txt` files so proposals account for trends across iterations, not just the latest metrics.
- Best/latest artifacts: the orchestrator maintains `autopilot/models/latest.pt` and (when improved) `autopilot/models/best.pt` plus `autopilot/runs/best.json`. Summaries stamp `resume_mode`/`resume_from` so you can audit warm starts.

Comparisons, notes template, and digests:
- Summaries now include `deltas.vs_previous` and `deltas.vs_baseline` (baseline defaults to `runs/best.json`).
- To pin a specific baseline, create `autopilot/runs/baseline.json` with at least `{ "run_id": "<run_id>" }`.
- The orchestrator pre-fills `runs/<run_id>/notes.txt` with a structured template (snapshot, comparisons, interaction effects, decision, next override). Fill it after each run.
 - For a large-context digest (Gemini CLI), save per-run: `autopilot/runs/<run_id>/gemini_summary.md` and `gemini_session.json`.

Troubleshooting tips:
- If the trainer “sticks” after a brief CPU spike, check divisibility (`vec.num_envs % vec.num_workers`) and the batch rule above.
- First MPS use per process can appear idle for 30–60s during kernel compilation — tee logs and wait before assuming a hang.
- Use `scripts/peak_probe.sh <workers> <vec_envs> [env_envs] [drones] [batch] [minibatch] [timesteps] [device]` to sweep for stable, high‑util configs; results land in `logs/peak/`.
