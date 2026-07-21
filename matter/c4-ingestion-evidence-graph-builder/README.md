# C4 — Ingestion, independent extraction, round-trip validation and evidence-graph builder

Proves that rendered (or, in production, ingested) documents actually support the state and task — without assuming the renderer succeeded.

Plane: C (Canonical matter and evidence) · Phase: 3 — Document-world proof (`BLOCKED`)

## Build

- [ ] File inventory and malware/macro controls
- [ ] OCR/layout/table extraction and clause/defined-term/entity/date/amount extraction
- [ ] Amendment/order-of-precedence resolver and document version/duplicate detection
- [ ] Cross-document relationship builder and state-to-document / document-to-state comparison
- [ ] Conflict/missing/unproduced classification, span locator, extraction-uncertainty scoring
- [ ] Assemble the `EvidenceGraph`

**Depends on:** C1/C3, B3, A3. Feeds D2/D3, E2, F1–F3, F5.
**Posture:** Hybrid — integrate multiple *independent* parsers/OCR engines; build legal extraction schemas, amendment resolution, evidence graph, comparison gates.
**Done when:** field-level precision/recall is measured by severity/file-type; state-to-document and document-to-state recovery is measured; unknown rate is explicit; no material task proceeds with unresolved render defects.
**Avoid — critical invariant of this whole phase:** using the same model/prompt for rendering (C3) and validation (C4). The independence of the ingestion path is the entire point of AR-002; sharing a model here silently defeats the round-trip proof.

## AR experiment

**Run AR-002 here** (the product specification §6), alongside C3 — see C3's README for the shared invariant.
