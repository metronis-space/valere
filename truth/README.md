# `truth/` — Phase 1 truth and policy kernel

`truth` is one flat Python package implementing the B1–B4 truth layer for the
bounded M&A proof of value. It compiles point-in-time sources, proposition
support, a typed ontology, and source-owned rules into one hashed Phase 1 exit
artifact.

Current POV status: **`TEST_READY`**. Phase 2 POV engineering is unblocked by
`scope/configs/demo/phase-1-test-exit.json`. Production remains blocked because
the bundled sources, buyer policy, owners, credentials, and AR-001 observations
are fictional test fixtures.

## Run it

Install the locked environment and run every Phase 0 and Phase 1 test:

```bash
uv sync --frozen
uv run python -m unittest discover -s tests -v
```

Regenerate the deterministic M&A POV bundle and exit artifact:

```bash
uv run valere-truth demo-generate \
  --phase0 scope/configs/demo/phase-0-test-exit.json \
  --authority scope/configs/demo/AuthoritySignoffMatrix.demo.yaml \
  --out-dir scope/configs/demo
```

Validate an existing bundle without writing a production artifact:

```bash
uv run valere-truth validate \
  --phase0 scope/configs/demo/phase-0-test-exit.json \
  --authority scope/configs/demo/AuthoritySignoffMatrix.demo.yaml \
  --bundle scope/configs/demo/TruthPolicyBundle.demo.json \
  --report /tmp/phase-1-validation.json
```

## Flat package layout

- `sources.py` — B1 acquisition boundaries, OCR injection, normalization,
  stable spans, freshness checks, coverage registers, immutable snapshots, and
  as-of replay.
- `authority.py` — B2 hierarchy, citation treatment, negative history,
  holding/dicta/text annotations, proposition-to-span support, controlling vs.
  persuasive classification, citator coverage, adverse authority, and quality
  metrics.
- `ontology.py` — B3 schema registry, the closed 22-workstream M&A packs,
  instance validation, orphan detection, ambiguous-type quarantine,
  migrations, deprecations, round trips, and change-impact reports.
- `rules.py` — B4 legal/contract/policy source separation, trigger expressions,
  materiality thresholds, primary/fallback actions, precedence, conflict
  checks, coverage/no-rule paths, held-out measurement, counterfactual checks,
  rule diffs, and AR-001.
- `compiler.py` — binds every B1–B4 artifact to the exact Phase 0 fingerprint
  and produces `READY`, `BLOCKED`, `TEST_READY`, or `TEST_BLOCKED`.
- `demo.py` — fictional single-task Harvey LAB M&A fixture pinned to commit
  `845a08840869b21a5c11958aae58bf5f00a7b775`.
- `cli.py` / `__main__.py` — command-line interface.
- `common.py` / `errors.py` — Phase 1 adapters over the dependency-neutral
  primitives in `utils/`.

There are intentionally no component subdirectories under `truth/`.

## B1 — Point-in-time source snapshot

Implemented controls:

- HTTPS official-source connector with a host allowlist, timeout, and byte cap
- in-memory connector for deterministic testing
- normalized plain text and HTML extraction
- explicit injected OCR boundary for binary/PDF inputs; missing OCR fails closed
- citation and docket normalization
- stable paragraph/section offsets and content hashes
- statute, regulation, court-rule, opinion, agency-guidance, contract, and
  playbook metadata
- effective, amendment, repeal, publication, and acquisition dates
- per-source freshness SLA and measured parse precision/recall
- explicit `COVERED`, `UNAVAILABLE`, and `OUT_OF_SCOPE` coverage entries
- immutable fingerprinted snapshots and cutoff-aware replay

The POV does not invent Delaware law. Its coverage register marks primary-law
and commercial-citator coverage unavailable/out of scope because its active
rules are limited to fixture contract text and a synthetic buyer playbook.

## B2 — Authority and proposition graph

Every proposition must link to an exact source span with a support type,
polarity, confidence, and verifier. Citation existence alone never counts as
support. Opinion authority requiring a citator abstains when citator coverage
is unavailable. Cutoff-invalid, repealed, overruled, reversed, withdrawn, or
superseded sources cannot silently support a result.

The test gold set measures:

- support-classification precision and recall
- proposition false-accept rate
- adverse-authority retrieval recall
- explicit abstention and coverage flags

## B3 — Typed ontology

The registry distinguishes entities, parties, capacities, ownership,
capitalization, transactions, agreements, documents, clauses, defined terms,
cross-references, amendments, facts, events, obligations, rights, issues,
consequences, remedies, deliverables, findings, truth sources, and verification
modes.

`consent-requirement` and `consent-status` are deliberately separate types.
Every production type must be a root or be consumed by another type or one of
the 22 closed M&A workstream packs. Ambiguous types are quarantined and cannot
be promoted to production. Registry changes require a version increment and
produce deterministic downstream impact reports.

## B4 — Rule and playbook compiler

Rules are explicitly typed as `LEGAL_RULE`, `CONTRACT_LOGIC`, or
`BUYER_POLICY`. The compiler rejects a rule when its source kind is mismatched,
its source span/proposition is absent, its owner lacks active Phase 0 authority,
its expression is unsatisfiable, or equal-precedence actions conflict.

Evaluation supports `AND`, `OR`, `NOT`, equality, comparison, membership,
containment, and existence predicates. Primary actions preserve their
prerequisites; fallback actions run only when no eligible primary action is
available. Unknown issue families and uncovered facts return `NO_RULE` or
`LOW_CONFIDENCE`, never an invented consequence.

## POV evidence

The generated exit artifact records:

- every Phase 1 gate passing
- authority precision/recall of `1.0`
- proposition false-accept rate of `0.0`
- held-out rule-family coverage of `1.0`
- a passing change-of-control counterfactual isolation check
- AR-001 scaling exponent of approximately `0.529`, below the `0.9` stop
  threshold, producing `CONTINUE`

These measurements prove the implementation and fixture behavior only. They
are not estimates of production legal quality.

## Production promotion

Production compilation remains fail-closed until all of the following replace
the test fixtures:

- a real Phase 0 `READY` artifact
- acquired, current, licensed/official sources with measured parser quality
- commercial-citator coverage where case law is used
- real proposition verification and adverse-authority gold sets
- an approved buyer playbook and currently authorized rule owners
- held-out matters and genuine senior-lawyer AR-001 time observations

No test artifact can become production-eligible by changing a status string.
