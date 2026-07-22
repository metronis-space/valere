"""Command-line entry point for the Phase 2 and 3 matter proofs."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from typing import Optional, Sequence

from utils.artifacts import atomic_write_json, load_document
from utils.cli import print_json
from utils.errors import ValereError
from utils.pov import POV_TIMESTAMP

from ..compiler import compile_phase2, compile_phase3


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="valere-matter")
    subparsers = parser.add_subparsers(dest="command", required=True)
    compile_command = subparsers.add_parser("compile", help="Compile a Phase 2 exit artifact from a Phase 1 exit")
    compile_command.add_argument("--phase1", required=True)
    compile_command.add_argument("--out", required=True)
    compile_command.add_argument("--seed", type=int, default=20260722)
    demo = subparsers.add_parser("demo-generate", help="Generate the bounded Phase 2 canonical-state POV")
    demo.add_argument("--phase1", default="scope/configs/demo/phase-1-test-exit.json")
    demo.add_argument("--out", default="scope/configs/demo/phase-2-test-exit.json")
    demo.add_argument("--seed", type=int, default=20260722)
    documents = subparsers.add_parser("document-world", help="Render and independently validate the Phase 3 document world")
    documents.add_argument("--phase2", default="scope/configs/demo/phase-2-test-exit.json")
    documents.add_argument("--vdr-out", default="scope/configs/demo/phase-3-vdr")
    documents.add_argument("--out", default="scope/configs/demo/phase-3-test-exit.json")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "document-world":
            phase2 = load_document(args.phase2)
            generated_at = datetime.fromisoformat(POV_TIMESTAMP).astimezone(timezone.utc) if phase2.get("pov_boundary", {}).get("test_fixture") else None
            artifact = compile_phase3(phase2, args.vdr_out, generated_at)
            atomic_write_json(args.out, artifact)
            print_json(
                {
                    "status": artifact["status"],
                    "production_eligible": artifact["production_eligible"],
                    "phase4_pov_unblocked": artifact["pov_boundary"]["pov_downstream_unblocked"],
                    "vdr": args.vdr_out,
                    "artifact": args.out,
                    "artifact_fingerprint": artifact["artifact_fingerprint"],
                }
            )
            return 0
        generated_at = datetime.fromisoformat(POV_TIMESTAMP).astimezone(timezone.utc) if args.command == "demo-generate" else None
        artifact = compile_phase2(load_document(args.phase1), args.seed, generated_at)
        atomic_write_json(args.out, artifact)
        print_json(
            {
                "status": artifact["status"],
                "production_eligible": artifact["production_eligible"],
                "phase3_pov_unblocked": artifact["pov_boundary"]["pov_downstream_unblocked"],
                "artifact": args.out,
                "artifact_fingerprint": artifact["artifact_fingerprint"],
            }
        )
        return 0
    except (OSError, ValueError, ValereError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
