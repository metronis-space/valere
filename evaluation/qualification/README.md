# F3 — Grader qualification, lawyer adjudication and requalification service

Establishes when a semantic grader may decide a task family, and provides an independent resolution path for disagreement and drift.

Plane: F (Verification, hardening, escalation) · Phase: 5 — Verifier-trust proof (`BLOCKED`)

New subdirectory — harvey-labs has no grader-qualification/lawyer-adjudication concept to fork.

## Build

- [ ] Qualification-set registry and blind lawyer-labeling workflow
- [ ] Second-reviewer workflow, disagreement analysis, adjudication panel
- [ ] Practice/workstream-specific qualification with severity strata
- [ ] Inter-rater agreement, calibration/selective-risk curves
- [ ] Grader-card issuance/expiry and continuous requalification with correction-to-rule feedback

**Depends on:** A4, D4, F1/F2. Feeds F4/F5, G3/G4/G5.
**Posture:** Build the workflow/cards/metrics; operate with a design-partner or contracted qualified lawyers; integrate secure annotation/review interfaces.
**Done when:** minimum agreement/calibration policy is met per family; requalification triggers after model/rubric/law drift.
**Avoid:** frontier-model consensus mislabeled as legal truth; unblinded reviewer anchoring; the same lawyers authoring and "independently" validating the same standard.

## AR experiment

**Run AR-004 here:** severe false-accept rate vs. two-lawyer adjudicated labels, plus senior adjudication.
