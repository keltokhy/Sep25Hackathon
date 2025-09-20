# Autopilot Notes

- Use this space to track what worked, what failed, and hypotheses for next runs.

Troubleshooting summary (2025-09-20):
- Heavy MPS launch “stuck” after brief CPU spike; likely caused by vec/env mismatch or MPS cold kernel compile.
- Serial probe (1 env, 1 drone, tiny batch) works reliably on MPS; dashboard appears within ~60s.
- Small Multiprocessing probe (2 workers, 2 vec envs, 1 env.num_envs, 1 drone) also works but only ~10% CPU total (expected at small scale).
- Invariants to respect as we scale:
  - vec.num_envs must be divisible by vec.num_workers.
  - batch_size must be divisible by (vec.num_envs / vec.num_workers).
  - Prefer OMP_NUM_THREADS/MKL_NUM_THREADS aligned with physical cores.
- Next: scale workers/envs stepwise (14/28 → 28/56), keep batch modest, confirm regular log output, then raise batch/env.drones.
