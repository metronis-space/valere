# B3 — Legal, contract and transaction ontology plus schema registry

Gives every plane a typed vocabulary and constraints for commercial contracts, M&A, evidence, and work products.

Plane: B (Legal truth and policy) · Phase: 1 — Truth and policy kernel (`READY_FOR_POV`; production blocked)

## Build

- [ ] Entity/party/capacity types and ownership/capitalization model
- [ ] Transaction-structure and agreement/document-family types
- [ ] Clause/defined-term/cross-reference types and amendment/order-of-precedence model
- [ ] Facts/events/obligations/rights and issues/consequences/remedies types
- [ ] The 22 M&A workstream packs, deliverable/finding types, truth-source/verification-mode taxonomies
- [ ] Schema migration and deprecation tooling

**Depends on:** A1/A2, B1/B2. Consumed by B4 and every C–G component.
**Posture:** Build as core IP; seed from public schemas/taxonomies without treating them as exhaustive ground truth.
**Done when:** no orphan/undefined production type exists; schema round-trip/migration tests pass; ambiguous types are quarantined; version changes produce complete impact reports.
**Avoid:** untyped generic dictionaries; collapsing "consent requirement" with "consent status"; schema drift between renderer, compiler, and verifier.

## AR experiment

None directly — B3's typed vocabulary underlies every AR experiment from AR-001 onward.
