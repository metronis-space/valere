# E4 — Tenant security, ethical walls, prompt-injection defense and observability fabric

Enforces the data boundary and makes every source, tool, model, reward, and administrative action auditable.

Plane: E (Runtime, tools, simulation, security) · Phase: 4 — Executable task/runtime proof (`BLOCKED`)

No documented harvey-labs mapping — placed here by inference (underlies E1–E3, same directory), not a verified fork target.

## Build

- [ ] Identity/RBAC/ABAC and tenant/matter isolation
- [ ] Ethical-wall/conflict policies, encryption/key management, secret/connector isolation
- [ ] Network/DLP controls and a mounted-document prompt-injection detector with instruction/data separation
- [ ] Immutable audit log, trace/reward store, anomaly/exfiltration monitoring
- [ ] Retention/deletion, incident response, compliance-evidence generation

**Depends on:** A3/A4. Underlies E1–E3 and all F/G runtime operations; feeds G5 compliance packaging.
**Posture:** Buy/integrate identity, KMS, DLP, SIEM, trace storage, compliance tooling; build matter-level ethical-wall, legal prompt-injection, reward/source-lineage controls.
**Done when:** penetration/cross-tenant tests pass; prompt-injection catch/false-positive rates are measured; audit-event completeness holds.
**Avoid:** treating mounted documents as trusted instructions; ethical walls enforced only by folder names; DLP blocking legitimate evidence or missing encoded exfiltration.

## AR experiment

None directly — E4 is re-engaged for production hardening in Phase 7 (T3 live-matter deployment raises its bar).
