# matter/ — Plane C: Canonical matter and evidence

Owns the hidden oracle, causal issue generator, document renderer, and independent
evidence round trip. C1–C4 and the Phase 2 D3 harness are **`POV_COMPLETE`**.

| Component | Directory | Role |
|---|---|---|
| C1 | [state.py](state.py) | Canonical matter/deal graph and invariant engine |
| C2 | [issues.py](issues.py) | Issue, dependency, mutation, and counterfactual generator |
| C3 | [rendering.py](rendering.py) | Deterministic DOCX/XLSX/PDF/email/JSON/text VDR renderer with field provenance |
| C4 | [ingestion.py](ingestion.py) | Independent parsers, inventory controls, round-trip metrics, and `EvidenceGraph` |
| Exit | [compiler/document_world.py](compiler/document_world.py) | Phase 3 and AR-002 gates |

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

## Run Phase 3

```bash
uv run valere-matter document-world \
  --phase2 scope/configs/demo/phase-2-test-exit.json \
  --vdr-out scope/configs/demo/phase-3-vdr \
  --out scope/configs/demo/phase-3-test-exit.json
```

The command renders 11 indexed files across six formats, independently parses
them, rejects unsafe or altered inventory, resolves amendment precedence,
classifies missing versus unproduced evidence, assembles an evidence graph, and
records AR-002 precision, recall, span accuracy, unknown rate, severity slices,
file-type slices, yield, and cost. Test fixtures may produce only `TEST_READY`.
