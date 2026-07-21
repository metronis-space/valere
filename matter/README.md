# matter/ — Plane C: Canonical matter and evidence

New directory with no harvey-labs equivalent. Owns the hidden oracle, and proof that it survives being rendered into documents and read back. The C1–C4 work is **`BLOCKED`**.

| Component | Directory | Role |
|---|---|---|
| C1 | [c1-canonical-matter-deal-graph/](c1-canonical-matter-deal-graph/) | Canonical matter/deal graph and world-state engine — **the hidden oracle** |
| C2 | [c2-issue-counterfactual-generator/](c2-issue-counterfactual-generator/) | Issue, dependency, counterfactual and procedural-state generator |
| C3 | [c3-document-vdr-renderer/](c3-document-vdr-renderer/) | Document, spreadsheet and virtual-data-room renderer — **AR-002 runs here** |
| C4 | [c4-ingestion-evidence-graph-builder/](c4-ingestion-evidence-graph-builder/) | Ingestion, independent extraction, round-trip validation and evidence-graph builder |
| [render_targets/](render_targets/) | — | Output target: C3/C4 write generated tasks into `tasks/`, in harvey-labs' own `task.json` + `documents/` shape (per the repository architecture) |

**Critical invariant (C3/C4):** never use the same model/prompt for rendering and validation — the independence of the ingestion path is the entire point of AR-002.
