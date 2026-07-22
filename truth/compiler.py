"""Compile B1–B4 into a Phase 1 exit artifact bound to Phase 0."""

from __future__ import annotations

import copy
from datetime import date, datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Set

from utils.artifacts import fingerprint, set_fingerprint, verify_fingerprint
from utils.errors import TruthError
from utils.pov import HARVEY_COMMIT, HARVEY_POV_TASK, POV_WORKFLOW, POV_WORKSTREAM

from .authority import AuthorityGraph, InMemoryCitator, classification_metrics
from .common import iso_date, iso_datetime, require
from .ontology import OntologyRegistry
from .rules import RuleCompiler, ar_001_effort_experiment, counterfactual_check, held_out_coverage
from .sources import AuthoritySnapshotBuilder


def _phase0_integrity(phase0: Mapping[str, Any]) -> bool:
    return verify_fingerprint(dict(phase0))


def _authorized_rule_owners(authority: Mapping[str, Any], as_of: date) -> Set[str]:
    owners = set()
    for actor in authority.get("actors", []):
        roles = set(actor.get("roles", []))
        if not roles & {"legal-owner", "lawyer-of-record", "customer-owner"}:
            continue
        credentials = actor.get("credentials", [])
        credential_active = any(
            item.get("status") == "ACTIVE" and iso_datetime(item.get("valid_until"), "credential.valid_until").date() >= as_of
            for item in credentials
        )
        delegations = actor.get("delegations", [])
        delegated = any(
            iso_datetime(item.get("valid_from"), "delegation.valid_from").date() <= as_of <= iso_datetime(item.get("valid_until"), "delegation.valid_until").date()
            and "release-work-product" in item.get("action_types", [])
            for item in delegations
        )
        if credential_active and delegated:
            owners.add(actor["actor_id"])
    return owners


