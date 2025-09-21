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
 - PP2 observation alignment: For the generic “to target” vector, use the hidden hover point (not box/drop) so the policy aims for the hover waypoint before descent; retain explicit to_box/to_drop vectors for context.

## 4) Open Questions & Next Hypotheses (≤5)
- Does the difficulty ramp (grip_k decay, box_k growth) explain the common “good start → poor end” pattern? Add/plot k vs perfect_* over updates.
 - Are hover/grip gates calibrated to typical velocity and distance distributions at k≈1? Consider logging distributions to validate (post spawn-near-box change).
- Is OOB driven by descent overshoot or lateral drift near the box? Compare `xy_dist_to_box` and vertical speed at failure.
- Do CPU spikes align with short env/learn bursts while GPU dominates wall‑time? Use performance/* timings to confirm resource balance.
- Are delivery gates too tight relative to grip dynamics at late k? Inspect failure transitions from gripping→drop.
 - After gentler descent (−0.06) and wider grip gates (0.20·k), do ho/de_pickup increase without raising collisions? Applied spawn-near-box; validate OOB↓ and ho/de_pickup↑ before considering soft‑floor.
 - Drop approach gating: previously drop hover z‑window (0.7–1.3m) didn’t match target (+0.4m), likely suppressing `ho_drop` and `to_drop`. Adjusted to 0.3–0.6m and set `approaching_drop=true` upon carry; verify `to_drop↑, ho_drop↑`, OOB↓ during carry.
 - New: Require XY alignment before descent (pickup/drop); hold altitude until `xy_dist <= 0.20·max(k,1)`. Add near‑miss counters (`attempt_grip`, `attempt_drop`). Hypothesis: OOB↓ by preventing drift‑descent; ho/de_pickup↑; first non‑zero gripping.
 - Relax pickup hover gate further: admit hovering when `dist_to_hidden < 1.8` and `speed < 1.2` (was 1.0/0.8). Rationale: agents struggle to satisfy hover gate at typical spawn offsets; descent remains XY‑gated and gentle (−0.06 m/s). Expect ho/de_pickup↑ and attempt_grip↑ without increasing collisions.
- New: Relax grip vertical descent gate — require `vel.z > -max(0.15, 0.06·k)` (still `< 0`) during pickup grip. Rationale: at k≈1 the −0.06 m/s cap is too strict and blocks legitimate grips; allowing moderate descent should yield first non‑zero grips and `to_drop > 0` without increasing collisions.
 - Physics damping test: Increase BASE_B_DRAG (0.1→0.2) and BASE_K_ANG_DAMP (0.2→0.3) to reduce drift/overshoot during hover and descent. Hypothesis: OOB↓; ho/de_pickup↑; attempt_grip↑; first grips emerge without raising collisions. If ineffective, consider action clamping next (keep observation space stable).
 - Soft boundary fields (current): Add gentle repulsive forces near XY walls and floor/ceiling in `dronelib.h` to prevent immediate OOB resets while untrained. Hypothesis: oob↓↓, episode_length↑, ho/de_pickup↑; keep collisions stable. Escalate by tuning constants only if OOB remains >0.5 after this change.

## 5) Decisions Log (terse, dated)
- 2025-09-21T03:58Z | Soft walls/floor in physics → reduce OOB; enable hover | Run 2025-09-21T034634Z showed ho/de_pickup≈0.015–0.035 and oob≈0.88 with zero grips; added `F_soft` near boundaries in `dronelib.h` (no gate/reward changes). Expect oob↓↓ and ho/de_pickup↑ next.
## 5) Decisions Log
- 2025-09-21 | Run 2025-09-21T035923Z: diagnostic_grip with extreme OOB (≈0.953), ho/de_pickup≈0.004→0.010, zero grips/deliveries. Decision: strengthen physics stability — increase BASE_B_DRAG (0.20→0.35) and widen/strengthen soft boundaries (wall_band 2.0, wall_k 12; floor_band 1.2, floor_k 12; ceil_band 1.2, ceil_k 8). Expect OOB↓, episode_length↑, ho/de_pickup↑; monitor attempt_grip and first grips next run.
 - 2025-09-21T04:23Z | Run 2025-09-21T040851Z: diagnostic_grip persists; OOB high (~0.86); ho/de_pickup≈0.007; zero grips. Decision: prioritize hover acquisition and reduce traverse distance — relax pickup hover gates (dist_to_hidden<2.4, speed<1.6; fallback xy≤0.75·k, z>0.3, speed<2.5), spawn nearer to box (r_xy 0.5–1.2; z +1.5..2.5), and set initial hover height to +0.6. Expect ho/de_pickup↑ and OOB↓; aim for first non‑zero grips next.
