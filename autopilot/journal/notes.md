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
- 2025-09-21T19:18Z | Run 2025-09-21T191359Z: OOB≈0.961 (no change), perfect_grip=0, ho/de_pickup=0. Decision: revert boundary action softening and slow early action ramp (0.5→1.0 over ~400k steps); raise PP2 spawn z (+1.0 m) and z-floor threshold (−GRID_Z+1.0, +0.3 if gripping). Hypothesis: OOB↓ (primary), episode_length↑, first ho_pickup>0.005.
 - 2025-09-21T19:30Z | Run 2025-09-21T192339Z: OOB≈0.954, ho_pickup≈0.004 (peaks ~0.028), zero grips/deliveries. Decision: relax Phase‑1 pickup hover gate in `drone_pp.h` (dist_to_hidden 0.4→0.8; speed 0.4→0.6). Hypothesis: ho_pickup↑, de_pickup↑; modest OOB↓ as policies spend longer near boxes; collisions stable.
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
 - 2025-09-21 (Run 2025-09-21T185523Z): OOB≈0.962; grips/deliveries=0; ho/de_pickup≈0.001. Implement gentle early action scaling in `drone_pp.h` (scale actions by 0.7→1.0 over ~100k global steps) before `move_drone`. Hypothesis: fewer boundary fly‑offs; OOB↓; episode_length↑; initial hover/descent signals become measurable. Proposals `{}`.
- 2025-09-21 (Run 2025-09-21T190433Z): OOB≈0.960 persists; no hover/descend/grip events. Change staged for next run: (a) boundary-aware action softening near XY walls (scale actions 1.0→0.5 from 90–100% GRID) to cut fly-offs without soft walls; (b) increase spawn edge_margin 10→17 for drones/box/drop to centralize starts. Expect OOB −20–30pp; ho_pickup > 0.005; collisions ↔. Proposals `{}` (fresh).
 - 2025-09-21T19:39:21Z | Run 2025-09-21T193424Z: OOB≈0.955 (Δ vs prev −0.005), perfect_grip=0, perfect_deliv=0; ho_pickup≈0.013 (Δ +0.009), de_pickup≈0.012 (Δ +0.012); to_pickup≈2938 (Δ +340); to_drop/ho_drop=0.
   Decision: OOB still the primary blocker. Keep relaxed hover gate; slow early action ramp further (0.5→1.0 over ~800k global steps) in `drone_pp.h::c_step` to reduce early fly‑offs without physics helpers. Expected: OOB↓, episode_length↑, ho/de_pickup↗; collisions stable. Next: if ho/de improve but grips remain 0, consider slightly relaxing pickup descent gates.

## 5) Decisions Log (2025‑09‑21)
- 2025‑09‑21T19:49:13Z (iter 7, run 2025‑09‑21T194416Z)
  • Result: oob≈0.952 (Δ vs prev −0.003), ho/de_pickup≈0.004/0.004 (Δ −0.009/−0.008), mean_reward≈31.14 (Δ +4.64), ep_len≈50.94 (Δ +3.13); perfect_grip/deliv=0.
  • Change: Increase PP2 spawn edge_margin 17→20 for box/drop and drone spawns (no soft walls). Rationale: reduce immediate boundary fly‑offs; centralize early experience near pickup.
  • Expected: OOB↓; ho/de_pickup↑; collisions ↔. Interactions: complements mild boundary proximity penalty (−0.15) without introducing helper forces.
  • Next config: {autopilot.resume=continue latest, save=best}.

## 7) Decisions Log
- 2025-09-21T21:49:34Z (run 2025-09-21T214439Z): Decouple success metrics from k. Perfect_* tied to k<1.01 never register under slow curriculum that resets each run. Implement strict, k‑independent envelopes for marking perfect_grip/deliv; keep acceptance gates unchanged. Expect perfect_* > 0 if true behaviors occur; continue from latest.

