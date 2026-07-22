"""A2 — rights, licensing, provenance, and fail-closed enforcement."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional, Set

from utils.catalogs import RIGHTS_DECISIONS, RIGHTS_USES
from utils.errors import BoundaryError, BoundaryValidationReport as ValidationReport

from .common import (
    duplicates,
    parse_date,
    parse_datetime,
    require_list,
    require_mapping,
    require_value,
)


KNOWN_LICENSES: Dict[str, Dict[str, Any]] = {
    "MIT": {
        "permissions": {use: "ALLOW" for use in RIGHTS_USES},
        "obligations": ["preserve-license-and-copyright-notice"],
    },
    "CC-BY-4.0": {
        "permissions": {use: "ALLOW" for use in RIGHTS_USES},
        "obligations": ["attribution", "indicate-changes", "link-license"],
    },
}


def parse_license_or_contract(source: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a known SPDX license or explicit reviewed contract grant.

    Unknown or free-text grants intentionally become REVIEW for every use. The
    parser is an enforcement hook, not a substitute for counsel.
    """

    kind = source.get("kind")
    if kind == "LICENSE":
        identifier = str(source.get("spdx_id", "")).upper()
        known = KNOWN_LICENSES.get(identifier)
        if known:
            return {
                "decision_source": "KNOWN_LICENSE_CATALOG",
                "permissions": dict(known["permissions"]),
                "obligations": list(known["obligations"]),
                "requires_review": False,
            }
    if kind == "CONTRACT" and source.get("counsel_reviewed") is True:
        explicit = source.get("explicit_permissions")
        if isinstance(explicit, dict) and set(explicit) == RIGHTS_USES:
            normalized = {str(key): str(value).upper() for key, value in explicit.items()}
            if set(normalized.values()) <= RIGHTS_DECISIONS:
                return {
                    "decision_source": "COUNSEL_REVIEWED_CONTRACT",
                    "permissions": normalized,
                    "obligations": list(source.get("obligations", [])),
                    "requires_review": any(value == "REVIEW" for value in normalized.values()),
                }
    return {
        "decision_source": "UNRESOLVED",
        "permissions": {use: "REVIEW" for use in RIGHTS_USES},
        "obligations": [],
        "requires_review": True,
    }


def _validate_asset(report: ValidationReport, asset: Dict[str, Any], index: int, today: date) -> None:
    path = "assets[%d]" % index
    for field in ("asset_id", "asset_type", "lifecycle"):
        require_value(report, asset, field, path)
    if asset.get("lifecycle") not in {"ACTIVE", "REFERENCE_ONLY", "BLOCKED", "RETIRED"}:
        report.add(path + ".lifecycle", "enum", "Unknown asset lifecycle")

    source = require_mapping(report, asset.get("source"), path + ".source")
    for field in ("uri", "content_fingerprint", "acquired_at"):
        require_value(report, source, field, path + ".source")
    owner = require_mapping(report, asset.get("owner"), path + ".owner")
    for field in ("owner_id", "legal_name", "rights_contact"):
        require_value(report, owner, field, path + ".owner")

    grant = require_mapping(report, asset.get("grant"), path + ".grant")
    for field in ("kind", "reference", "reviewed_by", "reviewed_at"):
        require_value(report, grant, field, path + ".grant")
    parse_datetime(grant.get("reviewed_at"), path + ".grant.reviewed_at", report)
    permissions = require_mapping(report, grant.get("permissions"), path + ".grant.permissions")
    if set(permissions) != RIGHTS_USES:
        report.add(
            path + ".grant.permissions",
            "incomplete-matrix",
            "Permissions must explicitly cover: %s" % ", ".join(sorted(RIGHTS_USES)),
        )
    for use, decision in permissions.items():
        if use not in RIGHTS_USES:
            report.add(path + ".grant.permissions.%s" % use, "unknown-use", "Unknown use")
        if decision not in RIGHTS_DECISIONS:
            report.add(path + ".grant.permissions.%s" % use, "enum", "Expected ALLOW, DENY, or REVIEW")

    expiry_value = grant.get("expiry_date")
    if expiry_value is not None:
        expiry = parse_date(expiry_value, path + ".grant.expiry_date", report)
        if expiry and expiry < today and asset.get("lifecycle") == "ACTIVE":
            report.add(path + ".grant.expiry_date", "expired", "An expired asset cannot remain ACTIVE")
    if grant.get("kind") not in {"LICENSE", "CONTRACT", "PUBLIC_DOMAIN", "INTERNAL_ORIGINAL"}:
        report.add(path + ".grant.kind", "enum", "Unknown rights-grant kind")
    if grant.get("kind") == "LICENSE":
        normalized = parse_license_or_contract({"kind": "LICENSE", "spdx_id": grant.get("reference")})
        if normalized["requires_review"] and asset.get("lifecycle") == "ACTIVE":
            report.add(path + ".grant.reference", "unreviewed-license", "Unknown license cannot support an ACTIVE asset")
    if grant.get("kind") == "CONTRACT" and grant.get("counsel_reviewed") is not True:
        report.add(path + ".grant.counsel_reviewed", "contract-review", "Contract permissions require affirmative counsel review")

    derivative = require_mapping(report, grant.get("derivative_outputs"), path + ".grant.derivative_outputs")
    for field in ("creation_allowed", "ownership", "release_allowed"):
        require_value(report, derivative, field, path + ".grant.derivative_outputs")
    checkpoint = require_mapping(report, grant.get("checkpoints"), path + ".grant.checkpoints")
    for field in ("finetune_allowed", "ownership", "distribution_allowed"):
        require_value(report, checkpoint, field, path + ".grant.checkpoints")

    classifications = require_mapping(report, asset.get("classifications"), path + ".classifications")
    for field in ("confidentiality", "privilege", "personal_data"):
        require_value(report, classifications, field, path + ".classifications")
    obligations = require_mapping(report, asset.get("obligations"), path + ".obligations")
    for field in ("attribution", "deletion", "publication", "renewal"):
        if field not in obligations:
            report.add(path + ".obligations." + field, "missing", "Obligation must be explicit, even when NONE")
    lineage = require_mapping(report, asset.get("lineage"), path + ".lineage")
    require_list(report, lineage.get("parent_asset_ids"), path + ".lineage.parent_asset_ids")
    require_value(report, lineage, "transformation", path + ".lineage")


