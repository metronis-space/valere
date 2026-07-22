"""A1 — product scope and workflow compiler."""

from __future__ import annotations

import copy
from typing import Any, Dict, Iterable, List, Tuple

from utils.artifacts import fingerprint
from utils.catalogs import (
    DELIVERABLE_KINDS,
    DEPLOYMENT_TIERS,
    MA_WORKSTREAM_CATALOG,
    RIGHTS_USES,
    TRANSACTION_STRUCTURES,
    WORKFLOW_CATALOG,
)
from utils.errors import BoundaryError, BoundaryValidationReport as ValidationReport
from utils.values import duplicates

from .common import (
    parse_date,
    parse_datetime,
    require_list,
    require_mapping,
    require_value,
)


APPROVAL_ROLES = {"commercial-sponsor", "legal-owner", "product-owner"}


def approval_fingerprint(manifest: Dict[str, Any]) -> str:
    payload = copy.deepcopy(manifest)
    payload.pop("approvals", None)
    payload.pop("change_impact_log", None)
    return fingerprint(payload)


def _validate_workflow(report: ValidationReport, manifest: Dict[str, Any]) -> None:
    workflow = require_mapping(report, manifest.get("workflow"), "workflow")
    selected = require_value(report, workflow, "selected", "workflow")
    if selected not in WORKFLOW_CATALOG:
        report.add("workflow.selected", "catalog", "Select exactly one workflow from the closed catalog")
        return
    mapping = require_mapping(report, workflow.get("mapping"), "workflow.mapping")
    expected = WORKFLOW_CATALOG[selected]
    for key in ("documents", "deliverables", "truth_modes", "signoff_actions"):
        actual = require_list(report, mapping.get(key), "workflow.mapping.%s" % key)
        missing = sorted(set(expected[key]) - set(actual))
        if missing:
            report.add(
                "workflow.mapping.%s" % key,
                "incomplete-mapping",
                "Missing catalog-required values: %s" % ", ".join(missing),
            )


def _validate_workstreams(report: ValidationReport, manifest: Dict[str, Any]) -> None:
    scope = require_mapping(report, manifest.get("ma_scope"), "ma_scope")
    matrix = require_list(report, scope.get("workstreams"), "ma_scope.workstreams")
    ids = [row.get("id") for row in matrix if isinstance(row, dict)]
    for repeated in duplicates(ids):
        report.add("ma_scope.workstreams", "duplicate", "Duplicate workstream %r" % repeated)
    missing = sorted(set(MA_WORKSTREAM_CATALOG) - set(ids))
    unknown = sorted(set(ids) - set(MA_WORKSTREAM_CATALOG))
    if missing:
        report.add("ma_scope.workstreams", "incomplete-matrix", "Missing workstreams: %s" % ", ".join(missing))
    if unknown:
        report.add("ma_scope.workstreams", "unknown-workstream", "Unknown workstreams: %s" % ", ".join(unknown))
    included = 0
    for index, value in enumerate(matrix):
        path = "ma_scope.workstreams[%d]" % index
        row = require_mapping(report, value, path)
        status = require_value(report, row, "status", path)
        if status not in {"IN_SCOPE", "OUT_OF_SCOPE"}:
            report.add(path + ".status", "enum", "Expected IN_SCOPE or OUT_OF_SCOPE")
        included += status == "IN_SCOPE"
        require_value(report, row, "rationale", path)
        if status == "IN_SCOPE":
            require_list(report, row.get("document_families"), path + ".document_families")
            require_list(report, row.get("deliverables"), path + ".deliverables")
            require_list(report, row.get("truth_modes"), path + ".truth_modes")
            require_value(report, row, "signoff_action", path)
    if not included:
        report.add("ma_scope.workstreams", "empty-scope", "At least one workstream must be in scope")

    transaction = require_mapping(report, scope.get("transaction"), "ma_scope.transaction")
    structure = require_value(report, transaction, "structure", "ma_scope.transaction")
    if structure not in TRANSACTION_STRUCTURES:
        report.add("ma_scope.transaction.structure", "catalog", "Unknown transaction structure")
    require_value(report, transaction, "buyer_side", "ma_scope.transaction")
    require_value(report, scope, "industry_profile", "ma_scope")


def _validate_jurisdiction(report: ValidationReport, manifest: Dict[str, Any]) -> None:
    jurisdiction = require_mapping(report, manifest.get("jurisdiction"), "jurisdiction")
    for field in ("governing_law", "forum", "entity_law"):
        require_value(report, jurisdiction, field, "jurisdiction")
    parse_date(jurisdiction.get("legal_cutoff_date"), "jurisdiction.legal_cutoff_date", report)
    overlays = require_list(report, jurisdiction.get("regulatory_overlays"), "jurisdiction.regulatory_overlays")
    for index, value in enumerate(overlays):
        path = "jurisdiction.regulatory_overlays[%d]" % index
        overlay = require_mapping(report, value, path)
        for field in ("name", "applicability", "owner"):
            require_value(report, overlay, field, path)
    governing = str(jurisdiction.get("governing_law", "")).lower()
    if "federal" in governing:
        report.add(
            "jurisdiction.governing_law",
            "conflated-jurisdiction",
            "Keep federal regulatory overlays separate from governing law",
        )


