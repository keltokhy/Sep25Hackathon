"""Support utilities for labbook logging, config validation, and run bookkeeping."""

from __future__ import annotations

import json
import datetime as dt
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union

AUTOPILOT_DIR = Path(__file__).resolve().parent
JOURNAL_DIR = AUTOPILOT_DIR / "journal"
RUNS_DIR = AUTOPILOT_DIR / "runs"

LABBOOK_PATH = JOURNAL_DIR / "labbook.md"
NOTES_PATH = JOURNAL_DIR / "notes.md"


class ValidationError(RuntimeError):
    """Raised when a proposed config or summary violates schema."""


Number = Union[int, float]

CONFIG_RANGES: Dict[Tuple[str, str], Tuple[type, Number, Number]] = {
    ("train", "learning_rate"): (float, 1e-6, 1.0),
    ("train", "ent_coef"): (float, 0.0, 1.0),
    ("train", "batch_size"): (int, 64, 65536),
    ("train", "minibatch_size"): (int, 64, 65536),
    ("train", "max_minibatch_size"): (int, 64, 65536),
    ("train", "bptt_horizon"): (int, 1, 512),
    ("train", "update_epochs"): (int, 1, 32),
    ("train", "gae_lambda"): (float, 0.0, 1.0),
    ("train", "gamma"): (float, 0.0, 0.999999),
    ("train", "clip_coef"): (float, 0.0, 1.0),
    ("train", "vf_clip_coef"): (float, 0.0, 10.0),
    ("train", "total_timesteps"): (int, 1_000, 1_000_000_000),
    ("train", "seed"): (int, 0, 2_147_483_647),
    ("env", "num_envs"): (int, 1, 256),
    ("env", "num_drones"): (int, 1, 256),
    ("vec", "num_envs"): (int, 1, 256),
    ("vec", "num_workers"): (int, 1, 256),
}

SUMMARY_REQUIRED = {"run_id", "timestamp", "config_diff"}
SUMMARY_OPTIONAL_FLOATS = {"success_rate", "mean_reward", "episode_length"}


def timestamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def append_labbook(action: str, observation: str, outcome: str, next_step: str = "") -> None:
    JOURNAL_DIR.mkdir(parents=True, exist_ok=True)
    entry = f"- {timestamp()} | {action} | {observation} | {outcome} | {next_step}\n"
    with LABBOOK_PATH.open("a", encoding="utf-8") as fp:
        fp.write(entry)


def _ensure_section(cfg: Dict[str, Any], key: str) -> Dict[str, Any]:
    if key not in cfg or not isinstance(cfg[key], dict):
        raise ValidationError(f"Config missing '{key}' section or it is not a dict")
    return cfg[key]


def _check_range(value: Any, expected_type: type, low: Number, high: Number, path: str) -> None:
    if not isinstance(value, expected_type):
        raise ValidationError(f"Config field '{path}' must be {expected_type.__name__}, got {type(value).__name__}")
    if not (low <= value <= high):
        raise ValidationError(f"Config field '{path}' out of range [{low}, {high}]: {value}")


def validate_config(config: Dict[str, Any]) -> None:
    if not isinstance(config, dict):
        raise ValidationError("Config must be a dictionary")

    sections: Dict[str, Dict[str, Any]] = {}
    for section, field in {(s, f) for s, f in CONFIG_RANGES.keys()}:
        if section not in sections:
            sections[section] = _ensure_section(config, section)

    for (section, field), (expected_type, low, high) in CONFIG_RANGES.items():
        sec = sections[section]
        if field not in sec:
            continue  # allow missing fields; defaults may apply elsewhere
        _check_range(sec[field], expected_type, low, high, f"{section}.{field}")

    train = sections.get("train", {})
    if {"batch_size", "minibatch_size"}.issubset(train):
        if train["batch_size"] < train["minibatch_size"]:
            raise ValidationError("train.batch_size must be >= train.minibatch_size")

    device = train.get("device")
    if device is not None and device not in {"mps", "cpu", "cuda"}:
        raise ValidationError("train.device must be one of {'mps', 'cpu', 'cuda'}")


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
    if not isinstance(summary["config_diff"], str):
        raise ValidationError("Summary config_diff must be a string (JSON)")

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
    validate_config(config)
    config_path = run_dir / "config.json"
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return config_path


def diff_configs(prev_config: Dict[str, Any], new_config: Dict[str, Any]) -> Dict[str, Any]:
    diff: Dict[str, Any] = {}
    keys = set(prev_config.keys()) | set(new_config.keys())
    for key in sorted(keys):
        prev_val = prev_config.get(key)
        new_val = new_config.get(key)
        if prev_val == new_val:
            continue
        if isinstance(prev_val, dict) and isinstance(new_val, dict):
            nested = diff_configs(prev_val, new_val)
            if nested:
                diff[key] = nested
        else:
            diff[key] = {"old": prev_val, "new": new_val}
    return diff


__all__ = [
    "append_labbook",
    "validate_config",
    "validate_summary",
    "register_run",
    "write_summary",
    "save_config",
    "diff_configs",
    "list_runs",
    "timestamp",
    "ValidationError",
]
