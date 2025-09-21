# Autopilot Notes (Curated)

Purpose: concise long‑term memory that guides future iterations at a glance. Updated in place; not an append‑only log. Prefer deltas vs previous and vs a named baseline.

## 0) Goal Stack
- North star: Robust pick‑and‑place (grip → carry → deliver) with stable OOB and collision rates.
- Current subgoal: Improve end‑to‑end conversion by raising hover/descent reliability without increasing OOB.
- Exit criteria for this subgoal: Δ (vs baseline) +5pp grip_success and +1pp delivery_success, with OOB not worse by >2pp.

## 1) Current Baseline (as of 2025‑09‑21)
- Header version: `PufferLib/pufferlib/ocean/drone_pp/drone_pp.h` at commit `552502e` (2025‑09‑20). Matches upstream/box2.
- Config profile: `autopilot/configs/baseline_full.json` mirrors box2 `drone_pp.ini`.
  • train: total_timesteps=200M; bptt_horizon=64; batch_size="auto"; minibatch_size=16384; max_minibatch_size=32768; lr≈0.00605; ent≈0.0712; clip≈0.6177; vf≈5.0; vf_clip≈1.2424; max_grad_norm≈3.05; gae_λ≈0.989; γ≈0.988; update_epochs=1; checkpoint_interval=200; anneal_lr=true; prio_alpha≈0.842; prio_beta0≈0.957.
  • env/vec: env.num_envs=24; env.num_drones=64; max_rings=10; vec.num_envs=24; vec.num_workers=24.
  • device: `mps` (local Mac). Upstream default is `cuda`.
- Runner policy: EXACT_CONFIG=1 (no normalization). Single‑run per iteration; proposals typically empty and contain only `autopilot.*`.

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

## 4) Critical Performance Analysis (2025-09-21)

### Task Performance Crisis
- **Grip attempts: 0.016% of episodes** - Drones almost never try to grip packages
- **Grip success: 4.3% of episodes** - When counted, most are false positives from cumulative logging
- **Delivery success: 0.04% of episodes** - Essentially zero task completion
- **Key insight**: Despite OOB improvements (95%→58% best case), actual task performance is negligible

### Root Cause: Curriculum Too Hard
- `grip_k` starts at 17.9, decays to 1.0 after only 200K timesteps (epoch 0.1)
- At k>5: grip gates require <0.35*k XY distance and <0.35*k Z distance - essentially impossible
- Training runs 200M timesteps but k=1.0 for 199.8M of them (99.9% of training)
- Drones never learn to grip during the brief easy window

### Training Stability Issues
- Best performance occurs mid-training (epoch 33-40) then degrades
- Run 095422Z: OOB 91.5%→57.7%→79.8% (start→best→final)
- Score pattern: 3.3→177.7→34.9 (collapse after epoch 60)
- Suggests overfitting or destabilization from velocity penalties

## 5) OOB Fix: Edge Margin Overcentralization (2025-09-21)
- **Problem**: OOB regressed to 96.8% after edge_margin curriculum change
- **Root cause**: Edge margin 22→14 over 200k steps caused extreme centralization
  - At start: boxes spawn in (-7,7) range only (vs arena ±30)
  - Drones spawn 0.2-0.6 units from box = overcrowding in center
- **Fix applied**: Gentler curriculum 10→5 over 500k steps, spawn radius 0.5-1.5
- **Expected**: Reduced initial collisions, better space utilization, lower OOB

## 6) Immediate Recommendations (R&D only; not autopilot overrides)
1. **Extend training to 1B+ timesteps** - Current 200M is far too short for this task complexity
2. **Fix curriculum decay** - Stretch grip_k decay over 50M+ timesteps, not 200K
3. **Remove velocity penalty** - It helped OOB but killed task learning
4. **Add grip attempt rewards** - Currently no learning signal for trying to grip
5. **Monitor within-run metrics** - Catch performance collapses early (epoch 64-65 pattern)
 - After gentler descent (−0.06) and wider grip gates (0.20·k), do ho/de_pickup increase without raising collisions? Applied spawn-near-box; validate OOB↓ and ho/de_pickup↑ before considering soft‑floor.
 - Drop approach gating: previously drop hover z‑window (0.7–1.3m) didn’t match target (+0.4m), likely suppressing `ho_drop` and `to_drop`. Adjusted to 0.3–0.6m and set `approaching_drop=true` upon carry; verify `to_drop↑, ho_drop↑`, OOB↓ during carry.
 - New: Require XY alignment before descent (pickup/drop); hold altitude until `xy_dist <= 0.20·max(k,1)`. Add near‑miss counters (`attempt_grip`, `attempt_drop`). Hypothesis: OOB↓ by preventing drift‑descent; ho/de_pickup↑; first non‑zero gripping.
 - Relax pickup hover gate further: admit hovering when `dist_to_hidden < 1.8` and `speed < 1.2` (was 1.0/0.8). Rationale: agents struggle to satisfy hover gate at typical spawn offsets; descent remains XY‑gated and gentle (−0.06 m/s). Expect ho/de_pickup↑ and attempt_grip↑ without increasing collisions.
