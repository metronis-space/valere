"""C1: deterministic canonical matter graph and invariant checks."""

from __future__ import annotations

import copy
import hashlib
from datetime import date
from typing import Any, Dict, Iterable, Mapping

from utils.artifacts import set_fingerprint, verify_fingerprint


COLLECTIONS = (
    "entities",
    "ownership",
    "capitalization",
    "contracts",
    "consents",
    "assets",
    "liabilities",
    "debts",
    "liens",
    "employees",
    "benefits",
    "ip",
    "data",
    "regulatory",
    "litigation",
    "evidence",
    "known_unknowns",
    "planted_non_issues",
    "ambiguities",
)
EVIDENCE_STATES = {"AVAILABLE", "MISSING", "UNPRODUCED"}


def build_world(phase1: Mapping[str, Any], seed: int = 20260722) -> Dict[str, Any]:
    """Build the one-family Phase 2 POV world without rendering documents."""

    values = (150_000, 250_000, 500_000)
    amount = values[int.from_bytes(hashlib.sha256(str(seed).encode()).digest()[:4], "big") % len(values)]
    world: Dict[str, Any] = {
        "artifact_type": "CanonicalMatterGraph",
        "schema_version": 1,
        "graph_version": 1,
        "seed": seed,
        "phase1_artifact_fingerprint": phase1["artifact_fingerprint"],
        "scope": copy.deepcopy(dict(phase1["scope"])),
        "matter": {
            "matter_id": "phase2-coc-%08x" % (seed & 0xFFFFFFFF),
            "lifecycle": "ACTIVE",
            "as_of": phase1["as_of"],
            "currency": "USD",
        },
        "entities": [
            {"entity_id": "buyer", "type_id": "legal-entity", "role": "BUYER", "name": "Synthetic Buyer LLC"},
            {"entity_id": "target", "type_id": "legal-entity", "role": "TARGET", "name": "Synthetic Target Inc."},
            {"entity_id": "seller", "type_id": "legal-entity", "role": "SELLER", "name": "Synthetic Seller LP"},
            {"entity_id": "target-sub", "type_id": "legal-entity", "role": "SUBSIDIARY", "name": "Synthetic Target Sub Inc."},
            {"entity_id": "counterparty", "type_id": "legal-entity", "role": "COUNTERPARTY", "name": "Synthetic SaaS Vendor Inc."},
        ],
        "ownership": [
            {"owner_id": "seller", "owned_id": "target", "type_id": "ownership-interest", "percentage": 100.0, "beneficial": True},
            {"owner_id": "target", "owned_id": "target-sub", "type_id": "ownership-interest", "percentage": 100.0, "beneficial": True},
        ],
        "capitalization": [
            {"entity_id": "target", "type_id": "capitalization-record", "security": "COMMON", "units": 1_000_000, "value": 10_000_000, "currency": "USD"}
        ],
        "transaction": {
            "transaction_id": "transaction-001",
            "type_id": "ma-transaction",
            "structure": "MERGER",
            "buyer_id": "buyer",
            "target_id": "target",
            "seller_ids": ["seller"],
            "timeline": {"signing": "2026-08-01", "closing": "2026-09-15"},
        },
        "contracts": [
            {
                "contract_id": "contract-001",
                "type_id": "material-contract",
                "parties": ["target", "counterparty"],
                "material": True,
                "annual_value": {"amount": amount, "currency": "USD"},
                "clauses": {"change_of_control": {"type_id": "change-of-control-clause", "present": True, "consent_required": True}},
                "amendments": [{"amendment_id": "amendment-001", "type_id": "contract-amendment", "effective_date": "2026-02-01", "order": 1}],
                "orders": [{"order_id": "order-001", "effective_date": "2026-03-01", "value": {"amount": 25_000, "currency": "USD"}}],
            }
        ],
        # Consent is deliberately separate from clause language.
        "consents": [
            {
                "contract_id": "contract-001",
                "type_id": "consent-status",
                "state": "NOT_OBTAINED",
                "notice_state": "NOT_SENT",
                "approval_state": "PENDING",
                "seller_response": "AWAITING_RESPONSE",
                "waived": None,
            }
        ],
        "assets": [{"asset_id": "asset-001", "owner_id": "target", "kind": "SOFTWARE", "value": {"amount": 2_000_000, "currency": "USD"}}],
        "liabilities": [{"liability_id": "liability-001", "entity_id": "target", "kind": "ACCOUNTS_PAYABLE", "value": {"amount": 125_000, "currency": "USD"}}],
        "debts": [{"debt_id": "debt-001", "borrower_id": "target", "principal": {"amount": 500_000, "currency": "USD"}, "maturity": "2027-06-30"}],
        "liens": [{"lien_id": "lien-001", "debt_id": "debt-001", "asset_id": "asset-001", "status": "ACTIVE"}],
        "employees": [{"employee_id": "employee-001", "employer_id": "target", "status": "ACTIVE", "annual_compensation": {"amount": 180_000, "currency": "USD"}}],
        "benefits": [{"plan_id": "benefit-001", "sponsor_id": "target", "kind": "HEALTH", "status": "ACTIVE"}],
        "ip": [{"ip_id": "ip-001", "owner_id": "target", "kind": "SOFTWARE", "registered": False}],
        "data": [{"data_id": "data-001", "controller_id": "target", "classification": "SYNTHETIC", "personal_data": False}],
        "regulatory": [{"record_id": "regulatory-001", "entity_id": "target", "kind": "GOOD_STANDING", "status": "CURRENT"}],
        "litigation": [{"matter_id": "litigation-001", "entity_id": "target", "status": "NONE_DISCLOSED", "material": False}],
        "evidence": [
            {
                "evidence_id": "evidence-clause",
                "type_id": "source-reference",
                "fact_path": "contract.change_control_clause",
                "availability": "AVAILABLE",
                "source_id": "harvey-change-control-contract-fixture",
                "span_id": "span-0001",
                "asserted_value": True,
            },
            {
                "evidence_id": "evidence-consent",
                "type_id": "source-reference",
                "fact_path": "contract.consent_status",
                "availability": "UNPRODUCED",
                "source_id": None,
                "span_id": None,
                "asserted_value": "NOT_OBTAINED",
            },
        ],
        "known_unknowns": [
            {"type_id": "ambiguous-consent", "fact_path": "contract.consent_waived", "reason": "No waiver has been produced", "evidence_status": "UNPRODUCED"}
        ],
        "planted_non_issues": [
            {"non_issue_id": "non-issue-employment", "fact_path": "employees.employee-001.status", "state": "ACTIVE"}
        ],
        "ambiguities": [
            {"ambiguity_id": "ambiguity-waiver", "fact_path": "contract.consent_waived", "intended": True, "resolution": "HUMAN_REVIEW"}
        ],
        "scenario": {"adverse_authority": False, "contradictions": []},
        "completeness": {"closed_world": True, "asserted_collections": list(COLLECTIONS)},
    }
    set_fingerprint(world, "matter_fingerprint")
    return world


