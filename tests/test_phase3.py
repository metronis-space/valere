"""Executable Phase 3 C3/C4 and AR-002 document-world proof."""

from __future__ import annotations

import copy
import tempfile
import unittest
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from matter.compiler import compile_phase2, compile_phase3
from matter.ingestion import ingest_document_world, inventory_document_world
from matter.rendering import render_document_world
from scope.compiler import Phase0Compiler
from scope.demo import build_demo_bundle as build_phase0_bundle
from truth.compiler import Phase1Compiler
from truth.demo import build_demo_bundle as build_phase1_bundle
from utils.artifacts import set_fingerprint, verify_fingerprint
from utils.errors import MatterError


NOW = datetime(2026, 7, 22, 12, tzinfo=timezone.utc)


class Phase3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        bundle = build_phase0_bundle()
        phase0 = Phase0Compiler(now=NOW).simulate(
            bundle["manifest"], bundle["rights"], bundle["governance"], bundle["authority"]
        )
        phase1 = Phase1Compiler(NOW).compile(phase0, bundle["authority"], build_phase1_bundle())
        cls.phase2 = compile_phase2(phase1, generated_at=NOW)
        cls.temporary = tempfile.TemporaryDirectory()
        cls.phase3 = compile_phase3(cls.phase2, cls.temporary.name, NOW)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def test_phase3_compiles_every_exit_gate(self) -> None:
        self.assertEqual(self.phase3["status"], "TEST_READY")
        self.assertEqual(self.phase3["trust_state"], "RENDER_VALIDATED")
        self.assertFalse(self.phase3["production_eligible"])
        self.assertTrue(all(self.phase3["gates"].values()))
        self.assertTrue(self.phase3["pov_boundary"]["independent_ingestion"])
        self.assertTrue(verify_fingerprint(self.phase3))
        self.assertTrue(verify_fingerprint(self.phase3["ingestion"]["evidence_graph"], "evidence_graph_fingerprint"))

    def test_c3_renders_openable_file_families_with_complete_provenance(self) -> None:
        root = Path(self.temporary.name)
        extensions = {Path(item["path"]).suffix for item in self.phase3["render_manifest"]["files"]}
        self.assertTrue({".docx", ".xlsx", ".pdf", ".eml", ".json", ".txt"} <= extensions)
        self.assertEqual(len(self.phase3["render_manifest"]["provenance"]), 24)
        self.assertEqual(
            {item["fact_path"] for item in self.phase3["render_manifest"]["provenance"]},
            {item["fact_path"] for item in self.phase3["ingestion"]["comparison"]},
        )
        for relative in (
            "contracts/material-services-agreement.docx",
            "contracts/amendment-001.docx",
            "disclosure/disclosure-schedule.docx",
            "financial/capitalization-funds-flow.xlsx",
        ):
            with zipfile.ZipFile(root / relative) as archive:
                self.assertIsNone(archive.testzip())
        self.assertTrue((root / "corporate/board-minutes.pdf").read_bytes().startswith(b"%PDF-1.4"))
        quality = self.phase3["ingestion"]["document_quality"]
        self.assertTrue(all(quality[name] for name in ("defined_terms_valid", "cross_references_valid", "signatures_valid", "math_valid", "precedence_valid")))

    def test_c4_is_independent_and_measures_recovery_by_severity_and_file_type(self) -> None:
        renderer = self.phase3["render_manifest"]["renderer"]
        ingestor = self.phase3["ingestion"]["ingestor"]
        self.assertNotEqual(renderer["engine_id"], ingestor["engine_id"])
        self.assertNotEqual(renderer["implementation"], ingestor["implementation"])
        self.assertGreaterEqual(len(ingestor["parser_engines"]), 5)
        metrics = self.phase3["ar_002"]
        self.assertEqual(metrics["precision"], 1.0)
        self.assertEqual(metrics["recall"], 1.0)
        self.assertEqual(metrics["span_accuracy"], 1.0)
        self.assertEqual(metrics["severity_weighted_recovery"], 1.0)
        self.assertEqual(metrics["unknown_rate"], 0.0)
        self.assertEqual(set(metrics["by_severity"]), {"CRITICAL", "HIGH", "MEDIUM", "LOW"})
        self.assertTrue({".docx", ".xlsx", ".pdf", ".txt"} <= set(metrics["by_file_type"]))
        self.assertEqual(
            {item["actual"] for item in self.phase3["ingestion"]["evidence_classifications"]},
            {"AVAILABLE", "MISSING", "UNPRODUCED"},
        )

    def test_phase3_is_deterministic_and_rejects_tampered_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as second:
            replay = compile_phase3(self.phase2, second, NOW)
        self.assertEqual(self.phase3, replay)

        tampered = copy.deepcopy(self.phase2)
        tampered["canonical_matter"]["contracts"][0]["annual_value"]["amount"] = 1
        set_fingerprint(tampered)
        with tempfile.TemporaryDirectory() as target:
            with self.assertRaisesRegex(MatterError, "canonical matter is invalid"):
                compile_phase3(tampered, target, NOW)

    def test_c4_detects_file_tamper_and_malware(self) -> None:
        with tempfile.TemporaryDirectory() as target:
            rendered = render_document_world(self.phase2["canonical_matter"], target)
            register = Path(target) / "consents/consent-register.txt"
            register.write_text(register.read_text().replace("NOT_OBTAINED", "OBTAINED"), encoding="utf-8")
            ingested = ingest_document_world(self.phase2["canonical_matter"], target, rendered, self.phase2)
            self.assertFalse(ingested["inventory"]["ok"])
            self.assertLess(ingested["metrics"]["recall"], 1.0)

        with tempfile.TemporaryDirectory() as target:
            attack = Path(target) / "payload.txt"
            attack.write_bytes(b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE")
            inventory = inventory_document_world(target, {"payload.txt": "sha256:" + __import__("hashlib").sha256(attack.read_bytes()).hexdigest()})
            self.assertFalse(inventory["ok"])
            self.assertFalse(inventory["files"][0]["safe"])


if __name__ == "__main__":
    unittest.main()
