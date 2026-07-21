# E3 — Bounded reactive counterparty, seller-Q&A and procedural simulator

Supports negotiation turns, diligence requests, and consent decisions without letting a free-form persona model manufacture ground truth.

Plane: E (Runtime, tools, simulation, security) · Phase: 4 — Executable task/runtime proof (`BLOCKED`)

No documented harvey-labs mapping — placed here by inference alongside E1/E2 (same per-matter-runtime posture), not a verified fork target.

## Build

- [ ] Typed state-transition engine — **not** a free-form persona model
- [ ] Role/authority profiles, request/response protocol, evidence-release schedule
- [ ] Seller disclosure/cure states, counterparty position/concession ledger, consent/creditor/regulator branch policies
- [ ] Response renderer (language renders state; it never creates it), deterministic seed/replay, branch-coverage/realism audit

**Depends on:** C1/C2, B4, E1/E2. Opted into by D2; graded by F1/F2; difficulty controlled by G2.
**Posture:** Build deterministic/constraint-based state logic; buy/self-host a model only for language rendering, never as the hidden oracle.
**Done when:** exact replay works; every natural-language response maps to a valid typed state; no unauthorized fact creation occurs.
**Avoid:** persona sycophancy; a language response contradicting the underlying state; nondeterminism destroying grading.

## AR experiment

None directly — E3 is optional per-task (opted into by D2), graded through the same F1/F2 paths as other components.
