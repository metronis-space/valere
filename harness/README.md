# harness/ — Plane E: Runtime, tools, simulation, security

Forked from harvey-labs' `harness/` (run.py, agent_loop.py, tools.py, adapters/) using the repository fork layout — that maps directly to E1 (runtime/lifecycle manager) and E2 (tool gateway). E3/E4 have **no explicit harvey-labs mapping**; they're placed here by inference (they're per-matter runtime concerns, same posture as E1/E2), not a documented fork target — flag this if it turns out wrong once engineering actually starts. Status: `BLOCKED`.

| Component | Directory | Role |
|---|---|---|
| E1 | [e1-runtime-lifecycle-manager/](e1-runtime-lifecycle-manager/) | Per-matter environment runtime and lifecycle manager |
| E2 | [e2-tool-gateway/](e2-tool-gateway/) | Legal document, calculation and research tool gateway |
| E3 | [e3-counterparty-qa-simulator/](e3-counterparty-qa-simulator/) | Bounded reactive counterparty, seller-Q&A and procedural simulator |
| E4 | [e4-tenant-security-fabric/](e4-tenant-security-fabric/) | Tenant security, ethical walls, prompt-injection defense and observability fabric |

E1's isolation/sandboxing requirement specifically is implemented in `../sandbox/` (Modal-backed, not forked from harvey-labs' Podman `sandbox.py`).