- New: Relax grip vertical descent gate — require `vel.z > -max(0.15, 0.06·k)` (still `< 0`) during pickup grip. Rationale: at k≈1 the −0.06 m/s cap is too strict and blocks legitimate grips; allowing moderate descent should yield first non‑zero grips and `to_drop > 0` without increasing collisions.

## 6) Decisions Log
 - 2025-09-21T085023Z: Relax drop success gates to match pickup (XY,Z ≤ 0.40·k). Rationale: to_drop and ho_drop are non‑trivial but perfect_deliv is low; carry is noisier than pickup. Expect delivery_success↑ and OOB↔/↓ without impacting collisions.
 - 2025-09-21T091542Z: Remove post‑grip random_bump and widen spawn edge_margin 8→12. Rationale: reduce boundary exits and carry instability triggered immediately after gripping; expect OOB↓ (primary), to_drop/ho_drop↑, attempt_drop↑; collisions stable.
\- 2025-09-21T090309Z: Tighten XY gating and cap k in phase gates (pickup/drop). Applied k_eff=min(k,2.0) in hover/descent/grip/drop checks; require stronger XY alignment before descent (≤0.20·k_eff, cap 0.8m); revert hover_ok_hidden to 1.8m/1.2m; clamp hover_ok_xy to ≤min(0.35·k_eff, 1.5m); similarly cap drop hover/descent; spawn: edge_margin 8m, r_xy 0.4–1.0m. Rationale: early high‑k phases allowed far‑field descent/hover, driving OOB. Expect OOB↓, ho/de_pickup↑, attempt_grip↔/↑, to_drop/ho_drop↑; collisions stable.
 - 2025-09-21T092754Z: Reduce boundary fly‑offs (OOB≈0.82 trending up within run). Changes: cap BASE_MAX_VEL to 20 m/s (was 50), move box/drop further from edges (edge_margin 12→16 m), spawn closer laterally to box (r_xy 0.4–1.0→0.3–0.8). Hypothesis: less far‑field drift → OOB↓, longer episodes, ho/de_pickup↔/↑; grip/deliv signals preserved. Run: 2025-09-21T092754Z.

Note (reverts applied after Run 2025-09-21T061611Z):
- Physics damping test (REVERTED): Increasing BASE_B_DRAG/BASE_K_ANG_DAMP degraded behavior (OOB≈0.95). Reverted to BASE_B_DRAG≈0.10 and BASE_K_ANG_DAMP≈0.20 per failsafe. Avoid reintroducing unless strong evidence.
- Soft boundary fields (REVERTED): Removed soft walls/ceil/floor and XY centralizing field; they likely fought control and increased OOB.

## 5) Decisions Log
- 2025-09-21 (Run 2025-09-21T184615Z): OOB≈0.959 with zero ho/de/grip. Reapply stability edits: edge_margin=10m and z=−GRID_Z+1.5 for box/drop spawns; PP2 agent spawns away from edges and above floor; gentle boundary proximity penalty; distance‑scaled velocity penalty; PP2 obs use hidden hover; slow pickup/drop descent; global_tick curriculum clamped to (k_max−k_min)/200k. Expect OOB↓, ho/de_pickup↑, first grip attempts. Proposals `{}`.
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
 
- 2025-09-21 (Run 2025-09-21T173030Z): OOB ≈ 0.92 is the primary blocker. Do not add soft walls/center forces. Change: tighten PP2 XY spawn band with a simple curriculum in `reset_pp2` — edge_margin starts at 22 m and linearly relaxes to 14 m over ~200k global steps (uses `global_tick`); reduce lateral spawn radius r_xy from 0.3–0.8 to 0.2–0.6 around the box. Expected: OOB↓ materially, episode_length↑, ho/de_pickup maintained or ↑; collisions stable. Next: if OOB still >0.9, consider mild XY action governor; if OOB improves but grips=0, relax grip gates (diagnostic_grip path).
 - 2025-09-21T06:43:20Z (Run 2025-09-21T063752Z): OOB ≈ 0.953 persists with some grips, zero deliveries. Decision: reduce floor OOB by raising pickup/drop altitude in `drone_pp.h/reset_pp2` (z: −GRID_Z+0.5→−GRID_Z+1.5) and increase initial hover target offset (+0.6→+0.8 m). Hypothesis: OOB↓ (fewer floor strikes), ho/de_pickup stable or ↑, collisions ~2.2%; delivery gates unchanged. Next: if OOB still >0.9, consider lateral spawn band tightening before any physics helpers.

