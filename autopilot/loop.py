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
QUICK_SCRIPT = SCRIPTS_DIR / "run_training.sh"
FULL_SCRIPT = SCRIPTS_DIR / "run_training.sh"
CODEX_PROMPT_PATH = PROMPTS_DIR / "codex_prompt.txt"
OVERRIDE_PATH = AUTOPILOT_DIR / "proposals" / "next_config.json"
LOGS_DIR = AUTOPILOT_DIR / "logs"
MODELS_DIR = AUTOPILOT_DIR / "models"


def load_config(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text())


def extract_metrics(log_path: Path) -> Dict[str, Optional[float]]:
    metrics = {
        # Core objectives (Dan's focus)
        "grip_success": None,          # perfect_grip
        "delivery_success": None,      # perfect_deliv
        "end_to_end_success": None,    # perfect_now (grip AND delivery)

        # Behavioral diagnostics
        "grip_attempts": None,         # to_pickup attempts
        "delivery_attempts": None,     # to_drop attempts
        "hover_efficiency": None,      # ho_pickup (hovering at pickup)

        # Performance context
        "mean_reward": None,
        "episode_length": None,
        "collision_rate": None,
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

                # Extract grip/delivery metrics
                if metrics["grip_success"] is None:
                    metrics["grip_success"] = data.get("environment/perfect_grip")
                if metrics["delivery_success"] is None:
                    metrics["delivery_success"] = data.get("environment/perfect_deliv")
                if metrics["end_to_end_success"] is None:
                    metrics["end_to_end_success"] = data.get("environment/perfect_now")

                # Extract behavioral metrics
                if metrics["grip_attempts"] is None:
                    metrics["grip_attempts"] = data.get("environment/to_pickup")
                if metrics["delivery_attempts"] is None:
                    metrics["delivery_attempts"] = data.get("environment/to_drop")
                if metrics["hover_efficiency"] is None:
                    metrics["hover_efficiency"] = data.get("environment/ho_pickup")

                # Performance metrics
                if metrics["mean_reward"] is None:
                    metrics["mean_reward"] = data.get("environment/score")
                if metrics["episode_length"] is None:
                    metrics["episode_length"] = data.get("environment/episode_length")
                if metrics["collision_rate"] is None:
                    metrics["collision_rate"] = data.get("environment/collision_rate")

                # Check if we have all essential metrics
                essential = ["grip_success", "delivery_success", "mean_reward", "episode_length"]
                if all(metrics.get(k) is not None for k in essential):
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


def experiments_dir() -> Path:
    # PufferLib saves to PufferLib/experiments when launched from that dir
    return (AUTOPILOT_DIR.parent / "PufferLib" / "experiments").resolve()


def latest_final_checkpoint() -> Optional[Path]:
    exp_dir = experiments_dir()
    if not exp_dir.exists():
        return None
    # Accept checkpoints for any env (pp or pickplace) and pick the newest
    candidates = sorted(exp_dir.glob("*.pt"), key=lambda p: p.stat().st_mtime)
    return candidates[-1] if candidates else None


def best_record_path() -> Path:
    return AUTOPILOT_DIR / "runs" / "best.json"


def read_best_score() -> tuple[Optional[float], Optional[float], Optional[str]]:
    bp = best_record_path()
    if not bp.exists():
        return (None, None, None)
    try:
        data = json.loads(bp.read_text())
        return (
            data.get("end_to_end_success") or data.get("success_rate"),  # Prefer new metric
            data.get("mean_reward"),
            data.get("model_path"),
        )
    except Exception:
        return (None, None, None)


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
        "grip_success": merged_metrics.get("grip_success"),
        "delivery_success": merged_metrics.get("delivery_success"),
        "end_to_end_success": merged_metrics.get("end_to_end_success"),
        "mean_reward": merged_metrics.get("mean_reward"),
        "episode_length": merged_metrics.get("episode_length"),
        "config_diff": json.dumps(diff, indent=2) if diff else "{}",
        "artifacts": [],
        "notes": "auto-generated run summary",
    }
    if trainer_summary:
        summary["trainer_summary"] = trainer_summary
    # Stamp resume info if present
    ap = config.get("autopilot", {})
    summary["resume_mode"] = ap.get("resume_mode", "fresh")
    summary["resume_from"] = ap.get("resume_from")
    summary["save_strategy"] = ap.get("save_strategy", "best")
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
    # Resolve resume policy and inject load_model_path (top-level) if continuing
    ap_cfg = config.get("autopilot", {}) or {}
    resume_mode = ap_cfg.get("resume_mode", "fresh")
    resume_from = ap_cfg.get("resume_from")  # None | 'latest' | 'best' | '/path/model.pt'

    load_path: Optional[str] = None
    if resume_mode == "continue":
        if isinstance(resume_from, str):
            if resume_from == "latest":
                lp = latest_final_checkpoint()
                load_path = str(lp) if lp else None
            elif resume_from == "best":
                _, _, best_path = read_best_score()
                load_path = best_path
            else:
                # Treat as explicit path
                load_path = resume_from
        elif resume_from is None:
            # Default to latest if continuing and not specified
            lp = latest_final_checkpoint()
            load_path = str(lp) if lp else None

    # Create a working copy for saving and rendering
    effective_config = json.loads(json.dumps(config))
    if load_path:
        effective_config["load_model_path"] = load_path

    save_config(run_dir, effective_config)
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
    summarize(run_dir, effective_config, diff, metrics, trainer_summary)

    # Discover and record final model path from experiments dir
    model_path = latest_final_checkpoint()
    if model_path:
        (run_dir / "model_path.txt").write_text(str(model_path), encoding="utf-8")
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        # Maintain a handy "latest" symlink
        latest_link = MODELS_DIR / "latest.pt"
        try:
            if latest_link.exists() or latest_link.is_symlink():
                latest_link.unlink()
            latest_link.symlink_to(model_path)
        except OSError:
            # Fallback to copy if symlinks are restricted
            import shutil as _sh
            _sh.copy2(model_path, latest_link)

    # Update best checkpoint depending on save_strategy
    save_strategy = ap_cfg.get("save_strategy", "best")
    if save_strategy in {"best", "latest"} and model_path:
        # Select score: prefer end_to_end_success, then delivery_success, then grip_success
        e2e = None
        delivery = None
        grip = None
        mr = None
        if trainer_summary:
            m = trainer_summary.get("metrics", {})
            e2e = m.get("end_to_end_success") or m.get("perfect_now")
            delivery = m.get("delivery_success") or m.get("perfect_deliv")
            grip = m.get("grip_success") or m.get("perfect_grip")
            mr = m.get("mean_reward")
        if e2e is None:
            e2e = metrics.get("end_to_end_success")
        if delivery is None:
            delivery = metrics.get("delivery_success")
        if grip is None:
            grip = metrics.get("grip_success")
        if mr is None:
            mr = metrics.get("mean_reward")

        # Use best available metric for comparison
        primary_score = e2e or delivery or grip or mr

        best_sr, best_mr, _best_path = read_best_score()
        is_better = False
        if save_strategy == "latest":
            is_better = True
        else:
            # Compare primary score first
            if best_sr is None and primary_score is not None:
                is_better = True
            elif primary_score is not None and best_sr is not None:
                if primary_score > best_sr + 1e-9:
                    is_better = True
                elif abs(primary_score - best_sr) <= 1e-9 and mr is not None and best_mr is not None and mr > best_mr:
                    is_better = True
            elif best_sr is None and best_mr is None and mr is not None:
                is_better = True

        if is_better:
            # Write best.json record and update symlink
            record = {
                "run_id": run_dir.name,
                "model_path": str(model_path),
                "end_to_end_success": e2e,
                "delivery_success": delivery,
                "grip_success": grip,
                "mean_reward": mr,
                "timestamp": timestamp(),
            }
            best_record_path().write_text(json.dumps(record, indent=2), encoding="utf-8")
            best_link = MODELS_DIR / "best.pt"
            try:
                if best_link.exists() or best_link.is_symlink():
                    best_link.unlink()
                best_link.symlink_to(model_path)
            except OSError:
                import shutil as _sh
                _sh.copy2(model_path, best_link)
    append_labbook(
        "run complete",
        f"Run {run_dir.name} (iteration {iteration})",
        "metrics captured",
    )

    return {
        "config": effective_config,
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
