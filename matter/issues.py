"""C2: causal issue scenarios and expected-delta inputs."""

from __future__ import annotations

import copy
from datetime import date
from graphlib import CycleError, TopologicalSorter
from itertools import combinations
from typing import Any, Dict, List, Mapping

from truth.rules import RulePack
from utils.artifacts import set_fingerprint
from utils.errors import MatterError

from .state import facts_from_world, validate_world


ISSUE_FAMILY = "change-of-control-consent"
ISSUE_TEMPLATE = {
    "template_id": "change-of-control-consent-v1",
    "issue_family": ISSUE_FAMILY,
    "workflow": "counterparty-paper-review",
    "workstream": "contracts-consents",
    "causal_variables": ["contract.change_control_clause"],
    "dependency_dag": {
        "nodes": [
            "contract.change_control_clause",
            "contract.consent_status",
            "rule.application",
            "issue.status",
            "issue.severity",
            "issue.recommendation",
        ],
        "edges": [
            ["contract.change_control_clause", "rule.application"],
            ["contract.consent_status", "rule.application"],
            ["rule.application", "issue.status"],
            ["issue.status", "issue.severity"],
            ["rule.application", "issue.recommendation"],
        ],
    },
}


def dag_is_acyclic(dag: Mapping[str, Any]) -> bool:
    nodes = set(dag.get("nodes", []))
    dependencies = {node: set() for node in nodes}
    for left, right in dag.get("edges", []):
        if left not in nodes or right not in nodes:
            return False
        dependencies[right].add(left)
    try:
        tuple(TopologicalSorter(dependencies).static_order())
        return True
    except CycleError:
        return False


def _set_mutation(world: Dict[str, Any], path: str, value: Any) -> None:
    if path == "contract.change_control_clause":
        world["contracts"][0]["clauses"]["change_of_control"]["present"] = value
        world["evidence"][0]["asserted_value"] = value
    elif path == "contract.consent_status":
        world["consents"][0]["state"] = value
        world["consents"][0]["seller_response"] = "CONSENT_PRODUCED" if value == "OBTAINED" else "AWAITING_RESPONSE"
        world["evidence"][1]["asserted_value"] = value
    elif path == "contract.annual_value_usd":
        world["contracts"][0]["annual_value"]["amount"] = value
    elif path == "authority.adverse":
        world["scenario"]["adverse_authority"] = bool(value)
    elif path == "evidence.contradiction":
        world["scenario"]["contradictions"] = [
            {
                "fact_path": "contract.consent_status",
                "canonical_value": world["consents"][0]["state"],
                "asserted_value": "OBTAINED",
                "source": "counterparty-response",
            }
        ] if value else []
    elif path == "evidence.consent_availability":
        world["evidence"][1]["availability"] = value
    else:
        raise MatterError("unsupported causal mutation %s" % path)


def _mutate_world(world: Mapping[str, Any], changes: Mapping[str, Any]) -> Dict[str, Any]:
    result = copy.deepcopy(dict(world))
    for path, value in changes.items():
        _set_mutation(result, path, value)
    set_fingerprint(result, "matter_fingerprint")
    report = validate_world(result)
    if not report["ok"]:
        raise MatterError("invalid mutation: %s" % "; ".join(report["issues"]))
    return result


def build_scenarios(world: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Cover positive, negative, boundary, missing, contradiction, and procedural states."""

    specifications = [
        {"id": "negative-no-clause", "kind": "NEGATIVE", "changes": {"contract.change_control_clause": False}},
        {"id": "borderline-value", "kind": "BORDERLINE", "changes": {"contract.annual_value_usd": 100_000}},
        {"id": "consent-obtained", "kind": "PROCEDURAL", "changes": {"contract.consent_status": "OBTAINED"}},
        {"id": "missing-consent-evidence", "kind": "MISSING_EVIDENCE", "changes": {"evidence.consent_availability": "MISSING"}},
        {"id": "contradictory-response", "kind": "CONTRADICTION", "changes": {"evidence.contradiction": True}},
        {"id": "adverse-authority", "kind": "ADVERSE_AUTHORITY", "changes": {"authority.adverse": True}},
    ]
    scenarios = [{"example_id": "positive", "kind": "POSITIVE", "changed_fact_paths": [], "world": copy.deepcopy(dict(world))}]
    for item in specifications:
        scenarios.append(
            {
                "example_id": item["id"],
                "kind": item["kind"],
                "changed_fact_paths": sorted(item["changes"]),
                "world": _mutate_world(world, item["changes"]),
            }
        )
    # A bounded pairwise sample proves composition without Cartesian explosion.
    for strength in (2, 3):
        for group in combinations(specifications[:3], strength):
            changes = {path: value for item in group for path, value in item["changes"].items()}
            scenarios.append(
                {
                    "example_id": "+".join(item["id"] for item in group),
                    "kind": "%d_WISE" % strength,
                    "changed_fact_paths": sorted(changes),
                    "world": _mutate_world(world, changes),
                }
            )
    return scenarios


def analyze_issue(world: Mapping[str, Any], rule_pack: RulePack, as_of: date) -> Dict[str, Any]:
    scope = world.get("scope", {})
    applicable = scope.get("workflow") == ISSUE_TEMPLATE["workflow"] and scope.get("workstream") == ISSUE_TEMPLATE["workstream"]
    if not applicable:
        raise MatterError("issue template is outside the canonical matter scope")
    facts = facts_from_world(world)
    outcome = rule_pack.evaluate(ISSUE_FAMILY, facts, as_of)
    matched = outcome.status == "MATCHED"
    evidence = [item for item in world["evidence"] if item["fact_path"] in set(outcome.dependent_facts)]
    if matched and not evidence:
        raise MatterError("matched issue has no mounted evidence state")
    result: Dict[str, Any] = {
        "artifact_type": "IssueAndMutationPlan",
        "schema_version": 1,
        "template_id": ISSUE_TEMPLATE["template_id"],
        "issue_family": ISSUE_FAMILY,
        "matter_fingerprint": world["matter_fingerprint"],
        "facts": facts,
        "rule_outcome": outcome.to_dict(),
        "issue": {
            "status": "OPEN" if matched else "NON_ISSUE",
            "severity": ("HIGH" if facts["contract"]["annual_value_usd"] >= 100_000 else "MEDIUM") if matched else "NONE",
            "recommendation": outcome.actions[0]["recommendation"] if outcome.actions else "ABSTAIN",
            "consequence": outcome.actions[0]["kind"] if outcome.actions else "NONE",
        },
        "procedural_state": copy.deepcopy(world["consents"][0]),
        "evidence_state": copy.deepcopy(evidence),
        "contradictions": copy.deepcopy(world["scenario"]["contradictions"]),
        "adverse_authority_injected": bool(world["scenario"]["adverse_authority"]),
    }
    set_fingerprint(result, "issue_plan_fingerprint")
    return result
