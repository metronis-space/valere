"""Command-line entry point for Phase 1 truth-policy controls."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Sequence

from utils.artifacts import atomic_write_json, load_document
from utils.cli import print_json
from utils.errors import ValereError
from utils.pov import POV_TIMESTAMP

from .compiler import Phase1Compiler
from .demo import build_demo_bundle


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="valere-truth")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "compile"):
        command = subparsers.add_parser(name, help="%s a Phase 1 bundle" % name.title())
        command.add_argument("--phase0", required=True)
        command.add_argument("--authority", required=True)
        command.add_argument("--bundle", required=True)
        if name == "compile":
            command.add_argument("--out", required=True)
        else:
            command.add_argument("--report")
    demo = subparsers.add_parser("demo-generate", help="Generate the bounded fictional M&A Phase 1 POV")
    demo.add_argument("--phase0", default="scope/configs/demo/phase-0-test-exit.json")
    demo.add_argument("--authority", default="scope/configs/demo/AuthoritySignoffMatrix.demo.yaml")
    demo.add_argument("--out-dir", default="scope/configs/demo")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command in {"validate", "compile"}:
            phase0 = load_document(args.phase0)
            authority = load_document(args.authority)
            bundle = load_document(args.bundle)
            compiler = Phase1Compiler()
            artifact = compiler.evaluate(phase0, authority, bundle) if args.command == "validate" else compiler.compile(phase0, authority, bundle)
            destination = args.report if args.command == "validate" else args.out
            if destination:
                atomic_write_json(destination, artifact)
            print_json({"status": artifact["status"], "artifact_fingerprint": artifact["artifact_fingerprint"], "out": destination})
            return 0 if artifact["status"] in {"READY", "TEST_READY"} else 2
        if args.command == "demo-generate":
            root = Path(args.out_dir)
            bundle = build_demo_bundle()
            bundle_path = root / "TruthPolicyBundle.demo.json"
            atomic_write_json(str(bundle_path), bundle)
            generated_at = datetime.fromisoformat(POV_TIMESTAMP).astimezone(timezone.utc)
            artifact = Phase1Compiler(generated_at=generated_at).compile(
                load_document(args.phase0),
                load_document(args.authority),
                bundle,
            )
            artifact_path = root / "phase-1-test-exit.json"
            atomic_write_json(str(artifact_path), artifact)
            print_json(
                {
                    "status": artifact["status"],
                    "production_eligible": artifact["production_eligible"],
                    "phase2_pov_unblocked": artifact["pov_boundary"]["pov_downstream_unblocked"],
                    "bundle": str(bundle_path),
                    "artifact": str(artifact_path),
                }
            )
            return 0
    except (OSError, ValueError, ValereError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
