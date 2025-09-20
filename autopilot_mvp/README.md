# Zero-Guard Autopilot Harness MVP

A minimal harness that lets an LLM propose code/config changes as unified diff patches, applies them automatically, runs training, records scores, and commits each attempt atomically.

## Quick Start

1. **Create a patch file** at `autopilot_mvp/proposals/next.patch` with a unified diff
2. **Run one iteration**:
   ```bash
   python autopilot_mvp/autopilot.py --iters 1
   ```
3. **Run multiple iterations**:
   ```bash
   python autopilot_mvp/autopilot.py --iters 10
   ```

## Options

- `--iters N`: Number of iterations to run (default: 5)
- `--patch PATH`: Path to patch file (default: `autopilot_mvp/proposals/next.patch`)
- `--revert-on-worse`: Automatically revert commits that decrease the score (default: off)

## Example Usage

```bash
# Run 10 iterations with automatic revert on worse scores
python autopilot_mvp/autopilot.py --iters 10 --revert-on-worse

# Use a custom patch file
python autopilot_mvp/autopilot.py --patch my_custom.patch --iters 5
```

## How It Works

1. **Baseline**: Run `python autopilot_mvp/train.py` to get current score
2. **Apply**: Apply the unified diff patch using `git apply`
3. **Evaluate**: Run training again to get new score
4. **Commit**: Create a git commit with score delta message
5. **Log**: Append result to `autopilot_mvp/labbook.md`
6. **Revert** (optional): If `--revert-on-worse` is set and score decreased, revert the commit

## Files Updated

- **`autopilot_mvp/labbook.md`**: Chronological log of all iterations
- **`autopilot_mvp/runs/state.json`**: Tracks best score achieved
- **Git history**: One commit per iteration with score deltas

## Example Patch File

Create `autopilot_mvp/proposals/next.patch`:

```diff
--- a/autopilot_mvp/config.json
+++ b/autopilot_mvp/config.json
@@ -1,5 +1,5 @@
 {
-  "lr": 0.005,
+  "lr": 0.010,
   "gamma": 0.95,
   "entropy_coef": 0.0005
 }
```

## Training Script Contract

The training script (`autopilot_mvp/train.py`) must:
- Read `autopilot_mvp/config.json` for parameters
- Print exactly one JSON object to stdout: `{"score": <float>}`
- Be deterministic enough for optimization

## Zero Guards Philosophy

This MVP has **no safety checks** by design:
- No schema validation
- No tests or CI
- No sandboxing
- Direct application of any provided patch

For production use, add appropriate safety measures.