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
