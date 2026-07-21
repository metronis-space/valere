# D4 — Dataset registry, split compiler, deduplication and contamination control

Preserves independent training, grader qualification, attacks, regressions, and private proof so success can't come from leakage.

Plane: D (Task, rubric, dataset factory) · Phase: 4 — Executable task/runtime proof (`BLOCKED`)

New directory — harvey-labs has no split/contamination concept to fork (per the repository architecture).

## Build

- [ ] Artifact/content hashing and semantic/structural near-duplicate detection
- [ ] Matter-family/template/rule/transformation/source/time/jurisdiction grouping
- [ ] Train/SFT/RL, grader-qualification, attack, regression, and frozen-private-holdout splits
- [ ] Public-benchmark separation, access control/unblinding, lineage and deletion propagation

**Depends on:** A2/A3, D2/D3. Feeds F3/F4, G1/G3/G4/G5.
**Posture:** Build split policy + legal-family leakage logic; integrate storage/catalog/fingerprinting primitives.
**Done when:** zero known exact duplicates cross protected boundaries; group separation holds by every declared axis; holdout access audit passes.
**Avoid:** a random row split across the same matter/template; public tasks used for both training and proof; paraphrases bypassing text-only dedup.

## AR experiment

None directly — D4's splits are what make AR-006 through AR-010 (Phase 6) valid rather than leaked/inflated.
