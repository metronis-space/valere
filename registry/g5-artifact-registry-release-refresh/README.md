# G5 — Artifact registry, packaging, deployment, refresh and continuous operations

Delivers reproducible environments/checkpoints with explicit trust and scope; monitors dependencies; refreshes, rolls back, quarantines, or retires them over time. Coordinates the closed loop — it does not own truth.

Plane: G (Diagnosis, learning, proof, operations) · Phase: 7 — Product release and refresh proof (`BLOCKED`)

## Build

- [ ] Immutable artifact registry and environment/task/verifier/checkpoint packages
- [ ] Compatibility/API versioning and reliability/trust cards
- [ ] Release approval, customer/VPC deployment, tenant configuration, public/private distribution controls
- [ ] Rollback/revocation and law/citator/playbook/model/grader/template change detection
- [ ] Dependency-impact graph, recompile/revalidate/retrain workflow, incident/exploit-family response
- [ ] Benchmark rotation and an SLA/cost/reviewer-operations dashboard

**Depends on:** all planes upstream. Refresh events flow back to B1/B2/B4, C1/C2, D2/D3/D4, F3/F4, G1–G4.
**Posture:** Integrate artifact/ML registries, CI/CD, observability, compliance, deployment infrastructure; build legal dependency-impact, trust-state, refresh/release logic. **Compute constraint: the deployment target is Modal (`modal deploy`)**, not Kubernetes/Baseten/SageMaker endpoints — registry/CI tools (MLflow, GitHub Actions, W&B) are still fine since they're control-plane, not compute substrate.
**Done when:** every release pins/hashes its dependencies; installation/replay succeeds; trust records are current; rollback is tested; staleness/incident SLAs are met.
**Avoid:** a package omitting its source/playbook version; an environment remaining "trusted" after a grader/law change silently invalidates it; a public release contaminating the private holdout.

## AR experiment

None directly — G5 is the release/refresh coordinator that acts on the proof AR-000 through AR-010 already established; it doesn't generate new proof itself.