def _validate_lineage(report: ValidationReport, assets: Dict[str, Dict[str, Any]]) -> None:
    graph = {
        asset_id: list(asset.get("lineage", {}).get("parent_asset_ids", []))
        for asset_id, asset in assets.items()
    }
    for asset_id, parents in graph.items():
        for parent in parents:
            if parent not in graph:
                report.add("assets.%s.lineage" % asset_id, "missing-parent", "Unknown parent asset %s" % parent)

    visiting: Set[str] = set()
    visited: Set[str] = set()

    def visit(asset_id: str) -> None:
        if asset_id in visiting:
            report.add("assets.%s.lineage" % asset_id, "cycle", "Provenance lineage contains a cycle")
            return
        if asset_id in visited:
            return
        visiting.add(asset_id)
        for parent in graph.get(asset_id, []):
            if parent in graph:
                visit(parent)
        visiting.remove(asset_id)
        visited.add(asset_id)

    for asset_id in graph:
        visit(asset_id)


def validate_rights_register(register: Dict[str, Any], today: Optional[date] = None) -> ValidationReport:
    report = ValidationReport()
    today = today or date.today()
    if register.get("schema_version") != 1:
        report.add("schema_version", "version", "Expected RightsRegister schema version 1")
    require_value(report, register, "register_id", "")
    version = require_value(report, register, "register_version", "")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        report.add("register_version", "version", "Version must be a positive integer")
    require_value(report, register, "rights_owner", "")
    assets_list = require_list(report, register.get("assets"), "assets")
    asset_ids = []
    indexed: Dict[str, Dict[str, Any]] = {}
    for index, value in enumerate(assets_list):
        asset = require_mapping(report, value, "assets[%d]" % index)
        _validate_asset(report, asset, index, today)
        asset_id = asset.get("asset_id")
        asset_ids.append(asset_id)
        if isinstance(asset_id, str):
            indexed[asset_id] = asset
    if duplicates(asset_ids):
        report.add("assets", "duplicate", "Asset IDs must be unique")
    _validate_lineage(report, indexed)

    queue = require_list(report, register.get("rights_review_queue"), "rights_review_queue")
    open_pairs = set()
    for index, value in enumerate(queue):
        path = "rights_review_queue[%d]" % index
        item = require_mapping(report, value, path)
        for field in ("review_id", "asset_id", "use", "reason", "status", "owner", "due_at"):
            require_value(report, item, field, path)
        parse_date(item.get("due_at"), path + ".due_at", report)
        if item.get("asset_id") not in indexed:
            report.add(path + ".asset_id", "unknown-asset", "Review must reference an inventoried asset")
        if item.get("use") not in RIGHTS_USES:
            report.add(path + ".use", "unknown-use", "Unknown rights use")
        if item.get("status") not in {"OPEN", "RESOLVED", "CANCELLED"}:
            report.add(path + ".status", "enum", "Unknown review status")
        if item.get("status") == "OPEN":
            open_pairs.add((item.get("asset_id"), item.get("use")))
    for asset_id, asset in indexed.items():
        for use, decision in asset.get("grant", {}).get("permissions", {}).items():
            if decision == "REVIEW" and (asset_id, use) not in open_pairs:
                report.add(
                    "assets.%s.grant.permissions.%s" % (asset_id, use),
                    "missing-review",
                    "REVIEW decisions must have an owned, open queue item",
                )
    return report