## 8) Open Questions & Next Hypotheses
- If perfect_* stay zero next run while `gripping`/`delivered` rise, relax strict envelopes slightly (XY/Z +0.05) or add a brief post‑grip hold requirement to reduce bounce false negatives.
- If OOB continues to rise (>0.72), consider modestly increasing boundary proximity penalty (from 0.15→0.20) or widening spawn z floor by +0.5 m.
 - New (2025-09-21T21:58Z): Despite ho/de_pickup↑ and to_drop↑, perfect_grip=0 with attempts flat. Hypothesis: pickup floors still block conversion at k≈1 and strict perfect envelope masks first wins. Action: relax pickup floors (XY 0.90, Z 0.70, speed 1.00, |vz|≤0.45, z>−0.30) and slightly relax perfect envelope (XY 0.50, Z 0.45, speed 0.80, |vz|≤0.25). Expect attempt_grip↑ and first perfect_grip>0 with OOB ≤0.70.
 - 2025‑09‑21T20:18:25Z (iter 10, run 2025‑09‑21T201321Z)
   • Result: mean_reward≈18.14 (Δ vs 195318Z −46.30; vs best 200258Z −183.80), ep_len≈330.80 (Δ +129.83), sps≈1.79M; oob≈0.678 (Δ vs 195318Z −0.127; vs best +0.288); collision_rate≈0.083 (Δ +0.072); perfect_grip=0, perfect_deliv=0; ho/de_pickup≫ (≈3.17k/3.15k); to_drop≈3.04k; ho_drop≈0.75k; attempt_grip>0; attempt_drop≈4.7.
   • Diagnosis: Pickup hover/descend OK; near‑miss grips appear, but actual grips blocked by narrow gates (speed<0.20, vz∈[−0.08,0]).
   • Change: In `drone_pp.h::c_step` Phase 2 (pickup), relax floors: XY 0.30 (was 0.20), Z 0.25 (was 0.20), speed 0.35 (was 0.20), |vz|≤0.12 (was 0.08) and allow slight contact (z>−0.02) while still requiring near‑zero descent (vz≤0.05). No physics helpers added.

