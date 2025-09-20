#!/usr/bin/env python3
"""
Zero-Guard Autopilot Harness MVP
Applies patches, runs training, records scores, commits automatically.
"""

import argparse
import json
import subprocess
import sys
import pathlib
import datetime

def run_train():
    """Run training script and parse score from stdout JSON."""
    try:
        result = subprocess.run(
            [sys.executable, "autopilot_mvp/train.py"],
            capture_output=True,
            text=True,
            check=True
        )
        output = result.stdout.strip()
        data = json.loads(output)
        return float(data["score"])
    except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError, ValueError) as e:
        print(f"Error running training: {e}", file=sys.stderr)
        sys.exit(1)

def apply_patch(patch_path):
    """Apply a unified diff patch using git apply."""
    try:
        subprocess.run(
            ["git", "apply", "--whitespace=fix", str(patch_path)],
            check=True,
            capture_output=True
        )
    except subprocess.CalledProcessError as e:
        print(f"Error applying patch {patch_path}: {e}", file=sys.stderr)
        print(f"Stderr: {e.stderr.decode()}", file=sys.stderr)
        sys.exit(1)

def commit(msg):
    """Stage all changes and commit with given message."""
    try:
        subprocess.run(["git", "add", "-A"], check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", msg], check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        print(f"Error committing: {e}", file=sys.stderr)
        sys.exit(1)

def revert_last_commit():
    """Hard reset to HEAD~1."""
    try:
        subprocess.run(["git", "reset", "--hard", "HEAD~1"], check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        print(f"Error reverting: {e}", file=sys.stderr)
        sys.exit(1)

def log_labbook(text):
    """Append timestamped line to labbook.md."""
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    labbook_path = pathlib.Path("autopilot_mvp/labbook.md")

    with open(labbook_path, "a") as f:
        f.write(f"- {timestamp} {text}\n")

def read_state():
    """Read state from runs/state.json, initialize if missing."""
    state_path = pathlib.Path("autopilot_mvp/runs/state.json")

    if not state_path.exists():
        # Initialize with very negative score
        initial_state = {"best_score": float("-inf")}
        write_state(initial_state)
        return initial_state

    with open(state_path, 'r') as f:
        return json.load(f)

def write_state(state):
    """Write state to runs/state.json."""
    state_path = pathlib.Path("autopilot_mvp/runs/state.json")
    state_path.parent.mkdir(parents=True, exist_ok=True)

    with open(state_path, 'w') as f:
        json.dump(state, f, indent=2)

def main():
    parser = argparse.ArgumentParser(description="Zero-Guard Autopilot Harness MVP")
    parser.add_argument("--iters", type=int, default=5, help="Number of iterations")
    parser.add_argument("--patch", default="autopilot_mvp/proposals/next.patch",
                       help="Path to patch file")
    parser.add_argument("--revert-on-worse", action="store_true",
                       help="Revert commit if score decreases")

    args = parser.parse_args()

    # Ensure we're in a git repo
    try:
        subprocess.run(["git", "status"], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        print("Error: Not in a git repository", file=sys.stderr)
        sys.exit(1)

    # Initialize state
    state = read_state()

    patch_path = pathlib.Path(args.patch)

    for i in range(1, args.iters + 1):
        print(f"Iteration {i}/{args.iters}")

        # Check if patch file exists
        if not patch_path.exists():
            print(f"Warning: Patch file {patch_path} does not exist, skipping iteration {i}")
            continue

        # Get baseline score
        print("  Running baseline training...")
        pre_score = run_train()
        print(f"  Baseline score: {pre_score:.4f}")

        # Apply patch
        print(f"  Applying patch: {patch_path}")
        apply_patch(patch_path)

        # Get new score
        print("  Running training with patch...")
        post_score = run_train()
        print(f"  New score: {post_score:.4f}")

        # Commit the change
        commit_msg = f"[{i}] autopilot: score {pre_score:.4f} -> {post_score:.4f}"
        print(f"  Committing: {commit_msg}")
        commit(commit_msg)

        # Log to labbook
        log_labbook(commit_msg)

        # Handle revert logic
        if args.revert_on_worse and post_score < pre_score:
            print(f"  Score decreased ({post_score:.4f} < {pre_score:.4f}), reverting...")
            revert_last_commit()
            revert_msg = f"[{i}] REVERTED: score {pre_score:.4f} -> {post_score:.4f} (worse)"
            log_labbook(revert_msg)
        else:
            # Update best score if improved
            if post_score > state["best_score"]:
                state["best_score"] = post_score
                write_state(state)
                print(f"  New best score: {post_score:.4f}")

        print()

    print("Autopilot run complete!")
    final_state = read_state()
    print(f"Best score achieved: {final_state['best_score']:.4f}")

if __name__ == "__main__":
    main()