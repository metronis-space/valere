# tasks/ — D1 catalog + D2 TaskManifest + D3 CriterionBundle

Forked from harvey-labs' `tasks/<practice-area>/<task-slug>/{task.json, documents/}` directory convention. Seeded from their 670/48,259 contracts+M&A task/criterion slice; extended with generated tasks written by `../matter/render_targets/`. Status: `BLOCKED`.

Under the repository fork layout, D1/D2/D3 are **not** separate top-level directories — they map onto this one, forked, tree:

| Component | Role | Maps to |
|---|---|---|
| D1 | [d1-usecase-workstream-catalog/](d1-usecase-workstream-catalog/) | Closed-universe use-case, workstream and deliverable catalog | catalog structure underlying `tasks/<practice-area>/` |
| D2 | [d2-task-instruction-compiler/](d2-task-instruction-compiler/) | Task, instruction, source-packet and typed-work-product compiler | `task.json`'s TaskManifest fields |
| D3 | [d3-atomic-criterion-compiler/](d3-atomic-criterion-compiler/) | Atomic criterion, rubric, evidence and example compiler | `task.json`'s `criteria[]` (CriterionBundle) — **harness-proven in Phase 2, full build in Phase 4** |

D4 (dataset registry/split compiler) is a separate directory: see `../datasets/`.
