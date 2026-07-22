"""Generate a fictional, structurally complete Phase 0 design-partner demo."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict, Optional

from utils.artifacts import atomic_write_yaml
from utils.catalogs import REQUIRED_GOVERNANCE_CONTROLS, RIGHTS_USES, WORKFLOW_CATALOG
from utils.pov import (
    HARVEY_COMMIT,
    HARVEY_MA_ROOT,
    HARVEY_POV_TASK,
    HARVEY_POV_TASK_URL,
    HARVEY_REPOSITORY,
    POV_BUYER_ID,
    POV_DATE,
    POV_LEGAL_ACTOR_ID,
    POV_MATTER_ID,
    POV_PRODUCT_ACTOR_ID,
    POV_SPONSOR_ACTOR_ID,
    POV_TIMESTAMP,
    POV_WORKFLOW,
    POV_WORKSTREAM,
)

from .io import load_document
from .manifest import approval_fingerprint


DEMO_NOW = POV_TIMESTAMP
DEMO_MATTER = POV_MATTER_ID
DEMO_ORG = POV_BUYER_ID
DEFAULT_TEMPLATE_DIR = Path(__file__).with_name("configs")


def _actor(actor_id: str, display_name: str, roles: list, actions: list) -> Dict[str, Any]:
    return {
        "actor_id": actor_id,
        "display_name": display_name,
        "organization": DEMO_ORG,
        "roles": roles,
        "credentials": [
            {
                "credential_id": "synthetic-credential-" + actor_id,
                "type": "SYNTHETIC_TEST_CREDENTIAL",
                "status": "ACTIVE",
                "verified_by": "synthetic-identity-adapter",
                "valid_until": "2035-01-01T00:00:00+00:00",
            }
        ],
        "delegations": [
            {
                "delegation_id": "synthetic-delegation-" + actor_id,
                "delegated_by": "synthetic-board",
                "action_types": actions,
                "severities": ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
                "deployment_tiers": ["T1", "T2", "T3"],
                "matter_ids": [DEMO_MATTER],
                "valid_from": "2026-01-01T00:00:00+00:00",
                "valid_until": "2035-01-01T00:00:00+00:00",
            }
        ],
        "conflicts": {"matter_ids": []},
        "ethical_walls": {"denied_matter_ids": []},
    }


def build_demo_bundle(template_dir: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    root = Path(template_dir) if template_dir else DEFAULT_TEMPLATE_DIR
    manifest = load_document(str(root / "ScopeManifest.template.yaml"))
    rights = load_document(str(root / "RightsRegister.template.yaml"))
    governance = load_document(str(root / "DataGovernancePolicy.template.yaml"))
    authority = load_document(str(root / "AuthoritySignoffMatrix.template.yaml"))

    manifest.update(
        {
            "test_fixture": True,
            "manifest_id": "harvey-ma-pov-scope-001",
            "approval_status": "APPROVED",
            "buyer": {
                "buyer_id": DEMO_ORG,
                "legal_name": "Harvey LAB M&A POV (Not a Legal Entity)",
                "persona": "Fictional buyer-side M&A deal team evaluating contract diligence",
                "perspective": "BUY_SIDE",
            },
            "pilot_matter_id": DEMO_MATTER,
            "workflow": {
                "selected": POV_WORKFLOW,
                "mapping": copy.deepcopy(WORKFLOW_CATALOG[POV_WORKFLOW]),
            },
            "high_severity_ambiguities": [],
            "required_asset_uses": [
                {"asset_id": "harvey-lab-ma-change-control-task", "uses": ["ingest", "transform", "evaluate"]}
            ],
            "pov_source": {
                "repository": HARVEY_REPOSITORY,
                "revision": HARVEY_COMMIT,
                "ma_root": HARVEY_MA_ROOT,
                "included_task_paths": [HARVEY_POV_TASK],
                "excluded_task_roots": "all tasks outside tasks/corporate-ma",
                "title": "Analyze Change of Control Provisions Across Target's Material Contracts — Due Diligence Report",
                "work_type": "analyze",
                "source_tags": ["Mergers & Acquisitions", "due-diligence", "change-of-control", "contract-analysis", "SaaS", "risk-assessment", "virtual-data-room"],
                "source_deliverable": "coc-analysis-report.docx",
                "source_criterion_count": 57,
            },
        }
    )
    for item in manifest["ma_scope"]["workstreams"]:
        included = item["id"] == POV_WORKSTREAM
        item.update(
            {
                "status": "IN_SCOPE" if included else "OUT_OF_SCOPE",
                "rationale": "Synthetic pilot workstream" if included else "Explicitly excluded from synthetic pilot",
                "document_families": ["material-contracts"] if included else [],
                "deliverables": ["memo"] if included else [],
                "truth_modes": ["document-span", "buyer-policy"] if included else [],
                "signoff_action": "release-work-product" if included else None,
            }
        )
    manifest["ma_scope"]["transaction"] = {"structure": "stock-purchase", "buyer_side": True}
    manifest["ma_scope"]["industry_profile"] = "SaaS target, matching the selected Harvey LAB M&A task"
    manifest["jurisdiction"] = {
        "governing_law": "Delaware state contract law (synthetic test selection)",
        "forum": "Delaware Court of Chancery (synthetic test selection)",
        "entity_law": "Delaware General Corporation Law (synthetic test selection)",
        "regulatory_overlays": [
            {"name": "Hart-Scott-Rodino Act", "applicability": "synthetic screen-and-escalate", "owner": POV_LEGAL_ACTOR_ID}
        ],
        "legal_cutoff_date": "2026-07-01",
    }
    manifest["product_mode"] = {
        "deployment_tier": "T1",
        "real_client_reliance": False,
        "target_model": {
            "provider": "synthetic-provider",
            "model_id": "synthetic-model-v1",
            "revision": "synthetic-revision-001",
            "access_method": "MOCK_ADAPTER",
            "access_owner": POV_PRODUCT_ACTOR_ID,
            "access_confirmed": True,
            "governance_route_id": "synthetic-route",
        },
    }
    manifest["deliverables"] = {
        "schemas": [
            {"kind": "memo", "schema_ref": "harvey-lab:%s/task.json#coc-analysis-report.docx" % HARVEY_POV_TASK, "required_sections": ["findings", "evidence", "escalations"]}
        ],
        "success_metrics": [
            {"id": "harvey-57-criteria-all-pass", "measure": "all 57 Harvey LAB task criteria pass", "operator": ">=", "threshold": 1.0, "owner": POV_PRODUCT_ACTOR_ID}
        ],
        "kill_criteria": [
            {"id": "synthetic-severe-false-accept", "measure": "severe false accepts", "operator": ">", "threshold": 0, "owner": POV_LEGAL_ACTOR_ID}
        ],
    }
    for exclusion in manifest["exclusions_register"]:
        exclusion["owner"] = POV_LEGAL_ACTOR_ID
    manifest["approvals"] = []
    signed = approval_fingerprint(manifest)
    manifest["approvals"] = [
        {"role": "commercial-sponsor", "actor_id": POV_SPONSOR_ACTOR_ID, "decision": "APPROVE", "approved_at": DEMO_NOW, "document_fingerprint": signed},
        {"role": "legal-owner", "actor_id": POV_LEGAL_ACTOR_ID, "decision": "APPROVE", "approved_at": DEMO_NOW, "document_fingerprint": signed},
        {"role": "product-owner", "actor_id": POV_PRODUCT_ACTOR_ID, "decision": "APPROVE", "approved_at": DEMO_NOW, "document_fingerprint": signed},
    ]

    rights.update({"test_fixture": True, "register_id": "harvey-ma-pov-rights-001", "rights_owner": POV_LEGAL_ACTOR_ID})
    parent = rights["assets"][0]
    parent["source"]["uri"] = HARVEY_REPOSITORY
    parent["source"]["content_fingerprint"] = "git:" + HARVEY_COMMIT
    parent["grant"]["reviewed_by"] = POV_LEGAL_ACTOR_ID
    parent["grant"]["reviewed_at"] = DEMO_NOW
    parent["grant"]["permissions"] = {use: "ALLOW" for use in RIGHTS_USES}
    task_asset = copy.deepcopy(parent)
    task_asset["asset_id"] = "harvey-lab-ma-change-control-task"
    task_asset["asset_type"] = "BENCHMARK_TASK_SLICE"
    task_asset["source"] = {
        "uri": HARVEY_POV_TASK_URL,
        "content_fingerprint": "git:%s#%s" % (HARVEY_COMMIT, HARVEY_POV_TASK),
        "acquired_at": POV_DATE,
    }
    task_asset["lineage"] = {
        "parent_asset_ids": ["harvey-lab"],
        "transformation": "FILTER_PATH:%s; INCLUDE_ONE_TASK:%s" % (HARVEY_MA_ROOT, HARVEY_POV_TASK),
    }
    rights["assets"] = [parent, task_asset]
    rights["rights_review_queue"] = []

    governance.update(
        {
            "test_fixture": True,
            "policy_id": "harvey-ma-pov-governance-001",
            "policy_owner": POV_LEGAL_ACTOR_ID,
            "approval_status": "APPROVED",
        }
    )
    governance["residency"] = {"allowed_regions": ["synthetic-region-1"], "cross_border_transfer": "DENY"}
    governance["encryption"] = {
        "at_rest": "AES-256",
        "in_transit": "TLS-1.3",
        "key_provider": "synthetic-kms",
        "key_scope": "TENANT",
        "rotation_days": 90,
    }
    governance["provider_routes"] = [
        {
            "route_id": "synthetic-route",
            "provider": "synthetic-provider",
            "model_id": "synthetic-model-v1",
            "allowed_classifications": ["PUBLIC", "SYNTHETIC"],
            "training_disabled": True,
            "retention_days": 0,
            "allowed_regions": ["synthetic-region-1"],
        }
    ]
    for rule in governance["retention"]["rules"]:
        rule["days"] = 30 if rule["classification"] != "PUBLIC" else 365
    governance["legal_hold"].update({"owner": POV_LEGAL_ACTOR_ID, "intake": "synthetic-legal-hold"})
    governance["dlp_export"]["allowed_destinations"] = ["synthetic-vdr"]
    governance["incident_response"] = {
        "owner": POV_LEGAL_ACTOR_ID,
        "intake_channel": "synthetic-security-incidents",
        "containment_sla_minutes": 30,
        "breach_assessment_owner": POV_LEGAL_ACTOR_ID,
    }
    governance["control_coverage"] = [
        {"control_id": control, "status": "IMPLEMENTED", "owner": POV_LEGAL_ACTOR_ID, "enforcement_point": "synthetic-adapter", "test_ids": ["test-" + control]}
        for control in sorted(REQUIRED_GOVERNANCE_CONTROLS)
    ]
    governance["approval"] = {"actor_id": POV_LEGAL_ACTOR_ID, "role": "governance-owner", "approved_at": DEMO_NOW}

    actions = [item["action_type"] for item in authority["approval_policies"]]
    authority.update(
        {
            "test_fixture": True,
            "matrix_id": "harvey-ma-pov-authority-001",
            "authority_owner": POV_LEGAL_ACTOR_ID,
            "approval_status": "APPROVED",
            "actors": [
                _actor(POV_SPONSOR_ACTOR_ID, "Synthetic Commercial Sponsor", ["commercial-sponsor", "customer-owner"], actions),
                _actor(POV_LEGAL_ACTOR_ID, "Synthetic Supervising Lawyer", ["legal-owner", "lawyer-of-record", "release-approver", "rights-owner", "governance-owner"], actions),
                _actor(POV_PRODUCT_ACTOR_ID, "Synthetic Product Owner", ["product-owner", "release-approver"], actions),
            ],
        }
    )
    authority["responsibility"] = {
        "lawyer_of_record_by_matter": {DEMO_MATTER: POV_LEGAL_ACTOR_ID},
        "customer_owner_by_matter": {DEMO_MATTER: POV_SPONSOR_ACTOR_ID},
        "rights_owner": POV_LEGAL_ACTOR_ID,
        "governance_owner": POV_LEGAL_ACTOR_ID,
        "release_owner": POV_PRODUCT_ACTOR_ID,
    }
    authority["release_signoff_workflow"]["e_signature_provider"] = "SYNTHETIC_E_SIGNATURE_ADAPTER"
    authority["approval"] = {"actor_id": POV_LEGAL_ACTOR_ID, "role": "legal-owner", "approved_at": DEMO_NOW}

    return {
        "manifest": manifest,
        "rights": rights,
        "governance": governance,
        "authority": authority,
    }


def write_demo_bundle(bundle: Dict[str, Dict[str, Any]], out_dir: str) -> Dict[str, str]:
    root = Path(out_dir)
    names = {
        "manifest": "ScopeManifest.demo.yaml",
        "rights": "RightsRegister.demo.yaml",
        "governance": "DataGovernancePolicy.demo.yaml",
        "authority": "AuthoritySignoffMatrix.demo.yaml",
    }
    paths = {}
    for key, filename in names.items():
        path = root / filename
        atomic_write_yaml(str(path), bundle[key])
        paths[key] = str(path)
    return paths
