"""Dependency-boundary tests for the shared utility layer."""

from __future__ import annotations

import ast
import os
import tempfile
import unittest
from pathlib import Path

from scope import BoundaryError as ExportedBoundaryError
from scope.demo import build_demo_bundle
from truth import TruthError as ExportedTruthError
from utils.errors import BoundaryError, TruthError


ROOT = Path(__file__).resolve().parents[1]


def imported_roots(package: str) -> set[str]:
    roots: set[str] = set()
    for path in (ROOT / package).glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                roots.add(node.module.split(".", 1)[0])
    return roots


class ArchitectureTests(unittest.TestCase):
    def test_phases_share_utils_without_importing_each_other(self) -> None:
        self.assertNotIn("truth", imported_roots("scope"))
        self.assertNotIn("scope", imported_roots("truth"))

    def test_utils_remains_dependency_neutral(self) -> None:
        roots = imported_roots("utils")
        self.assertNotIn("scope", roots)
        self.assertNotIn("truth", roots)

    def test_error_types_live_in_utils_and_remain_publicly_exported(self) -> None:
        self.assertFalse((ROOT / "scope" / "errors.py").exists())
        self.assertFalse((ROOT / "truth" / "errors.py").exists())
        self.assertIs(ExportedBoundaryError, BoundaryError)
        self.assertIs(ExportedTruthError, TruthError)

    def test_scope_demo_finds_bundled_templates_outside_repository_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            previous = Path.cwd()
            try:
                # Exercise the same path resolution used by an installed CLI.
                os.chdir(temporary)
                bundle = build_demo_bundle()
            finally:
                os.chdir(previous)
        self.assertEqual(bundle["manifest"]["approval_status"], "APPROVED")


if __name__ == "__main__":
    unittest.main()
