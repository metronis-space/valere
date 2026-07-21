# B1 — Point-in-time primary-law ingestion and normalization

Builds reproducible legal snapshots from authoritative sources instead of letting a model's memory stand in for law.

Plane: B (Legal truth and policy) · Phase: 1 — Truth and policy kernel (`READY_FOR_POV`; production blocked)

## Build

- [ ] Official-source connectors, document acquisition, OCR/parser
- [ ] Citation/docket normalization, statute/regulation/rule sectioning
- [ ] Opinion/agency-guidance normalization with effective/amendment/repeal dates
- [ ] Jurisdiction/court/regulator metadata plus content hashing and snapshotting

**Depends on:** A1/A2. Feeds B2/B4, D2/D3, E2, F1; refreshed by G5.
**Posture:** Integrate official/public feeds (GovInfo, eCFR, Federal Register, CourtListener); build normalization/snapshotting/provenance; purchase additional sources where public coverage is inadequate.
**Done when:** source-freshness SLA is met; parse accuracy is measured per source; as-of state replays immutably; a coverage register explicitly lists unavailable material.
**Avoid:** stale law; unofficial summaries substituted for primary authority; silent OCR corruption; retroactively rewriting prior snapshots.

## AR experiment

None directly — B1 feeds AR-001 (B4) as an input, not tested standalone.
