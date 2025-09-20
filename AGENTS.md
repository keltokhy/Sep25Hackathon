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
- The Codex agent must execute `bash -lc 'timeout 900 ./autopilot/scripts/run_training.sh'` as its first command each iteration; monitor for missing logs and rerun if that step is skipped.
- Post-run, read `runs/<run_id>/trainer_summary.json` (or the mirrored `train.log`) and then stage the **next** overrides in `autopilot/proposals/next_config.json`. The loop clears this file before launching the script, so anything present was written after the most recent run. Only touch the whitelisted keys (learning_rate, ent_coef, batch/minibatch/max_minibatch, bptt_horizon, update_epochs, gae_lambda, gamma, clip_coef, vf_clip_coef, total_timesteps, seed, device, env/vec counts) and keep values within range; write `{}` if you want to keep the baseline. The training scripts consume the saved config directly, so every override takes effect on the very next launch.
- Keep `vec.num_envs` divisible by `vec.num_workers` (e.g., on a 28‑core Mac Studio: workers 28 with envs 28/56/84). Note any tuning in the labbook for reproducibility.
- Capture run-specific rationale in `runs/<run_id>/notes.txt` and summarise longer-term heuristics back in the labbook so future iterations inherit the learning.

## Autopilot Baseline & Knobs
- Full baseline (high‑util on M3 Ultra) is encoded in `autopilot/configs/baseline_full.json`: `vec 28/56`, `env 4×8`, `bptt 16`, `batch 28672`.
- Expect one full iteration to complete in roughly 5–6 minutes; use the quicker baseline (`baseline_quick.json`, ~1 minute) for rapid smoke checks.
- Agent may change, post-run only: `train.learning_rate`, `train.ent_coef`, `train.seed`, `train.bptt_horizon`, `train.update_epochs`, `train.gae_lambda`, `train.gamma`, `train.clip_coef`, `train.vf_clip_coef`, `train.device`, `env.num_envs`, `env.num_drones`, `vec.num_workers`, `vec.num_envs`.
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
