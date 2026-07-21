# G2 — Difficulty, curriculum, regeneration and lifecycle controller

Selects coherent, learnable, verifier-reliable task distributions; raises or regenerates difficulty; retires stale/hacked items.

Plane: G (Diagnosis, learning, proof, operations) · Phase: 6 — Conditional changed-checkpoint proof (`BLOCKED`, only if claiming model improvement)

## Build

- [ ] Multidimensional difficulty vector and model pass-rate sampler
- [ ] Item-response/pass-band estimation across document/noise/issue/severity/conflict/jurisdiction/time/procedural/tool-depth axes
- [ ] Pairwise/t-wise and risk-weighted coverage, failure-cluster-to-task mapping
- [ ] Sampling/mixing policy, saturation/all-pass/all-fail detection
- [ ] Counterfactual/regeneration planner, dependency-change listener, quarantine/reverify/retire state machine, budget/cost controller

**Depends on:** G1, B4, C2, D4, F4/F5. Triggers regeneration in C1–C3 and training in G3; refresh events flow to G5.
**Posture:** Build experimentally as a differentiated controller; integrate generic optimization/scheduling/statistical tools.
**Done when:** empirical difficulty ordering is established (or explicitly rejected); verifier false-accept/reject rates don't degrade faster than model performance.
**Avoid:** document length mistaken for legal difficulty; the ladder entering an untrusted-verifier regime; endless regeneration breaking unit economics.

## AR experiment

**Run AR-007 here:** transfer must persist across genuinely held-out families (dedup-adjusted), not just template-near examples.
