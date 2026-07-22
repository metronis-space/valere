"""Bind C1/C2 and the D3 harness into the Phase 2 exit artifact."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Dict, Mapping, Optional

from tasks.compiler import compile_criteria
from truth.rules import RulePack
from utils.artifacts import set_fingerprint, verify_fingerprint
from utils.errors import MatterError

from ..issues import ISSUE_TEMPLATE, analyze_issue, build_scenarios, dag_is_acyclic
from ..state import build_world, validate_world
from .document_world import compile_phase3


EXPECTED_CHANGED = {
    "consequence",
    "exact-span",
    "issue-identification",
    "operative-clause",
    "recommendation",
    "rule-application",
    "severity",
}
EXPECTED_INVARIANT = {"annual-value-calculation", "operative-consent"}


def _criterion_values(bundle: Mapping[str, Any]) -> Dict[str, Any]:
    return {item["criterion_id"]: item["assertion"]["expected"] for item in bundle["criteria"]}


def _walk(value: Any):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from _walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)


def _require_phase1(phase1: Mapping[str, Any]) -> bool:
    if phase1.get("artifact_type") != "Phase1ExitArtifact" or phase1.get("schema_version") != 1:
        raise MatterError("Phase 1 input has an unsupported artifact schema")
    if not verify_fingerprint(dict(phase1)):
        raise MatterError("Phase 1 artifact fingerprint is invalid")
    fixture = bool(phase1.get("pov_boundary", {}).get("test_fixture"))
    expected = "TEST_READY" if fixture else "READY"
    gates = phase1.get("gates", {})
    if phase1.get("status") != expected or not gates or not all(gates.values()):
        raise MatterError("Phase 1 must be %s with every gate passing" % expected)
    if phase1.get("production_eligible") is not (not fixture):
        raise MatterError("Phase 1 production eligibility does not match its fixture boundary")
    try:
        date.fromisoformat(str(phase1["as_of"]))
        if not isinstance(phase1["scope"], dict) or not isinstance(phase1["authority_snapshot"]["documents"], list):
            raise TypeError
    except (KeyError, TypeError, ValueError) as exc:
        raise MatterError("Phase 1 input is missing scope, cutoff, or authority documents") from exc
    if bool(phase1.get("rule_pack", {}).get("test_fixture")) != fixture:
        raise MatterError("Phase 1 rule-pack fixture boundary does not match its exit artifact")
    if not verify_fingerprint(dict(phase1.get("rule_pack", {})), "rule_pack_fingerprint"):
        raise MatterError("Phase 1 rule pack fingerprint is invalid")
    return fixture


def compile_phase2(
    phase1: Mapping[str, Any], seed: int = 20260722, generated_at: Optional[datetime] = None
) -> Dict[str, Any]:
    generated_at = generated_at or datetime.now(timezone.utc)
    if generated_at.tzinfo is None:
        raise ValueError("generated_at must be timezone-aware")
    fixture = _require_phase1(phase1)
    world = build_world(phase1, seed)
    world_validation = validate_world(world)
    rule_pack = RulePack(phase1["rule_pack"])
    examples = []
    for scenario in build_scenarios(world):
        plan = analyze_issue(scenario["world"], rule_pack, date.fromisoformat(str(phase1["as_of"])))
        examples.append(
            {
                "example_id": scenario["example_id"],
                "kind": scenario["kind"],
                "changed_fact_paths": scenario["changed_fact_paths"],
                "matter_fingerprint": scenario["world"]["matter_fingerprint"],
                "issue_plan": plan,
                "criterion_bundle": compile_criteria(scenario["world"], plan, phase1["rule_pack"]),
            }
        )

    by_id = {item["example_id"]: item for item in examples}
    baseline = _criterion_values(by_id["positive"]["criterion_bundle"])
    counterfactual = _criterion_values(by_id["negative-no-clause"]["criterion_bundle"])
    changed = {key for key in baseline if baseline[key] != counterfactual[key]}
    invariant = set(baseline) - changed
    delta = {
        "counterfactual_id": "negative-no-clause",
        "changed_fact_paths": ["contract.change_control_clause"],
        "expected_changed_criterion_ids": sorted(EXPECTED_CHANGED),
        "actual_changed_criterion_ids": sorted(changed),
        "expected_invariant_criterion_ids": sorted(EXPECTED_INVARIANT),
        "actual_invariant_criterion_ids": sorted(invariant),
        "passed": changed == EXPECTED_CHANGED and invariant == EXPECTED_INVARIANT,
    }

    world_dicts = list(_walk(world))
    kinds = {item["kind"] for item in examples}
    criterion_validations = [item["criterion_bundle"]["validation"] for item in examples]
    criterion_kinds = {item["kind"] for item in by_id["positive"]["criterion_bundle"]["criteria"]}
    ontology_type_ids = {item["type_id"] for item in phase1["ontology"]["types"]}
    source_spans = {
        (document["source_id"], span["span_id"])
        for document in phase1["authority_snapshot"]["documents"]
        for span in document["spans"]
    }
    gates = {
        "c1_schema_and_invariants": world_validation["ok"],
        "c1_exact_seed_replay": build_world(phase1, seed)["matter_fingerprint"] == world["matter_fingerprint"],
        "c1_evidence_resolves": all(
            item["availability"] != "AVAILABLE" or (item.get("source_id"), item.get("span_id")) in source_spans
            for item in world["evidence"]
        ),
        "c1_ontology_bound": {item["type_id"] for item in world_dicts if "type_id" in item} <= ontology_type_ids,
        "c1_truth_not_precompiled": not any(
            {"criteria", "issue", "rule_outcome", "expected"} & item.keys() for item in world_dicts
        ),
        "c2_template_applicable": world["scope"].get("workflow") == ISSUE_TEMPLATE["workflow"]
        and world["scope"].get("workstream") == ISSUE_TEMPLATE["workstream"],
        "c2_dependency_dag_acyclic": dag_is_acyclic(ISSUE_TEMPLATE["dependency_dag"]),
        "c2_separate_procedural_state": "consents" in world
        and "consent_status" not in world["contracts"][0]["clauses"]["change_of_control"],
        "c2_variants_complete": {
            "POSITIVE",
            "NEGATIVE",
            "BORDERLINE",
            "PROCEDURAL",
            "MISSING_EVIDENCE",
            "CONTRADICTION",
            "ADVERSE_AUTHORITY",
            "2_WISE",
            "3_WISE",
        }
        <= kinds,
        "c2_injections_are_explicit": bool(by_id["contradictory-response"]["issue_plan"]["contradictions"])
        and any(
            item["availability"] == "MISSING"
            for item in by_id["missing-consent-evidence"]["issue_plan"]["evidence_state"]
        )
        and by_id["borderline-value"]["issue_plan"]["facts"]["contract"]["annual_value_usd"] == 100_000,
        "c2_adverse_contract_invariance": _criterion_values(
            by_id["adverse-authority"]["criterion_bundle"]
        )
        == baseline,
        "c2_nonissues_and_ambiguities": bool(world["planted_non_issues"]) and bool(world["ambiguities"]),
        "c2_causal_counterfactual": by_id["positive"]["issue_plan"]["rule_outcome"]["status"] == "MATCHED"
        and by_id["negative-no-clause"]["issue_plan"]["rule_outcome"]["status"] == "NO_RULE",
        "c2_expected_delta": delta["passed"],
        "d3_grammar_complete": {
            "ISSUE_IDENTIFICATION",
            "EXACT_SPAN",
            "OPERATIVE_FACT",
            "TRIGGER_APPLICATION",
            "CONSEQUENCE",
            "CALCULATION",
            "SEVERITY",
            "RECOMMENDATION",
        }
        <= criterion_kinds,
        "d3_atomic_satisfiable": all(
            item["gates"]["atomic"]
            and item["gates"]["satisfiable"]
            and item["gates"]["deduplicated"]
            and item["gates"]["truth_sources_assigned"]
            and item["gates"]["verification_modes_assigned"]
            for item in criterion_validations
        ),
        "d3_provenance_complete": all(item["provenance_coverage"] == 1.0 for item in criterion_validations),
        "d3_examples_complete": {"POSITIVE", "NEGATIVE", "BORDERLINE"} <= kinds,
        "d3_no_documents": all(item["gates"]["no_documents"] for item in criterion_validations),
    }
    if not all(gates.values()):
        raise MatterError("Phase 2 exit is blocked: %s" % ", ".join(name for name, passed in gates.items() if not passed))

    status = "TEST_READY" if fixture else "READY"
    artifact: Dict[str, Any] = {
        "artifact_type": "Phase2ExitArtifact",
        "schema_version": 1,
        "status": status,
        "production_eligible": not fixture,
        "generated_at": generated_at.astimezone(timezone.utc).isoformat(),
        "phase1_artifact_fingerprint": phase1["artifact_fingerprint"],
        "seed": seed,
        "canonical_matter": world,
        "issue_template": ISSUE_TEMPLATE,
        "examples": examples,
        "expected_delta": delta,
        "gates": gates,
        "issues": list(world_validation["issues"]),
        "pov_boundary": {
            "test_fixture": fixture,
            "pov_downstream_unblocked": fixture,
            "production_downstream_unblocked": not fixture,
            "documents_rendered": False,
        },
    }
    set_fingerprint(artifact)
    return artifact
