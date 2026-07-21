# G3 — Demonstration, SFT, critique/revision, RL and rollout orchestration

Improves a target checkpoint using trusted, rights-cleared tasks and decomposed rewards while preserving reproducibility.

Plane: G (Diagnosis, learning, proof, operations) · Phase: 6 — Conditional changed-checkpoint proof (`BLOCKED`, only if claiming model improvement)

## Build

- [ ] Expert-demonstration/corrected-work-product loader and proof-carrying SFT formatter
- [ ] Tool-use/source-grounding SFT and critique/revision training
- [ ] Rollout scheduler and group-relative (or selected) RL trainer
- [ ] Deterministic-anchor reward integration with lower-weighted semantic reward, dynamic sampling
- [ ] Checkpoint/seed registry, compute accounting, safety/untargeted-regression suite

**Depends on:** A2, D4, E1–E4, F1–F4, G2. Evaluated by G4.
**Posture:** Integrate/fork mature training/rollout frameworks (TRL/veRL/vLLM); build legal data adapters, decomposed-reward wiring, protected-split enforcement, checkpoint lineage. **Compute constraint: "rent GPU/compute" means Modal Labs GPU-attached Functions specifically** — not RunPod/CoreWeave/other GPU clouds. The training frameworks themselves are unaffected (they run inside Modal containers).
**Done when:** the checkpoint's weights genuinely changed; seeds/lineage are reproducible; training never reads private holdout/qualification data.
**Avoid:** prompt/runtime-only changes mislabeled as training; reward hacking; training on the public benchmark and then claiming held-out proof.

## AR experiment

None directly — G3's output (the changed checkpoint) is what AR-008 (G4) proves or disproves.