- 2025-09-21T070501Z: Remove proximity gating from velocity_penalty (drone_pp.h:compute_reward). Rationale: OOB≈0.95 from far-field runaways; penalize speed globally to curb drift while keeping approach shaping. Expect OOB↓, ho_drop↑, first deliveries as k→1.
- 2025-09-21 (CRITICAL FIX): Reverted harsh global velocity penalty that caused epoch 64→65 performance collapse (OOB 0.817→0.926, grips 0.98→0.19). Implemented gentle distance-scaled penalty: full strength <5m from target, 10% strength >25m. This preserves careful approach while allowing efficient far-field navigation.

- 2025-09-21 (Run 2025-09-21T072610Z): Clamp PP2 curriculum decay. Too‑fast decay (grip_k_decay=0.02) collapsed k→1 within ~900 steps, tightening gates prematurely and correlating with high OOB and weak carry/drop. Change: in `drone_pp.h::c_step`, use `decay = min(config_decay, (k_max−k_min)/200k)` with global_tick scheduling. Expect steadier phases, ho_drop↑, attempt_drop↑, first sustained deliveries; OOB↓. Keep proposals `{}`.
 - 2025-09-21 (Run 2025-09-21T073908Z): Carry-phase instability after grip; OOB≈0.865; to_drop/ho_drop low despite high ho/de_pickup. Change: call `update_gripping_physics()` immediately on grip in `drone_pp.h` so mass/inertia apply during carry. Expect OOB↓; to_drop/ho_drop↑; attempt_drop↑; more deliveries. Proposals `{}`.
 - 2025-09-21 (Run 2025-09-21T094027Z): OOB still high (≈0.82–0.84 across last 4 runs) with low deliveries; earlier epochs briefly better then regress by epoch 85. Decision: add mild XY boundary‑proximity penalty in `compute_reward` (0 when |x|,|y| ≤ 0.8·GRID; scales to −0.15 at boundary). Rationale: discourage far‑field runaways without re‑adding soft walls or centralizing forces. Expected: OOB↓ (primary), longer episodes, ho/de_pickup↔/↑, to_drop/ho_drop↑; collisions stable. Proposals `{}`.

- 2025-09-21T10:02:46Z | run complete | Run 2025-09-21T095422Z (iteration 6) | Decision: earlier, stronger XY boundary penalty in env/drone_pp.h (start at 0.6·GRID; weight −0.20). Expected: OOB↓, episode_len↑, to_drop/ho_drop↑; collisions stable.
- 2025-09-21T17:26:34Z | run complete | Run 2025-09-21T171823Z (iteration 1) | Decision: revert boundary proximity shaping to gentler version (start at 0.8·GRID; weight −0.15) after regression (oob≈0.921, perfect_grip=0). Keep spawn/physics/curriculum unchanged. Expect OOB↓, ho/de_pickup↔/↑, first non‑zero grips; collisions stable.
 - 2025-09-21T18:04:10Z | env change staged | Reduce BASE_MAX_VEL 20→12 m/s in `dronelib.h` to curb far‑field runaways causing OOB≈0.97 in Run 2025-09-21T175631Z. Rationale: lower per‑step displacement without adding drag/soft walls; preserves control authority. Expected: OOB↓ (primary), episode_len↑, ho/de_pickup↔/↑; collisions stable. Proposals `{}`.
 - 2025-09-21T18:11:03Z | run 2025-09-21T180522Z analysis | OOB≈0.969 with ho/de_pickup>0 but zero grips/deliveries. Decision: in `drone_pp.h`, raise PP2 spawn altitude (+2.5–3.5 m), add tiny initial upward dz (+0.03–0.08 m/s), slow pickup/drop descent (−0.05 m/s), slightly raise initial hover (+0.9 m). Expect OOB↓, attempt_grip↑, to_drop↑. Proposals `{}`.

- 2025-09-21T18:21:15Z | Run 2025-09-21T181559Z: OOB ≈ 0.968 (critical). Decision: add gentle early action scaling ramp (0.7→1.0 over ~100k global steps) in drone_pp.h before move_drone; no hparam changes. Hypothesis: reduce early saturation → OOB↓, ho/de_pickup ↔/↑, attempt_grip ↑; monitor for first non‑zero grips before touching drop.