- 2025‑09‑21T21:08:35Z (iter 15, run 2025‑09‑21T210327Z)
  • Result: perfect_grip=0.000 (↔), perfect_deliv=0.000 (↔); to_pickup≈18.21k (Δ −3.05k), ho/de_pickup≈2.52k/2.48k (Δ −0.98k/−0.99k), to_drop≈2.32k (Δ −1.04k), ho_drop≈506 (Δ +312); attempt_grip≈0.357 (Δ +0.006), attempt_drop≈3.326 (Δ +2.033); oob≈0.722 (Δ +0.047), collision_rate≈0.086 (Δ −0.011); score≈31.30 (Δ +0.86); epoch=85; sps≈1.78M.
  • Diagnosis: Curriculum clamp to ~50M keeps k near k_max for an entire run (per‑env global_tick≈180k at epoch 85). Since perfect_* credit requires k≈1, successes remain 0 despite visible carry/drop activity. Warm‑start across runs doesn’t advance k because env global_tick resets on init.
  • Change: Revert curriculum clamp to ~200k‑step decay (max_decay=(k_max−k_min)/200k) in `drone_pp.h` so k reaches strict regime within one run; keep relaxed pickup/drop floors so feasibility persists at k≈1.
  • Expected: attempt→grip conversion appears and perfect_grip/deliv become >0; OOB stable (≤0.78); collisions ≤0.11.
   • Expected: attempt_grip↑ and first grips; to_drop/ho_drop↑; OOB stable (≤0.70); collisions ≤0.09. Interactions: complements slow k‑decay and early action scaling; watch for floor taps (min_z buffer already +0.3m when gripping).
   • Next config: {autopilot.resume=continue latest, save=best}.
 - 2025‑09‑21T19:58:05Z (iter 8, run 2025‑09‑21T195318Z)
  • Result: oob≈0.805 (Δ vs prev −0.147), ho/de_pickup≈24.18/24.10 (≫), ho_drop≈0.108, attempt_grip=0, perfect_grip/deliv=0; mean_reward≈64.44 (Δ +33.30), ep_len≈200.97 (Δ +150.03), coll_rate≈0.0102.
  • Diagnosis: Phase emergence (hover/descend) without gripping → pickup gates too strict given k decays to 1.0 within ~200k global steps vs 200M total.
 • Change: In `drone_pp.h`, slow curriculum cap to (k_max−k_min)/50M (from /200k) so lenient gates persist far longer; add logging-only near‑miss counter (`attempt_grip`).
 • Expected: attempt_grip>0 and first grips; OOB stays ≤0.82; collisions stable.
 • Next config: {autopilot.resume=continue latest, save=best}.
 - 2025‑09‑21T20:02:58Z (iter 9, run 2025‑09‑21T200258Z)
  • Result: oob≈0.390 (Δ vs 195318Z −0.415), mean_reward≈201.94 (Δ +137.50), ep_len≈625.41 (Δ +424.44), coll_rate≈0.0211; ho/de_pickup≫ (≈5.29k/5.28k), ho_drop≈88–97; perfect_grip/deliv=0; attempt_grip=0; to_drop=0 due to missing flag.
  • Change: Relax pickup grip gate with floors (XY/Z/speed/vel_z) to allow grips at k≈1; apply gripped mass/drag immediately upon grip; set `approaching_drop` during carry/drop and log `attempt_drop` near‑misses.
  • Expected: attempt_grip>0 and first grips; `to_drop`>0 with ho_drop↗; OOB ≤0.45; collisions 2–3%.
  • Next config: {autopilot.resume=continue latest, save=best}.
 - 2025‑09‑21T20:27:20Z (iter 11, run 2025‑09‑21T202241Z)
  • Result: OOB≈0.463 (Δ vs prev −0.215), collision_rate≈0.043 (Δ −0.040), ep_len≈550.80 (Δ +220.00); perf≈0.283 (Δ −0.055); mean_reward≈−5.80 (Δ −23.94); attempts/events collapsed (attempt_grip≈0.001, attempt_drop≈0.003; ho/de_pickup≈3.2/3.2; to_drop≈2.9; ho_drop≈1.0). Grips/deliveries remain 0.
  • Diagnosis: Pickup gating still too strict at k≈1; near‑miss window too narrow → policy rarely registers attempts, preventing carry/drop.
  • Change staged (env/drone_pp.h): widen near‑miss window and relax pickup grip floors further: near_xy 0.40, near_z 0.35 (allow z>−0.10), grip_xy≥0.40, grip_z≥0.35, speed<0.50, |vz|≤0.18. No physics helpers; spawn/curriculum unchanged.
  • Expected: attempt_grip↑ and first non‑zero grips; to_drop/ho_drop↗; OOB stays ≤0.50; collisions ≤0.06.
  • Next config: {autopilot.resume=continue latest, save=best}.
 - 2025‑09‑21T20:38:40Z (iter 12, run 2025‑09‑21T203215Z)
   • Result: oob≈0.723 (Δ vs prev +0.260), collision_rate≈0.098 (Δ +0.055), ep_len≈284.96 (Δ −265.84); mean_reward≈31.68 (Δ +37.47); attempt_grip≈0.379; to_drop≈2646; ho_drop≈420; perfect_grip=0, perfect_deliv=0.
   • Diagnosis: Hover/descend established; pickup grip gate still too strict at k≈1; drop release tolerances too tight.
   • Change: Relax pickup grip acceptance (z > −0.06; speed<max(0.55, 0.35·k); |vz|≤0.22, vz≤0.08). Relax drop release (XY/Z < max(0.30, 0.25·k), z>−0.10). No physics helpers.
   • Expected: attempt_grip↗ and first grips; delivery attempts↗; early deliveries possible; OOB ≤0.78; collisions ≤0.12.
   • Next config: {autopilot.resume=continue latest, save=best}.

- 2025‑09‑21T20:47:51Z (iter 13, run 2025‑09‑21T204227Z)
  • Result: OOB≈0.485 (Δ vs 203215Z −0.238), collision_rate≈0.038 (Δ −0.060), ep_len≈527.81 (Δ +242.85); perf≈0.301 (Δ −0.023); perfect_grip/deliv=0; attempts/events regressed vs 203215Z (attempt_grip≈0.043, to_drop≈298, ho_drop≈22).
  • Hypothesis: pickup conversion still too strict; ho gate a bit tight when policy noisy → fewer descents and near‑misses.
  • Change: Widen hover gate (dist<1.0, speed<0.8). Relax pickup grip acceptance slightly (z floor −0.10 from −0.06; vz≤0.12 from 0.08; grip_z_tol floor 0.40). No physics/reward changes.
  • Expected: ho_pickup↑, attempt_grip↑, first non‑zero grips; OOB ≤0.55; collisions ≤0.06.
  • Next: continue from latest; reassess attempt→grip conversion; if attempts rise without grips, relax vz window further or add small attempt reward.

