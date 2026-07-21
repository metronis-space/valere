from __future__ import annotations

import copy
import json
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

from scope.authority import AuthorityEngine, read_audit_log, validate_authority_matrix
from scope.catalog import MA_WORKSTREAM_CATALOG, REQUIRED_GOVERNANCE_CONTROLS, RIGHTS_USES, WORKFLOW_CATALOG
from scope.compiler import Phase0Compiler
from scope.demo import build_demo_bundle
from scope.errors import BoundaryError
from scope.governance import GovernanceEngine
from scope.manifest import approval_fingerprint, change_impact, validate_manifest
from scope.rights import RightsRegistry, ar_000_report, parse_license_or_contract, validate_rights_register


NOW = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)


def actor(actor_id, roles, action_types):
    return {
        "actor_id": actor_id,
        "display_name": actor_id.replace("-", " ").title(),
        "organization": "buyer-001",
        "roles": roles,
        "credentials": [
            {
                "credential_id": "credential-" + actor_id,
                "type": "EMPLOYMENT_AND_ROLE_VERIFICATION",
                "status": "ACTIVE",
                "verified_by": "identity-admin",
                "valid_until": "2030-01-01T00:00:00+00:00",
            }
        ],
        "delegations": [
            {
                "delegation_id": "delegation-" + actor_id,
                "delegated_by": "board",
                "action_types": action_types,
                "severities": ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
                "deployment_tiers": ["T1", "T2", "T3"],
                "matter_ids": ["matter-001"],
                "valid_from": "2026-01-01T00:00:00+00:00",
                "valid_until": "2030-01-01T00:00:00+00:00",
            }
        ],
        "conflicts": {"matter_ids": []},
        "ethical_walls": {"denied_matter_ids": []},
    }


def valid_authority():
    actions = ["release-work-product", "accept-risk", "approve-scope", "override-control"]
    return {
        "schema_version": 1,
        "matrix_id": "authority-001",
        "matrix_version": 1,
        "authority_owner": "actor-legal",
        "approval_status": "APPROVED",
        "actors": [
            actor("actor-sponsor", ["commercial-sponsor", "customer-owner"], actions),
            actor("actor-legal", ["legal-owner", "lawyer-of-record", "release-approver", "rights-owner", "governance-owner"], actions),
            actor("actor-product", ["product-owner", "release-approver"], actions),
        ],
        "responsibility": {
            "lawyer_of_record_by_matter": {"matter-001": "actor-legal"},
            "customer_owner_by_matter": {"matter-001": "actor-sponsor"},
            "rights_owner": "actor-legal",
            "governance_owner": "actor-legal",
            "release_owner": "actor-product",
        },
        "approval_policies": [
            {
                "action_type": "release-work-product",
                "severities": ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
                "deployment_tiers": ["T1", "T2", "T3"],
                "required_roles": ["lawyer-of-record", "product-owner"],
                "min_approvers": 2,
                "self_approval_allowed": False,
                "distinct_actors_required": True,
                "lawyer_of_record_required": True,
            },
            {
                "action_type": "accept-risk",
                "severities": ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
                "deployment_tiers": ["T1", "T2", "T3"],
                "required_roles": ["lawyer-of-record", "customer-owner"],
                "min_approvers": 2,
                "self_approval_allowed": False,
                "distinct_actors_required": True,
                "lawyer_of_record_required": True,
            },
            {
                "action_type": "approve-scope",
                "severities": ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
                "deployment_tiers": ["T1", "T2", "T3"],
                "required_roles": ["commercial-sponsor", "legal-owner", "product-owner"],
                "min_approvers": 3,
                "self_approval_allowed": False,
                "distinct_actors_required": True,
                "lawyer_of_record_required": False,
            },
            {
                "action_type": "override-control",
                "severities": ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
                "deployment_tiers": ["T1", "T2", "T3"],
                "required_roles": ["lawyer-of-record", "product-owner"],
                "min_approvers": 2,
                "self_approval_allowed": False,
                "distinct_actors_required": True,
                "lawyer_of_record_required": True,
            },
        ],
        "release_signoff_workflow": {
            "stages": ["request", "legal-review", "product-review", "e-sign", "release"],
            "e_signature_provider": "TEST_ADAPTER",
        },
        "audit_logs": {
            "client_decisions": {"format": "HASH_CHAINED_JSONL", "append_only": True, "path": "var/audit/client-decisions.jsonl"},
            "exceptions_overrides": {"format": "HASH_CHAINED_JSONL", "append_only": True, "path": "var/audit/exceptions-overrides.jsonl"},
        },
        "approval": {"actor_id": "actor-legal", "role": "legal-owner", "approved_at": "2026-07-20T00:00:00+00:00"},
    }


