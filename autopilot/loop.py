#!/usr/bin/env python3
"""Autopilot orchestrator skeleton for structured training runs."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

from helpers import (
    append_labbook,
    register_run,
    save_config,
    write_summary,
    diff_configs,
    list_runs,
    timestamp,
    ValidationError,
)

AUTOPILOT_DIR = Path(__file__).resolve().parent
CONFIG_DIR = AUTOPILOT_DIR / "configs"
SCRIPTS_DIR = AUTOPILOT_DIR / "scripts"
PROMPTS_DIR = AUTOPILOT_DIR / "prompts"

BASELINE_CONFIG = CONFIG_DIR / "baseline_full.json"
QUICK_CONFIG = CONFIG_DIR / "baseline_quick.json"
QUICK_SCRIPT = SCRIPTS_DIR / "run_training_quick.sh"
FULL_SCRIPT = SCRIPTS_DIR / "run_training.sh"
CODEX_PROMPT_PATH = PROMPTS_DIR / "codex_prompt.txt"
OVERRIDE_PATH = AUTOPILOT_DIR / "proposals" / "next_config.json"
LOGS_DIR = AUTOPILOT_DIR / "logs"


def load_config(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text())


def extract_metrics(log_path: Path) -> Dict[str, Optional[float]]:
    metrics = {
        "success_rate": None,
        "mean_reward": None,
        "episode_length": None,
    }
    if not log_path.exists():
        return metrics

    try:
        for line in reversed(list(log_path.read_text().splitlines())):
            line = line.strip()
            if not line:
                continue
            if line.startswith("{") and line.endswith("}"):
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                metrics["success_rate"] = metrics["success_rate"] or data.get("environment/perfect_deliv")
                metrics["mean_reward"] = metrics["mean_reward"] or data.get("environment/score")
                metrics["episode_length"] = metrics["episode_length"] or data.get("environment/episode_length")
                if all(v is not None for v in metrics.values()):
                    break
    except UnicodeDecodeError:
        pass

    return metrics


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    result = json.loads(json.dumps(base))  # deep copy
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_override() -> Dict[str, Any]:
    OVERRIDE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not OVERRIDE_PATH.exists():
        return {}
    raw = OVERRIDE_PATH.read_text().strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {OVERRIDE_PATH}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"Override file {OVERRIDE_PATH} must contain a JSON object")
    return data


def load_trainer_summary(run_dir: Path) -> Dict[str, Any]:
    path = run_dir / "trainer_summary.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}


def run_training(script: Path, run_dir: Path) -> Path:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    before = {path: path.stat().st_mtime for path in LOGS_DIR.glob("*.log")}

    prompt_template = CODEX_PROMPT_PATH.read_text().strip()
    repo_root = AUTOPILOT_DIR.parent
    try:
        rel_script = script.relative_to(repo_root)
    except ValueError:
        rel_script = script

    notes_file = run_dir / "notes.txt"
    try:
        rel_notes = notes_file.relative_to(repo_root)
    except ValueError:
        rel_notes = notes_file

    prompt = prompt_template.format(script=str(rel_script), notes_path=str(rel_notes))

    env = os.environ.copy()
    summary_file = run_dir / "trainer_summary.json"
    env["PUFFER_AUTOPILOT_SUMMARY"] = str(summary_file)
    env["PUFFER_AUTOPILOT_RUN_ID"] = run_dir.name
    env["PUFFER_AUTOPILOT_RUN_DIR"] = str(run_dir)

    subprocess.run(
        ["codex", "exec", prompt, "--dangerously-bypass-approvals-and-sandbox"],
        cwd=repo_root,
        check=True,
        env=env,
    )

    candidates = []
    for path in LOGS_DIR.glob("*.log"):
        if path not in before or path.stat().st_mtime > before.get(path, 0):
            candidates.append(path)

    if not candidates:
        raise RuntimeError("Codex run did not produce a new log in autopilot/logs/")

    latest = max(candidates, key=lambda p: p.stat().st_mtime)
    log_path = run_dir / "train.log"
    log_path.write_text(latest.read_text(), encoding="utf-8")

    if not notes_file.exists():
        notes_file.write_text("Notes: pending entry\n", encoding="utf-8")
    return log_path


def summarize(
    run_dir: Path,
    config: Dict[str, Any],
    diff: Dict[str, Any],
    metrics: Dict[str, Optional[float]],
    trainer_summary: Dict[str, Any],
) -> None:
    trainer_metrics = trainer_summary.get("metrics", {}) if trainer_summary else {}
    merged_metrics = dict(metrics)
    for key, value in trainer_metrics.items():
        if value is not None:
            merged_metrics[key] = value

    summary = {
        "run_id": run_dir.name,
        "timestamp": timestamp(),
        "seed": config.get("train", {}).get("seed"),
        "success_rate": merged_metrics.get("success_rate"),
        "mean_reward": merged_metrics.get("mean_reward"),
        "episode_length": merged_metrics.get("episode_length"),
        "config_diff": json.dumps(diff, indent=2) if diff else "{}",
        "artifacts": [],
        "notes": "auto-generated run summary",
    }
    if trainer_summary:
        summary["trainer_summary"] = trainer_summary
    write_summary(run_dir, summary)
    if diff:
        (run_dir / "config_diff.json").write_text(json.dumps(diff, indent=2), encoding="utf-8")


def load_previous_config() -> Optional[Dict[str, Any]]:
    runs = list_runs()
    if not runs:
        return None
    for path in reversed(runs):
        cfg_path = path / "config.json"
        if cfg_path.exists():
            return load_config(cfg_path)
    return None


def run_iteration(iteration: int, use_quick: bool, prev_config: Optional[Dict[str, Any]], parent_run: Optional[str]) -> Dict[str, Any]:
    config_path = QUICK_CONFIG if use_quick else BASELINE_CONFIG
    if not config_path.exists():
        raise SystemExit(f"Missing config template: {config_path}")

    base_config = load_config(config_path)
    override = load_override()
    config = deep_merge(base_config, override) if override else base_config
    diff = diff_configs(prev_config or {}, config)

    metadata = {
        "mode": "quick" if use_quick else "full",
        "config_template": str(config_path.relative_to(AUTOPILOT_DIR)),
        "iteration": iteration,
    }
    if parent_run:
        metadata["parent_run"] = parent_run

    run_dir = register_run(metadata)
    save_config(run_dir, config)
    if override:
        (run_dir / "override.json").write_text(json.dumps(override, indent=2), encoding="utf-8")

    # Clear the staging file so the agent can propose the next override after this run completes.
    OVERRIDE_PATH.parent.mkdir(parents=True, exist_ok=True)
    OVERRIDE_PATH.write_text("{}\n", encoding="utf-8")

    script = QUICK_SCRIPT if use_quick else FULL_SCRIPT
    try:
        log_path = run_training(script, run_dir)
    except (subprocess.CalledProcessError, ValidationError, RuntimeError) as exc:
        append_labbook("run failed", f"{run_dir.name}: {exc}", "halt")
        raise

    trainer_summary = load_trainer_summary(run_dir)
    metrics = extract_metrics(log_path)
    summarize(run_dir, config, diff, metrics, trainer_summary)
    append_labbook(
        "run complete",
        f"Run {run_dir.name} (iteration {iteration})",
        "metrics captured",
    )

    return {
        "config": config,
        "run_dir": run_dir,
        "metrics": metrics,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Autopilot orchestrator loop")
    parser.add_argument("--runs", type=int, default=1, help="Number of iterations to execute")
    parser.add_argument(
        "--mode", choices=("quick", "full"), default="quick", help="Run smoke test or full training"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    use_quick = args.mode == "quick"

    OVERRIDE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not OVERRIDE_PATH.exists():
        OVERRIDE_PATH.write_text("{}\n", encoding="utf-8")

    prev_runs = list_runs()
    parent_run = prev_runs[-1].name if prev_runs else None
    prev_config = load_previous_config()

    for iteration in range(1, args.runs + 1):
        result = run_iteration(iteration, use_quick, prev_config, parent_run)
        prev_config = result["config"]
        parent_run = result["run_dir"].name


if __name__ == "__main__":
    main()
