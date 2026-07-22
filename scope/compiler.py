"""Cross-contract Phase 0 exit compiler."""

from __future__ import annotations

import copy
from datetime import date, datetime, timezone
from typing import Any, Dict, Optional

from utils.artifacts import fingerprint, set_fingerprint

from .authority import high_severity_ownership_report, validate_authority_matrix
from .errors import ValidationReport
from .governance import control_coverage_report, validate_governance_policy
from .manifest import approval_fingerprint, compile_manifest, validate_manifest
from .rights import ar_000_report, validate_rights_register


class Phase0Compiler:
    """Validate and bind all A1–A4 contracts into one exit artifact."""

    def __init__(self, today: Optional[date] = None, now: Optional[datetime] = None):
        self.now = now or datetime.now(timezone.utc)
        if self.now.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        self.today = today or self.now.date()

    def evaluate(
        self,
        manifest: Dict[str, Any],
        rights: Dict[str, Any],
        governance: Dict[str, Any],
        authority: Dict[str, Any],
    ) -> Dict[str, Any]:
        report = ValidationReport()
        report.merge(validate_manifest(manifest, require_approved=True), "scope_manifest")
        report.merge(validate_rights_register(rights, today=self.today), "rights_register")
        report.merge(validate_governance_policy(governance), "data_governance_policy")
        report.merge(validate_authority_matrix(authority, now=self.now), "authority_signoff_matrix")

        ar_000 = ar_000_report(rights, manifest.get("required_asset_uses", []), today=self.today)
        if not ar_000["passed"]:
            report.add("cross_contract.ar_000", "rights-gate", "Every required asset/use must be affirmatively rights-cleared")

        coverage = control_coverage_report(governance)
        if not coverage["complete"]:
            report.add("cross_contract.control_coverage", "governance-gate", "Policy-to-control coverage must be complete and tested")

        ownership = high_severity_ownership_report(authority, now=self.now)
        if not ownership["complete"]:
            report.add("cross_contract.human_ownership", "authority-gate", "Every high-severity action needs a currently authorized human owner")

        tier = manifest.get("product_mode", {}).get("deployment_tier")
        if governance.get("deployment_tier") != tier:
            report.add("cross_contract.deployment_tier", "tier-mismatch", "Manifest and governance tiers must match")
        target = manifest.get("product_mode", {}).get("target_model", {})
        route_id = target.get("governance_route_id")
        route = next(
            (item for item in governance.get("provider_routes", []) if item.get("route_id") == route_id),
            None,
        )
        if not route:
            report.add("cross_contract.model_route", "missing-route", "Target model must reference an approved governance route")
        elif route.get("provider") != target.get("provider") or route.get("model_id") != target.get("model_id"):
            report.add("cross_contract.model_route", "route-mismatch", "Governance route must match the exact target provider/model")

        actors = {item.get("actor_id"): item for item in authority.get("actors", []) if isinstance(item, dict)}
        for index, approval in enumerate(manifest.get("approvals", [])):
            actor = actors.get(approval.get("actor_id"))
            if not actor or approval.get("role") not in actor.get("roles", []):
                report.add(
                    "cross_contract.manifest_approvals[%d]" % index,
                    "unauthorized-approver",
                    "Manifest approver must hold the recorded approval role",
                )

        responsibility = authority.get("responsibility", {})
        pilot_matter_id = manifest.get("pilot_matter_id")
        if pilot_matter_id not in responsibility.get("lawyer_of_record_by_matter", {}):
            report.add("cross_contract.pilot_lawyer", "missing-owner", "Pilot matter needs a lawyer of record")
        if pilot_matter_id not in responsibility.get("customer_owner_by_matter", {}):
            report.add("cross_contract.pilot_customer", "missing-owner", "Pilot matter needs a customer owner")
        if rights.get("rights_owner") != responsibility.get("rights_owner"):
            report.add("cross_contract.rights_owner", "owner-mismatch", "Rights owner must match the authority matrix")
        if governance.get("policy_owner") != responsibility.get("governance_owner"):
            report.add("cross_contract.governance_owner", "owner-mismatch", "Governance owner must match the authority matrix")

        for index, asset in enumerate(rights.get("assets", [])):
            reviewer_id = asset.get("grant", {}).get("reviewed_by")
            reviewer = actors.get(reviewer_id)
            if asset.get("lifecycle") == "ACTIVE" and (
                not reviewer
                or not ({"rights-owner", "legal-owner"} & set(reviewer.get("roles", [])))
            ):
                report.add(
                    "cross_contract.rights_reviewers[%d]" % index,
                    "unauthorized-rights-reviewer",
                    "Every active asset must be reviewed by a registered rights/legal owner",
                )
        governance_approver = actors.get(governance.get("approval", {}).get("actor_id"))
        governance_role = governance.get("approval", {}).get("role")
        if not governance_approver or governance_role not in governance_approver.get("roles", []):
            report.add(
                "cross_contract.governance_approval",
                "unauthorized-governance-approver",
                "Governance approval must reference a registered actor holding the stated role",
            )

        policies = {item.get("action_type") for item in authority.get("approval_policies", []) if isinstance(item, dict)}
        required_actions = set(manifest.get("workflow", {}).get("mapping", {}).get("signoff_actions", []))
        for workstream in manifest.get("ma_scope", {}).get("workstreams", []):
            if isinstance(workstream, dict) and workstream.get("status") == "IN_SCOPE":
                required_actions.add(workstream.get("signoff_action"))
        missing_actions = sorted(action for action in required_actions if action and action not in policies)
        if missing_actions:
            report.add("cross_contract.signoff_actions", "missing-policy", "Missing authority policies: %s" % ", ".join(missing_actions))

        fixture = any(
            document.get("test_fixture") is True
            for document in (manifest, rights, governance, authority)
        )
        status = "READY" if report.ok and not fixture else "BLOCKED"
        if fixture:
            report.add("cross_contract.test_fixture", "fixture-boundary", "Test fixtures cannot produce a Phase 0 exit artifact")

        artifact = {
            "artifact_type": "Phase0ExitArtifact",
            "schema_version": 1,
            "status": status,
            "generated_at": self.now.astimezone(timezone.utc).isoformat(),
            "scope": {
                "manifest_id": manifest.get("manifest_id"),
                "manifest_version": manifest.get("manifest_version"),
                "buyer_id": manifest.get("buyer", {}).get("buyer_id"),
                "workflow": manifest.get("workflow", {}).get("selected"),
                "governing_law": manifest.get("jurisdiction", {}).get("governing_law"),
                "target_model": target.get("model_id"),
                "deployment_tier": tier,
            },
            "contract_fingerprints": {
                "scope_manifest": fingerprint(manifest),
                "rights_register": fingerprint(rights),
                "data_governance_policy": fingerprint(governance),
                "authority_signoff_matrix": fingerprint(authority),
            },
            "gates": {
                "scope_approved": validate_manifest(manifest, require_approved=True).ok,
                "ar_000": ar_000,
                "governance_control_coverage": coverage,
                "high_severity_human_ownership": ownership,
            },
            "validation": report.to_dict(),
        }
        set_fingerprint(artifact)
        return artifact

    def compile(
        self,
        manifest: Dict[str, Any],
        rights: Dict[str, Any],
        governance: Dict[str, Any],
        authority: Dict[str, Any],
    ) -> Dict[str, Any]:
        artifact = self.evaluate(manifest, rights, governance, authority)
        if artifact["status"] != "READY":
            errors = artifact["validation"]["issues"]
            detail = "; ".join("%s [%s]" % (item["path"], item["code"]) for item in errors[:10])
            from .errors import BoundaryError

            raise BoundaryError("Phase 0 exit is blocked: %s" % detail)
        # This separately exercises compilation and enriches the artifact with
        # the closed workflow contract only after all cross-contract gates pass.
        artifact["compiled_scope"] = compile_manifest(manifest, require_approved=True)
        set_fingerprint(artifact)
        return artifact

    def simulate(
        self,
        manifest: Dict[str, Any],
        rights: Dict[str, Any],
        governance: Dict[str, Any],
        authority: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Exercise all gates with fixtures without producing a real exit.

        Every input must opt into the fixture boundary. The returned status is
        TEST_READY/TEST_BLOCKED and is never accepted by downstream phases.
        """

        source_documents = (manifest, rights, governance, authority)
        if not all(document.get("test_fixture") is True for document in source_documents):
            from .errors import BoundaryError

            raise BoundaryError("Simulation requires test_fixture: true on all four contracts")
        simulated = [copy.deepcopy(document) for document in source_documents]
        for document in simulated:
            document.pop("test_fixture", None)
        simulated_manifest = simulated[0]
        signed = approval_fingerprint(simulated_manifest)
        for approval in simulated_manifest.get("approvals", []):
            approval["document_fingerprint"] = signed
        artifact = self.evaluate(*simulated)
        ready = artifact["status"] == "READY"
        artifact["status"] = "TEST_READY" if ready else "TEST_BLOCKED"
        artifact["production_eligible"] = False
        artifact["simulation"] = {
            "fictional_design_partner": True,
            "pov_downstream_unblocked": ready,
            "production_downstream_unblocked": False,
            "source_fixture_fingerprints": {
                "scope_manifest": fingerprint(manifest),
                "rights_register": fingerprint(rights),
                "data_governance_policy": fingerprint(governance),
                "authority_signoff_matrix": fingerprint(authority),
            },
        }
        if ready:
            artifact["compiled_scope"] = compile_manifest(simulated_manifest, require_approved=True)
        set_fingerprint(artifact)
        return artifact
