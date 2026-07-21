# render_targets/

Not a component of its own — this is where C3 (renderer) and C4 (evidence-graph builder) write generated tasks into `../../tasks/`, in harvey-labs' own `task.json` + `documents/` shape.

The C1–C4 pipeline produces a `tasks/<slug>/documents/` folder in harvey-labs' own format. This directory is the output adapter that writes into the task tree, not a peer of it.

Nothing to build here directly; see [`../c3-document-vdr-renderer/`](../c3-document-vdr-renderer/) and [`../c4-ingestion-evidence-graph-builder/`](../c4-ingestion-evidence-graph-builder/).
