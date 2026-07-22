"""Compile the C3/C4 document-world proof and AR-002 exit artifact."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Optional

from utils.artifacts import set_fingerprint, verify_fingerprint
from utils.errors import MatterError

from ..ingestion import ingest_document_world
from ..rendering import render_document_world
from ..state import validate_world


def _require_phase2(phase2: Mapping[str, Any]) -> bool:
    if phase2.get("artifact_type") != "Phase2ExitArtifact" or phase2.get("schema_version") != 1:
        raise MatterError("Phase 2 input has an unsupported artifact schema")
    if not verify_fingerprint(dict(phase2)):
        raise MatterError("Phase 2 artifact fingerprint is invalid")
    fixture = bool(phase2.get("pov_boundary", {}).get("test_fixture"))
    expected = "TEST_READY" if fixture else "READY"
    gates = phase2.get("gates", {})
    if phase2.get("status") != expected or not gates or not all(gates.values()):
        raise MatterError("Phase 2 must be %s with every gate passing" % expected)
    if phase2.get("production_eligible") is not (not fixture):
        raise MatterError("Phase 2 production eligibility does not match its fixture boundary")
    if phase2.get("pov_boundary", {}).get("documents_rendered") is not False:
        raise MatterError("Phase 2 input must precede document rendering")
    try:
        world = phase2["canonical_matter"]
    except KeyError as exc:
        raise MatterError("Phase 2 input has no canonical matter") from exc
    validation = validate_world(world)
    if not validation["ok"]:
        raise MatterError("Phase 2 canonical matter is invalid: %s" % "; ".join(validation["issues"]))
    return fixture


def compile_phase3(
    phase2: Mapping[str, Any],
    output_dir: str,
    generated_at: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Render, independently ingest, measure, and gate one Phase 3 world."""

    generated_at = generated_at or datetime.now(timezone.utc)
    if generated_at.tzinfo is None:
        raise ValueError("generated_at must be timezone-aware")
    fixture = _require_phase2(phase2)
    world = phase2["canonical_matter"]
    rendered = render_document_world(world, output_dir)
    ingested = ingest_document_world(world, output_dir, rendered, phase2)
    expected_paths = {item["fact_path"] for item in ingested["comparison"]}
    provenance_paths = {item["fact_path"] for item in rendered["provenance"]}
    severities = ingested["metrics"]["by_severity"]
    file_types = ingested["metrics"]["by_file_type"]
    graph = ingested["evidence_graph"]
    issue_paths = {"contract.change_control_clause", "contract.consent_required", "contract.consent_status", "contract.annual_value_usd"}
    recovered_paths = {item["fact_path"] for item in ingested["comparison"] if item["status"] == "RECOVERED"}
    gates = {
        "c3_multiple_file_families": {".docx", ".xlsx", ".pdf", ".eml", ".json", ".txt"} <= set(ingested["file_types"])
        and len({item["family"] for item in rendered["files"]}) >= 8,
        "c3_files_open_and_parse": ingested["all_files_open_and_parse"],
        "c3_defined_terms_and_cross_references": ingested["document_quality"]["defined_terms_valid"]
        and ingested["document_quality"]["cross_references_valid"],
        "c3_signatures_valid": ingested["document_quality"]["signatures_valid"],
        "c3_spreadsheet_math_valid": ingested["document_quality"]["math_valid"],
        "c3_render_provenance_complete": provenance_paths == expected_paths
        and len(rendered["provenance"]) == len(expected_paths)
        and all(item["file"] and item["locator"] for item in rendered["provenance"]),
        "c3_current_versions_only": ingested["document_quality"]["precedence_valid"]
        and all(item["status"] == "CURRENT" for item in rendered["files"]),
        "c3_issue_state_survives_rendering": issue_paths <= recovered_paths,
        "c4_inventory_safe": ingested["inventory"]["ok"]
        and ingested["vdr_index_valid"]
        and not ingested["inventory"]["macro_count"],
        "c4_independent_path": rendered["renderer"]["engine_id"] != ingested["ingestor"]["engine_id"]
        and rendered["renderer"]["implementation"] != ingested["ingestor"]["implementation"]
        and not rendered["renderer"]["uses_model"]
        and not ingested["ingestor"]["uses_model"],
        "c4_parser_coverage": len(ingested["ingestor"]["parser_engines"]) >= 5
        and ingested["ingestor"]["ocr"]["status"] in {"AVAILABLE", "NOT_REQUIRED"},
        "c4_amendment_precedence": ingested["document_quality"]["precedence_valid"],
        "c4_duplicates_resolved": not ingested["inventory"]["duplicate_groups"],
        "c4_relationships_built": any(item["type"] == "AMENDS" for item in graph["relationships"])
        and any(item["type"] == "SUPPORTS_FACT" for item in graph["relationships"]),
        "c4_missing_unproduced_distinct": ingested["classification_valid"],
        "c4_evidence_graph_complete": verify_fingerprint(dict(graph), "evidence_graph_fingerprint")
        and {"MATTER", "DOCUMENT", "FACT", "EVIDENCE_SPAN", "EVIDENCE_AVAILABILITY"}
        <= {item["node_type"] for item in graph["nodes"]},
        "ar002_field_metrics_complete": set(severities) == {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
        and {".docx", ".xlsx", ".pdf", ".txt"} <= set(file_types),
        "ar002_typed_fact_recovery": ingested["metrics"]["precision"] == 1.0
        and ingested["metrics"]["recall"] == 1.0
        and ingested["metrics"]["span_accuracy"] == 1.0,
        "ar002_severity_weighted_recovery": ingested["metrics"]["severity_weighted_recovery"] == 1.0
        and severities["CRITICAL"]["recall"] == 1.0,
        "ar002_unknown_rate_explicit": ingested["metrics"]["unknown_rate"] == 0.0
        and ingested["metrics"]["mean_extraction_uncertainty"] == 0.0
        and not ingested["metrics"]["unrecoverable_fact_paths"],
        "ar002_render_extract_yield_economic": ingested["economics"]["economically_viable"]
        and ingested["economics"]["render_extract_yield"] == 1.0,
    }
    failures = [name for name, passed in gates.items() if not passed]
    issues = list(ingested["inventory"]["issues"]) + ["failed gate: %s" % name for name in failures]
    if failures:
        raise MatterError("Phase 3 exit is blocked: %s" % ", ".join(failures))
    status = "TEST_READY" if fixture else "READY"
    artifact: Dict[str, Any] = {
        "artifact_type": "Phase3ExitArtifact",
        "schema_version": 1,
        "status": status,
        "trust_state": "RENDER_VALIDATED",
        "production_eligible": not fixture,
        "generated_at": generated_at.astimezone(timezone.utc).isoformat(),
        "phase2_artifact_fingerprint": phase2["artifact_fingerprint"],
        "matter_fingerprint": world["matter_fingerprint"],
        "render_manifest": rendered,
        "ingestion": ingested,
        "ar_002": {
            "experiment_id": "AR-002",
            "metric": "severity-weighted typed-fact recovery",
            "passed": True,
            **ingested["metrics"],
            "economics": ingested["economics"],
        },
        "gates": gates,
        "issues": issues,
        "pov_boundary": {
            "test_fixture": fixture,
            "pov_downstream_unblocked": fixture,
            "production_downstream_unblocked": not fixture,
            "documents_rendered": True,
            "independent_ingestion": True,
        },
    }
    set_fingerprint(artifact)
    return artifact
