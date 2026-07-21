"""Closed catalogs controlled by the approved ScopeManifest."""

from __future__ import annotations

from typing import Dict, List


WORKFLOW_CATALOG: Dict[str, Dict[str, List[str]]] = {
    "counterparty-paper-review": {
        "documents": ["counterparty-paper", "buyer-playbook"],
        "deliverables": ["memo", "tracker", "checklist"],
        "truth_modes": ["document-span", "buyer-policy", "point-in-time-law"],
        "signoff_actions": ["release-work-product"],
    },
    "first-draft": {
        "documents": ["term-sheet", "buyer-template", "matter-facts"],
        "deliverables": ["draft", "checklist"],
        "truth_modes": ["matter-state", "buyer-policy", "point-in-time-law"],
        "signoff_actions": ["release-work-product"],
    },
    "first-turn-redline": {
        "documents": ["counterparty-paper", "buyer-playbook", "matter-facts"],
        "deliverables": ["redline", "memo"],
        "truth_modes": ["document-span", "buyer-policy", "matter-state"],
        "signoff_actions": ["release-work-product"],
    },
    "playbook-escalation": {
        "documents": ["agreement", "buyer-playbook", "matter-facts"],
        "deliverables": ["tracker", "memo"],
        "truth_modes": ["document-span", "buyer-policy", "human-adjudication"],
        "signoff_actions": ["adjudicate-policy", "release-work-product"],
    },
    "subsequent-turn-redline": {
        "documents": ["prior-redline", "counterparty-response", "buyer-playbook"],
        "deliverables": ["redline", "issue-list"],
        "truth_modes": ["document-span", "negotiation-state", "buyer-policy"],
        "signoff_actions": ["release-work-product"],
    },
    "term-negotiation": {
        "documents": ["agreement", "issue-list", "buyer-playbook"],
        "deliverables": ["negotiation-plan", "tracker"],
        "truth_modes": ["document-span", "buyer-policy", "client-decision"],
        "signoff_actions": ["accept-risk", "release-work-product"],
    },
}


# The source corpus is internally inconsistent: product.md claims 22, later
# says 21, and enumerates 20.  The first 20 entries preserve that enumeration.
# The final two make separately controllable dimensions that the same corpus
# already discusses.  They default to excluded in the template and cannot be
# activated without a manifest approval and impact report.
MA_WORKSTREAM_CATALOG: List[str] = [
    "corporate-org",
    "contracts-consents",
    "financing",
    "ip",
    "privacy",
    "employment",
    "benefits",
    "tax",
    "real-estate",
    "environmental",
    "regulatory",
    "litigation",
    "antitrust-hsr",
    "trade-cfius",
    "insurance",
    "diligence-synthesis",
    "purchase-agreement",
    "disclosure-schedules",
    "closing",
    "post-closing",
    "commercial-customers",
    "technology-cybersecurity",
]

TRANSACTION_STRUCTURES = {"stock-purchase", "asset-purchase", "merger"}
DEPLOYMENT_TIERS = {"T1", "T2", "T3"}
DELIVERABLE_KINDS = {
    "memo",
    "draft",
    "redline",
    "tracker",
    "checklist",
    "schedule",
    "calculation",
    "issue-list",
    "negotiation-plan",
}
RIGHTS_USES = {
    "ingest",
    "transform",
    "train",
    "evaluate",
    "share",
    "publish",
}
RIGHTS_DECISIONS = {"ALLOW", "DENY", "REVIEW"}
SEVERITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}

REQUIRED_GOVERNANCE_CONTROLS = {
    "classification",
    "tenant-isolation",
    "privilege-confirmation",
    "pii-detection",
    "residency",
    "encryption-at-rest",
    "encryption-in-transit",
    "key-management",
    "provider-no-training",
    "retention-deletion",
    "legal-hold",
    "dlp-export",
    "incident-response",
}

