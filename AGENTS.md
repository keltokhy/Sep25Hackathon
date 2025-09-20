# Repository Guidelines

## Project Structure
- Core library code lives in `PufferLib/pufferlib/`; configs in `pufferlib/config/`; shared assets in `PufferLib/resources/`.
- The autopilot workspace sits under `autopilot/` with key subdirectories:
  - `configs/` for baseline run templates.
  - `scripts/` for training and Codex wrappers.
  - `journal/` containing `labbook.md` and `notes.md`.
  - `prompts/`, `proposals/`, `logs/`, and `runs/` for agent interaction and artifacts.

## Build & Run
- `pip install -e PufferLib` — editable install for local hacking.
- `python3 PufferLib/setup.py build_ext --inplace --force` — rebuild native extensions after touching C/CUDA sources.
- `pytest PufferLib/tests -k <pattern>` — run the full test suite or targeted subsets.
- `python3 -m pufferlib.pufferl train puffer_drone_pp --train.device mps --train.total-timesteps 200000000 --train.bptt-horizon 16 --vec.num-workers 20 --vec.num-envs 20 --env.num-envs 32 --env.num-drones 32 --train.checkpoint-interval 100 --wandb` — reference command for full training on Mac Studio; tune worker/env counts as needed.
- `python3 -m pufferlib.pufferl train puffer_drone_pp --train.device mps --train.total-timesteps 10000000 --train.bptt-horizon 16 --vec.num-workers 28 --vec.num-envs 56 --env.num-envs 4 --env.num-drones 8 --train.batch-size 28672 --train.minibatch-size 28672 --train.max-minibatch-size 28672 --train.checkpoint-interval 200` — default “full” baseline (~5–6 minutes) used by the autopilot.

## Experiment Logging & Autopilot Workflow
- `autopilot/journal/labbook.md` is the canonical audit log—record every meaningful action, hypothesis, and follow-up there immediately after the run; mirror key observations in `autopilot/journal/notes.md` when longer context helps.
- The Codex agent must execute `autopilot/scripts/run_training.sh` immediately (from repo root via `bash -lc`) with a timeout budget of at least 15 minutes; monitor for missing logs and rerun if that step is skipped.
- Before proposing overrides, scan recent entries in `autopilot/runs/` (summaries, notes, diffs) so adjustments reflect multi-run trends rather than single-episode noise.
- Post-run, read `runs/<run_id>/trainer_summary.json` (or the mirrored `train.log`) and then stage the **next** overrides in `autopilot/proposals/next_config.json`. The loop clears this file before launching the script, so anything present was written after the most recent run. Only touch the whitelisted keys — core PPO scalars (`learning_rate`, `ent_coef`, `bptt_horizon`, `total_timesteps`, `seed`, `update_epochs`, `gae_lambda`, `gamma`, `clip_coef`, `vf_clip_coef`), optimiser/stability knobs (`optimizer`, `vf_coef`, `max_grad_norm`, `checkpoint_interval`, `adam_beta1`, `adam_beta2`, `adam_eps`), schedule/determinism toggles (`anneal_lr`, `torch_deterministic`, `cpu_offload`, `compile`, `compile_fullgraph`, `precision`, `compile_mode`), and topology (`device`, `env.num_envs`, `env.num_drones`, `vec.num_workers`, `vec.num_envs`). Stick to JSON booleans for the toggles and keep every value inside the documented ranges; write `{}` if you want to keep the baseline. The training scripts consume the saved config directly, so every override takes effect on the very next launch.
 - Warm starts are supported. Use the autopilot-only fields in the override to control resume and artifact policy (these are handled by the orchestrator and are not passed to the trainer CLI):
   - `autopilot.resume_mode`: `fresh` (default) or `continue`.
   - `autopilot.resume_from`: `latest`, `best`, or an explicit checkpoint path.
   - `autopilot.save_strategy`: `best` (default), `latest`, or `all`.
   The orchestrator injects `--load-model-path` when resuming and maintains `autopilot/models/latest.pt` and `autopilot/models/best.pt` plus `autopilot/runs/best.json`.
- Keep `vec.num_envs` divisible by `vec.num_workers` (e.g., on a 28‑core Mac Studio: workers 28 with envs 28/56/84). Note any tuning in the labbook for reproducibility.
- Capture run-specific rationale in `runs/<run_id>/notes.txt` and summarise longer-term heuristics back in the labbook so future iterations inherit the learning.