def facts_from_world(world: Mapping[str, Any]) -> Dict[str, Any]:
    contract = world["contracts"][0]
    consent = world["consents"][0]
    return {
        "contract": {
            "material": contract["material"],
            "change_control_clause": contract["clauses"]["change_of_control"]["present"],
            "consent_waived": consent["waived"],
            "consent_status": consent["state"],
            "annual_value_usd": contract["annual_value"]["amount"],
        },
        "transaction": {"structure": world["transaction"]["structure"]},
    }


def validate_world(world: Mapping[str, Any]) -> Dict[str, Any]:
    issues = []

    def fail(gate: str, message: str) -> None:
        gates[gate] = False
        issues.append(message)

    gates = {
        "schema_valid": world.get("artifact_type") == "CanonicalMatterGraph" and world.get("schema_version") == 1,
        "required_domain_objects": True,
        "identifiers_unique": True,
        "referential_integrity": True,
        "temporal_integrity": True,
        "financial_integrity": True,
        "evidence_explicit": True,
        "closed_world_complete": True,
        "fingerprint_valid": verify_fingerprint(dict(world), "matter_fingerprint"),
    }
    if not gates["schema_valid"]:
        issues.append("unsupported canonical matter schema")
    if not gates["fingerprint_valid"]:
        issues.append("canonical matter fingerprint is invalid")

    missing = [name for name in COLLECTIONS if not isinstance(world.get(name), list)]
    if missing or set(world.get("completeness", {}).get("asserted_collections", [])) != set(COLLECTIONS):
        fail("closed_world_complete", "closed-world collections are missing or undeclared: %s" % ", ".join(missing))
    if any(not world.get(name) for name in COLLECTIONS):
        fail("required_domain_objects", "every Phase 2 C1 object family needs a concrete POV record")

    id_fields = {
        "entities": "entity_id",
        "contracts": "contract_id",
        "assets": "asset_id",
        "liabilities": "liability_id",
        "debts": "debt_id",
        "liens": "lien_id",
        "employees": "employee_id",
        "benefits": "plan_id",
        "ip": "ip_id",
        "data": "data_id",
        "regulatory": "record_id",
        "litigation": "matter_id",
        "evidence": "evidence_id",
        "planted_non_issues": "non_issue_id",
        "ambiguities": "ambiguity_id",
    }
    for collection, field in id_fields.items():
        identifiers = [item.get(field) for item in world.get(collection, [])]
        if None in identifiers or len(identifiers) != len(set(identifiers)):
            fail("identifiers_unique", "%s must have unique concrete %s values" % (collection, field))

    entities = {item.get("entity_id") for item in world.get("entities", [])}
    transaction = world.get("transaction", {})
    referenced_entities = {
        transaction.get("buyer_id"),
        transaction.get("target_id"),
        *transaction.get("seller_ids", []),
        *(item.get("owner_id") for item in world.get("ownership", [])),
        *(item.get("owned_id") for item in world.get("ownership", [])),
        *(party for contract in world.get("contracts", []) for party in contract.get("parties", [])),
    }
    if None in entities or None in referenced_entities or not referenced_entities <= entities:
        fail("referential_integrity", "entity references must resolve inside the graph")
    entity_reference_fields = {
        "capitalization": "entity_id",
        "assets": "owner_id",
        "liabilities": "entity_id",
        "debts": "borrower_id",
        "employees": "employer_id",
        "benefits": "sponsor_id",
        "ip": "owner_id",
        "data": "controller_id",
        "regulatory": "entity_id",
        "litigation": "entity_id",
    }
    if any(item.get(field) not in entities for collection, field in entity_reference_fields.items() for item in world.get(collection, [])):
        fail("referential_integrity", "domain objects must reference existing entities")

    owned_totals: Dict[str, float] = {}
    for relation in world.get("ownership", []):
        percentage = float(relation.get("percentage", -1))
        owned_totals[relation.get("owned_id")] = owned_totals.get(relation.get("owned_id"), 0.0) + percentage
        if not 0 < percentage <= 100:
            fail("financial_integrity", "ownership percentages must be in (0,100]")
    if any(total > 100 for total in owned_totals.values()):
        fail("financial_integrity", "beneficial ownership cannot exceed 100 percent")

    timeline = transaction.get("timeline", {})
    try:
        if date.fromisoformat(timeline["signing"]) > date.fromisoformat(timeline["closing"]):
            fail("temporal_integrity", "signing cannot follow closing")
        for contract in world.get("contracts", []):
            dates = [date.fromisoformat(item["effective_date"]) for item in contract.get("amendments", []) + contract.get("orders", [])]
            if dates != sorted(dates) or any(item > date.fromisoformat(timeline["closing"]) for item in dates):
                fail("temporal_integrity", "contract amendments/orders must be ordered before closing")
        if any(date.fromisoformat(item["maturity"]) <= date.fromisoformat(world["matter"]["as_of"]) for item in world.get("debts", [])):
            fail("temporal_integrity", "active debt maturity must follow the matter as-of date")
    except (KeyError, TypeError, ValueError):
        fail("temporal_integrity", "timeline dates must be valid ISO dates")

    def money_values() -> Iterable[Mapping[str, Any]]:
        for item in world.get("capitalization", []):
            yield {"amount": item.get("value"), "currency": item.get("currency")}
        for collection, field in (("assets", "value"), ("liabilities", "value"), ("debts", "principal"), ("employees", "annual_compensation")):
            for item in world.get(collection, []):
                yield item.get(field, {})
        for contract in world.get("contracts", []):
            yield contract.get("annual_value", {})
            for order in contract.get("orders", []):
                yield order.get("value", {})

    if any(not isinstance(value.get("amount"), (int, float)) or value.get("amount", -1) < 0 or not isinstance(value.get("currency"), str) or len(value["currency"]) != 3 for value in money_values()):
        fail("financial_integrity", "money must be non-negative and carry a three-letter currency")

    contract_ids = {item.get("contract_id") for item in world.get("contracts", [])}
    if any(item.get("contract_id") not in contract_ids for item in world.get("consents", [])):
        fail("referential_integrity", "consent records must reference a contract")
    asset_ids = {item.get("asset_id") for item in world.get("assets", [])}
    debt_ids = {item.get("debt_id") for item in world.get("debts", [])}
    if any(item.get("asset_id") not in asset_ids or item.get("debt_id") not in debt_ids for item in world.get("liens", [])):
        fail("referential_integrity", "liens must reference existing assets and debts")

    try:
        facts = facts_from_world(world)
    except (IndexError, KeyError, TypeError):
        fail("schema_valid", "one contract and its separate consent record are required")
        facts = {"contract": {}, "transaction": {}}
    fact_paths = {"contract.%s" % key for key in facts["contract"]} | {"transaction.%s" % key for key in facts["transaction"]}
    evidence_paths = {item.get("fact_path") for item in world.get("evidence", [])}
    unknown_paths = {item.get("fact_path") for item in world.get("known_unknowns", [])}
    if any(item.get("availability") not in EVIDENCE_STATES for item in world.get("evidence", [])) or not {"contract.change_control_clause", "contract.consent_status"} <= evidence_paths or not unknown_paths <= fact_paths:
        fail("evidence_explicit", "material facts need explicit evidence or known-unknown state")

    return {"ok": all(gates.values()), "gates": gates, "issues": issues}
