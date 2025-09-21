# Autopilot Notes (Curated)

Purpose: concise long‑term memory that guides future iterations at a glance. Updated in place; not an append‑only log.

## 1) Current Baseline (as of 2025‑09‑21)
- Header version: `PufferLib/pufferlib/ocean/drone_pp/drone_pp.h` at commit `552502e` (2025‑09‑20). Matches upstream/box2.
- Config profile: `autopilot/configs/baseline_full.json` mirrors box2 `drone_pp.ini`.
  • train: total_timesteps=200M; bptt_horizon=64; batch_size="auto"; minibatch_size=16384; max_minibatch_size=32768; lr≈0.00605; ent≈0.0712; clip≈0.6177; vf≈5.0; vf_clip≈1.2424; max_grad_norm≈3.05; gae_λ≈0.989; γ≈0.988; update_epochs=1; checkpoint_interval=200; anneal_lr=true; prio_alpha≈0.842; prio_beta0≈0.957.
  • env/vec: env.num_envs=24; env.num_drones=64; max_rings=10; vec.num_envs=24; vec.num_workers=24.
  • device: `mps` (local Mac). Upstream default is `cuda`.
- Runner policy: EXACT_CONFIG=1 (no normalization). Single‑run per iteration; proposals typically empty.

## 2) Stable Learnings (keep under 10 bullets)
- Environment logic changes tend to be more interpretable than hyperparameter adjustments; env modifications usually provide clearer cause-effect relationships.
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

Note (reverts applied after Run 2025-09-21T061611Z):
- Physics damping test (REVERTED): Increasing BASE_B_DRAG/BASE_K_ANG_DAMP degraded behavior (OOB≈0.95). Reverted to BASE_B_DRAG≈0.10 and BASE_K_ANG_DAMP≈0.20 per failsafe. Avoid reintroducing unless strong evidence.
- Soft boundary fields (REVERTED): Removed soft walls/ceil/floor and XY centralizing field; they likely fought control and increased OOB.

## 5) Decisions Log
- 2025-09-21T06:21:38Z (Run 2025-09-21T061611Z): OOB 0.953 primary issue. Reverted physics helpers in `dronelib.h` (BASE_B_DRAG 0.10, BASE_K_ANG_DAMP 0.20; removed soft walls + centralizing). Expected: OOB↓; ho/de_pickup stable or ↑; collisions ~2.2%. Keep global-step curriculum; no hyperparameter edits.
 - Physics damping test: Increase BASE_B_DRAG (0.1→0.2) and BASE_K_ANG_DAMP (0.2→0.3) to reduce drift/overshoot during hover and descent. Hypothesis: OOB↓; ho/de_pickup↑; attempt_grip↑; first grips emerge without raising collisions. If ineffective, consider action clamping next (keep observation space stable).
 - Soft boundary fields (current): Add gentle repulsive forces near XY walls and floor/ceiling in `dronelib.h` to prevent immediate OOB resets while untrained. Hypothesis: oob↓↓, episode_length↑, ho/de_pickup↑; keep collisions stable. Escalate by tuning constants only if OOB remains >0.5 after this change.

## 5) Decisions Log (terse, dated)
- 2025-09-21T03:58Z | Soft walls/floor in physics → reduce OOB; enable hover | Run 2025-09-21T034634Z showed ho/de_pickup≈0.015–0.035 and oob≈0.88 with zero grips; added `F_soft` near boundaries in `dronelib.h` (no gate/reward changes). Expect oob↓↓ and ho/de_pickup↑ next.
## 5) Decisions Log
- 2025-09-21 | Run 2025-09-21T035923Z: diagnostic_grip with extreme OOB (≈0.953), ho/de_pickup≈0.004→0.010, zero grips/deliveries. Decision: strengthen physics stability — increase BASE_B_DRAG (0.20→0.35) and widen/strengthen soft boundaries (wall_band 2.0, wall_k 12; floor_band 1.2, floor_k 12; ceil_band 1.2, ceil_k 8). Expect OOB↓, episode_length↑, ho/de_pickup↑; monitor attempt_grip and first grips next run.
- 2025-09-21T04:23Z | Run 2025-09-21T040851Z: diagnostic_grip persists; OOB high (~0.86); ho/de_pickup≈0.007; zero grips. Decision: prioritize hover acquisition and reduce traverse distance — relax pickup hover gates (dist_to_hidden<2.4, speed<1.6; fallback xy≤0.75·k, z>0.3, speed<2.5), spawn nearer to box (r_xy 0.5–1.2; z +1.5..2.5), and set initial hover height to +0.6. Expect ho/de_pickup↑ and OOB↓; aim for first non‑zero grips next.
 - 2025-09-21T04:34Z | Run 2025-09-21T043409Z: extreme OOB (~0.953) with ho/de_pickup≈0.009 and zero grips/deliveries. Decision: add early action governor (scale actions when k>1) in `drone_pp.h` to curb untrained saturation; no hparam edits. Expect OOB↓, ho/de_pickup↑, attempt_grip↑; first non‑zero grips likely.
 - 2025-09-21T04:52Z | Run 2025-09-21T044717Z: diagnostic_grip with extreme OOB (≈0.954), ho/de_pickup≈0.003, perfect_* = 0. Decision: strengthen the early action governor (scale = 1 − 0.05·(k−1); floor 0.25), keeping other gates/physics unchanged. Hypothesis: OOB↓, episode_length↑, ho/de_pickup↑, attempt_grip↑; monitor for first non‑zero grips before touching drop.
