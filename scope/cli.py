"""Command line entry point for Phase 0 controls."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

from utils.artifacts import atomic_write_json
from utils.cli import print_json
from utils.errors import BoundaryError

from .authority import AuthorityEngine
from .compiler import Phase0Compiler
from .demo import build_demo_bundle, write_demo_bundle
from .governance import GovernanceEngine
from .io import load_document
from .manifest import change_impact
from .rights import RightsRegistry


def _phase_documents(args: argparse.Namespace) -> Sequence[Dict[str, Any]]:
    return (
        load_document(args.manifest),
        load_document(args.rights),
        load_document(args.governance),
        load_document(args.authority),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="valere-boundary")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name in ("validate", "compile"):
        command = subparsers.add_parser(name, help="%s all four Phase 0 contracts" % name.title())
        command.add_argument("--manifest", required=True)
        command.add_argument("--rights", required=True)
        command.add_argument("--governance", required=True)
        command.add_argument("--authority", required=True)
        if name == "compile":
            command.add_argument("--out", required=True)
        else:
            command.add_argument("--report")

    rights = subparsers.add_parser("rights-check", help="Check one asset/use and its full lineage")
    rights.add_argument("--rights", required=True)
    rights.add_argument("--asset", required=True)
    rights.add_argument("--use", required=True)
    rights.add_argument("--as-of")

    impact = subparsers.add_parser("impact", help="Diff two versioned ScopeManifests")
    impact.add_argument("--previous", required=True)
    impact.add_argument("--current", required=True)
    impact.add_argument("--out")

    classify = subparsers.add_parser("classify", help="Classify text under a governance policy")
    classify.add_argument("--governance", required=True)
    classify.add_argument("--tenant", required=True)
    classify.add_argument("--matter", required=True)
    text_group = classify.add_mutually_exclusive_group(required=True)
    text_group.add_argument("--text")
    text_group.add_argument("--text-file")
    classify.add_argument("--declared-level")
    classify.add_argument("--privilege-confirmed", action="store_true")

    authorize = subparsers.add_parser("authorize", help="Evaluate an action signoff request")
    authorize.add_argument("--authority", required=True)
    authorize.add_argument("--request", required=True)
    authorize.add_argument("--approvals", required=True)

    audit = subparsers.add_parser("audit-append", help="Append a hash-chained decision/override")
    audit.add_argument("--authority", required=True)
    audit.add_argument("--log", required=True)
    audit.add_argument("--event-type", choices=["CLIENT_DECISION", "EXCEPTION_OVERRIDE"], required=True)
    audit.add_argument("--actor", required=True)
    audit.add_argument("--payload", required=True, help="Path to a JSON/YAML payload")
    audit.add_argument("--request", help="Required for EXCEPTION_OVERRIDE")
    audit.add_argument("--approvals", help="Required for EXCEPTION_OVERRIDE")

    demo = subparsers.add_parser("demo-generate", help="Generate and validate a fictional design-partner bundle")
    demo.add_argument("--templates", help="Template directory (defaults to the templates bundled with scope)")
    demo.add_argument("--out-dir", default="scope/configs/demo")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command in {"validate", "compile"}:
            documents = _phase_documents(args)
            compiler = Phase0Compiler()
            if args.command == "validate":
                artifact = compiler.evaluate(*documents)
                if args.report:
                    atomic_write_json(args.report, artifact)
                print_json(artifact)
                return 0 if artifact["status"] == "READY" else 2
            artifact = compiler.compile(*documents)
            atomic_write_json(args.out, artifact)
            print_json({"status": artifact["status"], "out": args.out, "artifact_fingerprint": artifact["artifact_fingerprint"]})
            return 0

        if args.command == "rights-check":
            today = date.fromisoformat(args.as_of) if args.as_of else None
            decision = RightsRegistry(load_document(args.rights), today=today).decide(args.asset, args.use)
            print_json(decision.to_dict())
            return 0 if decision.allowed else 3

        if args.command == "impact":
            result = change_impact(load_document(args.previous), load_document(args.current))
            if args.out:
                atomic_write_json(args.out, result)
            print_json(result)
            return 0

        if args.command == "classify":
            text = args.text if args.text is not None else Path(args.text_file).read_text(encoding="utf-8")
            result = GovernanceEngine(load_document(args.governance)).classify(
                text,
                args.tenant,
                args.matter,
                declared_level=args.declared_level,
                privilege_confirmed=args.privilege_confirmed,
            )
            print_json(result.to_dict())
            return 0

        if args.command == "authorize":
            request = load_document(args.request)
            approval_document = load_document(args.approvals)
            approvals = approval_document.get("approvals", [])
            result = AuthorityEngine(load_document(args.authority)).evaluate_signoff(request, approvals)
            print_json(result.to_dict())
            return 0 if result.approved else 4

        if args.command == "audit-append":
            engine = AuthorityEngine(load_document(args.authority))
            payload = load_document(args.payload)
            if args.event_type == "CLIENT_DECISION":
                event = engine.record_client_decision(args.log, args.actor, payload)
            else:
                if not args.request or not args.approvals:
                    raise BoundaryError("EXCEPTION_OVERRIDE requires --request and --approvals")
                approval_document = load_document(args.approvals)
                event = engine.record_override(
                    args.log,
                    load_document(args.request),
                    approval_document.get("approvals", []),
                    payload,
                )
            print_json(event)
            return 0

        if args.command == "demo-generate":
            bundle = build_demo_bundle(args.templates)
            paths = write_demo_bundle(bundle, args.out_dir)
            artifact = Phase0Compiler().simulate(
                bundle["manifest"],
                bundle["rights"],
                bundle["governance"],
                bundle["authority"],
            )
            artifact_path = str(Path(args.out_dir) / "phase-0-test-exit.json")
            atomic_write_json(artifact_path, artifact)
            print_json(
                {
                    "status": artifact["status"],
                    "production_eligible": False,
                    "pov_downstream_unblocked": artifact["status"] == "TEST_READY",
                    "production_downstream_unblocked": False,
                    "configs": paths,
                    "artifact": artifact_path,
                }
            )
            return 0 if artifact["status"] == "TEST_READY" else 2
    except (BoundaryError, OSError, ValueError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
