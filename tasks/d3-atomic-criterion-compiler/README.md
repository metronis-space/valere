# D3 — Atomic criterion, rubric, evidence and example compiler

Turns matter state + rules into gradable, leak-free tasks. **Two-stage build:** harness proof against hidden state alone (Phase 2, one issue family, no documents), then full build across the whole D1 catalog (Phase 4).

Plane: D (Task, rubric, dataset factory) · Phases: 2 — Canonical-state compiler proof (harness, `POV_COMPLETE`) and 4 — Executable task/runtime proof (full build, `BLOCKED`)

## Build — Phase 2 (harness proof only)

- [x] Criterion grammar and truth-source/verification-mode assignment
- [x] Prove issue-identification/exact-span checks and operative-fact extraction compile directly from C1/C2 state
- [x] Prove trigger/application/consequence/calculation/severity/recommendation compile from B4 rules + state
- [x] Generate positive/negative/borderline examples and expected-delta counterfactual tests for one issue family, end to end

**Depends on:** B4, C1/C2.
**Posture:** Build the compiler/registry; seed from public rubrics (Harvey LAB); models only draft candidate paraphrases.
**Done when (Phase 2):** 100% criterion provenance for the one proven family; atomicity/satisfiability holds; paired gold/negative examples exist.
**Avoid:** encoding the expected conclusion without a source; the generator and compiler sharing a systematic misconception (the common-mode failure the whole architecture is designed to prevent).

## Build — Phase 4 (full build)

- [ ] Extend to full criterion coverage: dependent-document reconciliation, missing-information/abstention, deliverable/audience checks
- [ ] Required/optional and AND/OR criterion logic with tolerances
- [ ] Criterion satisfiability and deduplication checking across the full catalog

**Depends on:** B4, C1/C2/C4, D2. Feeds D4, F1–F4, G1/G3/G4.
**Done when (Phase 4):** the Phase-2 gates now hold across the full D1 catalog, not just one issue family.
**Avoid:** one criterion bundling many propositions; unsupported severe issues silently omitted.

## AR experiment

None directly — D3's output (`criteria[]` / CriterionBundle) is what AR-003 through AR-005 (Phase 5, F1–F5) grade against.