def valid_manifest():
    workstreams = []
    for workstream_id in MA_WORKSTREAM_CATALOG:
        included = workstream_id == "contracts-consents"
        workstreams.append(
            {
                "id": workstream_id,
                "status": "IN_SCOPE" if included else "OUT_OF_SCOPE",
                "rationale": "Pilot workstream" if included else "Explicitly excluded from the first pilot",
                "document_families": ["material-contracts"] if included else [],
                "deliverables": ["memo"] if included else [],
                "truth_modes": ["document-span", "buyer-policy"] if included else [],
                "signoff_action": "release-work-product" if included else None,
            }
        )
    manifest = {
        "schema_version": 1,
        "manifest_id": "scope-001",
        "manifest_version": 1,
        "approval_status": "APPROVED",
        "buyer": {
            "buyer_id": "buyer-001",
            "legal_name": "Example Buyer LLC",
            "persona": "Private equity deal team and buyer-side M&A counsel",
            "perspective": "BUY_SIDE",
        },
        "pilot_matter_id": "matter-001",
        "workflow": {
            "selected": "counterparty-paper-review",
            "mapping": copy.deepcopy(WORKFLOW_CATALOG["counterparty-paper-review"]),
        },
        "ma_scope": {
            "workstreams": workstreams,
            "transaction": {"structure": "stock-purchase", "buyer_side": True},
            "industry_profile": "B2B software",
        },
        "jurisdiction": {
            "governing_law": "Delaware state contract law",
            "forum": "Delaware Court of Chancery",
            "entity_law": "Delaware General Corporation Law",
            "regulatory_overlays": [
                {"name": "Hart-Scott-Rodino Act", "applicability": "screen-and-escalate", "owner": "actor-legal"}
            ],
            "legal_cutoff_date": "2026-07-01",
        },
        "product_mode": {
            "deployment_tier": "T1",
            "real_client_reliance": False,
            "target_model": {
                "provider": "approved-provider",
                "model_id": "model-v1",
                "revision": "rev-001",
                "access_method": "API",
                "access_owner": "actor-product",
                "access_confirmed": True,
                "governance_route_id": "route-model-v1",
            },
        },
        "deliverables": {
            "schemas": [{"kind": "memo", "schema_ref": "schemas/diligence-memo-v1", "required_sections": ["findings", "evidence", "escalations"]}],
            "success_metrics": [{"id": "all-pass", "measure": "severity-weighted all-pass rate", "operator": ">=", "threshold": 0.9, "owner": "actor-product"}],
            "kill_criteria": [{"id": "severe-false-accept", "measure": "severe false accepts", "operator": ">", "threshold": 0, "owner": "actor-legal"}],
        },
        "required_asset_uses": [{"asset_id": "harvey-lab", "uses": ["ingest", "transform", "evaluate"]}],
        "exclusions_register": [
            {"id": "no-live-advice", "description": "No autonomous final legal advice or live-client reliance", "owner": "actor-legal"},
            {"id": "one-workflow", "description": "Every workflow other than counterparty paper review is excluded", "owner": "actor-product"},
        ],
        "high_severity_ambiguities": [],
        "change_impact_log": [],
        "approvals": [],
    }
    signed = approval_fingerprint(manifest)
    manifest["approvals"] = [
        {"role": "commercial-sponsor", "actor_id": "actor-sponsor", "decision": "APPROVE", "approved_at": "2026-07-20T01:00:00+00:00", "document_fingerprint": signed},
        {"role": "legal-owner", "actor_id": "actor-legal", "decision": "APPROVE", "approved_at": "2026-07-20T02:00:00+00:00", "document_fingerprint": signed},
        {"role": "product-owner", "actor_id": "actor-product", "decision": "APPROVE", "approved_at": "2026-07-20T03:00:00+00:00", "document_fingerprint": signed},
    ]
    return manifest