- 2025‑09‑21T20:58:21Z (iter 14, run 2025‑09‑21T205326Z)
  • Result: OOB≈0.675 (Δ vs 204227Z +0.190), collision_rate≈0.097 (Δ +0.059), ep_len≈333.90 (Δ −193.91), mean_reward≈30.43 (Δ +13.92); ho/de_pickup≫ (≈3.50k/3.47k), to_drop≈3.36k, ho_drop≈194; attempt_grip≈0.351; perfect_grip/deliv=0.
  • Diagnosis: Hover/descend established; “descending but can’t grip” persists at k≈1. Acceptance remains too strict (speed/vz/XY/Z) causing near‑misses without conversion.
  • Change: Relax pickup floors further (XY 0.50, Z 0.45, speed 0.60, |vz|≤0.15 with descent not faster than 0.28). Broaden near‑miss window (XY/Z +0.05; speed +0.10). Physics/drag unchanged; spawn unchanged; curriculum clamp remains.
  • Expected: attempt_grip↑ and first non‑zero perfect_grip; to_drop/ho_drop↗; OOB ≤0.70; collisions ≤0.11.
  • Next config: {autopilot.resume_mode="continue", resume_from="latest", save_strategy="best"}.
 
 - 2025‑09‑21T21:19:50Z (iter 16, run 2025‑09‑21T211342Z)
  • Result: oob≈0.50 (Δ vs 210327Z −0.23), collision_rate≈0.045 (Δ −0.041); ho/de_pickup dropped sharply; attempt_grip≈0.08; perfect_grip/deliv=0.
  • Diagnosis: Curriculum clamp back to ~200k improved stability, but pickup acceptance still too strict at k≈1 causing “descend without grip”.
  • Change: relax pickup floors again in `drone_pp.h` to convert near‑misses: XY 0.60, Z 0.55, speed 0.75, |vz|≤0.35, allow z>−0.20 and vz≤0.20. Physics/spawn unchanged; curriculum clamp unchanged.
  • Next: continue from latest; expect attempt_grip↗ and first non‑zero grips with OOB ≤0.55.

- 2025‑09‑21T22:07:20Z (iter 21, run 2025‑09‑21T220242Z)
  • Result: oob≈0.566 (Δ vs 215341Z −8.1pp), collision_rate≈0.045 (Δ −1.3pp), mean_reward≈32.25 (Δ −3.71), ep_len≈445.46; attempts down vs prev (attempt_grip≈0.222, attempt_drop≈0.803); phases present (ho/de_pickup≈2.04k/2.02k, to_drop≈1.99k, ho_drop≈130); perfect_grip/deliv=0.
  • Diagnosis: Stability improved, but strict “perfect” envelopes likely suppress success recognition at k≈1 despite active carry/drop.
  • Change: In `drone_pp.h` — revert curriculum clamp to ~200k-step max_decay (was 5M) so k reaches easy regime earlier; relax strict perfect envelopes (pickup: XY<0.60, Z<0.55, speed<0.90, |vz|≤0.30; drop: XY<0.50, Z<0.45). Keep acceptance gates unchanged.
  • Expected: first non‑zero perfect_grip and possibly perfect_deliv; attempts stable; OOB ≤0.60; collisions ≤0.07.
  • Next: {autopilot.resume_mode="continue", resume_from="latest", save_strategy="best"}.

- 2025‑09‑21T21:40:11Z (iter 18, run 2025‑09‑21T213444Z)
  • Result: mean_reward≈37.91 (Δ vs prev +3.88), ep_len≈390.15 (Δ +73.46), collision_rate≈0.074 (Δ −0.021), SPS≈1.63M; UI: oob≈0.620 (Δ −3.4pp vs prev tail); attempt_grip≈0.379; attempt_drop≈1.332; perfect_grip/deliv=0.
  • Change: env/drone_pp.h — slow curriculum 25× (k_decay cap (k_max−k_min)/5M vs /200k) and relax acceptance floors: pickup (XY 0.70, Z 0.60, speed 0.85, |vz|≤0.35; z>−0.30, vz≤0.30); drop near/accept (near XY/Z 0.50/0.35; accept XY/Z 0.40/0.35).
  • Expected: attempt_grip↑ and first non‑zero perfect_grip; to_drop/ho_drop↑; first deliveries plausible; OOB ≤0.70; collisions ≤0.10.
  • Proposal: {autopilot.resume_mode="continue", resume_from="latest", save_strategy="best"}.
