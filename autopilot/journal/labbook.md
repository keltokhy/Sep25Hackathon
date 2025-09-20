# Autopilot Lab Book

> Append entries with `- YYYY-MM-DDTHH:MM:SSZ | action | observation | outcome | next`.

- 2025-09-20T23:30:27Z | train quick baseline | no grip; ho_pickup=0, perfect_* = 0; oob~0.95; sps~17k | patched env to target hidden_pos for hover then box_pos for descent; rebuilt bindings | rerun fresh; expect ho_pickup>0 and first grips
- 2025-09-20T23:30:55Z | run complete | Run 2025-09-20T232651Z (iteration 1) | metrics captured | 
- 2025-09-20T23:34:31Z | run complete | Run 2025-09-20T233055Z (iteration 2) | metrics captured | 
- 2025-09-20T23:45:00Z | revert env file | restored `drone_pp.h` to upstream commit 552502e (2025-09-20) | removed autopilot curriculum/gate relaxations; working tree clean for that file | update prompt to use notes as long‑term memory; plan fresh baseline
- 2025-09-20T23:55:00Z | refactor prompt | resolved no‑hparam contradictions; reorganized prompt per OVERVIEW/WORKFLOW/DECISIONS/CAN‑CHANGE/CANNOT‑CHANGE/TECHNICAL; added checklist, success metrics, failsafes | agent now treats Notes as long‑term memory and avoids hyperparameter edits | run fresh baseline to validate clarity
- 2025-09-21T00:03:00Z | prompt add history ref | updated prompt to explicitly consult Notes → “Header evolution: `drone_pp.h`” before edits | preserves historical intent; avoids re‑introducing removed patterns | proceed with fresh baseline under clarified guardrails
- 2025-09-20T23:50:08Z | ignore overrides | Dropped keys ['autopilot.resume_mode', 'autopilot.save_strategy'] per no-hparam policy | using baselines | 