def _validate_product_mode(report: ValidationReport, manifest: Dict[str, Any]) -> None:
    mode = require_mapping(report, manifest.get("product_mode"), "product_mode")
    tier = require_value(report, mode, "deployment_tier", "product_mode")
    if tier not in DEPLOYMENT_TIERS:
        report.add("product_mode.deployment_tier", "enum", "Expected T1, T2, or T3")
    model = require_mapping(report, mode.get("target_model"), "product_mode.target_model")
    for field in ("provider", "model_id", "revision", "access_method", "access_owner"):
        require_value(report, model, field, "product_mode.target_model")
    if model.get("access_confirmed") is not True:
        report.add("product_mode.target_model.access_confirmed", "model-access", "Target-model access must be affirmatively confirmed")
    if tier == "T1" and mode.get("real_client_reliance") is not False:
        report.add("product_mode.real_client_reliance", "tier-boundary", "T1 must explicitly prohibit real-client reliance")


def _validate_deliverables(report: ValidationReport, manifest: Dict[str, Any]) -> None:
    section = require_mapping(report, manifest.get("deliverables"), "deliverables")
    schemas = require_list(report, section.get("schemas"), "deliverables.schemas")
    if not schemas:
        report.add("deliverables.schemas", "empty", "At least one deliverable schema is required")
    for index, value in enumerate(schemas):
        path = "deliverables.schemas[%d]" % index
        item = require_mapping(report, value, path)
        kind = require_value(report, item, "kind", path)
        if kind not in DELIVERABLE_KINDS:
            report.add(path + ".kind", "catalog", "Unknown deliverable kind")
        require_value(report, item, "schema_ref", path)
        require_list(report, item.get("required_sections"), path + ".required_sections")
    for key in ("success_metrics", "kill_criteria"):
        rows = require_list(report, section.get(key), "deliverables.%s" % key)
        if not rows:
            report.add("deliverables.%s" % key, "empty", "At least one concrete entry is required")
        for index, value in enumerate(rows):
            path = "deliverables.%s[%d]" % (key, index)
            row = require_mapping(report, value, path)
            for field in ("id", "measure", "operator", "threshold", "owner"):
                require_value(report, row, field, path)


def _validate_assets_exclusions(report: ValidationReport, manifest: Dict[str, Any]) -> None:
    required_assets = require_list(report, manifest.get("required_asset_uses"), "required_asset_uses")
    if not required_assets:
        report.add("required_asset_uses", "empty", "The manifest must declare every required asset/use")
    pairs: List[Tuple[Any, Any]] = []
    for index, value in enumerate(required_assets):
        path = "required_asset_uses[%d]" % index
        item = require_mapping(report, value, path)
        asset_id = require_value(report, item, "asset_id", path)
        uses = require_list(report, item.get("uses"), path + ".uses")
        if not uses:
            report.add(path + ".uses", "empty", "At least one use is required")
        for use in uses:
            pairs.append((asset_id, use))
            if use not in RIGHTS_USES:
                report.add(path + ".uses", "catalog", "Unknown rights use %r" % use)
    if duplicates(pairs):
        report.add("required_asset_uses", "duplicate", "Duplicate asset/use declarations are not allowed")

    exclusions = require_list(report, manifest.get("exclusions_register"), "exclusions_register")
    if not exclusions:
        report.add("exclusions_register", "empty", "Explicit exclusions are mandatory")
    for index, value in enumerate(exclusions):
        path = "exclusions_register[%d]" % index
        item = require_mapping(report, value, path)
        for field in ("id", "description", "owner"):
            require_value(report, item, field, path)


def _validate_approvals(report: ValidationReport, manifest: Dict[str, Any]) -> None:
    status = manifest.get("approval_status")
    if status not in {"DRAFT", "APPROVED", "REVOKED"}:
        report.add("approval_status", "enum", "Expected DRAFT, APPROVED, or REVOKED")
    ambiguities = require_list(report, manifest.get("high_severity_ambiguities"), "high_severity_ambiguities")
    if status == "APPROVED" and ambiguities:
        report.add("high_severity_ambiguities", "unresolved-ambiguity", "Approved manifests cannot retain high-severity ambiguity")

    approvals = require_list(report, manifest.get("approvals"), "approvals")
    if status != "APPROVED":
        return
    expected_fingerprint = approval_fingerprint(manifest)
    seen_roles = set()
    actor_ids = []
    for index, value in enumerate(approvals):
        path = "approvals[%d]" % index
        approval = require_mapping(report, value, path)
        role = require_value(report, approval, "role", path)
        actor_id = require_value(report, approval, "actor_id", path)
        seen_roles.add(role)
        actor_ids.append(actor_id)
        if approval.get("decision") != "APPROVE":
            report.add(path + ".decision", "approval", "Approval decision must be APPROVE")
        parse_datetime(approval.get("approved_at"), path + ".approved_at", report)
        if approval.get("document_fingerprint") != expected_fingerprint:
            report.add(path + ".document_fingerprint", "stale-approval", "Approval does not cover the current manifest payload")
    missing = APPROVAL_ROLES - seen_roles
    if missing:
        report.add("approvals", "missing-approvals", "Missing approval roles: %s" % ", ".join(sorted(missing)))
    if len(set(actor_ids)) != len(actor_ids):
        report.add("approvals", "separation-of-duties", "Commercial, legal, and product approvals must come from distinct actors")


