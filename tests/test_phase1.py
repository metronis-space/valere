from __future__ import annotations

import copy
import json
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

from scope.compiler import Phase0Compiler
from scope.demo import build_demo_bundle as build_phase0_demo_bundle
from truth.authority import AuthorityGraph, InMemoryCitator, classification_metrics
from truth.compiler import Phase1Compiler
from truth.demo import DEMO_AS_OF, build_demo_bundle
from truth.errors import TruthError
from truth.ontology import OntologyRegistry, registry_impact
from truth.rules import (
    RuleCompiler,
    ar_001_effort_experiment,
    counterfactual_check,
    evaluate_expression,
    expression_satisfiable,
    held_out_coverage,
    rule_version_diff,
)
from truth.sources import AuthoritySnapshotBuilder, SnapshotStore, normalize_source


NOW = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)


class Phase1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        contracts = build_phase0_demo_bundle()
        cls.authority_contract = contracts["authority"]
        cls.phase0 = Phase0Compiler(today=NOW.date(), now=NOW).simulate(
            contracts["manifest"],
            contracts["rights"],
            contracts["governance"],
            contracts["authority"],
        )

    def setUp(self):
        self.bundle = build_demo_bundle()

    def snapshot(self, bundle=None):
        value = bundle or self.bundle
        return AuthoritySnapshotBuilder().build(
            value["sources"],
            date.fromisoformat(value["as_of"]),
            value["coverage_register"],
            value["parse_metrics"],
            value["freshness_sla_days"],
            self.phase0["artifact_fingerprint"],
        )

    def graph(self, bundle=None):
        value = bundle or self.bundle
        return AuthorityGraph(
            self.snapshot(value),
            value["hierarchy"],
            value["treatments"],
            value["propositions"],
            InMemoryCitator(value["citator"]["statuses"], value["citator"]["covered"]),
        )

    def rule_pack(self, bundle=None, owners=None):
        value = bundle or self.bundle
        return RuleCompiler(
            self.graph(value),
            OntologyRegistry(value["ontology"]),
            owners or {"synthetic-legal"},
        ).compile(value["rule_pack"])

    def test_b1_normalizes_html_citations_dockets_and_sections(self):
        source = copy.deepcopy(self.bundle["sources"][0])
        source.update(
            {
                "media_type": "text/html",
                "content": "<h1>Section 1</h1><p>Consent &amp; notice.</p><script>ignore()</script><p>Second paragraph.</p>",
                "citation": "  Del.   Code tit. 8,§251 ",
                "docket": " c.a.  123 ",
            }
        )
        normalized = normalize_source(source)
        self.assertEqual(normalized["citation"], "Del. Code tit. 8, § 251")
        self.assertEqual(normalized["docket"], "C.A.-123")
        self.assertNotIn("ignore", normalized["content"])
        self.assertGreaterEqual(len(normalized["spans"]), 2)
        self.assertTrue(normalized["content_fingerprint"].startswith("sha256:"))

    def test_b1_binary_source_requires_explicit_ocr_adapter(self):
        source = copy.deepcopy(self.bundle["sources"][0])
        source.pop("content")
        source["payload"] = b"%PDF-test"
        source["media_type"] = "application/pdf"
        with self.assertRaisesRegex(TruthError, "requires an OCR"):
            normalize_source(source)

    def test_b1_snapshot_is_hashed_replayable_and_append_only(self):
        snapshot = self.snapshot()
        self.assertTrue(snapshot["ready"])
        self.assertTrue(snapshot["reproducible"])
        with tempfile.TemporaryDirectory() as temporary:
            store = SnapshotStore(temporary)
            path = store.append(snapshot)
            self.assertTrue(path.exists())
            replayed = store.replay([snapshot], date(2026, 7, 23))
            self.assertEqual(replayed["snapshot_id"], snapshot["snapshot_id"])
            with self.assertRaisesRegex(TruthError, "cannot be overwritten"):
                store.append(snapshot)

    def test_b1_fails_freshness_and_implicit_coverage(self):
        stale = copy.deepcopy(self.bundle)
        stale["sources"][0]["acquired_at"] = "2020-01-01T00:00:00+00:00"
        snapshot = self.snapshot(stale)
        self.assertFalse(snapshot["ready"])
        broken = copy.deepcopy(self.bundle)
        broken["coverage_register"][2].pop("reason")
        with self.assertRaisesRegex(TruthError, "explicit reason"):
            self.snapshot(broken)

    def test_b2_requires_exact_proposition_span(self):
        broken = copy.deepcopy(self.bundle)
        broken["propositions"][0]["support"][0]["span_id"] = "missing"
        with self.assertRaisesRegex(TruthError, "unknown source span"):
            self.graph(broken)

    def test_b2_support_is_not_inferred_from_citation_existence(self):
        graph = self.graph()
        supported = graph.classify("prop-contract-consent-trigger", "Delaware", date.fromisoformat(DEMO_AS_OF))
        missing = graph.classify("real-looking-but-unlinked-citation", "Delaware", date.fromisoformat(DEMO_AS_OF))
        self.assertTrue(supported.supported)
        self.assertFalse(missing.supported)
        self.assertEqual(missing.status, "NO_RULE")

    def test_b2_classifies_controlling_law_and_blocks_negative_history(self):
        bundle = copy.deepcopy(self.bundle)
        statute = bundle["sources"][0]
        statute.update({"source_type": "OFFICIAL", "authority_kind": "STATUTE", "official": True, "issuing_body": "Delaware General Assembly"})
        bundle["hierarchy"] = {"Delaware General Assembly": {"rank": 100, "binding": True, "jurisdiction": "Delaware"}}
        bundle["propositions"][0]["support"][0]["support_type"] = "TEXT"
        graph = self.graph(bundle)
        decision = graph.classify("prop-contract-consent-trigger", "Delaware", date.fromisoformat(DEMO_AS_OF))
        self.assertEqual(len(decision.controlling), 1)
        opinion = copy.deepcopy(bundle)
        opinion["sources"][0]["authority_kind"] = "OPINION"
        opinion["citator"] = {"covered": True, "statuses": {"harvey-change-control-contract-fixture": {"status": "OVERRULED"}}}
        blocked = self.graph(opinion).classify("prop-contract-consent-trigger", "Delaware", date.fromisoformat(DEMO_AS_OF))
        self.assertFalse(blocked.supported)
        self.assertIn("NEGATIVE_HISTORY", blocked.coverage_flags)

    def test_b2_dicta_is_never_classified_as_controlling(self):
        bundle = copy.deepcopy(self.bundle)
        statute = bundle["sources"][0]
        statute.update({"source_type": "OFFICIAL", "authority_kind": "OPINION", "official": True, "issuing_body": "Delaware Supreme Court"})
        bundle["hierarchy"] = {"Delaware Supreme Court": {"rank": 100, "binding": True, "jurisdiction": "Delaware"}}
        bundle["citator"] = {"covered": True, "statuses": {}}
        bundle["propositions"][0]["support"][0]["support_type"] = "DICTA"
        decision = self.graph(bundle).classify("prop-contract-consent-trigger", "Delaware", date.fromisoformat(DEMO_AS_OF))
        self.assertEqual(decision.controlling, [])
        self.assertEqual(len(decision.persuasive), 1)

    def test_b2_metrics_bound_false_acceptance_and_adverse_retrieval(self):
        metrics = classification_metrics(
            [
                {"expected_supported": True, "predicted_supported": True, "expected_adverse": True, "predicted_adverse": True},
                {"expected_supported": False, "predicted_supported": True, "expected_adverse": False, "predicted_adverse": False},
            ]
        )
        self.assertEqual(metrics["false_accept_rate"], 0.5)
        self.assertEqual(metrics["adverse_retrieval_recall"], 1.0)

    def test_b3_has_closed_22_pack_catalog_and_distinct_consent_types(self):
        registry = OntologyRegistry(self.bundle["ontology"])
        artifact = registry.artifact()
        self.assertEqual(artifact["workstream_pack_count"], 22)
        self.assertIn("consent-requirement", registry.types)
        self.assertIn("consent-status", registry.types)
        self.assertNotEqual(registry.types["consent-requirement"]["category"], registry.types["consent-status"]["category"])

    def test_b3_rejects_orphans_and_ambiguous_production_types(self):
        orphan = copy.deepcopy(self.bundle["ontology"])
        orphan["types"].append(
            {"type_id": "orphan-type", "category": "FACT", "status": "ACTIVE", "production": True, "root": False, "references": [], "schema": {"type": "object", "required": [], "properties": {}, "additionalProperties": False}}
        )
        with self.assertRaisesRegex(TruthError, "orphan production"):
            OntologyRegistry(orphan)
        ambiguous = copy.deepcopy(self.bundle["ontology"])
        next(item for item in ambiguous["types"] if item["type_id"] == "ambiguous-consent")["production"] = True
        with self.assertRaisesRegex(TruthError, "cannot be production"):
            OntologyRegistry(ambiguous)

    def test_b3_round_trip_rejects_schema_drift(self):
        registry = OntologyRegistry(self.bundle["ontology"])
        valid = registry.validate_instance("consent-status", {"contract_id": "c-1", "status": "NOT_OBTAINED"})
        self.assertEqual(valid["status"], "NOT_OBTAINED")
        with self.assertRaisesRegex(TruthError, "unknown fields"):
            registry.validate_instance("consent-status", {"contract_id": "c-1", "status": "OBTAINED", "requirement": True})

    def test_b3_migration_and_impact_are_versioned(self):
        current = copy.deepcopy(self.bundle["ontology"])
        current["version"] = 2
        current["migrations"] = [
            {"from_version": 1, "to_version": 2, "operations": [{"op": "rename_field", "type_id": "material-contract", "from": "is_material", "to": "material"}]}
        ]
        registry = OntologyRegistry(current)
        migrated = registry.migrate("material-contract", {"contract_id": "c-1", "title": "Master Services Agreement", "is_material": True}, 1)
        self.assertTrue(migrated["material"])
        impact = registry_impact(self.bundle["ontology"], current)
        self.assertEqual(impact["to_version"], 2)
        with self.assertRaisesRegex(TruthError, "version increment"):
            registry_impact(current, current)

    def test_b4_expression_logic_and_unsatisfiable_rules(self):
        facts = {"contract": {"material": True, "value": 125000}}
        expression = {"all": [{"fact": "contract.material", "op": "eq", "value": True}, {"fact": "contract.value", "op": "gte", "value": 100000}]}
        self.assertTrue(evaluate_expression(expression, facts))
        impossible = {"all": [{"fact": "contract.material", "op": "eq", "value": True}, {"fact": "contract.material", "op": "eq", "value": False}]}
        self.assertFalse(expression_satisfiable(impossible))
        broken = copy.deepcopy(self.bundle)
        broken["rule_pack"]["rules"][0]["trigger"] = impossible
        with self.assertRaisesRegex(TruthError, "unsatisfiable"):
            self.rule_pack(broken)

    def test_b4_enforces_rule_source_kind_and_authorized_owner(self):
        wrong_source = copy.deepcopy(self.bundle)
        wrong_source["rule_pack"]["rules"][0]["kind"] = "LEGAL_RULE"
        with self.assertRaisesRegex(TruthError, "cannot present CONTRACT"):
            self.rule_pack(wrong_source)
        with self.assertRaisesRegex(TruthError, "no authorized owner"):
            self.rule_pack(owners={"someone-else"})

    def test_b4_required_fallback_no_rule_and_low_confidence_paths(self):
        pack = self.rule_pack()
        case = copy.deepcopy(self.bundle["held_out_cases"][0]["facts"])
        required = pack.evaluate("change-of-control-consent", case, date.fromisoformat(DEMO_AS_OF))
        self.assertEqual(required.status, "MATCHED")
        self.assertEqual(required.actions[0]["kind"], "REQUIRED")
        case["contract"].pop("consent_status")
        fallback = pack.evaluate("change-of-control-consent", case, date.fromisoformat(DEMO_AS_OF))
        self.assertEqual(fallback.actions[0]["kind"], "FALLBACK")
        self.assertEqual(pack.evaluate("unmapped-ma-issue", case, date.fromisoformat(DEMO_AS_OF)).status, "NO_RULE")
        low = copy.deepcopy(self.bundle)
        low["rule_pack"]["rules"][0]["confidence"] = 0.5
        self.assertEqual(self.rule_pack(low).evaluate("change-of-control-consent", self.bundle["held_out_cases"][0]["facts"], date.fromisoformat(DEMO_AS_OF)).status, "LOW_CONFIDENCE")

    def test_b4_rejects_equal_precedence_conflicts(self):
        broken = copy.deepcopy(self.bundle)
        conflicting = copy.deepcopy(broken["rule_pack"]["rules"][0])
        conflicting["rule_id"] = "rule-conflicting-consent"
        conflicting["actions"][0]["recommendation"] = "Proceed without consent."
        broken["rule_pack"]["rules"].append(conflicting)
        with self.assertRaisesRegex(TruthError, "unresolved equal-precedence"):
            self.rule_pack(broken)

    def test_b4_rule_diff_coverage_and_counterfactuals(self):
        current = copy.deepcopy(self.bundle["rule_pack"])
        current["version"] = 2
        current["rules"][0]["confidence"] = 0.99
        diff = rule_version_diff(self.bundle["rule_pack"], current)
        self.assertEqual(diff["changed_rule_ids"], ["rule-contract-change-control-consent"])
        pack = self.rule_pack()
        coverage = held_out_coverage(pack, self.bundle["held_out_cases"])
        self.assertEqual(coverage["coverage"], 1.0)
        item = self.bundle["counterfactuals"][0]
        counterfactual = counterfactual_check(pack, item["issue_family"], item["baseline"], item["counterfactual"], item["changed_fact_paths"], date.fromisoformat(item["as_of"]))
        self.assertTrue(counterfactual["passed"])

    def test_ar_001_requires_sublinear_effort(self):
        passing = ar_001_effort_experiment("change-of-control-consent", self.bundle["ar_001"]["observations"])
        self.assertTrue(passing["passed"])
        linear = ar_001_effort_experiment(
            "change-of-control-consent",
            [
                {"accepted_matters": 1, "senior_lawyer_minutes": 10},
                {"accepted_matters": 2, "senior_lawyer_minutes": 20},
                {"accepted_matters": 4, "senior_lawyer_minutes": 40},
            ],
        )
        self.assertFalse(linear["passed"])
        self.assertEqual(linear["decision"], "STOP_OR_NARROW")

    def test_phase1_demo_compiles_every_exit_gate(self):
        artifact = Phase1Compiler(generated_at=NOW).compile(self.phase0, self.authority_contract, self.bundle)
        self.assertEqual(artifact["status"], "TEST_READY")
        self.assertFalse(artifact["production_eligible"])
        self.assertTrue(all(artifact["gates"].values()))
        self.assertEqual(artifact["held_out_coverage"]["coverage"], 1.0)
        self.assertTrue(artifact["ar_001"]["passed"])

    def test_phase1_is_deterministic_for_same_inputs_and_clock(self):
        compiler = Phase1Compiler(generated_at=NOW)
        first = compiler.compile(self.phase0, self.authority_contract, self.bundle)
        second = compiler.compile(self.phase0, self.authority_contract, self.bundle)
        self.assertEqual(first["artifact_fingerprint"], second["artifact_fingerprint"])
        self.assertEqual(first["authority_snapshot"]["snapshot_id"], second["authority_snapshot"]["snapshot_id"])

    def test_phase1_fails_closed_on_tamper_scope_and_production_claims(self):
        tampered = copy.deepcopy(self.phase0)
        tampered["scope"]["workflow"] = "first-draft"
        blocked = Phase1Compiler(generated_at=NOW).evaluate(tampered, self.authority_contract, self.bundle)
        self.assertEqual(blocked["status"], "TEST_BLOCKED")
        self.assertFalse(blocked["gates"]["phase0_bound"])
        wrong_pin = copy.deepcopy(self.bundle)
        wrong_pin["scope"]["source_revision"] = "moving-main"
        blocked = Phase1Compiler(generated_at=NOW).evaluate(self.phase0, self.authority_contract, wrong_pin)
        self.assertEqual(blocked["status"], "TEST_BLOCKED")
        production_claim = copy.deepcopy(self.bundle)
        production_claim["test_fixture"] = False
        blocked = Phase1Compiler(generated_at=NOW).evaluate(self.phase0, self.authority_contract, production_claim)
        self.assertEqual(blocked["status"], "TEST_BLOCKED")
        self.assertFalse(blocked["production_eligible"])
        self.assertIn("nested test fixtures cannot be promoted", " ".join(blocked["issues"]))


if __name__ == "__main__":
    unittest.main()
