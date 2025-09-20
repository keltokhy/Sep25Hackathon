# Autopilot Build Plan

## Objectives
- Stand up a reproducible "autopilot" workspace where every decision, run, and artifact is captured for auditing.
- Provide non-interactive entry points so automation (Codex/Claude) can launch training and evaluation without human prompts.
- Enforce guardrails (config-only edits, schema validation, rollback) while the system proves it can improve metrics reliably.

## Directory Layout
- `autopilot/configs/` — baseline configs (`baseline_quick.json`, `baseline_full.json`).
- `autopilot/scripts/` — training launchers and Codex wrappers.
- `autopilot/prompts/` — Codex instruction templates.
- `autopilot/journal/` — `labbook.md` and `notes.md` for structured logging.
- `autopilot/proposals/next_config.json` — override file Codex may edit between runs.
- `autopilot/logs/` — raw stdout/stderr captures; `autopilot/runs/` — per-run snapshots (config/summary/notes, archived overrides).

## Execution Surface
- Codex calls use `--dangerously-bypass-approvals-and-sandbox`; ensure this remains acceptable for your environment.
- `autopilot/scripts/run_training.sh`: activates venv, renders CLI args from `runs/<run_id>/config.json` via `scripts/render_cli_args.py`, then launches training (used for both quick and full modes).
- `autopilot/scripts/run_codex.py`: one-off helper to trigger Codex manually.
- Scripts should ultimately emit structured output so agents avoid parsing terminal noise (current tee logging is temporary).

## Orchestrator Loop (`autopilot/loop.py`)
- Each iteration merges overrides from `autopilot/proposals/next_config.json`, validates them, and archives the applied proposal in the run folder. The file is immediately cleared so the agent can write the **next** proposal after the run completes.
- Codex executions receive `PUFFER_AUTOPILOT_RUN_DIR` and `PUFFER_AUTOPILOT_SUMMARY` so they can inspect run artifacts before staging the next override.
- Training emits structured metrics to `trainer_summary.json`; the loop ingests those summaries (falling back to log scraping when absent).
- Orchestrator drives training via Codex (`codex exec`), so prompts must stay in sync with allowed scripts; logs are mirrored into each run folder for parsing.
1. **Bootstrap Run 001**: copy baseline config, launch full train, collect `summary.json`, log findings.
2. **For Run _i_ ≥ 2**:
   - Read `journal/labbook.md`, `journal/notes.md`, and the latest `summary.json`.
   - Evaluate previous result (improved / regressed / inconclusive) using statistical criteria (bootstrap CI, etc.).
   - Generate next proposal: initially whitelist config keys (lr, batch size, entropy, etc.); validate against safe ranges.
   - Write proposal to `autopilot/proposals/run_{i}.json`, log rationale + hypotheses, launch the appropriate script.
   - Record run metadata and append structured notes.

## Guardrails & Instrumentation
- Config range validation before every run; reject edits outside the safe set.
- Enforce seed tagging, checkpoint naming, WandB/Neptune logging plus local JSON mirrors.
- Implement timeouts + kill switches for hung runs; mark failures in both labbook and summary reports.
- Maintain rollback by keeping prior configs and git commits atomic per run.

## Next Steps
- Structured trainer summaries now exist; validate contents and expand metrics as the optimization loop matures.
1. Verify the new `trainer_summary.json` covers the metrics the decision policy needs; extend with additional stats if required.
2. Teach the agent decision logic: read the last summary, evaluate improvement significance, and justify any config overrides in journal notes.
3. Dry-run `loop.py` end-to-end with the new metrics and document regression expectations before enabling full runs.
4. Extend to evaluation runs/checkpoint comparisons once decision logic is stable.
