#!/usr/bin/env python3
"""S-Class Production Command Line Interface (CLI).

Wraps SClassControlPlane without maintaining independent state or authorization logic.
All user operations submit canonical Command objects to the single authority runtime.
"""

import argparse
import sys
from pathlib import Path

# Add project roots
_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "10-CONFORMANCE"))
sys.path.insert(0, str(_ROOT / "20-RUNTIME"))
sys.path.insert(0, str(_ROOT / "src"))

from sclass_runtime_v6_0_1 import (
    ChainStatus,
)

from sclass.client import SClassClient


def cmd_init(args):
    client = SClassClient.connect(args.db)
    state = client.get_state(args.workspace)
    print(f"Initialized workspace '{args.workspace}' (Head sequence: {state.event_sequence})")
    client.close()


def cmd_status(args):
    client = SClassClient.connect(args.db)
    state = client.get_state(args.workspace)
    chain = client.verify_chain(args.workspace)
    print(f"Workspace: {state.workspace_id}")
    print(f"Sequence:  {state.event_sequence}")
    print(f"Revision:  {state.state_revision[:24]}...")
    print(f"Chain:     {chain.value}")
    client.close()


def cmd_audit(args):
    client = SClassClient.connect(args.db)
    status = client.verify_chain(args.workspace)
    print(f"Hash Chain Audit: {status.value}")
    if status is not ChainStatus.VALID:
        sys.exit(1)
    client.close()


def cmd_run(args):
    client = SClassClient.connect(args.db)
    client.compile_and_submit_intent(args.intent, args.workspace)
    client.run_autonomous_cycle(args.workspace, ".")
    print(f"Executed intent: {args.intent}")
    client.close()


def cmd_verify(args):
    client = SClassClient.connect(args.db)
    client.verify_obligations(args.workspace, ".")
    print("Verification complete.")
    client.close()


def cmd_release(args):
    client = SClassClient.connect(args.db)
    verdict = client.evaluate_and_release(args.workspace)
    print(f"Release verdict: {verdict.name}")
    if str(verdict) != "ReleaseVerdict.READY":
        sys.exit(1)
    client.close()


def main():
    parser = argparse.ArgumentParser(description="S-Class Authority & Control Plane CLI")
    parser.add_argument("--db", default="sclass.sqlite", help="Path to SQLite authority database")
    parser.add_argument("--workspace", default="default", help="Workspace identifier")

    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Initialize workspace authority")
    init_parser.set_defaults(func=cmd_init)

    status_parser = subparsers.add_parser("status", help="Display canonical workspace status")
    status_parser.set_defaults(func=cmd_status)

    audit_parser = subparsers.add_parser("audit", help="Verify cryptographic event hash chain")
    audit_parser.set_defaults(func=cmd_audit)

    run_parser = subparsers.add_parser("run", help="Run autonomous cycle for intent")
    run_parser.add_argument("intent", help="The intent to execute")
    run_parser.set_defaults(func=cmd_run)

    verify_parser = subparsers.add_parser("verify", help="Verify obligations")
    verify_parser.set_defaults(func=cmd_verify)

    release_parser = subparsers.add_parser("release", help="Evaluate and release")
    release_parser.set_defaults(func=cmd_release)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
