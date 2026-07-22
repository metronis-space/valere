"""Fictional M&A change-of-control fixture for the Phase 1 POV."""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional

from utils.catalogs import MA_WORKSTREAM_CATALOG
from utils.pov import (
    HARVEY_COMMIT,
    HARVEY_POV_TASK,
    HARVEY_POV_TASK_URL,
    POV_DATE,
    POV_LEGAL_ACTOR_ID,
    POV_TIMESTAMP,
    POV_WORKFLOW,
    POV_WORKSTREAM,
)


DEMO_AS_OF = POV_DATE
DEMO_ACQUIRED_AT = POV_TIMESTAMP


def _object_schema(required: List[str], properties: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    return {"type": "object", "required": required, "properties": properties, "additionalProperties": False}


def _type(
    type_id: str,
    category: str,
    required: List[str],
    properties: Dict[str, Dict[str, Any]],
    references: Optional[List[str]] = None,
    root: bool = False,
    production: bool = True,
    status: str = "ACTIVE",
) -> Dict[str, Any]:
    return {
        "type_id": type_id,
        "category": category,
        "status": status,
        "production": production,
        "root": root,
        "references": references or [],
        "schema": _object_schema(required, properties),
    }


def build_demo_ontology() -> Dict[str, Any]:
    identifier = {"type": "string"}
    text = {"type": "string"}
    boolean = {"type": "boolean"}
    number = {"type": "number"}
    types = [
        _type("legal-entity", "ENTITY", ["entity_id", "legal_name"], {"entity_id": identifier, "legal_name": text}, root=True),
        _type("deal-party", "PARTY", ["party_id", "entity_id", "side"], {"party_id": identifier, "entity_id": identifier, "side": {"type": "string", "enum": ["BUYER", "SELLER", "TARGET", "COUNTERPARTY"]}}, ["legal-entity"]),
        _type("party-capacity", "CAPACITY", ["party_id", "capacity"], {"party_id": identifier, "capacity": text}, ["deal-party"]),
        _type("ownership-interest", "OWNERSHIP", ["owner_id", "owned_id", "percentage"], {"owner_id": identifier, "owned_id": identifier, "percentage": number}, ["legal-entity"]),
        _type("capitalization-record", "CAPITALIZATION", ["entity_id", "security", "amount"], {"entity_id": identifier, "security": text, "amount": number}, ["legal-entity"]),
        _type("ma-transaction", "TRANSACTION", ["transaction_id", "structure", "buyer_id", "target_id"], {"transaction_id": identifier, "structure": {"type": "string", "enum": ["STOCK_PURCHASE", "ASSET_PURCHASE", "MERGER"]}, "buyer_id": identifier, "target_id": identifier}, ["deal-party"], root=True),
        _type("material-contract", "AGREEMENT", ["contract_id", "title", "material"], {"contract_id": identifier, "title": text, "material": boolean}, root=True),
        _type("contract-document", "DOCUMENT", ["document_id", "contract_id", "family"], {"document_id": identifier, "contract_id": identifier, "family": text}, ["material-contract"]),
        _type("change-of-control-clause", "CLAUSE", ["clause_id", "contract_id", "requires_consent"], {"clause_id": identifier, "contract_id": identifier, "requires_consent": boolean}, ["material-contract"]),
        _type("contract-defined-term", "DEFINED_TERM", ["term", "definition"], {"term": text, "definition": text}, ["contract-document"]),
        _type("contract-cross-reference", "CROSS_REFERENCE", ["from_clause_id", "to_reference"], {"from_clause_id": identifier, "to_reference": text}, ["change-of-control-clause"]),
        _type("contract-amendment", "AMENDMENT", ["amendment_id", "contract_id", "order"], {"amendment_id": identifier, "contract_id": identifier, "order": {"type": "integer"}}, ["material-contract"]),
        _type("transaction-fact", "FACT", ["fact_id", "name", "value"], {"fact_id": identifier, "name": text, "value": text}, root=True),
        _type("change-of-control-event", "EVENT", ["event_id", "transaction_id", "triggered"], {"event_id": identifier, "transaction_id": identifier, "triggered": boolean}, ["ma-transaction"]),
        _type("consent-requirement", "OBLIGATION", ["contract_id", "required"], {"contract_id": identifier, "required": boolean}, ["material-contract"]),
        _type("contractual-consent-right", "RIGHT", ["holder_id", "contract_id"], {"holder_id": identifier, "contract_id": identifier}, ["deal-party", "material-contract"]),
        _type("change-of-control-consent-issue", "ISSUE", ["issue_id", "contract_id", "severity"], {"issue_id": identifier, "contract_id": identifier, "severity": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"]}}, ["consent-requirement", "consent-status"], root=True),
        _type("closing-delay-consequence", "CONSEQUENCE", ["issue_id", "description"], {"issue_id": identifier, "description": text}, ["change-of-control-consent-issue"]),
        _type("consent-remedy", "REMEDY", ["issue_id", "action"], {"issue_id": identifier, "action": text}, ["change-of-control-consent-issue"]),
        _type("diligence-memo", "DELIVERABLE", ["deliverable_id", "matter_id"], {"deliverable_id": identifier, "matter_id": identifier}, ["consent-finding"], root=True),
        _type("consent-finding", "FINDING", ["finding_id", "issue_id", "evidence_ids"], {"finding_id": identifier, "issue_id": identifier, "evidence_ids": {"type": "array", "items": identifier}}, ["change-of-control-consent-issue", "source-reference"], root=True),
        _type("source-reference", "TRUTH_SOURCE", ["source_id", "span_id"], {"source_id": identifier, "span_id": identifier}, root=True),
        _type("verification-mode", "VERIFICATION_MODE", ["mode_id", "kind"], {"mode_id": identifier, "kind": {"type": "string", "enum": ["DOCUMENT_SPAN", "BUYER_POLICY", "POINT_IN_TIME_LAW", "HUMAN_ADJUDICATION"]}}, root=True),
        _type("consent-status", "FACT", ["contract_id", "status"], {"contract_id": identifier, "status": {"type": "string", "enum": ["NOT_OBTAINED", "REQUESTED", "OBTAINED", "WAIVED", "UNKNOWN"]}}, ["material-contract"]),
        _type("ambiguous-consent", "FACT", ["raw_text"], {"raw_text": text}, production=False, status="QUARANTINED"),
    ]
    common = ["legal-entity", "ma-transaction", "diligence-memo", "consent-finding", "source-reference", "verification-mode"]
    packs = []
    for workstream_id in MA_WORKSTREAM_CATALOG:
        type_ids = list(common)
        if workstream_id == "corporate-org":
            type_ids.extend(["deal-party", "party-capacity", "ownership-interest", "capitalization-record"])
        if workstream_id == POV_WORKSTREAM:
            type_ids.extend(
                [
                    "material-contract",
                    "contract-document",
                    "change-of-control-clause",
                    "contract-defined-term",
                    "contract-cross-reference",
                    "contract-amendment",
                    "change-of-control-event",
                    "consent-requirement",
                    "contractual-consent-right",
                    "consent-status",
                    "change-of-control-consent-issue",
                    "closing-delay-consequence",
                    "consent-remedy",
                ]
            )
        packs.append({"workstream_id": workstream_id, "type_ids": type_ids, "status": "ACTIVE" if workstream_id == POV_WORKSTREAM else "DEFINED_OUT_OF_SCOPE"})
    return {
        "registry_id": "harvey-ma-pov-ontology",
        "version": 1,
        "test_fixture": True,
        "types": types,
        "workstream_packs": packs,
        "migrations": [],
    }


def build_demo_bundle() -> Dict[str, Any]:
    contract_uri = HARVEY_POV_TASK_URL
    sources = [
        {
            "source_id": "harvey-change-control-contract-fixture",
            "source_type": "PUBLIC_BENCHMARK",
            "authority_kind": "CONTRACT",
            "title": "Harvey LAB change-of-control material-contract fixture",
            "uri": contract_uri,
            "jurisdiction": "Delaware",
            "issuing_body": "Contracting parties (fictional fixture)",
            "effective_date": "2026-01-01",
            "acquired_at": DEMO_ACQUIRED_AT,
            "media_type": "text/plain",
            "official": False,
            "test_fixture": True,
            "content": "Section 1. Change of Control. A merger or transfer of control requires the counterparty's prior written consent.\n\nSection 2. Evidence. Consent must be recorded before closing unless the requirement is expressly waived.",
        },
        {
            "source_id": "synthetic-buyer-playbook",
            "source_type": "SYNTHETIC",
            "authority_kind": "PLAYBOOK",
            "title": "Synthetic buyer change-of-control escalation policy",
            "uri": "urn:valere:test:buyer-playbook:change-control:v1",
            "jurisdiction": "Buyer policy (not law)",
            "issuing_body": "Synthetic Buyer",
            "effective_date": "2026-01-01",
            "acquired_at": DEMO_ACQUIRED_AT,
            "media_type": "text/plain",
            "official": False,
            "test_fixture": True,
            "content": "Escalate every unobtained change-of-control consent for a material contract with annual value of at least USD 100,000 to supervising counsel.",
        },
    ]
    propositions = [
        {
            "proposition_id": "prop-contract-consent-trigger",
            "text": "The fixture contract requires prior written consent for a merger or transfer of control.",
            "support": [
                {"source_id": "harvey-change-control-contract-fixture", "span_id": "span-0001", "support_type": "CONTRACT_TEXT", "polarity": "SUPPORTS", "confidence": 1.0, "verified_by": POV_LEGAL_ACTOR_ID}
            ],
        },
        {
            "proposition_id": "prop-buyer-materiality-escalation",
            "text": "The synthetic buyer policy escalates unobtained consent at or above USD 100,000 annual value.",
            "support": [
                {"source_id": "synthetic-buyer-playbook", "span_id": "span-0001", "support_type": "BUYER_POLICY", "polarity": "SUPPORTS", "confidence": 1.0, "verified_by": POV_LEGAL_ACTOR_ID}
            ],
        },
    ]
    contract_rule = {
        "rule_id": "rule-contract-change-control-consent",
        "version": 1,
        "kind": "CONTRACT_LOGIC",
        "active": True,
        "test_fixture": True,
        "owner": POV_LEGAL_ACTOR_ID,
        "issue_family": "change-of-control-consent",
        "issue_type_id": "change-of-control-consent-issue",
        "effective_from": "2026-01-01",
        "effective_until": None,
        "priority": 100,
        "confidence": 1.0,
        "applies_when": {"all": [{"fact": "contract.material", "op": "eq", "value": True}, {"fact": "contract.change_control_clause", "op": "eq", "value": True}]},
        "trigger": {"fact": "transaction.structure", "op": "in", "value": ["MERGER", "STOCK_PURCHASE"]},
        "exceptions": {"fact": "contract.consent_waived", "op": "eq", "value": True},
        "source_refs": [{"source_id": "harvey-change-control-contract-fixture", "span_id": "span-0001", "proposition_id": "prop-contract-consent-trigger"}],
        "actions": [
            {"action_id": "obtain-written-consent", "kind": "REQUIRED", "recommendation": "Obtain and record written counterparty consent before closing.", "authority_action": "release-work-product", "priority": 100, "prerequisites": {"fact": "contract.consent_status", "op": "eq", "value": "NOT_OBTAINED"}},
            {"action_id": "confirm-consent-status", "kind": "FALLBACK", "recommendation": "Escalate to supervising counsel to confirm consent status.", "authority_action": "release-work-product", "priority": 50, "prerequisites": {"fact": "contract.consent_status", "op": "exists", "value": False}},
        ],
        "overrides": [],
    }
    policy_rule = {
        "rule_id": "rule-buyer-material-consent-escalation",
        "version": 1,
        "kind": "BUYER_POLICY",
        "active": True,
        "test_fixture": True,
        "owner": POV_LEGAL_ACTOR_ID,
        "issue_family": "material-consent-escalation",
        "issue_type_id": "change-of-control-consent-issue",
        "effective_from": "2026-01-01",
        "effective_until": None,
        "priority": 100,
        "confidence": 1.0,
        "applies_when": {"all": [{"fact": "contract.material", "op": "eq", "value": True}, {"fact": "contract.consent_status", "op": "eq", "value": "NOT_OBTAINED"}]},
        "trigger": {"fact": "contract.annual_value_usd", "op": "gte", "value": 100000},
        "source_refs": [{"source_id": "synthetic-buyer-playbook", "span_id": "span-0001", "proposition_id": "prop-buyer-materiality-escalation"}],
        "actions": [
            {"action_id": "escalate-material-consent", "kind": "REQUIRED", "recommendation": "Escalate the material unobtained consent to supervising counsel.", "authority_action": "release-work-product", "priority": 100}
        ],
        "overrides": [],
    }
    baseline = {
        "contract": {"material": True, "change_control_clause": False, "consent_waived": False, "consent_status": "NOT_OBTAINED", "annual_value_usd": 250000},
        "transaction": {"structure": "MERGER"},
    }
    counterfactual = copy.deepcopy(baseline)
    counterfactual["contract"]["change_control_clause"] = True
    return {
        "bundle_id": "harvey-ma-change-control-truth-pov-v1",
        "version": 1,
        "test_fixture": True,
        "as_of": DEMO_AS_OF,
        "scope": {
            "workflow": POV_WORKFLOW,
            "workstream": POV_WORKSTREAM,
            "task": HARVEY_POV_TASK,
            "source_revision": HARVEY_COMMIT,
            "jurisdiction_assumption": "Delaware state contract law (synthetic test selection)",
        },
        "sources": sources,
        "coverage_register": [
            {"topic": "contract-change-control", "status": "COVERED", "source_ids": ["harvey-change-control-contract-fixture"], "reason": None},
            {"topic": "buyer-policy-change-control", "status": "COVERED", "source_ids": ["synthetic-buyer-playbook"], "reason": None},
            {"topic": "delaware-primary-law-change-control", "status": "UNAVAILABLE", "source_ids": [], "reason": "The POV asserts no legal proposition; acquire official current law before adding any legal rule."},
            {"topic": "commercial-citator", "status": "OUT_OF_SCOPE", "source_ids": [], "reason": "No case-law proposition is used in the contract-only POV."},
        ],
        "freshness_sla_days": 1,
        "parse_metrics": {"sample_size": 2, "precision": 1.0, "recall": 1.0, "minimum": 0.95},
        "hierarchy": {},
        "treatments": [],
        "propositions": propositions,
        "citator": {"covered": False, "statuses": {}},
        "authority_gold_set": [
            {"case_id": "gold-contract", "proposition_id": "prop-contract-consent-trigger", "target_jurisdiction": "Delaware", "expected_supported": True, "expected_adverse": False},
            {"case_id": "gold-policy", "proposition_id": "prop-buyer-materiality-escalation", "target_jurisdiction": "Delaware", "expected_supported": True, "expected_adverse": False},
            {"case_id": "gold-unknown", "proposition_id": "prop-no-such-rule", "target_jurisdiction": "Delaware", "expected_supported": False, "expected_adverse": False},
        ],
        "authority_quality_thresholds": {"precision": 1.0, "recall": 1.0, "maximum_false_accept_rate": 0.0, "adverse_retrieval_recall": 1.0},
        "ontology": build_demo_ontology(),
        "rule_pack": {
            "rule_pack_id": "harvey-ma-change-control-rules",
            "version": 1,
            "test_fixture": True,
            "minimum_confidence": 0.8,
            "rules": [contract_rule, policy_rule],
            "coverage_declaration": {
                "issue_families": ["change-of-control-consent", "material-consent-escalation", "unmapped-ma-issue"],
                "no_rule": [{"issue_family": "unmapped-ma-issue", "reason": "Outside the single-task POV and must route to human review.", "owner": POV_LEGAL_ACTOR_ID}],
            },
        },
        "held_out_cases": [
            {"case_id": "holdout-contract-trigger", "issue_family": "change-of-control-consent", "as_of": DEMO_AS_OF, "facts": counterfactual, "expected_status": "MATCHED", "expected_rule_ids": ["rule-contract-change-control-consent"]},
            {"case_id": "holdout-no-clause", "issue_family": "change-of-control-consent", "as_of": DEMO_AS_OF, "facts": baseline, "expected_status": "NO_RULE", "expected_rule_ids": []},
            {"case_id": "holdout-material-policy", "issue_family": "material-consent-escalation", "as_of": DEMO_AS_OF, "facts": counterfactual, "expected_status": "MATCHED", "expected_rule_ids": ["rule-buyer-material-consent-escalation"]},
            {"case_id": "holdout-unmapped", "issue_family": "unmapped-ma-issue", "as_of": DEMO_AS_OF, "facts": counterfactual, "expected_status": "NO_RULE", "expected_rule_ids": []},
        ],
        "minimum_held_out_coverage": 1.0,
        "counterfactuals": [
            {"counterfactual_id": "coc-clause-toggle", "issue_family": "change-of-control-consent", "as_of": DEMO_AS_OF, "baseline": baseline, "counterfactual": counterfactual, "changed_fact_paths": ["contract.change_control_clause"]}
        ],
        "ar_001": {
            "issue_family": "change-of-control-consent",
            "maximum_exponent": 0.9,
            "observations": [
                {"accepted_matters": 1, "senior_lawyer_minutes": 40},
                {"accepted_matters": 2, "senior_lawyer_minutes": 58},
                {"accepted_matters": 4, "senior_lawyer_minutes": 84},
                {"accepted_matters": 8, "senior_lawyer_minutes": 120},
            ],
        },
    }
