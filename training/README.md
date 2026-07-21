# training/ — Plane G (part 1): Diagnosis, learning, proof

New directory with no harvey-labs equivalent. Runs *after* `evaluation/`, consuming its `scores.json`, and needs its own frozen-holdout/split-manifest concerns (D4) harvey-labs has no reason to model since it has no train/eval leakage problem. **conditional phase, only if claiming model improvement**, currently `BLOCKED`.

| Component | Directory | Role |
|---|---|---|
| G1 | [g1-capability-diagnosis-failure-atlas/](g1-capability-diagnosis-failure-atlas/) | Target-model capability diagnosis and failure atlas — **AR-006 runs here** |
| G2 | [g2-curriculum-regeneration-controller/](g2-curriculum-regeneration-controller/) | Difficulty, curriculum, regeneration and lifecycle controller — **AR-007 runs here** |
| G3 | [g3-sft-rl-rollout-orchestration/](g3-sft-rl-rollout-orchestration/) | Demonstration, SFT, critique/revision, RL and rollout orchestration |
| G4 | [g4-frozen-holdout-proof-harness/](g4-frozen-holdout-proof-harness/) | Frozen-holdout proof, lawyer-blind review and economic acceptance harness — **AR-008, AR-009, AR-010 run here** |

G5 (artifact registry, packaging, deployment, refresh) is a separate directory: see `../registry/`.

**Compute constraint:** G3's "rent GPU/compute" means Modal Labs GPU-attached Functions specifically — not RunPod/CoreWeave/other GPU clouds.
