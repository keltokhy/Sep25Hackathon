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

## Experiment Logging & Autopilot Workflow
- `autopilot/journal/labbook.md` is the canonical audit log—record every meaningful action, hypothesis, and follow-up there immediately after the run; mirror key observations in `autopilot/journal/notes.md` when longer context helps.
- Post-run, read `runs/<run_id>/trainer_summary.json` (or the mirrored `train.log`) and then stage the **next** overrides in `autopilot/proposals/next_config.json`. The loop clears this file before launching the script, so anything present was written after the most recent run. Only touch the whitelisted keys (learning_rate, ent_coef, batch/minibatch/max_minibatch, bptt_horizon, total_timesteps, seed, env/vec counts) and keep values within range; write `{}` if you want to keep the baseline. The training scripts consume the saved config directly, so every override takes effect on the very next launch.
- Keep `vec.num_envs` divisible by `vec.num_workers` (e.g., on a 28‑core Mac Studio: workers 28 with envs 28/56/84). Note any tuning in the labbook for reproducibility.
- Capture run-specific rationale in `runs/<run_id>/notes.txt` and summarise longer-term heuristics back in the labbook so future iterations inherit the learning.

## Performance Tuning
- The Mac Studio (M3 Ultra) can usually handle higher concurrency—bump `vec.num_workers`, `vec.num_envs`, and `env.num_envs` via `proposals/next_config.json` until the `train.log` utilisation panel shows sustained 90%+ CPU without throttling.
- To push the GPU, raise `env.num_drones` or `train.batch_size` cautiously and set `PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.0` before launching to let Metal use the full VRAM budget.
- Keep `OMP_NUM_THREADS`/`MKL_NUM_THREADS` aligned with available cores (e.g., 24–32) so Python workers don’t starve; record any tuning in `journal/labbook.md` for reproducibility.

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
