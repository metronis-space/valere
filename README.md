# Valare

Valare is an executable legal-AI control plane for defining scope, checking
data and content rights, enforcing governance controls, and requiring human
authority before work advances to later phases.

The current implementation completes the Phase 0 engineering controls in
[`scope/`](scope/). It also includes a fictional M&A design-partner bundle for
testing the Phase 1 POV without representing that real buyer or production
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
```

## Verify Phase 0

Run the complete test suite:

```bash
uv run python -m unittest discover -s tests -v
```

Generate and validate the fictional M&A POV bundle:

```bash
uv run valere-boundary demo-generate --out-dir scope/configs/demo
```

The generated `scope/configs/demo/phase-0-test-exit.json` must report
`TEST_READY`. That status permits POV development only. Production remains
blocked until authorized people replace the `TBD`/`DRAFT` values in the four
`scope/configs/*.template.yaml` contracts and satisfy every Phase 0 exit gate.

## Configuration

All YAML contracts live under [`scope/configs/`](scope/configs/):

- `*.template.yaml` — production contracts requiring real approvals
- `*.example.yaml` — fictional source-shape examples
- `demo/*.demo.yaml` — generated M&A POV fixtures

See [`scope/README.md`](scope/README.md) for validation, compilation, rights,
governance, impact-analysis, and authorization commands.

## Repository layout

- `scope/` — Phase 0 boundary implementation and configuration
- `tests/` — executable Phase 0 controls and negative tests
- `truth/` — Phase 1 truth and policy kernel scaffold
- `matter/`, `tasks/`, `datasets/` — downstream compiler scaffolds
- `harness/`, `evaluation/`, `training/`, `registry/` — runtime and release scaffolds
