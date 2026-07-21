# F4 — Verifier hardening, attack generation and trust-gate service (core moat) / F5 — Coverage, OOD, abstention and human-escalation router

Two components share this subdirectory: F4 demonstrates validators/graders distinguish acceptable from strategically-wrong outputs under attack; F5 safely routes cases outside coverage instead of forcing a plausible answer.

Plane: F (Verification, hardening, escalation) · Phase: 5 — Verifier-trust proof (`BLOCKED`)

New subdirectory — harvey-labs has no attack/OOD-routing concept to fork.

## F4 — Build

- [ ] Fabricated/near-match citation attack generator
- [ ] Opposite-proposition/overruled/wrong-jurisdiction/dicta/context attacks
- [ ] Superseded-document, wrong-trigger-date/math, omitted-adverse-authority, plausible-non-issue attacks
- [ ] Verbose-dispositive-omission, internal-inconsistency, keyword/rubric-gaming, prompt-injection attacks
- [ ] Grader-reject-all canary, criterion/graph mutation, best-of-N/adversarial-optimization runner
- [ ] Exploit-family registry, paired gold-accept/attack-reject runner, trust-card generator

**Depends on:** C2, D3/D4, F1–F3. Feeds the trusted pool, G1/G3/G4/G5.
**Posture:** Build as core moat; integrate generic fuzzing/mutation/attack orchestration and external red-team services.
**Done when:** both gold acceptance and attack rejection pass; FP/FN confidence bounds exist by severity; attack catch rate is measured against hidden families.
**Avoid:** an attack-only gate passed by a reject-all grader; suite overfit; the same generator producing both attacks and defenses; ever claiming "zero false positives" instead of "0 observed under suite S, budget B."

## F5 — Build

- [ ] Rule/ontology coverage trace and source-completeness checks
- [ ] No-match/multiple-match detection and an intentionally-uncovered evaluation set
- [ ] Embedding/structure novelty detection, conflict/grader-disagreement signals, calibrated confidence
- [ ] Severity/authorization policy and selective-prediction logic
- [ ] Human queue, sampling of auto-accepted work, correction/newly-discovered-issue feedback loop

**Depends on:** A4, B4, C4, F1–F4. Feeds G1/G2/G4/G5 and human operations.
**Done when:** selective-risk-vs-coverage curves are measured; escalation precision/recall is tested on intentionally uncovered cases.
**Avoid:** self-reported model confidence used as the sole OOD detector; excessive escalation destroying unit economics; low escalation hiding silent omissions.

## AR experiment

**F4:** attack suite validated inline with AR-003/AR-004 (no separate ID). **F5: run AR-005 here** — high-severity error rate among auto-accepted cases as a function of coverage; adopt only operating points with a measured risk-coverage advantage.
