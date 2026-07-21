# E2 — Legal document, calculation and research tool gateway

Gives agents controlled professional-work capabilities while preserving provenance, least privilege, and replayability.

Plane: E (Runtime, tools, simulation, security) · Phase: 4 — Executable task/runtime proof (`BLOCKED`)

Forked from harvey-labs' `harness/tools.py` (bash, read, write, edit, glob, grep — 6 closed-workspace tools) using the repository fork layout, extended with legal-specific tools.

## Build

- [ ] File listing/read/search and OCR/layout/table access
- [ ] Clause/defined-term/cross-reference navigation and document/redline comparison
- [ ] Spreadsheet read/write/formula calculation and date/deadline/cap/basket/funds-flow calculators
- [ ] DOCX/PDF/XLSX writer, citation/source lookup, approved legal-research/citator connector
- [ ] Evidence-span capture, tool-result cache, input/output validation

**Depends on:** B2, C4, E1/E4. Feeds F1/F2, G1/G4.
**Posture:** Integrate mature document/spreadsheet/OCR/legal-research tools; build the normalized gateway, evidence contract, permission model, deterministic calculators.
**Done when:** tool golden-task accuracy is measured; source-span fidelity holds; calculation reproducibility is verified.
**Avoid:** a wrong spreadsheet formula behind a plausible displayed value; search missing OCR text; tool output lacking provenance.

## AR experiment

None directly — E2's calculators/tools feed F1's deterministic validators (AR-003).