- 2025-09-21T05:12Z | Run 2025-09-21T050357Z: diagnostic_grip + fix_stability with extreme OOB (≈0.953), ho/de_pickup≈0.01, perfect_* = 0. Decision: escalate physics stability — increase BASE_B_DRAG (0.35→0.50) and BASE_K_ANG_DAMP (0.30→0.35); widen/strengthen soft boundaries (wall_band 3.0, wall_k 18; floor_band 2.0, floor_k 20; ceil_band 2.0, ceil_k 12); raise pickup spawn z (+2.0..3.0 over box). Expected: OOB↓↓, episode_length↑, ho/de_pickup↑; first near‑miss grips likely. If OOB still >0.5, consider a gentle centralizing field next.
 - 2025-09-21T05:22Z | Run 2025-09-21T051313Z: diagnostic_grip persists; OOB≈0.953; ho/de_pickup≈0.005–0.015; perfect_* = 0. Decision: add gentle centralizing field in `dronelib.h` (XY spring, center_k=0.08) alongside soft walls/floor to curb lateral drift without affecting vertical dynamics. Expected: OOB↓, ho/de_pickup↑; collisions stable. Next: if OOB still >0.5 with low ho/de_pickup, modestly widen hover gate or slow curriculum via `grip_k_decay` in `.ini` before deeper physics.
- 2025-09-21T05:27Z | Run 2025-09-21T052213Z: diagnostic_grip persists; OOB≈0.953; ho/de_pickup≈0.015; perfect_* = 0. Decision: slow curriculum — set `env.grip_k_decay` 0.0905→0.02 in baseline config. Rationale: gates tighten and action scaling relaxes too quickly; policy never stabilizes hover. Expect OOB↓, ho/de↑, first grips; collisions stable. Revisit hover gate width only if ho/de <0.05 next run.
 - 2025-09-21T05:38Z | Run 2025-09-21T053033Z: OOB≈0.952 with ho/de_pickup≈0.008; perfect_* = 0. Decision: revert early action governor in `drone_pp.h` (remove k-based action scaling before `move_drone`). Rationale: scaling to ≤0.25 at high k reduced control authority and correlated with OOB↑ across runs. Expected: OOB↓, episode_length↑, ho/de_pickup↑; first grips likely once hover stabilizes. Keep grip_k_decay=0.02; no trainer hparam changes.
- 2025-09-21T05:53Z | Run 2025-09-21T054645Z: first non‑zero grips; deliveries 0; ho_drop very low; OOB≈0.954; coll≈0.022. Decision: relax drop hover and delivery gates in `drone_pp.h` to mirror pickup (hover XY<0.75·k & z>0.3 with speed<2.5; success XY/z<0.30·k_floor). Expected: ho_drop↑, attempt_drop↑, and first deliveries; collisions stable; no hparam changes; next `{}`.
- 2025-09-21T06:03Z | Run 2025-09-21T055652Z: improve_carrying persists; ho_drop low (~37), attempt_drop≈0.003; perfect_deliv=0; OOB≈0.95. Decision: widen drop gates to account for carry jitter — hover XY<1.25·k; drop descent when XY≤0.55·max(k,1); success XY<0.35·max(k,1) and z<0.30·max(k,1). Expect ho_drop↑, attempt_drop↑, and first deliveries. Keep proposals `{}`.
 - 2025-09-21T06:11Z | Run 2025-09-21T060555Z: perfect_grip≈0.15 but perfect_deliv=0; ho_drop fell (~27), attempt_drop≈0.002; OOB≈0.954. Decision: fix curriculum reset — add global_tick and schedule k by global steps; set grip_k_decay≈8.5e-5 so k decays 17.9→1 over ~200k steps. Hypothesis: stable phases → ho_drop↑ and first deliveries; monitor OOB and drop gates next.

## 5) Decisions Log
- 2025-09-21 (Run 2025-09-21T062450Z): OOB ≈ 0.952 remains primary. Clamp dynamics to curb drift/spin and widen spawn margins: BASE_MAX_VEL 50→20 m/s; BASE_MAX_OMEGA 50→25 rad/s (dronelib.h). Increase PP2 edge_margin 3→6 m for box/drop spawns. Hypothesis: OOB↓, longer episodes, hover stability↑; grips convert; deliveries follow once OOB under control.
 - 2025-09-21T06:43:20Z (Run 2025-09-21T063752Z): OOB ≈ 0.953 persists with some grips, zero deliveries. Decision: reduce floor OOB by raising pickup/drop altitude in `drone_pp.h/reset_pp2` (z: −GRID_Z+0.5→−GRID_Z+1.5) and increase initial hover target offset (+0.6→+0.8 m). Hypothesis: OOB↓ (fewer floor strikes), ho/de_pickup stable or ↑, collisions ~2.2%; delivery gates unchanged. Next: if OOB still >0.9, consider lateral spawn band tightening before any physics helpers.

- 2025-09-21T070501Z: Remove proximity gating from velocity_penalty (drone_pp.h:compute_reward). Rationale: OOB≈0.95 from far-field runaways; penalize speed globally to curb drift while keeping approach shaping. Expect OOB↓, ho_drop↑, first deliveries as k→1.
- 2025-09-21 (CRITICAL FIX): Reverted harsh global velocity penalty that caused epoch 64→65 performance collapse (OOB 0.817→0.926, grips 0.98→0.19). Implemented gentle distance-scaled penalty: full strength <5m from target, 10% strength >25m. This preserves careful approach while allowing efficient far-field navigation.