class Phase1Compiler:
    def __init__(self, generated_at: Optional[datetime] = None):
        self.generated_at = generated_at or datetime.now(timezone.utc)
        if self.generated_at.tzinfo is None:
            raise ValueError("generated_at must be timezone-aware")

    def _validate_phase0(self, phase0: Mapping[str, Any], authority_contract: Mapping[str, Any], fixture: bool) -> List[str]:
        issues = []
        if not _phase0_integrity(phase0):
            issues.append("Phase 0 artifact fingerprint is invalid")
        expected_status = "TEST_READY" if fixture else "READY"
        if phase0.get("status") != expected_status:
            issues.append("Phase 0 status must be %s" % expected_status)
        if fixture and phase0.get("simulation", {}).get("production_downstream_unblocked") is not False:
            issues.append("POV Phase 0 artifact must keep production blocked")
        expected_authority = phase0.get("simulation", {}).get("source_fixture_fingerprints", {}).get("authority_signoff_matrix") if fixture else phase0.get("contract_fingerprints", {}).get("authority_signoff_matrix")
        if expected_authority and fingerprint(authority_contract) != expected_authority:
            issues.append("authority contract does not match the Phase 0 binding")
        scope = phase0.get("scope", {})
        if fixture:
            if scope.get("workflow") != POV_WORKFLOW:
                issues.append("POV workflow must remain %s" % POV_WORKFLOW)
            compiled = phase0.get("compiled_scope", {})
            source = compiled.get("pov_source", {}) if isinstance(compiled, dict) else {}
            included_tasks = source.get("included_task_paths", [])
            if source.get("revision") != HARVEY_COMMIT or included_tasks != [HARVEY_POV_TASK]:
                issues.append("POV source must remain pinned to the approved Harvey task and revision")
        return issues

    def evaluate(self, phase0: Mapping[str, Any], authority_contract: Mapping[str, Any], bundle: Mapping[str, Any]) -> Dict[str, Any]:
        declared_fixture = bool(bundle.get("test_fixture"))
        nested_fixture = (
            any(bool(item.get("test_fixture")) for item in bundle.get("sources", []))
            or bool(bundle.get("ontology", {}).get("test_fixture"))
            or bool(bundle.get("rule_pack", {}).get("test_fixture"))
            or any(bool(item.get("test_fixture")) for item in bundle.get("rule_pack", {}).get("rules", []))
        )
        fixture = declared_fixture or nested_fixture
        issues = self._validate_phase0(phase0, authority_contract, fixture)
        if nested_fixture and not declared_fixture:
            issues.append("nested test fixtures cannot be promoted by clearing bundle.test_fixture")
        as_of = iso_date(bundle.get("as_of"), "bundle.as_of")
        scope = bundle.get("scope", {})
        if fixture:
            expected = {
                "workflow": POV_WORKFLOW,
                "workstream": POV_WORKSTREAM,
                "task": HARVEY_POV_TASK,
                "source_revision": HARVEY_COMMIT,
            }
            for key, value in expected.items():
                if scope.get(key) != value:
                    issues.append("POV scope.%s must equal %s" % (key, value))
        phase0_binding = str(phase0.get("artifact_fingerprint") or "INVALID")
        snapshot = AuthoritySnapshotBuilder().build(
            bundle.get("sources", []),
            as_of,
            bundle.get("coverage_register", []),
            bundle.get("parse_metrics", {}),
            int(bundle.get("freshness_sla_days", 0)),
            phase0_binding,
        )
        citator_config = bundle.get("citator", {})
        graph = AuthorityGraph(
            snapshot,
            bundle.get("hierarchy", {}),
            bundle.get("treatments", []),
            bundle.get("propositions", []),
            citator=InMemoryCitator(citator_config.get("statuses", {}), covered=bool(citator_config.get("covered"))),
        )
        gold_rows = []
        for row in bundle.get("authority_gold_set", []):
            decision = graph.classify(row["proposition_id"], row["target_jurisdiction"], as_of)
            gold_rows.append(
                {
                    "case_id": row["case_id"],
                    "expected_supported": bool(row.get("expected_supported")),
                    "predicted_supported": decision.supported,
                    "expected_adverse": bool(row.get("expected_adverse")),
                    "predicted_adverse": bool(decision.adverse),
                    "decision": decision.to_dict(),
                }
            )
        authority_quality = classification_metrics(gold_rows)
        thresholds = bundle.get("authority_quality_thresholds", {})
        authority_quality["thresholds"] = copy.deepcopy(dict(thresholds))
        authority_quality["passed"] = (
            authority_quality["precision"] >= float(thresholds.get("precision", 1))
            and authority_quality["recall"] >= float(thresholds.get("recall", 1))
            and authority_quality["false_accept_rate"] <= float(thresholds.get("maximum_false_accept_rate", 0))
            and authority_quality["adverse_retrieval_recall"] >= float(thresholds.get("adverse_retrieval_recall", 1))
        )
        ontology = OntologyRegistry(bundle.get("ontology", {}))
        owners = _authorized_rule_owners(authority_contract, as_of)
        if not owners:
            issues.append("no currently authorized rule owner is available")
        rule_pack = RuleCompiler(graph, ontology, owners).compile(bundle.get("rule_pack", {}))
        held_out = held_out_coverage(rule_pack, bundle.get("held_out_cases", []))
        held_out["minimum"] = float(bundle.get("minimum_held_out_coverage", 1.0))
        held_out["passed"] = held_out["coverage"] >= held_out["minimum"]
        counterfactuals = []
        for item in bundle.get("counterfactuals", []):
            result = counterfactual_check(
                rule_pack,
                item["issue_family"],
                item["baseline"],
                item["counterfactual"],
                item["changed_fact_paths"],
                iso_date(item["as_of"], "counterfactual.as_of"),
            )
            result["counterfactual_id"] = item["counterfactual_id"]
            counterfactuals.append(result)
        ar_config = bundle.get("ar_001", {})
        ar_001 = ar_001_effort_experiment(
            str(ar_config.get("issue_family")),
            ar_config.get("observations", []),
            float(ar_config.get("maximum_exponent", 0.9)),
        )
        gates = {
            "phase0_bound": not self._validate_phase0(phase0, authority_contract, fixture),
            "b1_authority_snapshot": snapshot["ready"],
            "b2_proposition_quality": authority_quality["passed"],
            "b3_typed_ontology": all(ontology.artifact()["gates"].values()),
            "b4_rule_pack": all(rule_pack.artifact["gates"].values()),
            "held_out_coverage": held_out["passed"],
            "counterfactual_isolation": bool(counterfactuals) and all(item["passed"] for item in counterfactuals),
            "ar_001_sublinear_effort": ar_001["passed"],
        }
        if issues:
            gates["phase0_bound"] = False
        ready = all(gates.values())
        status = ("TEST_READY" if fixture else "READY") if ready else ("TEST_BLOCKED" if fixture else "BLOCKED")
        artifact = {
            "artifact_type": "Phase1ExitArtifact",
            "schema_version": 1,
            "status": status,
            "production_eligible": ready and not fixture,
            "generated_at": self.generated_at.astimezone(timezone.utc).isoformat(),
            "as_of": as_of.isoformat(),
            "phase0_artifact_fingerprint": phase0_binding,
            "bundle_id": bundle.get("bundle_id"),
            "bundle_version": bundle.get("version"),
            "scope": copy.deepcopy(dict(scope)),
            "authority_snapshot": snapshot,
            "authority_graph": graph.artifact(),
            "authority_quality": authority_quality,
            "ontology": ontology.artifact(),
            "rule_pack": rule_pack.artifact,
            "held_out_coverage": held_out,
            "counterfactuals": counterfactuals,
            "ar_001": ar_001,
            "gates": gates,
            "issues": issues,
            "pov_boundary": {
                "test_fixture": fixture,
                "pov_downstream_unblocked": status == "TEST_READY",
                "production_downstream_unblocked": status == "READY",
                "no_real_client_or_legal_claim": fixture,
            },
        }
        set_fingerprint(artifact)
        return artifact

    def compile(self, phase0: Mapping[str, Any], authority_contract: Mapping[str, Any], bundle: Mapping[str, Any]) -> Dict[str, Any]:
        artifact = self.evaluate(phase0, authority_contract, bundle)
        if artifact["status"] not in {"READY", "TEST_READY"}:
            failures = [name for name, passed in artifact["gates"].items() if not passed]
            raise TruthError("Phase 1 exit is blocked: %s%s" % (", ".join(failures), "; " + "; ".join(artifact["issues"]) if artifact["issues"] else ""))
        return artifact
