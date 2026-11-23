"""S-Class Production Command Line Interface (CLI).

Wraps SClassControlPlane without maintaining independent state or authorization logic.
All user operations submit canonical Command objects to the single authority runtime.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import sys

from sclass import ChainStatus
from sclass.client import SClassClient


def cmd_init(args: argparse.Namespace) -> None:
    client = SClassClient.connect(args.db)
    state = client.get_state(args.workspace)
    print(f"Initialized workspace '{args.workspace}' (Head sequence: {state.event_sequence})")
    client.close()


def cmd_status(args: argparse.Namespace) -> None:
    client = SClassClient.connect(args.db)
    state = client.get_state(args.workspace)
    chain = client.verify_chain(args.workspace)
    print(f"Workspace: {state.workspace_id}")
    print(f"Sequence:  {state.event_sequence}")
    print(f"Revision:  {state.state_revision[:24]}...")
    print(f"Chain:     {chain.value}")
    client.close()


def cmd_audit(args: argparse.Namespace) -> None:
    if getattr(args, "audit_subcommand", None) == "export":
        cmd_audit_export(args)
        return
    if getattr(args, "audit_subcommand", None) == "view":
        cmd_audit_view(args)
        return
    client = SClassClient.connect(args.db)
    status = client.verify_chain(args.workspace)
    print(f"Hash Chain Audit: {status.value}")
    if status is not ChainStatus.VALID:
        sys.exit(1)
    client.close()


def cmd_audit_export(args: argparse.Namespace) -> None:
    from sclass.product.audit_export import export_audit_bundle, write_audit_bundle
    from sclass.product.registry import REGISTRY_AUTHORITY, evaluate, list_musts

    out_path = pathlib.Path(args.out)
    musts = list_musts()
    records = []
    for m in musts:
        out = evaluate(m.must_id, {}, authority=REGISTRY_AUTHORITY)
        records.append({
            "must_id": m.must_id,
            "inputs": {},
            "output": out,
        })
    bundle = export_audit_bundle(records, max_entries=getattr(args, "max_entries", None))
    write_audit_bundle(bundle, out_path)
    print(f"Audit bundle exported to {out_path} ({bundle['exported_count']} gates, sha256={bundle['bundle_sha256']})")


def cmd_audit_view(args: argparse.Namespace) -> None:
    from sclass.product.audit_export import open_bundle_readonly

    bundle_path = pathlib.Path(args.bundle)
    fd, loaded = open_bundle_readonly(bundle_path)
    try:
        print(f"Audit bundle verified (O_RDONLY): sha256={loaded['bundle_sha256']}")
        print(f"Gates exported: {loaded['exported_count']} (total={loaded['total_count']}, truncated={loaded['truncated']})")
        print("Authoritative sources:")
        for name, src in loaded.get("sources", {}).items():
            print(f"  - {name}: type={src.get('type')}, count={src.get('record_count')}")
    finally:
        os.close(fd)


def cmd_run(args: argparse.Namespace) -> None:
    client = SClassClient.connect(args.db)
    client.compile_and_submit_intent(args.intent, args.workspace)
    client.run_autonomous_cycle(args.workspace, ".")
    print(f"Executed intent: {args.intent}")
    client.close()


def cmd_verify(args: argparse.Namespace) -> None:
    client = SClassClient.connect(args.db)
    client.verify_obligations(args.workspace, ".")
    print("Verification complete.")
    client.close()


def cmd_release(args: argparse.Namespace) -> None:
    client = SClassClient.connect(args.db)
    verdict = client.evaluate_and_release(args.workspace)
    print(f"Release verdict: {verdict.name}")
    if str(verdict) != "ReleaseVerdict.READY":
        sys.exit(1)
    client.close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="S-Class Authority & Control Plane CLI")
    parser.add_argument("--db", default="sclass.sqlite", help="Path to SQLite authority database")
    parser.add_argument("--workspace", default="default", help="Workspace identifier")

    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Initialize workspace authority")
    init_parser.set_defaults(func=cmd_init)

    status_parser = subparsers.add_parser("status", help="Display canonical workspace status")
    status_parser.set_defaults(func=cmd_status)

    audit_parser = subparsers.add_parser("audit", help="Verify cryptographic event hash chain or manage audit bundles")
    audit_subparsers = audit_parser.add_subparsers(dest="audit_subcommand")

    audit_export_parser = audit_subparsers.add_parser("export", help="Export audit bundle")
    audit_export_parser.add_argument("--out", default="audit_bundle.json", help="Path to export bundle JSON")
    audit_export_parser.add_argument("--max-entries", type=int, default=None, help="Max entries to export")
    audit_export_parser.set_defaults(func=cmd_audit_export)

    audit_view_parser = audit_subparsers.add_parser("view", help="View audit bundle with O_RDONLY verification")
    audit_view_parser.add_argument("bundle", help="Path to audit bundle JSON")
    audit_view_parser.set_defaults(func=cmd_audit_view)

    audit_parser.set_defaults(func=cmd_audit)

    run_parser = subparsers.add_parser("run", help="Run autonomous cycle for intent")
    run_parser.add_argument("intent", help="The intent to execute")
    run_parser.set_defaults(func=cmd_run)

    verify_parser = subparsers.add_parser("verify", help="Verify obligations")
    verify_parser.set_defaults(func=cmd_verify)

    release_parser = subparsers.add_parser("release", help="Evaluate and release")
    release_parser.set_defaults(func=cmd_release)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
