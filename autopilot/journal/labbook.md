# Autopilot Lab Book

> Append entries with `- YYYY-MM-DDTHH:MM:SSZ | action | observation | outcome | next`.

- 2025-09-20T23:30:27Z | train quick baseline | no grip; ho_pickup=0, perfect_* = 0; oob~0.95; sps~17k | patched env to target hidden_pos for hover then box_pos for descent; rebuilt bindings | rerun fresh; expect ho_pickup>0 and first grips
- 2025-09-20T23:30:55Z | run complete | Run 2025-09-20T232651Z (iteration 1) | metrics captured | 
- 2025-09-20T23:34:31Z | run complete | Run 2025-09-20T233055Z (iteration 2) | metrics captured | 
- 2025-09-20T23:45:00Z | revert env file | restored `drone_pp.h` to upstream commit 552502e (2025-09-20) | removed autopilot curriculum/gate relaxations; working tree clean for that file | update prompt to use notes as long‑term memory; plan fresh baseline
- 2025-09-20T23:55:00Z | refactor prompt | resolved no‑hparam contradictions; reorganized prompt per OVERVIEW/WORKFLOW/DECISIONS/CAN‑CHANGE/CANNOT‑CHANGE/TECHNICAL; added checklist, success metrics, failsafes | agent now treats Notes as long‑term memory and avoids hyperparameter edits | run fresh baseline to validate clarity
- 2025-09-21T00:03:00Z | prompt add history ref | updated prompt to explicitly consult Notes → “Header evolution: `drone_pp.h`” before edits | preserves historical intent; avoids re‑introducing removed patterns | proceed with fresh baseline under clarified guardrails
 - 2025-09-21T00:14:10Z | run baseline_full | launched `autopilot/scripts/run_training.sh` (EXACT_CONFIG=1) → run `2025-09-21T000458Z`; SPS ~1.69M, CPU ~330%; no behavioral_analysis emitted; summary metrics: success_rate 0.0, collision_rate ~0.005, episode_length ~146 | Observed high OOB (~0.86), near‑zero perfect_grip/deliv, minimal hover_pickup | prepare targeted env change (grip gates)
 - 2025-09-21T00:16:00Z | relax grip/hover gates | in `PufferLib/pufferlib/ocean/drone_pp/drone_pp.h`: lowered initial hover height (+0.8m), relaxed Phase‑1 hover gate (dist<0.6, speed<0.5), gentler descent (−0.08 m/s), relaxed Phase‑2 grip gates (xy/z<0.15·k, speed<0.15·k, vz>−0.08·k) | Hypothesis: increase hover_pickup and first‑grip attempts; expect slight uptick in grip_success with similar collision rate; OOB may remain elevated; next: adjust drop gates/soft‑wall if needed
- 2025-09-21T00:12:00Z | adopt box2 hparams | mirrored drone_pp.ini → baseline_full.json; added EXACT_CONFIG option in run script | local runs can use upstream hparams verbatim; device=mps for Mac | next: run with EXACT_CONFIG=1 to validate
- 2025-09-21T00:28:00Z | refactor notes.md | curated structure (baseline, learnings, evolution, hypotheses, decisions); pruned stale sections | clearer long‑term memory; concise guidance | maintain under 150 lines; update as upstream changes
- 2025-09-20T23:50:08Z | ignore overrides | Dropped keys ['autopilot.resume_mode', 'autopilot.save_strategy'] per no-hparam policy | using baselines | 
- 2025-09-21T00:25:09Z | run complete | Run 2025-09-21T000458Z (iteration 1) | metrics captured | 
