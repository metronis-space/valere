"""Executable Phase 2 C1/C2/D3 exit-gate proof."""

from __future__ import annotations

import copy
import unittest
from datetime import datetime, timezone

from matter import MatterError as ExportedMatterError
from matter.compiler import compile_phase2
from matter.state import build_world, validate_world
from scope.compiler import Phase0Compiler
from scope.demo import build_demo_bundle as build_phase0_bundle
from truth.compiler import Phase1Compiler
from truth.demo import build_demo_bundle as build_phase1_bundle
from utils.artifacts import set_fingerprint, verify_fingerprint
from utils.errors import MatterError


NOW = datetime(2026, 7, 22, 12, tzinfo=timezone.utc)


class Phase2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        phase0_bundle = build_phase0_bundle()
        cls.phase0 = Phase0Compiler(now=NOW).simulate(
            phase0_bundle["manifest"],
            phase0_bundle["rights"],
            phase0_bundle["governance"],
            phase0_bundle["authority"],
        )
        cls.phase1 = Phase1Compiler(NOW).compile(cls.phase0, phase0_bundle["authority"], build_phase1_bundle())
        cls.phase2 = compile_phase2(cls.phase1, generated_at=NOW)

    def test_phase2_compiles_every_exit_gate(self) -> None:
        self.assertEqual(self.phase2["status"], "TEST_READY")
        self.assertFalse(self.phase2["production_eligible"])
        self.assertTrue(all(self.phase2["gates"].values()))
        self.assertTrue(self.phase2["pov_boundary"]["pov_downstream_unblocked"])
        self.assertFalse(self.phase2["pov_boundary"]["documents_rendered"])
        self.assertTrue(verify_fingerprint(self.phase2))

    def test_c1_replays_seed_and_checks_all_invariant_classes(self) -> None:
        first = build_world(self.phase1, 7)
        self.assertEqual(first, build_world(self.phase1, 7))
        self.assertNotEqual(first["matter_fingerprint"], build_world(self.phase1, 8)["matter_fingerprint"])
        self.assertTrue(validate_world(first)["ok"])

        mutations = {
            "identifiers_unique": lambda value: value["entities"].append(copy.deepcopy(value["entities"][0])),
            "referential_integrity": lambda value: value["contracts"][0]["parties"].append("missing-entity"),
            "temporal_integrity": lambda value: value["transaction"]["timeline"].update({"signing": "2026-10-01"}),
            "financial_integrity": lambda value: value["contracts"][0]["annual_value"].update({"amount": -1}),
            "evidence_explicit": lambda value: value["evidence"][0].update({"availability": "IMPLICIT"}),
            "closed_world_complete": lambda value: value["completeness"].update({"asserted_collections": []}),
        }
        for gate, mutate in mutations.items():
            with self.subTest(gate=gate):
                invalid = copy.deepcopy(first)
                mutate(invalid)
                set_fingerprint(invalid, "matter_fingerprint")
                self.assertFalse(validate_world(invalid)["gates"][gate])

    def test_c2_counterfactual_changes_only_declared_criteria(self) -> None:
        delta = self.phase2["expected_delta"]
        self.assertEqual(delta["changed_fact_paths"], ["contract.change_control_clause"])
        self.assertEqual(delta["actual_changed_criterion_ids"], delta["expected_changed_criterion_ids"])
        self.assertEqual(delta["actual_invariant_criterion_ids"], delta["expected_invariant_criterion_ids"])
        self.assertTrue(delta["passed"])

        examples = {item["example_id"]: item for item in self.phase2["examples"]}
        self.assertEqual(examples["positive"]["issue_plan"]["rule_outcome"]["status"], "MATCHED")
        self.assertEqual(examples["negative-no-clause"]["issue_plan"]["rule_outcome"]["status"], "NO_RULE")
        self.assertTrue(examples["contradictory-response"]["issue_plan"]["contradictions"])
        self.assertEqual(examples["missing-consent-evidence"]["issue_plan"]["evidence_state"][1]["availability"], "MISSING")
        self.assertIn("3_WISE", {item["kind"] for item in examples.values()})
        self.assertNotIn("consent_status", self.phase2["canonical_matter"]["contracts"][0]["clauses"]["change_of_control"])

    def test_d3_criteria_are_atomic_provenanced_and_document_free(self) -> None:
        examples = {item["example_id"]: item for item in self.phase2["examples"]}
        positive = examples["positive"]["criterion_bundle"]
        by_id = {item["criterion_id"]: item for item in positive["criteria"]}
        self.assertEqual(by_id["exact-span"]["assertion"]["expected"], "span-0001")
        self.assertEqual(
            {item["kind"] for item in positive["criteria"]},
            {"ISSUE_IDENTIFICATION", "EXACT_SPAN", "OPERATIVE_FACT", "TRIGGER_APPLICATION", "CONSEQUENCE", "CALCULATION", "SEVERITY", "RECOMMENDATION"},
        )
        for example in examples.values():
            validation = example["criterion_bundle"]["validation"]
            self.assertTrue(validation["ok"])
            self.assertEqual(validation["provenance_coverage"], 1.0)
            self.assertFalse(example["criterion_bundle"]["documents_used"])

    def test_phase2_rejects_tampered_or_promoted_phase1(self) -> None:
        self.assertIs(ExportedMatterError, MatterError)
        promoted = copy.deepcopy(self.phase1)
        promoted["status"] = "READY"
        set_fingerprint(promoted)
        with self.assertRaisesRegex(MatterError, "Phase 1 must be TEST_READY"):
            compile_phase2(promoted, generated_at=NOW)

        tampered = copy.deepcopy(self.phase1)
        tampered["rule_pack"]["rules"][0]["priority"] = 999
        set_fingerprint(tampered)
        with self.assertRaisesRegex(MatterError, "rule pack fingerprint"):
            compile_phase2(tampered, generated_at=NOW)


if __name__ == "__main__":
    unittest.main()
