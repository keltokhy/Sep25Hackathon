# Repository Guidelines

## Project Structure & Module Organization
- Core library code lives in `PufferLib/pufferlib/`; environment logic is under `pufferlib/ocean/` and reusable utilities under `pufferlib/vector/`, `pufferlib/pytorch/`, etc.
- Experiment artifacts and checkpoints are written to `PufferLib/experiments/`, while reference configs live in `PufferLib/pufferlib/config/`.
- Tests reside in `PufferLib/tests/`; asset bundles (raylib, box2d, shaders) are stored in `PufferLib/resources/`.

## Build, Test, and Development Commands
- `pip install -e PufferLib` — install the library in editable mode for local iteration.
- `python3 PufferLib/setup.py build_ext --inplace --force` — rebuild native extensions (required after touching C/C++ bindings).
- `pytest PufferLib/tests -k <pattern>` — run the test suite or target subsets during development.
- `python3 -m pufferlib.pufferl train puffer_drone_pp --train.device mps --train.total-timesteps 200000000 --train.bptt-horizon 16 --vec.num-workers 20 --vec.num-envs 20 --env.num-envs 32 --env.num-drones 32 --train.checkpoint-interval 100 --wandb` — known-good Mac Studio M3 Ultra config for the drone trainer; adjust worker/env counts if thermals clamp.

## Experiment Logging & Lab Notes
- Treat `labbook.md` as the primary logbook: append entries with timestamped, structured bullets (action, observation, outcome, next steps) whenever you run experiments, tweak configs, or hit notable issues.
- Capture tricks, anomalies, and environment-specific gotchas immediately; this avoids knowledge loss between training sessions and informs future patches.

## Coding Style & Naming Conventions
- Follow PEP 8 with 4-space indentation; prefer descriptive snake_case for Python symbols and CapWords for classes.
- Keep C headers consistent with existing style (brace on new line, ALL_CAPS macros).
- Use type hints in new Python modules and keep docstrings concise; mirror existing logger and config patterns when extending the training CLI.

## Testing Guidelines
- Targeted tests should live beside related modules inside `PufferLib/tests/`; name files `test_<area>.py` and parametrise with pytest where possible.
- When editing C/C++ bindings, rebuild extensions and rerun `pytest PufferLib/tests/test_env_binding.py` to ensure ABI compatibility.
- Aim to keep new features covered by deterministic unit tests; document any stochastic behaviours in test comments.

## Commit & Pull Request Guidelines
- Craft commit messages in the imperative mood (`add`, `fix`, `refactor`) and keep every commit atomic—one logical change per commit that passes tests and rebuilds cleanly.
- Squash unrelated work; each commit should build and test cleanly (`pytest` + extension build if relevant).
- Pull requests should summarise the change, log notable labbook entries, list verification steps (commands executed, benchmarks), and link issues or lab notes when available; attach screenshots for UI/visual tooling changes.