def validate_manifest(manifest: Dict[str, Any], require_approved: bool = True) -> ValidationReport:
    report = ValidationReport()
    if manifest.get("schema_version") != 1:
        report.add("schema_version", "version", "Expected ScopeManifest schema version 1")
    require_value(report, manifest, "manifest_id", "")
    version = require_value(report, manifest, "manifest_version", "")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        report.add("manifest_version", "version", "Version must be a positive integer")
    buyer = require_mapping(report, manifest.get("buyer"), "buyer")
    for field in ("buyer_id", "legal_name", "persona", "perspective"):
        require_value(report, buyer, field, "buyer")
    if buyer.get("perspective") not in {"BUY_SIDE", "SELL_SIDE"}:
        report.add("buyer.perspective", "enum", "Expected BUY_SIDE or SELL_SIDE")
    require_value(report, manifest, "pilot_matter_id", "")

    _validate_workflow(report, manifest)
    _validate_workstreams(report, manifest)
    _validate_jurisdiction(report, manifest)
    _validate_product_mode(report, manifest)
    _validate_deliverables(report, manifest)
    _validate_assets_exclusions(report, manifest)
    _validate_approvals(report, manifest)

    if manifest.get("test_fixture") is True and manifest.get("approval_status") == "APPROVED":
        report.add("test_fixture", "fixture-boundary", "A test fixture can never be an approved production ScopeManifest")
    if require_approved and manifest.get("approval_status") != "APPROVED":
        report.add("approval_status", "not-approved", "Phase exit requires an approved manifest")
    return report


def _walk_diff(old: Any, new: Any, path: str = "") -> Iterable[Dict[str, Any]]:
    if isinstance(old, dict) and isinstance(new, dict):
        for key in sorted(set(old) | set(new)):
            child = "%s.%s" % (path, key) if path else key
            if key not in old:
                yield {"path": child, "change": "ADDED", "before": None, "after": new[key]}
            elif key not in new:
                yield {"path": child, "change": "REMOVED", "before": old[key], "after": None}
            else:
                yield from _walk_diff(old[key], new[key], child)
    elif old != new:
        yield {"path": path, "change": "CHANGED", "before": old, "after": new}


def change_impact(previous: Dict[str, Any], current: Dict[str, Any]) -> Dict[str, Any]:
    """Create a deterministic, machine-reviewable manifest change report."""

    old_version = previous.get("manifest_version")
    new_version = current.get("manifest_version")
    if not isinstance(old_version, int) or not isinstance(new_version, int) or new_version <= old_version:
        raise BoundaryError("A changed manifest must have a strictly higher integer version")
    ignored = {"approvals", "change_impact_log", "approval_status"}
    old = {key: value for key, value in previous.items() if key not in ignored}
    new = {key: value for key, value in current.items() if key not in ignored}
    changes = list(_walk_diff(old, new))
    high_roots = {"buyer", "workflow", "ma_scope", "jurisdiction", "product_mode", "required_asset_uses"}
    for change in changes:
        root = change["path"].split(".", 1)[0].split("[", 1)[0]
        change["severity"] = "HIGH" if root in high_roots else "MEDIUM"
        change["requires_reapproval"] = True
    return {
        "from_version": old_version,
        "to_version": new_version,
        "from_fingerprint": approval_fingerprint(previous),
        "to_fingerprint": approval_fingerprint(current),
        "changed": bool(changes),
        "changes": changes,
        "affected_controls": sorted({item["path"].split(".", 1)[0] for item in changes}),
    }


def compile_manifest(manifest: Dict[str, Any], require_approved: bool = True) -> Dict[str, Any]:
    report = validate_manifest(manifest, require_approved=require_approved)
    report.require_ok()
    compiled = copy.deepcopy(manifest)
    compiled["compiled_fingerprint"] = fingerprint(manifest)
    compiled["approval_fingerprint"] = approval_fingerprint(manifest)
    compiled["selected_workflow_contract"] = WORKFLOW_CATALOG[manifest["workflow"]["selected"]]
    compiled["included_workstreams"] = sorted(
        row["id"] for row in manifest["ma_scope"]["workstreams"] if row["status"] == "IN_SCOPE"
    )
    return compiled
