# `scope/` — Phase 0 boundary, rights, governance, and authority

This directory contains the executable A1–A4 Phase 0 boundary layer. It builds
and tests the controls; it cannot invent the buyer, rights grants, security
policy, model access, or accountable humans needed to approve real contracts.

## Current status

Engineering scope is complete and covered by the standard-library test suite.
The real Phase 0 exit remains **blocked on external decisions**:

- a named buyer, one selected workflow, jurisdictional frame, target model,
  success thresholds, and three distinct scope approvers;
- affirmative rights review/ownership for every asset/use selected by that
  manifest (AR-000);
- an approved provider/region/KMS/retention/DLP/incident policy and responsible
  governance owner; and
- real credentialed/delegated people, including a lawyer of record and customer
  owner for the pilot matter.

The four `configs/*.template.yaml` files are the production schema and deliberately
contain `TBD`/`DRAFT` values. The older `*.example.yaml` files preserve the
public Harvey LAB fictional scenario as source-shape illustrations only; they
are not accepted as production contracts and are not used by tests.

## What is implemented

### A1 — Scope/workflow compiler

- [x] Buyer/persona registry contract and a six-workflow closed selector
- [x] Explicit 22-row M&A matrix, transaction structure, and industry profile
- [x] Separate governing law, forum, entity law, regulatory overlays, and legal cutoff
- [x] Deployment tier plus exact model/revision/access/governance-route profile
- [x] Typed deliverables, success metrics, and kill criteria
- [x] Versioned approval payload fingerprints, exclusions, deterministic change-impact reports

The source corpus is inconsistent about the workstream count: it claims 22,
later claims 21, and enumerates 20. `catalog.py` preserves the enumerated 20 and
adds separately controllable `commercial-customers` and
`technology-cybersecurity` rows already implied by the corpus. Both default to
out of scope and cannot be activated silently.

### A2 — Rights/licensing/provenance

- [x] Asset/source/owner inventory and complete lifecycle-use matrix
- [x] Known-license and counsel-reviewed structured-contract normalization;
  unknown/free-text grants route to `REVIEW`, never inferred permission
- [x] Derivative and checkpoint creation/ownership/distribution controls
- [x] Confidentiality, privilege, expiry, renewal, deletion, and publication fields
- [x] Recursive lineage checks, expiry enforcement, review queue, and AR-000 report

Every operation fails closed if an asset is unknown, inactive, expired, denied,
under review, or depends on an uncleared parent.

### A3 — Data-governance engine

- [x] Classification, required tenant/matter labels, PII detection, potential-privilege flagging
- [x] Residency and encryption/key policy contracts
- [x] Exact provider/model routes with no-provider-training controls
- [x] Retention/deletion scheduling with legal-hold precedence
- [x] Cross-tenant/ethical-wall access, DLP export, and incident-response mapping
- [x] Mandatory 13-control coverage report tied to test IDs/enforcement points

Privilege markers only produce `potential_privilege`; the engine requires an
authorized human to confirm the `PRIVILEGED` label.

### A4 — Human authority/signoff

- [x] Role, credential, conflict, wall, and time-bounded delegation registry
- [x] Severity/tier/action approval policies with immediate expiry enforcement
- [x] Lawyer-of-record/customer-owner mappings and release stages
- [x] No self-approval, distinct-actor, role-coverage, and separation-of-duties checks
- [x] Fsync'd append-only, hash-chained client-decision and override audit logs

Hash chaining makes post-write edits evident. A production deployment should
also send the log to immutable/WORM storage through its audit integration.

## Commands

Run from the repository root:

```bash
python3 -m scope validate \
  --manifest scope/configs/ScopeManifest.template.yaml \
  --rights scope/configs/RightsRegister.template.yaml \
  --governance scope/configs/DataGovernancePolicy.template.yaml \
  --authority scope/configs/AuthoritySignoffMatrix.template.yaml

python3 -m scope compile \
  --manifest approved-scope.yaml \
  --rights approved-rights.yaml \
  --governance approved-governance.yaml \
  --authority approved-authority.yaml \
  --out phase-0-exit.json

python3 -m scope rights-check --rights approved-rights.yaml --asset ASSET --use train
python3 -m scope impact --previous scope-v1.yaml --current scope-v2.yaml
python3 -m scope classify --governance approved-governance.yaml --tenant TENANT --matter MATTER --text "text"
python3 -m scope authorize --authority approved-authority.yaml --request request.yaml --approvals approvals.yaml
python3 -m scope audit-append --authority approved-authority.yaml --log var/audit/client-decisions.jsonl \
  --event-type CLIENT_DECISION --actor ACTOR_ID --payload decision.yaml
```

`validate` returns status `BLOCKED` and exit code 2 until every external
decision is resolved. `compile` writes a fingerprint-bound
`Phase0ExitArtifact` only when all A1–A4 and cross-contract gates pass.

For an end-to-end fictional design-partner check that unlocks Phase 1 POV work but never the production track:

```bash
python3 -m scope demo-generate --out-dir scope/configs/demo
```

This writes four `test_fixture: true` contracts and a `TEST_READY` artifact.
The POV is restricted to the Harvey LAB `tasks/corporate-ma` family and one
change-of-control diligence task, pinned at commit
`845a08840869b21a5c11958aae58bf5f00a7b775`. Production `compile` deliberately
rejects the same contracts.

## Verification

```bash
PYTHONPYCACHEPREFIX=/tmp/valere-pycache python3 -m unittest discover -s tests -v
```

The suite includes a fully bound in-memory test contract plus negative checks
for stale approval, rights lineage, review queues, tenant isolation, disallowed
providers, privilege inference, legal hold, self-approval, expired authority,
and audit tampering. Test data is never treated as a real Phase 0 approval.