def valid_rights():
    return {
        "schema_version": 1,
        "register_id": "rights-001",
        "register_version": 1,
        "rights_owner": "actor-legal",
        "assets": [
            {
                "asset_id": "harvey-lab",
                "asset_type": "BENCHMARK_DATASET",
                "lifecycle": "ACTIVE",
                "source": {"uri": "https://github.com/harveyai/harvey-labs", "content_fingerprint": "git:845a088", "acquired_at": "2026-07-20"},
                "owner": {"owner_id": "harvey-ai", "legal_name": "Harvey AI", "rights_contact": "public-license"},
                "grant": {
                    "kind": "LICENSE",
                    "reference": "MIT",
                    "reviewed_by": "actor-legal",
                    "reviewed_at": "2026-07-20T00:00:00+00:00",
                    "expiry_date": None,
                    "permissions": {use: "ALLOW" for use in RIGHTS_USES},
                    "derivative_outputs": {"creation_allowed": True, "ownership": "PROJECT", "release_allowed": True},
                    "checkpoints": {"finetune_allowed": True, "ownership": "SUBJECT_TO_MODEL_TERMS", "distribution_allowed": False},
                },
                "classifications": {"confidentiality": "PUBLIC", "privilege": "NONE", "personal_data": "NONE"},
                "obligations": {"attribution": "PRESERVE_MIT_NOTICE", "deletion": "NONE", "publication": "PRESERVE_NOTICE", "renewal": "NONE"},
                "lineage": {"parent_asset_ids": [], "transformation": "SOURCE"},
            }
        ],
        "rights_review_queue": [],
    }


def valid_governance():
    levels = [
        {"id": "PUBLIC", "rank": 0, "description": "Public rights-cleared data"},
        {"id": "SYNTHETIC", "rank": 1, "description": "Synthetic data"},
        {"id": "CONFIDENTIAL", "rank": 2, "description": "Confidential data"},
        {"id": "PRIVILEGED", "rank": 3, "description": "Human-confirmed privilege"},
        {"id": "RESTRICTED", "rank": 4, "description": "Most restrictive"},
    ]
    return {
        "schema_version": 1,
        "policy_id": "governance-001",
        "policy_version": 1,
        "policy_owner": "actor-legal",
        "approval_status": "APPROVED",
        "deployment_tier": "T1",
        "classification": {
            "levels": levels,
            "default_level": "SYNTHETIC",
            "privilege_requires_human_confirmation": True,
        },
        "labels": {"tenant_required": True, "matter_required": True, "enforcement_point": "storage-and-tool-gateway"},
        "pii_detection": {"detectors": [{"name": "matter-id", "pattern": r"\bMAT-[0-9]{6}\b"}], "on_detection": "UPCLASSIFY_AND_REVIEW"},
        "residency": {"allowed_regions": ["ap-south-1"], "cross_border_transfer": "DENY"},
        "encryption": {"at_rest": "AES-256", "in_transit": "TLS-1.3", "key_provider": "approved-kms", "key_scope": "TENANT", "rotation_days": 90},
        "provider_routes": [
            {
                "route_id": "route-model-v1",
                "provider": "approved-provider",
                "model_id": "model-v1",
                "allowed_classifications": ["PUBLIC", "SYNTHETIC"],
                "training_disabled": True,
                "retention_days": 0,
                "allowed_regions": ["ap-south-1"],
            }
        ],
        "retention": {
            "rules": [
                {"classification": item["id"], "days": 30 if item["id"] != "PUBLIC" else 365, "disposition": "DELETE"}
                for item in levels
            ]
        },
        "legal_hold": {"owner": "actor-legal", "intake": "legal-hold-service", "release_requires_approval": True, "active_matter_ids": ["matter-held"]},
        "dlp_export": {"default": "DENY", "approval_action": "release-work-product", "allowed_destinations": ["approved-vdr"]},
        "incident_response": {"owner": "actor-legal", "intake_channel": "security-incidents", "containment_sla_minutes": 30, "breach_assessment_owner": "actor-legal"},
        "control_coverage": [
            {"control_id": control_id, "status": "IMPLEMENTED", "owner": "actor-legal", "enforcement_point": "phase0-engine", "test_ids": ["test-" + control_id]}
            for control_id in sorted(REQUIRED_GOVERNANCE_CONTROLS)
        ],
        "approval": {"actor_id": "actor-legal", "role": "governance-owner", "approved_at": "2026-07-20T00:00:00+00:00"},
    }


