"""Support utilities for labbook logging and run bookkeeping."""

from __future__ import annotations

import json
import datetime as dt
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, List

AUTOPILOT_DIR = Path(__file__).resolve().parent
JOURNAL_DIR = AUTOPILOT_DIR / "journal"
RUNS_DIR = AUTOPILOT_DIR / "runs"
MODELS_DIR = AUTOPILOT_DIR / "models"

LABBOOK_PATH = JOURNAL_DIR / "labbook.md"
NOTES_PATH = JOURNAL_DIR / "notes.md"


class ValidationError(RuntimeError):
    """Raised when a config or summary violates requirements."""


SUMMARY_REQUIRED = {"run_id", "timestamp"}
SUMMARY_OPTIONAL_FLOATS = {"grip_success", "delivery_success", "end_to_end_success", "mean_reward", "episode_length"}


def timestamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def append_labbook(action: str, observation: str, outcome: str, next_step: str = "") -> None:
    JOURNAL_DIR.mkdir(parents=True, exist_ok=True)
    entry = f"- {timestamp()} | {action} | {observation} | {outcome} | {next_step}\n"
    with LABBOOK_PATH.open("a", encoding="utf-8") as fp:
        fp.write(entry)


def validate_autopilot_config(config: Dict[str, Any]) -> None:
    """Only validate autopilot section since we don't change hyperparameters."""
    if not isinstance(config, dict):
        raise ValidationError("Config must be a dictionary")

    # Only check autopilot section if present
    ap = config.get("autopilot", {})
    if ap:
        if not isinstance(ap, dict):
            raise ValidationError("autopilot section must be a dict if present")
        mode = ap.get("resume_mode")
        if mode is not None and mode not in {"fresh", "continue"}:
            raise ValidationError("autopilot.resume_mode must be 'fresh' or 'continue'")
        save = ap.get("save_strategy")
        if save is not None and save not in {"all", "best", "latest"}:
            raise ValidationError("autopilot.save_strategy must be one of {'all','best','latest'}")
        rf = ap.get("resume_from")
        if rf is not None and not isinstance(rf, (str, type(None))):
            raise ValidationError("autopilot.resume_from must be null or a string")


def validate_summary(summary: Dict[str, Any]) -> None:
    if not isinstance(summary, dict):
        raise ValidationError("Summary must be a dictionary")

    missing = SUMMARY_REQUIRED - summary.keys()
    if missing:
        raise ValidationError(f"Summary missing required keys: {', '.join(sorted(missing))}")

    if not isinstance(summary["run_id"], str):
        raise ValidationError("Summary run_id must be a string")
    if not isinstance(summary["timestamp"], str):
        raise ValidationError("Summary timestamp must be a string")

    for key in SUMMARY_OPTIONAL_FLOATS:
        value = summary.get(key)
        if value is None:
            continue
        if not isinstance(value, (int, float)):
            raise ValidationError(f"Summary field '{key}' must be numeric or null")


def register_run(metadata: Dict[str, Any]) -> Path:
    """Create a new run folder with metadata stub and return its path."""
    run_id = metadata.get("run_id") or timestamp().replace(":", "")
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    manifest_path = run_dir / "run.json"
    ordered = OrderedDict([
        ("run_id", run_id),
        ("created_at", timestamp()),
        ("metadata", metadata),
    ])
    manifest_path.write_text(json.dumps(ordered, indent=2), encoding="utf-8")
    return run_dir


def list_runs() -> List[Path]:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    return sorted([p for p in RUNS_DIR.iterdir() if p.is_dir()], key=lambda path: path.name)


def write_summary(run_dir: Path, summary: Dict[str, Any]) -> Path:
    validate_summary(summary)
    summary_path = run_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary_path


def save_config(run_dir: Path, config: Dict[str, Any]) -> Path:
    """Save config to run directory (no validation needed since we use baselines)."""
    config_path = run_dir / "config.json"
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return config_path


__all__ = [
    "append_labbook",
    "validate_autopilot_config",
    "validate_summary",
    "register_run",
    "write_summary",
    "save_config",
    "list_runs",
    "timestamp",
    "ValidationError",
]
