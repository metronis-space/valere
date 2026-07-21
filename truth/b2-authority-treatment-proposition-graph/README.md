# B2 — Authority, treatment and proposition-support graph

Distinguishes "the citation exists" from "this authority, in this jurisdiction, on this date, supports this proposition and remains usable."

Plane: B (Legal truth and policy) · Phase: 1 — Truth and policy kernel (`READY_FOR_POV`; production blocked)

## Build

- [ ] Court/regulator hierarchy and citation network
- [ ] Treatment/negative-history layer and holding-vs-dicta annotations
- [ ] Proposition-to-span links and a controlling/persuasive classifier
- [ ] Conflicting-authority set, commercial-citator connector, uncertainty/coverage flags

**Depends on:** B1, A2. Feeds B4, C2, D3, E2, F1–F3, G5.
**Posture:** Hybrid — license/integrate a citator (KeyCite/Shepard's/BCite); build the normalized graph, proposition-evidence contract, cutoff-aware query layer.
**Done when:** citation/status gold-set precision/recall is measured; proposition-support false-accept rate is bounded; adverse-authority retrieval is tested; coverage/abstention is explicit rather than guessed.
**Avoid:** real-but-non-supporting citations; overruled/wrong-jurisdiction authority; dicta treated as holding; correlated model/citator error.

## AR experiment

None directly — B2 feeds AR-001 (B4) and AR-003 (F1) as an input.
