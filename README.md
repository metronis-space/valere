# Valare

Valare is an executable legal-AI control plane for defining scope, checking
data and content rights, enforcing governance controls, and requiring human
authority before work advances to later phases.

The current implementation completes the Phase 0 controls in [`scope/`](scope/),
the Phase 1 truth-policy kernel in [`truth/`](truth/), and the Phase 2 canonical
state plus Phase 3 document-world proofs in [`matter/`](matter/). It includes a fictional M&A
bundle for testing the POV without representing that a real buyer or production
approvals exist.

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
uv run valere-matter --help
```

## Verify Phases 0–3

Run the complete test suite:

```bash
uv run python -m unittest discover -s tests -v
```

Generate and validate the fictional M&A POV bundle:

```bash
uv run valere-boundary demo-generate --out-dir scope/configs/demo
uv run valere-truth demo-generate --out-dir scope/configs/demo
uv run valere-matter demo-generate
uv run valere-matter document-world
```

The generated Phase 0–3 exit artifacts under `scope/configs/demo/`
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
- `matter/` — Phase 2 canonical state and Phase 3 document/VDR round-trip proof
- `tasks/compiler/` — Phase 2 D3 atomic criterion harness
- `utils/` — dependency-neutral infrastructure and shared POV identity
- `tests/` — executable Phase 0–3 controls and negative tests
- `datasets/` — downstream dataset/split scaffold
- `harness/`, `evaluation/`, `training/`, `registry/` — runtime and release scaffolds