## Autopilot Baseline & Knobs
- Full baseline (high‑util on M3 Ultra) is encoded in `autopilot/configs/baseline_full.json`: `vec 28/56`, `env 4×8`, `bptt 16`, `batch 28672`.
- Expect one full iteration to complete in roughly 5–6 minutes; use the quicker baseline (`baseline_quick.json`, ~1 minute) for rapid smoke checks.
- Agent may change, post-run only:
  - Core PPO scalars: `train.learning_rate`, `train.ent_coef`, `train.seed`, `train.bptt_horizon`, `train.update_epochs`, `train.gae_lambda`, `train.gamma`, `train.clip_coef`, `train.vf_clip_coef`, `train.total_timesteps`.
  - Optimiser & stability: `train.optimizer`, `train.vf_coef`, `train.max_grad_norm`, `train.checkpoint_interval`, `train.adam_beta1`, `train.adam_beta2`, `train.adam_eps`.
  - Schedule & determinism: `train.anneal_lr`, `train.torch_deterministic`, `train.cpu_offload`, `train.compile`, `train.compile_fullgraph`, `train.precision`, `train.compile_mode`.
  - Device & topology: `train.device`, `env.num_envs`, `env.num_drones`, `vec.num_workers`, `vec.num_envs`.
- Always enforce:
  - `vec.num_envs % vec.num_workers == 0`.
  - `train.batch_size = (env.num_envs × env.num_drones × vec.num_envs) × train.bptt_horizon`.
  - `train.minibatch_size = train.batch_size = train.max_minibatch_size`.
  - Record rationale and observed SPS/utilization in `journal/labbook.md`.
- `train.device` should typically stay on `mps`; switch to `cpu` only for diagnostics and log the slower runtime expectations.

## Performance Tuning
- The Mac Studio (M3 Ultra) can usually handle higher concurrency—bump `vec.num_workers`, `vec.num_envs`, and `env.num_envs` via `proposals/next_config.json` until the `train.log` utilisation panel shows sustained 90%+ CPU without throttling.
- To push the GPU, raise `env.num_drones` or `train.batch_size` cautiously and set `PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.0` before launching to let Metal use the full VRAM budget.
- Keep `OMP_NUM_THREADS`/`MKL_NUM_THREADS` aligned with available cores (e.g., 24–32) so Python workers don’t starve; record any tuning in `journal/labbook.md` for reproducibility.
- For stability and throughput, set `train.batch_size = (env.num_envs × env.num_drones × vec.num_envs) × train.bptt_horizon`. This ensures segment count equals total agents and avoids tensor size errors.
- Known-good high‑utilization presets on M3 Ultra:
  - Quick: `vec 4/4`, `env 4×8`, `batch 2048`, `bptt 16` (already in baseline_quick).
  - Full: `vec 28/56`, `env 4×8`, `batch 28672`, `bptt 16`, `total_timesteps 1e7`, checkpoint 200 (in baseline_full, ~5–6 minutes).

## Atomic Commits & Notes Discipline
- Treat each run and any proposal as an atomic commit: config, logs, summary, and labbook entry must land together. Use imperative messages (e.g., “tune lr to 3e-3; +1.2% SPS”).
- Keep meticulous notes in `autopilot/journal/labbook.md`: actions, observations (SPS, CPU%), outcome, next step. This is the primary audit trail for the autopilot loop.
 - When warm-starting, record the resume policy (`fresh`/`continue`) and source (`latest`/`best`/path) in both the run `summary.json` and the labbook entry for traceability and reproducibility.

## Coding Style
- Follow PEP 8 (4-space indent, snake_case functions, CapWords classes).
- Match the existing C style: braces on new lines, ALL_CAPS macros, minimal inline comments.
- Use type hints and concise docstrings in new Python modules; mirror the existing logging/config patterns.

## Testing Expectations
- Co-locate new tests under `PufferLib/tests/` (use `test_<area>.py` naming) and prefer pytest parametrisation.
- Rebuild extensions and rerun `pytest PufferLib/tests/test_env_binding.py` whenever native bindings change.
- Add deterministic coverage for new features; document any stochastic behaviour directly in the test.

## Commit & PR Hygiene
- Always craft imperative, atomic commits (`add`, `fix`, `refactor`) for every change; treat each run + adjustment as a self-contained commit with verification noted in the message.
- Summarise changes and verification steps in PR descriptions, link issues or lab notes, and include screenshots when altering tooling with UI impact.
