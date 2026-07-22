# Valare

Valare is an executable legal-AI control plane for defining scope, checking
data and content rights, enforcing governance controls, and requiring human
authority before work advances to later phases.

The current implementation completes the Phase 0 engineering controls in
[`scope/`](scope/) and the Phase 1 truth-policy kernel in [`truth/`](truth/).
It includes a fictional M&A design-partner bundle for testing the POV without
representing that a real buyer or production approvals exist.

## Requirements

- [`uv`](https://docs.astral.sh/uv/)
- Python 3.9 or newer (managed automatically by `uv` when needed)

## Setup

Clone the repository, then install the locked environment:

```bash
uv sync
```

Confirm the command-line interface is available:

```bash
uv run valere-boundary --help
uv run valere-truth --help
```

## Verify Phase 0

Run the complete test suite:

```bash
uv run python -m unittest discover -s tests -v
```

Generate and validate the fictional M&A POV bundle:

```bash
uv run valere-boundary demo-generate --out-dir scope/configs/demo
uv run valere-truth demo-generate --out-dir scope/configs/demo
```

The generated Phase 0 and Phase 1 exit artifacts under `scope/configs/demo/`
must report `TEST_READY`. That status permits POV development only. Production
remains blocked until authorized people replace the `TBD`/`DRAFT` values in the
four `scope/configs/*.template.yaml` contracts and supply real Phase 1 sources,
playbooks, owners, quality measurements, and AR-001 observations.

## Configuration

All YAML contracts live under [`scope/configs/`](scope/configs/):

- `*.template.yaml` — production contracts requiring real approvals
- `*.example.yaml` — fictional source-shape examples
- `demo/*.demo.yaml` — generated M&A POV fixtures

See [`scope/README.md`](scope/README.md) for validation, compilation, rights,
governance, impact-analysis, and authorization commands.

## Repository layout

- `scope/` — Phase 0 boundary implementation and configuration
- `truth/` — Phase 1 truth and policy kernel
- `utils/` — dependency-neutral infrastructure and shared POV identity
- `tests/` — executable Phase 0/1 controls and negative tests
- `matter/`, `tasks/`, `datasets/` — downstream compiler scaffolds
- `harness/`, `evaluation/`, `training/`, `registry/` — runtime and release scaffolds