@dataclass(frozen=True)
class RightsDecision:
    allowed: bool
    asset_id: str
    use: str
    reasons: List[str]
    lineage_checked: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "asset_id": self.asset_id,
            "use": self.use,
            "reasons": self.reasons,
            "lineage_checked": self.lineage_checked,
        }


class RightsRegistry:
    """Fail-closed rights enforcement for asset lifecycle operations."""

    def __init__(self, register: Dict[str, Any], today: Optional[date] = None):
        self.today = today or date.today()
        self.register = register
        validation = validate_rights_register(register, self.today)
        validation.require_ok()
        self.assets = {item["asset_id"]: item for item in register["assets"]}
        self.open_reviews = {
            (item["asset_id"], item["use"])
            for item in register["rights_review_queue"]
            if item["status"] == "OPEN"
        }

    def decide(self, asset_id: str, use: str) -> RightsDecision:
        if use not in RIGHTS_USES:
            return RightsDecision(False, asset_id, use, ["unknown-use"], [])
        reasons: List[str] = []
        checked: List[str] = []
        visiting: Set[str] = set()

        def check(current_id: str) -> None:
            if current_id in visiting:
                reasons.append("lineage-cycle:%s" % current_id)
                return
            asset = self.assets.get(current_id)
            if not asset:
                reasons.append("unknown-asset:%s" % current_id)
                return
            visiting.add(current_id)
            checked.append(current_id)
            if asset["lifecycle"] != "ACTIVE":
                reasons.append("inactive:%s:%s" % (current_id, asset["lifecycle"]))
            grant = asset["grant"]
            expiry = grant.get("expiry_date")
            if expiry is not None and date.fromisoformat(str(expiry)) < self.today:
                reasons.append("expired:%s" % current_id)
            decision = grant["permissions"].get(use, "REVIEW")
            if decision != "ALLOW":
                reasons.append("permission-%s:%s:%s" % (decision.lower(), current_id, use))
            if (current_id, use) in self.open_reviews:
                reasons.append("open-review:%s:%s" % (current_id, use))
            if use == "transform" and grant["derivative_outputs"]["creation_allowed"] is not True:
                reasons.append("derivative-creation-denied:%s" % current_id)
            if use == "publish" and grant["derivative_outputs"]["release_allowed"] is not True:
                reasons.append("derivative-release-denied:%s" % current_id)
            if use == "train" and grant["checkpoints"]["finetune_allowed"] is not True:
                reasons.append("finetune-denied:%s" % current_id)
            for parent in asset["lineage"]["parent_asset_ids"]:
                check(parent)
            visiting.remove(current_id)

        check(asset_id)
        return RightsDecision(not reasons, asset_id, use, reasons, checked)

    def require(self, asset_id: str, use: str) -> RightsDecision:
        decision = self.decide(asset_id, use)
        if not decision.allowed:
            raise BoundaryError("Rights denied: %s" % ", ".join(decision.reasons))
        return decision


def ar_000_report(register: Dict[str, Any], required_asset_uses: List[Dict[str, Any]], today: Optional[date] = None) -> Dict[str, Any]:
    try:
        registry = RightsRegistry(register, today=today)
    except BoundaryError as exc:
        return {"gate": "AR-000", "passed": False, "decisions": [], "registry_error": str(exc)}
    decisions = []
    for requirement in required_asset_uses:
        for use in requirement.get("uses", []):
            decisions.append(registry.decide(requirement.get("asset_id", ""), use).to_dict())
    return {
        "gate": "AR-000",
        "passed": bool(decisions) and all(item["allowed"] for item in decisions),
        "decisions": decisions,
        "registry_error": None,
    }
