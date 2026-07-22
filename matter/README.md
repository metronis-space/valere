# matter/ — Plane C: Canonical matter and evidence

Owns the hidden oracle and the causal issue generator. C1/C2 and the Phase 2 D3
harness are **`POV_COMPLETE`**; C3/C4 are **`READY_FOR_POV`** in Phase 3.

| Component | Directory | Role |
|---|---|---|
| C1 | [c1-canonical-matter-deal-graph/](c1-canonical-matter-deal-graph/) | Canonical matter/deal graph and world-state engine — **POV complete** |
| C2 | [c2-issue-counterfactual-generator/](c2-issue-counterfactual-generator/) | Issue/dependency/counterfactual generator — **POV complete** |
| C3 | [c3-document-vdr-renderer/](c3-document-vdr-renderer/) | Document/VDR renderer — **Phase 3** |
| C4 | [c4-ingestion-evidence-graph-builder/](c4-ingestion-evidence-graph-builder/) | Independent ingestion/evidence graph — **Phase 3** |
| [render_targets/](render_targets/) | — | Output target: C3/C4 write generated tasks into `tasks/`, in harvey-labs' own `task.json` + `documents/` shape (per the repository architecture) |

**Critical invariant (C3/C4):** never use the same model/prompt for rendering and validation — the independence of the ingestion path is the entire point of AR-002.

## Run Phase 2

```bash
uv run valere-matter demo-generate \
  --phase1 scope/configs/demo/phase-1-test-exit.json \
  --out scope/configs/demo/phase-2-test-exit.json
```

The exit artifact binds the exact Phase 1 fingerprint to a deterministic C1
world, C2 positive/negative/boundary/evidence/procedural/t-wise scenarios, and
D3 criteria compiled directly from state and B4 rules. `state.py`, `issues.py`,
and `compiler/` own those steps; `cli/` owns the command line and
`tasks/compiler/` owns D3.
