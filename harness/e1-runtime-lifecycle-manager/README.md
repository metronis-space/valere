# E1 — Per-matter environment runtime and lifecycle manager

Executes each task in an isolated, reproducible legal workspace enforcing trust state and mounted-input immutability.

Plane: E (Runtime, tools, simulation, security) · Phase: 4 — Executable task/runtime proof (`BLOCKED`)

Forked from harvey-labs' `harness/` (run.py, agent_loop.py) using the repository fork layout — agent-loop/tool logic is substrate-independent; only the "where does the subprocess actually run" plumbing changes.

## Build

- [ ] Environment provisioning and the lifecycle state machine
- [ ] Read-only matter mount and writable deliverables directory with reset/state/submit contract
- [ ] Deterministic seed/clock, resource/time limits, network/egress policy
- [ ] Model adapter, context-window/compaction service, artifact collection, quarantine/teardown

**Depends on:** A3, D2/D4, E4. Hosts E2/E3; feeds F1–F5, G1–G3.
**Posture:** Integrate/buy a sandbox/container substrate + model adapters; build legal matter lifecycle, trust enforcement, artifact contract. **Compute constraint: the substrate is Modal Labs specifically (Modal Sandboxes)** — see `../../sandbox/`; harvey-labs' Podman-based `sandbox/sandbox.py` gets reimplemented, not forked as-is.
**Done when:** hermeticity/tenant-isolation tests pass; reset is reproducible; read-only input integrity holds; teardown leaves no recoverable confidential data.
**Avoid:** a task that can see verifier/answers; a writable source packet; a stale environment reused across matters; context compaction dropping dispositive evidence.

## AR experiment

None directly — E1 hosts the runtime that every downstream AR experiment (AR-003 onward) executes inside.
