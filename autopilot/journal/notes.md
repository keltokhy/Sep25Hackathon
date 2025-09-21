# Autopilot Notes (Curated)

Purpose: concise long‑term memory that guides future iterations at a glance. Updated in place; not an append‑only log.

## 1) Current Baseline (as of 2025‑09‑21)
- Header version: `PufferLib/pufferlib/ocean/drone_pp/drone_pp.h` at commit `552502e` (2025‑09‑20). Matches upstream/box2.
- Config profile: `autopilot/configs/baseline_full.json` mirrors box2 `drone_pp.ini`.
  • train: total_timesteps=200M; bptt_horizon=64; batch_size="auto"; minibatch_size=16384; max_minibatch_size=32768; lr≈0.00605; ent≈0.0712; clip≈0.6177; vf≈5.0; vf_clip≈1.2424; max_grad_norm≈3.05; gae_λ≈0.989; γ≈0.988; update_epochs=1; checkpoint_interval=200; anneal_lr=true; prio_alpha≈0.842; prio_beta0≈0.957.
  • env/vec: env.num_envs=24; env.num_drones=64; max_rings=10; vec.num_envs=24; vec.num_workers=24.
  • device: `mps` (local Mac). Upstream default is `cuda`.
- Runner policy: EXACT_CONFIG=1 (no normalization). Single‑run per iteration; no hparam edits allowed in proposals.

## 2) Stable Learnings (keep under 10 bullets)
- Favor environment logic over hyperparameters; enforce the no‑hparam policy.
- Preserve clear phase boundaries and success gates (hover → descend → grip → carry → deliver) with thresholds consistent with reward shaping.
- Difficulty ramp is intentional (e.g., grip_k decay, box_k growth). Expect apparent early success followed by stricter gating; interpret metrics in that light.
- Use event rewards to shape toward the next feasible subgoal but avoid over‑rewarding noisy behaviors.
- Keep observations focused and stable; velocity obs help reduce aliasing in approach/descent.
- Instrument attempts and successes (hover/grip/deliver) to explain failure modes; correlate with difficulty variables.
- Small, testable env edits beat broad refactors; document the behavioral hypothesis for each change.

## 3) Header Evolution (high‑level)
- Reward shaping matured from simple signals to event‑swept weights with distance decay and “perfect” gates.
- Observations shifted away from spawn specifics toward velocities/orientation to stabilize approach and descent.
- Phase logic clarified: hover at a hidden point above the box, then controlled descent onto center; delivery mirrors this.
- Physics/curriculum adjusted: box mass dynamics and occasional perturbations to make early grips achievable without removing challenge later.

## 4) Open Questions & Next Hypotheses (≤5)
- Does the difficulty ramp (grip_k decay, box_k growth) explain the common “good start → poor end” pattern? Add/plot k vs perfect_* over updates.
 - Are hover/grip gates calibrated to typical velocity and distance distributions at k≈1? Consider logging distributions to validate (post spawn-near-box change).
- Is OOB driven by descent overshoot or lateral drift near the box? Compare `xy_dist_to_box` and vertical speed at failure.
- Do CPU spikes align with short env/learn bursts while GPU dominates wall‑time? Use performance/* timings to confirm resource balance.
- Are delivery gates too tight relative to grip dynamics at late k? Inspect failure transitions from gripping→drop.
 - After gentler descent (−0.06) and wider grip gates (0.20·k), do ho/de_pickup increase without raising collisions? Applied spawn-near-box; validate OOB↓ and ho/de_pickup↑ before considering soft‑floor.
 - Drop approach gating: previously drop hover z‑window (0.7–1.3m) didn’t match target (+0.4m), likely suppressing `ho_drop` and `to_drop`. Adjusted to 0.3–0.6m and set `approaching_drop=true` upon carry; verify `to_drop↑, ho_drop↑`, OOB↓ during carry.
 - New: Require XY alignment before descent (pickup/drop); hold altitude until `xy_dist <= 0.20·max(k,1)`. Add near‑miss counters (`attempt_grip`, `attempt_drop`). Hypothesis: OOB↓ by preventing drift‑descent; ho/de_pickup↑; first non‑zero gripping.

## 5) Decisions Log (terse, dated)
- 2025‑09‑20: Restore header to upstream commit `552502e`; revert local edits; baseline re‑established.
- 2025‑09‑20: Prompt refactor — remove hparam contradictions; add workflow/constraints/checklist.
- 2025‑09‑21: Adopt box2 INI hparams in `baseline_full.json`; add EXACT_CONFIG passthrough.
- 2025‑09‑21: Remove personal names from prompt/notes; prefer “latest committed environment code”.
- 2025‑09‑21: Enforce single‑run per iteration; add Notes.md discipline (curated, concise, edit‑in‑place).
 - 2025-09-21: Grip diagnostic patch — lower hover offset (+0.6m), slower descent (−0.06 m/s), relax grip gates to 0.20·k; goal: convert hover attempts into grips, reduce OOB modestly; verify ho/de_pickup↑ and any non‑zero deliveries next run (fresh).
- 2025-09-21: Spawn near box — in PP2 reset, spawn 1.0–2.5 m laterally and 1.5–2.5 m above box; clamp to grid and zero initial vel/omega; goal: reduce early OOB and raise hover/grip attempts.
 - 2025-09-21: Raise pickup hover + spawn z — increase hidden pickup hover to +0.9 m (from +0.6) and raise spawn altitude to 2.0–3.0 m above box; rationale: OOB remained ~0.80 with near‑floor starts; aligns with fix_stability without re‑introducing low‑altitude penalties; expect OOB↓ and ho/de_pickup↑ next run.
 - 2025-09-21: Gate descent on XY alignment; add near‑miss counters — descend only when `xy_dist <= 0.20·max(k,1)` for pickup/drop; otherwise hold altitude. Added `attempt_grip/attempt_drop` logging and exported in binding. Rationale: high OOB with misaligned descents; expected OOB↓ and better grip attempts.
