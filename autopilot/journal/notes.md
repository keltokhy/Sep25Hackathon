# Autopilot Notes

This file serves as long‑term memory for the agent. Summaries below distill stable
lessons and intent so future iterations don’t re‑learn the same context.

## 2025‑09‑20 — Restore `drone_pp.h` to latest upstream state
- Action: Reverted local/drex edits to `PufferLib/pufferlib/ocean/drone_pp/drone_pp.h` back to the latest committed version at commit `552502e` (2025‑09‑20 17:17:36‑0400), titled “Good - Sweep Event Rewards - Alter Hover Reward”.
- Rationale: Undo curriculum/gate relaxations introduced by autopilot to return to the validated baseline before making any new changes.
- Impact: Working tree now matches the upstream header; no pending diff for that file.

## Header evolution: `drone_pp.h` (Sep 11 → Sep 20, 2025)
High‑level themes extracted from 62 commits touching `drone_pp.h`:

- Reward shaping & events
  - Introduced and iterated “Perfect” metrics and rewards; tightened/loosened gates to make “perfect grip” achievable without over‑rewarding noise.
  - Added sweepable reward coefficients (A/B/C/D), distance‑based decay, and later “event reward sweeps” to balance hover, grip, carry, and deliver signals.
  - Experimented with low‑altitude penalties (added → removed) and adjusted hover reward magnitude and criteria.

- State/observation & stability
  - Removed spawn‑related observations; added velocity observations to reduce aliasing and encourage smoother approach/descent.
  - Added jitter logging and trained under jitter to improve robustness.
  - Multiple passes on velocity/distance alignment, using squared distance and decay for more stable gradients.

- Phase logic (hover → descend → grip → carry → deliver)
  - Clarified phase transitions and success gating; “hidden” hover target above box, then controlled descent onto box center for grip.
  - Tweaks to thresholds for distance, speed, and vertical velocity to enter GRIP safely and consistently.

- Physics & task curriculum
  - Adjusted box mass and grip physics (reduce base mass, taper/grow mass over training) and experimented with larger drones and grip decay.
  - Occasional random bumps and curriculum sweeps aimed at making grips achievable early while preserving difficulty later.

Key commits (chronology paraphrased)
- 2025‑09‑16..09‑18: distance decay; velocity alignment; sweepable rewards A/B/C/D; cleaner method; INI/H changes before sweep; success‑gate bugfix; remove original TASK_PP.
- 2025‑09‑17..09‑18: remove spawn obs, add velocity obs; grip decay; curriculum sweeps; perfect metric for multiple pickups; tighter logging.
- 2025‑09‑19: refactors and physics tweaks — reduce/taper/grow box mass; adjust grip; add random bump; larger drones; cleanup.
- 2025‑09‑20: add/remove low‑altitude penalty; add “Perfect Now” baseline; adjust hover reward; event‑reward sweeps (552502e).

Guidance for future edits
- Prefer environment/logic changes over hyperparameter tweaks (see no‑hparam policy).
- Maintain clear, testable phase boundaries and success criteria; keep thresholds consistent with reward shaping.
- When proposing curriculum or gating changes, document the behavioral failure being targeted and how the change makes the success preconditions more reachable.

## 2025‑09‑21 — Adopt box2 INI hparams as baseline
- Action: Mirrored `PufferLib/pufferlib/config/ocean/drone_pp.ini` into `autopilot/configs/baseline_full.json`:
  - vec/env: 24/24 envs, 64 drones, max_rings 10.
  - train: total_timesteps=200M, bptt_horizon=64, batch_size="auto", minibatch_size=16384, max_minibatch_size=32768, lr=0.006047…, ent_coef=0.071235…, clip_coef=0.617688…, vf_coef=5.0, vf_clip_coef=1.24236…, max_grad_norm=3.04955…, gae_lambda=0.989234…, gamma=0.987853…, update_epochs=1, checkpoint_interval=200, anneal_lr=true, prio_alpha=0.841906…, prio_beta0=0.957297…
  - device set to `mps` for compatibility on this workstation (original default INI uses `cuda`).
- Run script: added `EXACT_CONFIG=1` mode to skip normalization of batch sizes and vec divisibility so runs can use these settings verbatim.
- Rationale: Align local runs with the exact hyperparameters used on branch `box2` while preserving hardware compatibility.

## 2025‑09‑20 — Prompt refactor to remove contradictions
- Problem: The Codex prompt mixed a strict no‑hyperparameter policy with detailed guidance about editing hyperparameters, creating a contradiction.
- Fixes:
  - Removed hyperparameter ranges/guidance; made “WHAT YOU CANNOT CHANGE” explicit (no `train.*`, `env.*`, `vec.*`).
  - Reorganized into: OVERVIEW & GOALS; WORKFLOW; DECISION FRAMEWORK; WHAT YOU CAN CHANGE; WHAT YOU CANNOT CHANGE; TECHNICAL DETAILS.
  - Clarified the core loop and added an Environment Debugging Checklist.
  - Reframed experiment selection as environment‑change priorities (not hparam tuning).
  - Added success thresholds and failsafes for missing analysis, build failures, regressions, and reverts.
- Intent: Make the agent thoughtful, memory‑driven, and environment‑focused.
