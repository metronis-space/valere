"""Compile D3 atomic criteria from canonical state and rules."""

from __future__ import annotations

import copy
from typing import Any, Dict, Mapping

from utils.artifacts import set_fingerprint


def compile_criteria(world: Mapping[str, Any], issue_plan: Mapping[str, Any], rule_pack: Mapping[str, Any]) -> Dict[str, Any]:
    outcome = issue_plan["rule_outcome"]
    issue = issue_plan["issue"]
    facts = issue_plan["facts"]["contract"]
    evidence = outcome.get("evidence", [])
    rule_ids = outcome.get("matched_rule_ids", [])

    def criterion(
        criterion_id: str,
        kind: str,
        expected: Any,
        truth_source: str,
        verification_mode: str,
        depends_on: list,
        path: str,
    ) -> Dict[str, Any]:
        provenance = [
            {"artifact": "CanonicalMatterGraph", "fingerprint": world["matter_fingerprint"], "path": path},
            {"artifact": "IssueAndMutationPlan", "fingerprint": issue_plan["issue_plan_fingerprint"], "path": path},
        ]
        if truth_source in {"RULE_PACK", "AUTHORITY_SPAN"}:
            provenance.append(
                {
                    "artifact": "RulePack",
                    "fingerprint": rule_pack["rule_pack_fingerprint"],
                    "rule_ids": list(rule_ids),
                    "source_refs": copy.deepcopy(evidence),
                }
            )
        return {
            "criterion_id": criterion_id,
            "kind": kind,
            "assertion": {"operator": "EQUALS", "expected": expected},
            "truth_source": truth_source,
            "verification_mode": verification_mode,
            "depends_on": list(depends_on),
            "provenance": provenance,
        }

    criteria = [
        criterion("issue-identification", "ISSUE_IDENTIFICATION", issue["status"] == "OPEN", "ISSUE_PLAN", "EXACT", ["rule.application"], "issue.status"),
        criterion("exact-span", "EXACT_SPAN", evidence[0]["span_id"] if evidence else "NONE", "AUTHORITY_SPAN" if evidence else "RULE_PACK", "EXACT", ["rule.application"], "rule_outcome.evidence"),
        criterion("operative-clause", "OPERATIVE_FACT", facts["change_control_clause"], "CANONICAL_STATE", "EXACT", ["contract.change_control_clause"], "contracts.contract-001.clauses.change_of_control.present"),
        criterion("operative-consent", "OPERATIVE_FACT", facts["consent_status"], "CANONICAL_STATE", "EXACT", ["contract.consent_status"], "consents.contract-001.state"),
        criterion("rule-application", "TRIGGER_APPLICATION", outcome["status"], "RULE_PACK", "EXACT", outcome["dependent_facts"], "rule_outcome.status"),
        criterion("consequence", "CONSEQUENCE", issue["consequence"], "RULE_PACK", "EXACT", ["rule.application"], "issue.consequence"),
        criterion("annual-value-calculation", "CALCULATION", facts["annual_value_usd"], "CANONICAL_STATE", "NUMERIC_EXACT", ["contract.annual_value_usd"], "contracts.contract-001.annual_value.amount"),
        criterion("severity", "SEVERITY", issue["severity"], "ISSUE_PLAN", "EXACT", ["issue.status", "contract.annual_value_usd"], "issue.severity"),
        criterion("recommendation", "RECOMMENDATION", issue["recommendation"], "RULE_PACK", "EXACT", ["rule.application"], "issue.recommendation"),
    ]
    bundle: Dict[str, Any] = {
        "artifact_type": "CriterionBundle",
        "schema_version": 1,
        "issue_family": issue_plan["issue_family"],
        "matter_fingerprint": world["matter_fingerprint"],
        "issue_plan_fingerprint": issue_plan["issue_plan_fingerprint"],
        "criteria": criteria,
        "documents_used": False,
    }
    bundle["validation"] = validate_criteria(bundle)
    set_fingerprint(bundle, "criterion_bundle_fingerprint")
    return bundle


def validate_criteria(bundle: Mapping[str, Any]) -> Dict[str, Any]:
    criteria = bundle.get("criteria", [])
    ids = [item.get("criterion_id") for item in criteria]
    semantic_keys = [
        (item.get("kind"), tuple(item.get("depends_on", [])), item.get("assertion", {}).get("operator"))
        for item in criteria
    ]
    atomic = all(
        set(item.get("assertion", {})) == {"operator", "expected"}
        and item["assertion"].get("operator") in {"EQUALS"}
        for item in criteria
    )
    satisfiable = all(item.get("assertion", {}).get("expected") is not None for item in criteria)
    provenance = all(item.get("provenance") and all(entry.get("artifact") and entry.get("fingerprint") for entry in item["provenance"]) for item in criteria)
    sources_assigned = all(item.get("truth_source") in {"CANONICAL_STATE", "ISSUE_PLAN", "RULE_PACK", "AUTHORITY_SPAN"} for item in criteria)
    modes_assigned = all(item.get("verification_mode") in {"EXACT", "NUMERIC_EXACT"} for item in criteria)
    gates = {
        "non_empty": bool(criteria),
        "unique_ids": len(ids) == len(set(ids)),
        "deduplicated": len(semantic_keys) == len(set(semantic_keys)),
        "atomic": atomic,
        "satisfiable": satisfiable,
        "provenance_complete": provenance,
        "truth_sources_assigned": sources_assigned,
        "verification_modes_assigned": modes_assigned,
        "no_documents": bundle.get("documents_used") is False,
    }
    return {
        "ok": all(gates.values()),
        "gates": gates,
        "provenance_coverage": sum(bool(item.get("provenance")) for item in criteria) / len(criteria) if criteria else 0.0,
    }
