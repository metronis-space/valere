"""A3 — confidentiality, privilege, and data-governance policy engine."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence

from utils.catalogs import DEPLOYMENT_TIERS, REQUIRED_GOVERNANCE_CONTROLS

from .common import (
    duplicates,
    parse_datetime,
    require_list,
    require_mapping,
    require_value,
)
from .errors import BoundaryError, ValidationReport


DEFAULT_PII_PATTERNS = {
    "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
    "us-ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    "phone": r"(?<!\d)(?:\+?\d{1,3}[ .-]?)?(?:\(?\d{3}\)?[ .-]?)\d{3}[ .-]\d{4}(?!\d)",
}
PRIVILEGE_MARKERS = (
    "attorney-client privileged",
    "attorney client privileged",
    "attorney work product",
    "privileged and confidential",
)


def validate_governance_policy(policy: Dict[str, Any]) -> ValidationReport:
    report = ValidationReport()
    if policy.get("schema_version") != 1:
        report.add("schema_version", "version", "Expected DataGovernancePolicy schema version 1")
    for field in ("policy_id", "policy_version", "policy_owner"):
        require_value(report, policy, field, "")
    if not isinstance(policy.get("policy_version"), int) or isinstance(policy.get("policy_version"), bool) or policy.get("policy_version", 0) < 1:
        report.add("policy_version", "version", "Version must be a positive integer")
    tier = require_value(report, policy, "deployment_tier", "")
    if tier not in DEPLOYMENT_TIERS:
        report.add("deployment_tier", "enum", "Expected T1, T2, or T3")

    scheme = require_mapping(report, policy.get("classification"), "classification")
    levels = require_list(report, scheme.get("levels"), "classification.levels")
    level_ids = [value.get("id") for value in levels if isinstance(value, dict)]
    if duplicates(level_ids):
        report.add("classification.levels", "duplicate", "Classification IDs must be unique")
    for index, value in enumerate(levels):
        path = "classification.levels[%d]" % index
        level = require_mapping(report, value, path)
        for field in ("id", "rank", "description"):
            require_value(report, level, field, path)
        if not isinstance(level.get("rank"), int) or isinstance(level.get("rank"), bool) or level.get("rank", -1) < 0:
            report.add(path + ".rank", "range", "Classification rank must be a non-negative integer")
    if "PUBLIC" not in level_ids or "CONFIDENTIAL" not in level_ids or "PRIVILEGED" not in level_ids:
        report.add("classification.levels", "incomplete", "PUBLIC, CONFIDENTIAL, and PRIVILEGED levels are mandatory")
    if scheme.get("privilege_requires_human_confirmation") is not True:
        report.add("classification.privilege_requires_human_confirmation", "privilege", "Privilege must not be inferred without human confirmation")
    require_value(report, scheme, "default_level", "classification")
    if scheme.get("default_level") not in level_ids:
        report.add("classification.default_level", "unknown-classification", "Default must reference a declared level")

    labels = require_mapping(report, policy.get("labels"), "labels")
    for field in ("tenant_required", "matter_required", "enforcement_point"):
        require_value(report, labels, field, "labels")
    if labels.get("tenant_required") is not True or labels.get("matter_required") is not True:
        report.add("labels", "tenant-labels", "Tenant and matter labels must be mandatory")

    pii = require_mapping(report, policy.get("pii_detection"), "pii_detection")
    detectors = require_list(report, pii.get("detectors"), "pii_detection.detectors")
    if not detectors:
        report.add("pii_detection.detectors", "empty", "At least one PII detector is required")
    for index, value in enumerate(detectors):
        if not isinstance(value, dict):
            continue
        detector_path = "pii_detection.detectors[%d]" % index
        for field in ("name", "pattern"):
            require_value(report, value, field, detector_path)
        try:
            re.compile(str(value.get("pattern", "")))
        except re.error:
            report.add(detector_path + ".pattern", "regex", "Detector pattern is not a valid regular expression")
    require_value(report, pii, "on_detection", "pii_detection")

    residency = require_mapping(report, policy.get("residency"), "residency")
    allowed_regions = require_list(report, residency.get("allowed_regions"), "residency.allowed_regions")
    if not allowed_regions:
        report.add("residency.allowed_regions", "empty", "At least one concrete region is required")
    require_value(report, residency, "cross_border_transfer", "residency")

    encryption = require_mapping(report, policy.get("encryption"), "encryption")
    for field in ("at_rest", "in_transit", "key_provider", "key_scope", "rotation_days"):
        require_value(report, encryption, field, "encryption")
    if encryption.get("key_scope") not in {"TENANT", "MATTER"}:
        report.add("encryption.key_scope", "enum", "Expected TENANT or MATTER key scope")
    if not isinstance(encryption.get("rotation_days"), int) or isinstance(encryption.get("rotation_days"), bool) or encryption.get("rotation_days", 0) <= 0:
        report.add("encryption.rotation_days", "range", "Key rotation must be a positive number of days")

    routes = require_list(report, policy.get("provider_routes"), "provider_routes")
    if not routes:
        report.add("provider_routes", "empty", "At least one explicit provider/model route is required")
    route_ids = []
    for index, value in enumerate(routes):
        path = "provider_routes[%d]" % index
        route = require_mapping(report, value, path)
        for field in ("route_id", "provider", "model_id", "training_disabled", "retention_days"):
            require_value(report, route, field, path)
        route_ids.append(route.get("route_id"))
        allowed = require_list(report, route.get("allowed_classifications"), path + ".allowed_classifications")
        route_regions = require_list(report, route.get("allowed_regions"), path + ".allowed_regions")
        unknown_levels = set(allowed) - set(level_ids)
        if unknown_levels:
            report.add(path + ".allowed_classifications", "unknown-classification", "Unknown levels: %s" % ", ".join(sorted(unknown_levels)))
        outside_residency = set(route_regions) - set(allowed_regions)
        if outside_residency:
            report.add(path + ".allowed_regions", "residency", "Route uses disallowed regions: %s" % ", ".join(sorted(outside_residency)))
        if not isinstance(route.get("retention_days"), int) or isinstance(route.get("retention_days"), bool) or route.get("retention_days", -1) < 0:
            report.add(path + ".retention_days", "range", "Provider retention must be a non-negative integer")
        if any(level in {"CONFIDENTIAL", "PRIVILEGED", "RESTRICTED"} for level in allowed) and route.get("training_disabled") is not True:
            report.add(path + ".training_disabled", "provider-training", "Sensitive routes must prohibit provider training")
    if duplicates(route_ids):
        report.add("provider_routes", "duplicate", "Route IDs must be unique")

    retention = require_mapping(report, policy.get("retention"), "retention")
    rules = require_list(report, retention.get("rules"), "retention.rules")
    covered = {item.get("classification") for item in rules if isinstance(item, dict)}
    missing_retention = set(level_ids) - covered
    if missing_retention:
        report.add("retention.rules", "incomplete", "Missing retention rules for: %s" % ", ".join(sorted(missing_retention)))
    for index, value in enumerate(rules):
        path = "retention.rules[%d]" % index
        rule = require_mapping(report, value, path)
        for field in ("classification", "days", "disposition"):
            require_value(report, rule, field, path)
        if not isinstance(rule.get("days"), int) or isinstance(rule.get("days"), bool) or rule.get("days", -1) < 0:
            report.add(path + ".days", "range", "Retention days must be a non-negative integer")

    hold = require_mapping(report, policy.get("legal_hold"), "legal_hold")
    for field in ("owner", "intake", "release_requires_approval"):
        require_value(report, hold, field, "legal_hold")
    require_list(report, hold.get("active_matter_ids"), "legal_hold.active_matter_ids")

    dlp = require_mapping(report, policy.get("dlp_export"), "dlp_export")
    for field in ("default", "approval_action"):
        require_value(report, dlp, field, "dlp_export")
    require_list(report, dlp.get("allowed_destinations"), "dlp_export.allowed_destinations")

    incident = require_mapping(report, policy.get("incident_response"), "incident_response")
    for field in ("owner", "intake_channel", "containment_sla_minutes", "breach_assessment_owner"):
        require_value(report, incident, field, "incident_response")

    coverage = require_list(report, policy.get("control_coverage"), "control_coverage")
    control_ids = [item.get("control_id") for item in coverage if isinstance(item, dict)]
    missing_controls = REQUIRED_GOVERNANCE_CONTROLS - set(control_ids)
    if missing_controls:
        report.add("control_coverage", "incomplete", "Missing controls: %s" % ", ".join(sorted(missing_controls)))
    if duplicates(control_ids):
        report.add("control_coverage", "duplicate", "Control IDs must be unique")
    for index, value in enumerate(coverage):
        path = "control_coverage[%d]" % index
        control = require_mapping(report, value, path)
        for field in ("control_id", "status", "owner", "enforcement_point"):
            require_value(report, control, field, path)
        if control.get("status") != "IMPLEMENTED":
            report.add(path + ".status", "not-implemented", "Phase exit requires IMPLEMENTED status")
        tests = require_list(report, control.get("test_ids"), path + ".test_ids")
        if not tests:
            report.add(path + ".test_ids", "untested", "Each control needs at least one verification test")

    if policy.get("approval_status") != "APPROVED":
        report.add("approval_status", "not-approved", "Governance policy requires owner approval")
    approval = require_mapping(report, policy.get("approval"), "approval")
    for field in ("actor_id", "role", "approved_at"):
        require_value(report, approval, field, "approval")
    parse_datetime(approval.get("approved_at"), "approval.approved_at", report)
    if policy.get("test_fixture") is True and policy.get("approval_status") == "APPROVED":
        report.add("test_fixture", "fixture-boundary", "A test fixture cannot approve a production governance policy")
    return report


@dataclass(frozen=True)
class ClassificationResult:
    level: str
    tenant_id: str
    matter_id: str
    pii_findings: Dict[str, List[str]]
    potential_privilege: bool
    privilege_confirmed: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "level": self.level,
            "tenant_id": self.tenant_id,
            "matter_id": self.matter_id,
            "pii_findings": self.pii_findings,
            "potential_privilege": self.potential_privilege,
            "privilege_confirmed": self.privilege_confirmed,
        }


class GovernanceEngine:
    def __init__(self, policy: Dict[str, Any]):
        self.policy = policy
        report = validate_governance_policy(policy)
        report.require_ok()
        self.level_rank = {
            item["id"]: item["rank"] for item in policy["classification"]["levels"]
        }
        self.routes = {item["route_id"]: item for item in policy["provider_routes"]}
        self.retention = {
            item["classification"]: item for item in policy["retention"]["rules"]
        }
        self.detectors = dict(DEFAULT_PII_PATTERNS)
        for item in policy["pii_detection"]["detectors"]:
            if isinstance(item, dict) and item.get("name") and item.get("pattern"):
                self.detectors[item["name"]] = item["pattern"]

    def classify(
        self,
        text: str,
        tenant_id: str,
        matter_id: str,
        declared_level: Optional[str] = None,
        privilege_confirmed: bool = False,
    ) -> ClassificationResult:
        if not tenant_id or not matter_id:
            raise BoundaryError("Tenant and matter labels are mandatory")
        level = declared_level or self.policy["classification"]["default_level"]
        if level not in self.level_rank:
            raise BoundaryError("Unknown classification %s" % level)
        findings: Dict[str, List[str]] = {}
        for name, pattern in self.detectors.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                findings[name] = [str(value) for value in matches]
        lower = text.lower()
        potential_privilege = any(marker in lower for marker in PRIVILEGE_MARKERS)
        if findings and self.level_rank[level] < self.level_rank.get("CONFIDENTIAL", 0):
            level = "CONFIDENTIAL"
        if privilege_confirmed:
            level = "PRIVILEGED"
        return ClassificationResult(
            level=level,
            tenant_id=tenant_id,
            matter_id=matter_id,
            pii_findings=findings,
            potential_privilege=potential_privilege,
            privilege_confirmed=privilege_confirmed,
        )

    def authorize_tenant_access(
        self,
        actor_tenant_id: str,
        actor_matter_ids: Sequence[str],
        resource_tenant_id: str,
        resource_matter_id: str,
        ethical_wall_matter_ids: Sequence[str] = (),
    ) -> bool:
        if resource_matter_id in ethical_wall_matter_ids:
            return False
        return actor_tenant_id == resource_tenant_id and resource_matter_id in set(actor_matter_ids)

    def require_provider_route(self, route_id: str, classification: str, region: str) -> Dict[str, Any]:
        route = self.routes.get(route_id)
        reasons = []
        if not route:
            reasons.append("unknown-route")
        else:
            if classification not in route["allowed_classifications"]:
                reasons.append("classification-not-allowed")
            if region not in route["allowed_regions"]:
                reasons.append("region-not-allowed")
            if classification in {"CONFIDENTIAL", "PRIVILEGED", "RESTRICTED"} and route["training_disabled"] is not True:
                reasons.append("provider-training-not-disabled")
        if reasons:
            raise BoundaryError("Provider route denied: %s" % ", ".join(reasons))
        return dict(route)

    def retention_action(
        self,
        classification: str,
        created_at: datetime,
        matter_id: str,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        now = now or datetime.now(timezone.utc)
        if created_at.tzinfo is None:
            raise BoundaryError("created_at must be timezone-aware")
        if matter_id in self.policy["legal_hold"]["active_matter_ids"]:
            return {"action": "HOLD", "due_at": None, "reason": "active-legal-hold"}
        rule = self.retention.get(classification)
        if not rule:
            raise BoundaryError("No retention rule for %s" % classification)
        due_at = created_at + timedelta(days=rule["days"])
        return {
            "action": rule["disposition"] if now >= due_at else "RETAIN",
            "due_at": due_at.astimezone(timezone.utc).isoformat(),
            "reason": "retention-schedule",
        }

    def require_export(self, classification: str, destination: str, approved: bool = False) -> None:
        allowed = destination in self.policy["dlp_export"]["allowed_destinations"]
        sensitive = classification in {"CONFIDENTIAL", "PRIVILEGED", "RESTRICTED"}
        if not allowed or (sensitive and not approved):
            raise BoundaryError("DLP export denied for %s to %s" % (classification, destination))


def control_coverage_report(policy: Dict[str, Any]) -> Dict[str, Any]:
    report = validate_governance_policy(policy)
    entries = policy.get("control_coverage", [])
    implemented = {
        item.get("control_id")
        for item in entries
        if isinstance(item, dict) and item.get("status") == "IMPLEMENTED" and item.get("test_ids")
    }
    return {
        "complete": report.ok and REQUIRED_GOVERNANCE_CONTROLS <= implemented,
        "required": sorted(REQUIRED_GOVERNANCE_CONTROLS),
        "implemented_and_tested": sorted(implemented),
        "validation": report.to_dict(),
    }
