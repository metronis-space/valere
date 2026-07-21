# F2 — Qualified semantic grader and decomposed reward composer

Evaluates semantic equivalence, completeness, and drafting fidelity only where exact validation is insufficient — kept inspectable and anchored.

Plane: F (Verification, hardening, escalation) · Phase: 5 — Verifier-trust proof (`BLOCKED`)

Forked from harvey-labs' `evaluation/judge.py` using the repository fork layout — replace the judge prompts; this is the semantic half of the judge.py split (F1 is the deterministic half, in `../validators/`).

## Build

- [ ] Per-criterion grader and controlled criterion batching
- [ ] Evidence-required decision format with separate correctness/completeness/instruction/drafting/recommendation dimensions
- [ ] Abstention, multiple prompt/model paths, severity weights
- [ ] Deterministic-anchor precedence, reward cap/component vector, contradiction checker
- [ ] Grade-rationale and confidence capture

**Depends on:** D3, E1/E2, F1. Feeds F3–F5, G1/G3/G4. **Cannot qualify itself.**
**Posture:** Buy/self-host candidate base models; build grading prompts/contracts, reward composition, evidence enforcement, multi-path orchestration.
**Done when:** qualification agreement is measured by criterion family/severity; evidence faithfulness holds; reward correlates with lawyer correction time, not verbosity.
**Avoid:** style/length/keyword bias; the grader sharing the generator's misconception (common-mode failure); a high average pass hiding one fatal omission.

## AR experiment

None directly — F2 is qualified by F3's AR-004, not tested standalone (it cannot qualify itself).
