# sandbox/ — Modal-backed isolation substrate (E1/E4)

Not a separate component — this is the implementation target for E1's isolation requirement (per-task sandboxing) and part of E4's tenant-isolation enforcement. See [`../harness/e1-runtime-lifecycle-manager/`](../harness/e1-runtime-lifecycle-manager/) and [`../harness/e4-tenant-security-fabric/`](../harness/e4-tenant-security-fabric/).

The harvey-labs reference sandbox is Podman-based (`sandbox.py`, `--network=none --cap-drop=ALL`). **Do not fork as-is** — the project requires Modal compute. Reimplement the same isolation *policy* (network off, read-only mounted docs, writable output, per-task teardown) against Modal's Sandbox SDK instead:

- `outbound_cidr_allowlist` / `outbound_domain_allowlist` for network=none
- Persistent volumes for the read-only/writable mount split

Everything that calls into this (`harness/e1-runtime-lifecycle-manager/`) keeps the same interface — this is a swap-the-implementation change, not a redesign. `test_sandbox.py` (forked from harvey-labs' `tests/`) needs rewriting against Modal's Sandbox SDK rather than Podman.

Phase: 4 — Executable task/runtime proof (`BLOCKED`).