class Phase0Tests(unittest.TestCase):
    def test_fictional_design_partner_is_test_ready_but_never_production_ready(self):
        bundle = build_demo_bundle("scope/configs")
        compiler = Phase0Compiler(now=NOW)
        artifact = compiler.simulate(
            bundle["manifest"], bundle["rights"], bundle["governance"], bundle["authority"]
        )
        self.assertEqual("TEST_READY", artifact["status"])
        self.assertFalse(artifact["production_eligible"])
        self.assertTrue(artifact["simulation"]["pov_downstream_unblocked"])
        self.assertFalse(artifact["simulation"]["production_downstream_unblocked"])
        self.assertEqual(
            ["tasks/corporate-ma/analyze-change-of-control-provisions-across-targets-material-contracts"],
            bundle["manifest"]["pov_source"]["included_task_paths"],
        )
        self.assertEqual(
            "harvey-lab-ma-change-control-task",
            bundle["manifest"]["required_asset_uses"][0]["asset_id"],
        )
        with self.assertRaises(BoundaryError):
            compiler.compile(
                bundle["manifest"], bundle["rights"], bundle["governance"], bundle["authority"]
            )

    def test_closed_catalogs_cover_six_workflows_and_22_workstreams(self):
        self.assertEqual(6, len(WORKFLOW_CATALOG))
        self.assertEqual(22, len(MA_WORKSTREAM_CATALOG))
        for mapping in WORKFLOW_CATALOG.values():
            self.assertTrue(mapping["documents"])
            self.assertTrue(mapping["deliverables"])
            self.assertTrue(mapping["truth_modes"])
            self.assertTrue(mapping["signoff_actions"])

    def test_complete_phase_exit_compiles(self):
        artifact = Phase0Compiler(now=NOW).compile(
            valid_manifest(), valid_rights(), valid_governance(), valid_authority()
        )
        self.assertEqual("READY", artifact["status"])
        self.assertTrue(artifact["gates"]["ar_000"]["passed"])
        self.assertEqual(["contracts-consents"], artifact["compiled_scope"]["included_workstreams"])

    def test_stale_manifest_signature_is_rejected(self):
        manifest = valid_manifest()
        manifest["jurisdiction"]["forum"] = "Changed forum"
        report = validate_manifest(manifest)
        self.assertFalse(report.ok)
        self.assertIn("stale-approval", {item.code for item in report.issues})

    def test_change_impact_is_reproducible_and_requires_version_increment(self):
        previous = valid_manifest()
        current = copy.deepcopy(previous)
        current["manifest_version"] = 2
        current["jurisdiction"]["forum"] = "Delaware Superior Court"
        first = change_impact(previous, current)
        second = change_impact(previous, current)
        self.assertEqual(first, second)
        self.assertEqual("HIGH", next(item for item in first["changes"] if item["path"] == "jurisdiction.forum")["severity"])
        current["manifest_version"] = 1
        with self.assertRaises(BoundaryError):
            change_impact(previous, current)

    def test_rights_gate_checks_unknown_use_and_recursive_lineage(self):
        rights = valid_rights()
        derivative = copy.deepcopy(rights["assets"][0])
        derivative["asset_id"] = "derived-task"
        derivative["lineage"] = {"parent_asset_ids": ["harvey-lab"], "transformation": "FILTER"}
        rights["assets"].append(derivative)
        registry = RightsRegistry(rights, today=date(2026, 7, 22))
        self.assertTrue(registry.decide("derived-task", "evaluate").allowed)
        rights["assets"][0]["grant"]["permissions"]["evaluate"] = "DENY"
        denied = RightsRegistry(rights, today=date(2026, 7, 22)).decide("derived-task", "evaluate")
        self.assertFalse(denied.allowed)
        self.assertIn("harvey-lab", denied.lineage_checked)
        gate = ar_000_report(rights, [{"asset_id": "derived-task", "uses": ["evaluate"]}], today=date(2026, 7, 22))
        self.assertFalse(gate["passed"])

    def test_unknown_license_routes_to_review(self):
        parsed = parse_license_or_contract({"kind": "LICENSE", "spdx_id": "LicenseRef-Unknown"})
        self.assertTrue(parsed["requires_review"])
        self.assertEqual({"REVIEW"}, set(parsed["permissions"].values()))
        rights = valid_rights()
        rights["assets"][0]["grant"]["reference"] = "LicenseRef-Unknown"
        self.assertFalse(validate_rights_register(rights, today=date(2026, 7, 22)).ok)

    def test_governance_privilege_is_flagged_not_inferred(self):
        engine = GovernanceEngine(valid_governance())
        result = engine.classify(
            "Privileged and confidential. Email counsel@example.com.",
            "buyer-001",
            "matter-001",
        )
        self.assertTrue(result.potential_privilege)
        self.assertFalse(result.privilege_confirmed)
        self.assertEqual("CONFIDENTIAL", result.level)
        confirmed = engine.classify("attorney work product", "buyer-001", "matter-001", privilege_confirmed=True)
        self.assertEqual("PRIVILEGED", confirmed.level)

    def test_governance_blocks_cross_tenant_provider_and_export(self):
        engine = GovernanceEngine(valid_governance())
        self.assertFalse(engine.authorize_tenant_access("buyer-001", ["matter-001"], "buyer-002", "matter-001"))
        with self.assertRaises(BoundaryError):
            engine.require_provider_route("route-model-v1", "CONFIDENTIAL", "ap-south-1")
        with self.assertRaises(BoundaryError):
            engine.require_export("CONFIDENTIAL", "approved-vdr", approved=False)

    def test_retention_scheduler_respects_legal_hold(self):
        engine = GovernanceEngine(valid_governance())
        created = datetime(2026, 1, 1, tzinfo=timezone.utc)
        held = engine.retention_action("CONFIDENTIAL", created, "matter-held", now=NOW)
        self.assertEqual("HOLD", held["action"])
        expired = engine.retention_action("CONFIDENTIAL", created, "matter-001", now=NOW)
        self.assertEqual("DELETE", expired["action"])

    def test_authority_blocks_self_approval_and_accepts_separated_signoff(self):
        engine = AuthorityEngine(valid_authority(), now=NOW)
        request = {
            "requester_id": "actor-product",
            "action_type": "release-work-product",
            "severity": "HIGH",
            "deployment_tier": "T1",
            "matter_id": "matter-001",
        }
        self_approval = [
            {"actor_id": "actor-product", "decision": "APPROVE", "approved_at": "2026-07-22T10:00:00+00:00"},
            {"actor_id": "actor-legal", "decision": "APPROVE", "approved_at": "2026-07-22T10:01:00+00:00"},
        ]
        self.assertFalse(engine.evaluate_signoff(request, self_approval).approved)
        request["requester_id"] = "actor-sponsor"
        accepted = engine.evaluate_signoff(request, self_approval)
        self.assertTrue(accepted.approved, accepted.reasons)

    def test_expired_authority_is_blocked_immediately(self):
        engine = AuthorityEngine(valid_authority(), now=NOW)
        future = datetime(2031, 1, 1, tzinfo=timezone.utc)
        reasons = engine.actor_authorized(
            "actor-legal", "release-work-product", "HIGH", "T1", "matter-001", at=future
        )
        self.assertIn("no-active-credential", reasons)
        self.assertIn("no-active-delegation", reasons)

    def test_high_severity_role_coverage_cannot_be_faked_by_headcount(self):
        matrix = valid_authority()
        product = next(item for item in matrix["actors"] if item["actor_id"] == "actor-product")
        product["roles"] = ["release-approver"]
        report = validate_authority_matrix(matrix, now=NOW)
        self.assertIn("unowned-required-role", {item.code for item in report.issues})

    def test_audit_log_is_append_only_and_tamper_evident(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "audit.jsonl")
            engine = AuthorityEngine(valid_authority(), now=NOW)
            engine.record_client_decision(
                path,
                "actor-sponsor",
                {"matter_id": "matter-001", "decision": "proceed"},
                NOW,
            )
            engine.record_override(
                path,
                {
                    "requester_id": "actor-sponsor",
                    "action_type": "override-control",
                    "severity": "HIGH",
                    "deployment_tier": "T1",
                    "matter_id": "matter-001",
                },
                [
                    {"actor_id": "actor-legal", "decision": "APPROVE", "approved_at": "2026-07-22T10:00:00+00:00"},
                    {"actor_id": "actor-product", "decision": "APPROVE", "approved_at": "2026-07-22T10:01:00+00:00"},
                ],
                {
                    "reason": "time-limited test",
                    "control": "export",
                    "expires_at": "2026-07-23T00:00:00+00:00",
                },
                NOW,
            )
            self.assertEqual(2, len(read_audit_log(path)))
            lines = Path(path).read_text(encoding="utf-8").splitlines()
            event = json.loads(lines[0])
            event["payload"]["decision"] = "tampered"
            lines[0] = json.dumps(event)
            Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
            with self.assertRaises(BoundaryError):
                read_audit_log(path)

    def test_phase_exit_blocks_unknown_rights(self):
        rights = valid_rights()
        rights["assets"][0]["grant"]["permissions"]["evaluate"] = "REVIEW"
        rights["rights_review_queue"] = [
            {
                "review_id": "review-001",
                "asset_id": "harvey-lab",
                "use": "evaluate",
                "reason": "contract ambiguity",
                "status": "OPEN",
                "owner": "actor-legal",
                "due_at": "2026-08-01",
            }
        ]
        artifact = Phase0Compiler(now=NOW).evaluate(
            valid_manifest(), rights, valid_governance(), valid_authority()
        )
        self.assertEqual("BLOCKED", artifact["status"])
        self.assertFalse(artifact["gates"]["ar_000"]["passed"])


if __name__ == "__main__":
    unittest.main()
