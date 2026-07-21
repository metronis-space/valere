# evaluation/ — Plane F: Verification, hardening, escalation

Forked from harvey-labs' `evaluation/` (judge.py, scoring.py, compare.py) using the repository fork layout — their all-pass-per-task scoring already implements invariant #9 ("high-severity items are gates, not average-score contributions"). Fork the harness, replace the judge prompts; `judge.py` is split into F1 (deterministic) + F2 (semantic). Status: `BLOCKED`.

| Component | Directory | Role |
|---|---|---|
| F1 | [validators/](validators/) | Deterministic and source-grounded validator mesh — **AR-003 runs here** |
| F2 | [f2-semantic-grader-reward-composer/](f2-semantic-grader-reward-composer/) | Qualified semantic grader and decomposed reward composer |
| F3 | [qualification/](qualification/) | Grader qualification, lawyer adjudication and requalification service — **AR-004 runs here** |
| F4, F5 | [attacks/](attacks/) | Verifier hardening/attack generation (F4, core moat) + coverage/OOD/abstention router (F5) — **AR-005 runs here (F5)** |
