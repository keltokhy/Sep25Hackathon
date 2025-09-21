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
    metrics: Dict[str, Optional[float]] = {
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
        "oob_rate": None,
        # Attempts and events (for conversion calculations)
        "gripping_events": None,
        "delivered_events": None,
        # System/throughput
        "SPS": None,
        "performance_env": None,
        "performance_learn": None,
        # Optimizer health
        "policy_loss": None,
        "value_loss": None,
        "entropy": None,
        "approx_kl": None,
        "clipfrac": None,
        "explained_variance": None,
        "importance": None,
        # Derived conversions (filled after parse if possible)
        "grip_conv_rate": None,
        "deliv_conv_rate": None,
        "e2e_conv_rate": None,
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
                if metrics["gripping_events"] is None:
                    metrics["gripping_events"] = data.get("environment/gripping")
                if metrics["delivered_events"] is None:
                    metrics["delivered_events"] = data.get("environment/delivered")

                # Performance metrics
                if metrics["mean_reward"] is None:
                    metrics["mean_reward"] = data.get("environment/score")
                if metrics["episode_length"] is None:
                    metrics["episode_length"] = data.get("environment/episode_length")
                if metrics["collision_rate"] is None:
                    metrics["collision_rate"] = data.get("environment/collision_rate")
                if metrics["oob_rate"] is None:
                    metrics["oob_rate"] = data.get("environment/oob")
                if metrics["SPS"] is None:
                    metrics["SPS"] = data.get("SPS")
                if metrics["performance_env"] is None:
                    metrics["performance_env"] = data.get("performance/env")
                if metrics["performance_learn"] is None:
                    metrics["performance_learn"] = data.get("performance/learn")

                # Optimizer health
                if metrics["policy_loss"] is None:
                    metrics["policy_loss"] = data.get("losses/policy_loss")
                if metrics["value_loss"] is None:
                    metrics["value_loss"] = data.get("losses/value_loss")
                if metrics["entropy"] is None:
                    metrics["entropy"] = data.get("losses/entropy")
                if metrics["approx_kl"] is None:
                    metrics["approx_kl"] = data.get("losses/approx_kl")
                if metrics["clipfrac"] is None:
                    metrics["clipfrac"] = data.get("losses/clipfrac")
                if metrics["explained_variance"] is None:
                    metrics["explained_variance"] = data.get("losses/explained_variance")
                if metrics["importance"] is None:
                    metrics["importance"] = data.get("losses/importance")

                # Check if we have all essential metrics
                essential = ["grip_success", "delivery_success", "mean_reward", "episode_length"]
                if all(metrics.get(k) is not None for k in essential):
                    break
    except UnicodeDecodeError:
        pass

    # Derived conversions (safe division)
    def _safe_div(n, d):
        try:
            if n is None or d is None:
                return None
            d = float(d)
            return float(n) / d if d > 0 else None
        except Exception:
            return None

    metrics["grip_conv_rate"] = _safe_div(metrics["grip_success"], metrics["grip_attempts"])  # perfect_grip / to_pickup
    # Delivery conversion uses achieved grips as denominator if available; fallback to attempts to_drop
    denom_deliv = metrics["gripping_events"] if metrics["gripping_events"] not in (None, 0) else metrics["delivery_attempts"]
    metrics["deliv_conv_rate"] = _safe_div(metrics["delivery_success"], denom_deliv)
    metrics["e2e_conv_rate"] = _safe_div(metrics["end_to_end_success"], metrics["grip_attempts"])  # perfect_now / to_pickup

    return metrics


def apply_autopilot_override(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Apply only autopilot settings to base config."""
    result = json.loads(json.dumps(base))  # deep copy
    if "autopilot" in override:
        result["autopilot"] = override["autopilot"]
    return result


def load_override() -> Dict[str, Any]:
    """Load overrides from proposals/next_config.json but enforce the
    no-hyperparameter policy: only the top-level 'autopilot' section
    is honored. Any 'train', 'env', or 'vec' keys are ignored.

    This implements the repo policy to lock hparams to the baselines
    (Dan's defaults) and keep DREX focused on environment iteration
    and run policy (resume/save) decisions.
    """
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
        return {}

    # Keep only autopilot policy; drop any accidental hparam overrides
    allowed: Dict[str, Any] = {}
    if "autopilot" in data:
        ap = data.get("autopilot")
        if isinstance(ap, dict):
            allowed["autopilot"] = ap

    dropped_keys = [k for k in data.keys() if k not in {"autopilot"}]
    if dropped_keys:
        try:
            append_labbook(
                "ignore overrides",
                f"Dropped keys {dropped_keys} per no-hparam policy",
                "using baselines",
            )
        except Exception:
            pass
    return allowed


def capture_environment_state(run_dir: Path) -> Dict[str, str]:
    """Capture current state of environment code for tracking changes."""
    env_state = {}

    # Get git diff of uncommitted changes to drone environment
    drone_path = "PufferLib/pufferlib/ocean/drone_pp/"

    # Get unstaged changes (working directory)
    result = subprocess.run(
        ["git", "diff", drone_path],
        capture_output=True,
        text=True,
        cwd=AUTOPILOT_DIR.parent
    )
    if result.stdout:
        env_state["uncommitted_changes"] = result.stdout
        (run_dir / "env_uncommitted.diff").write_text(result.stdout)

    # Get staged changes
    result = subprocess.run(
        ["git", "diff", "--cached", drone_path],
        capture_output=True,
        text=True,
        cwd=AUTOPILOT_DIR.parent
    )
    if result.stdout:
        env_state["staged_changes"] = result.stdout
        (run_dir / "env_staged.diff").write_text(result.stdout)

    # Get current commit hash for reference
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        cwd=AUTOPILOT_DIR.parent
    )
    env_state["base_commit"] = result.stdout.strip()

    # Get list of modified files
    result = subprocess.run(
        ["git", "status", "--porcelain", drone_path],
        capture_output=True,
        text=True,
        cwd=AUTOPILOT_DIR.parent
    )
    if result.stdout:
        env_state["modified_files"] = result.stdout.strip()

    return env_state


# Note: compare_environment_changes is defined below with an improved
# signature returning structured details; remove the earlier variant to
# avoid shadowing and confusion.


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


def _format_prompt(template: str, **kwargs: str) -> str:
    """Safely inject named fields into a prompt containing literal braces.

    We escape all braces, then re-enable the specific placeholders we intend
    to fill (e.g., {script}, {notes_path}) before calling str.format().
    """
    escaped = template.replace('{', '{{').replace('}', '}}')
    for key in kwargs.keys():
        escaped = escaped.replace(f'{{{{{key}}}}}', f'{{{key}}}')
    return escaped.format(**kwargs)


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

    # Load iteration and run_id context for prompt formatting
    try:
        run_meta = json.loads((run_dir / "run.json").read_text())
        iteration_num = run_meta.get("metadata", {}).get("iteration")
    except Exception:
        iteration_num = None
    prompt = _format_prompt(
        prompt_template,
        script=str(rel_script),
        notes_path=str(rel_notes),
        iteration=str(iteration_num) if iteration_num is not None else "?",
        run_id=run_dir.name,
    )

    env = os.environ.copy()
    summary_file = run_dir / "trainer_summary.json"
    env["PUFFER_AUTOPILOT_SUMMARY"] = str(summary_file)
    env["PUFFER_AUTOPILOT_RUN_ID"] = run_dir.name
    env["PUFFER_AUTOPILOT_RUN_DIR"] = str(run_dir)
    # Enforce exact upstream config usage (no normalization) each run
    env["EXACT_CONFIG"] = os.environ.get("EXACT_CONFIG", "1")

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


def analyze_drone_behavior(metrics: Dict[str, Optional[float]]) -> Dict[str, Any]:
    """Analyze metrics to understand what the drone is actually doing."""
    insights = []
    severity = "ok"
    next_focus = "continue"

    # Get metrics with safe defaults
    grip_rate = metrics.get("grip_success", 0) or 0
    grip_attempts = metrics.get("grip_attempts", 0) or 0
    delivery_rate = metrics.get("delivery_success", 0) or 0
    e2e_rate = metrics.get("end_to_end_success", 0) or 0
    hover_efficiency = metrics.get("hover_efficiency", 0) or 0
    collision_rate = metrics.get("collision_rate", 0) or 0

    # Calculate grip efficiency
    grip_efficiency = 0
    if grip_attempts > 0:
        grip_efficiency = grip_rate / grip_attempts

    # Analyze grip behavior
    if grip_attempts == 0 or grip_attempts < 0.001:
        insights.append("🚨 Drone not attempting to grip objects at all")
        severity = "critical"
        next_focus = "diagnostic_grip"
    elif grip_rate < 0.1:
        insights.append("🔧 Grip mechanism failing (<10% success rate)")
        severity = "warning"
        next_focus = "improve_grip"
    elif grip_rate < 0.3:
        insights.append("⚠️ Low grip success rate (<30%)")
        next_focus = "tune_grip"

    # Analyze delivery chain
    if grip_rate > 0.3 and delivery_rate < 0.1:
        insights.append("📦 Can grip but cannot deliver - carrying/navigation issue")
        next_focus = "improve_carrying"
    elif delivery_rate > 0.3 and e2e_rate < 0.1:
        insights.append("🔄 Delivery works but full chain fails")
        next_focus = "improve_coordination"

    # Check for stability issues
    if collision_rate > 0.5:
        insights.append("💥 High collision rate - stability/control problem")
        severity = "warning" if severity == "ok" else severity
        next_focus = "fix_stability"

    # Check hovering behavior
    if hover_efficiency > 0.5 and grip_rate < 0.2:
        insights.append("🎯 Hovering at pickup but not gripping")
        next_focus = "fix_grip_activation"

    # If everything is working reasonably well
    if grip_rate > 0.5 and delivery_rate > 0.3:
        insights.append("✅ Basic behaviors working - ready for optimization")
        next_focus = "optimize_performance"

    return {
        "insights": insights,
        "severity": severity,
        "next_focus": next_focus,
        "grip_efficiency": grip_efficiency,
        "metrics_summary": {
            "grip_success": f"{grip_rate:.1%}",
            "delivery_success": f"{delivery_rate:.1%}",
            "end_to_end": f"{e2e_rate:.1%}",
            "collision_rate": f"{collision_rate:.1%}"
        }
    }


def compare_environment_changes(current_run: Path, previous_run: Optional[Path]) -> Dict[str, Any]:
    """Compare environment changes between runs."""
    comparison = {
        "has_changes": False,
        "description": "",
        "files_changed": []
    }

    if not previous_run:
        return comparison

    prev_diff = previous_run / "env_uncommitted.diff"
    curr_diff = current_run / "env_uncommitted.diff"

    if curr_diff.exists():
        curr_content = curr_diff.read_text()
        if prev_diff.exists():
            prev_content = prev_diff.read_text()
            if curr_content != prev_content:
                comparison["has_changes"] = True
                comparison["description"] = "Environment code modified since last run"
                # Parse diff to extract file names
                for line in curr_content.split("\n"):
                    if line.startswith("diff --git"):
                        parts = line.split()
                        if len(parts) > 2:
                            file_path = parts[2].replace("a/", "")
                            if file_path not in comparison["files_changed"]:
                                comparison["files_changed"].append(file_path)
        elif curr_content:
            comparison["has_changes"] = True
            comparison["description"] = "New environment modifications in this run"

    return comparison


def summarize(
    run_dir: Path,
    config: Dict[str, Any],
    metrics: Dict[str, Optional[float]],
    trainer_summary: Dict[str, Any],
    env_state: Dict[str, str],
) -> None:
    trainer_metrics = trainer_summary.get("metrics", {}) if trainer_summary else {}
    merged_metrics = dict(metrics)
    for key, value in trainer_metrics.items():
        if value is not None:
            merged_metrics[key] = value

    # Perform behavioral analysis
    behavior = analyze_drone_behavior(merged_metrics)

    # Check if there were environment changes
    has_env_changes = bool(env_state.get("uncommitted_changes") or env_state.get("staged_changes"))

    # Compare with previous run's environment
    prev_run = None
    runs = list_runs()
    if len(runs) > 1:
        # Find the most recent run before this one
        for run in reversed(runs):
            if run != run_dir:
                prev_run = run
                break

    env_comparison = compare_environment_changes(run_dir, prev_run)

    # Build summary with core and extended metrics (parse-only additions)
    summary = {
        "run_id": run_dir.name,
        "timestamp": timestamp(),
        "seed": config.get("train", {}).get("seed"),
        "grip_success": merged_metrics.get("grip_success"),
        "delivery_success": merged_metrics.get("delivery_success"),
        "end_to_end_success": merged_metrics.get("end_to_end_success"),
        "mean_reward": merged_metrics.get("mean_reward"),
        "episode_length": merged_metrics.get("episode_length"),
        # Extended metrics: funnel, stability, throughput, optimizer
        "metrics_extended": {
            "grip_attempts": merged_metrics.get("grip_attempts"),
            "delivery_attempts": merged_metrics.get("delivery_attempts"),
            "gripping_events": merged_metrics.get("gripping_events"),
            "delivered_events": merged_metrics.get("delivered_events"),
            "grip_conv_rate": merged_metrics.get("grip_conv_rate"),
            "deliv_conv_rate": merged_metrics.get("deliv_conv_rate"),
            "e2e_conv_rate": merged_metrics.get("e2e_conv_rate"),
            "hover_efficiency": merged_metrics.get("hover_efficiency"),
            "collision_rate": merged_metrics.get("collision_rate"),
            "oob_rate": merged_metrics.get("oob_rate"),
            "SPS": merged_metrics.get("SPS"),
            "performance_env": merged_metrics.get("performance_env"),
            "performance_learn": merged_metrics.get("performance_learn"),
            "policy_loss": merged_metrics.get("policy_loss"),
            "value_loss": merged_metrics.get("value_loss"),
            "entropy": merged_metrics.get("entropy"),
            "approx_kl": merged_metrics.get("approx_kl"),
            "clipfrac": merged_metrics.get("clipfrac"),
            "explained_variance": merged_metrics.get("explained_variance"),
            "importance": merged_metrics.get("importance"),
        },
        "behavioral_analysis": behavior,  # Add behavioral insights
        "environment_changes": has_env_changes,  # Flag if environment was modified
        "environment_comparison": env_comparison,  # Comparison with previous run
        "base_commit": env_state.get("base_commit", "unknown"),
        "modified_files": env_state.get("modified_files", ""),
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

    # Print behavioral insights to console for immediate feedback
    if behavior["insights"]:
        print(f"\n🔍 DREX Behavioral Analysis for {run_dir.name}:")
        print(f"   Severity: {behavior['severity'].upper()}")
        for insight in behavior["insights"]:
            print(f"   {insight}")
        print(f"   Next Focus: {behavior['next_focus']}")
        print(f"   Metrics: Grip {behavior['metrics_summary']['grip_success']} | "
              f"Delivery {behavior['metrics_summary']['delivery_success']} | "
              f"E2E {behavior['metrics_summary']['end_to_end']}")

    # Report environment changes if any
    if has_env_changes or env_comparison["has_changes"]:
        print(f"\n🛠️  Environment Code Changes:")
        if env_comparison["has_changes"]:
            print(f"   {env_comparison['description']}")
            if env_comparison["files_changed"]:
                for file in env_comparison["files_changed"][:3]:  # Show first 3 files
                    print(f"   • {file}")
                if len(env_comparison["files_changed"]) > 3:
                    print(f"   • ... and {len(env_comparison['files_changed']) - 3} more files")
        elif has_env_changes:
            print(f"   Uncommitted changes in environment code")
            if env_state.get("modified_files"):
                print(f"   Files: {env_state['modified_files']}")
        print(f"   See {run_dir}/env_uncommitted.diff for full details")


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
    config = apply_autopilot_override(base_config, override) if override else base_config

    metadata = {
        "mode": "quick" if use_quick else "full",
        "config_template": str(config_path.relative_to(AUTOPILOT_DIR)),
        "iteration": iteration,
    }
    if parent_run:
        metadata["parent_run"] = parent_run

    run_dir = register_run(metadata)

    # Capture environment state at start of run
    env_state = capture_environment_state(run_dir)

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
    summarize(run_dir, effective_config, metrics, trainer_summary, env_state)

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
        "--mode", choices=("quick", "full"), default="full", help="Run smoke test or full training"
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
