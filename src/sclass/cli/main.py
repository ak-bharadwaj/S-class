"""
S-Class CLI: Developer and Agent Control Plane Interface.
Freezes the authoritative initial CLI surface:
- sclass init
- sclass doctor
- sclass status
- sclass task (create, list, verify)
- sclass verify
- sclass handoff
- sclass adapter
- sclass logs
- sclass trust
"""

from __future__ import annotations
import os
import sys
import json
import argparse
from typing import Optional

from sclass import __version__
from sclass.storage.paths import WorkspacePaths
from sclass.state.tasks import StateRepository
from sclass.state.sqlite import SQLiteStateStore
from sclass.domain.project import Project, ProjectBoundary
from sclass.domain.task import Task, TaskState, TaskPriority
from sclass.domain.claim import Claim
from sclass.observation.receipt import load_receipt
from sclass.verification.engine import verify_claim
from sclass.trust.ledger import LocalLedger
from sclass.trust.integrity import LedgerIntegrityAuditor
from sclass.context.handoff import HandoffAssembler
from sclass.integrations.claude.adapter import ClaudeCodeAdapter
from sclass.integrations.codex.adapter import CodexAdapter
from sclass.integrations.cursor.adapter import CursorAdapter
from sclass.integrations.opencode.adapter import OpenCodeAdapter
from sclass.integrations.generic.adapter import GenericProcessAdapter
from sclass.state.events import EventJournal


def cmd_init(args: argparse.Namespace) -> int:
    """Initializes S-Class workspace control plane."""
    ws = os.path.abspath(args.workspace)
    paths = WorkspacePaths(ws)
    paths.ensure_directories()
    repo = StateRepository(ws)

    # Initialize project record if absent
    proj_name = os.path.basename(ws)
    project = repo.get_project(proj_name)
    if not project:
        project = Project(
            project_id=proj_name,
            name=proj_name,
            boundary=ProjectBoundary(ws),
        )
        repo.save_project(project)

    ledger = LocalLedger(ws)
    ledger.append("initialization", {"workspace": ws, "version": __version__})

    print(f"[S-Class] Initialized workspace control plane at: {ws}")
    print(f"[S-Class] Authoritative state: {paths.state_dir}")
    print(f"[S-Class] Cryptographic ledger: {paths.ledger_dir}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Displays project state, active tasks, and ledger health."""
    ws = os.path.abspath(args.workspace)
    paths = WorkspacePaths(ws)
    if not os.path.exists(paths.state_dir):
        print(f"[S-Class] No S-Class state found in {ws}. Run 'sclass init' first.")
        return 1

    repo = StateRepository(ws)
    proj_name = os.path.basename(ws)
    project = repo.get_project(proj_name)
    tasks = repo.list_tasks(project_id=proj_name)
    ledger = LocalLedger(ws)
    is_valid, err = ledger.verify_integrity()

    print(f"=== S-Class Control Plane Status ({__version__}) ===")
    print(f"Workspace: {ws}")
    print(f"Project:   {project.name if project else 'None'}")
    print(f"Ledger:    {'OK (Chain Valid)' if is_valid else f'CORRUPTED ({err})'}")
    print(f"Entries:   {len(ledger.read_all_entries())}")
    print("\nTasks:")
    if not tasks:
        print("  (No tasks registered)")
    for t in tasks:
        print(f"  [{t.state.value.upper():^11}] {t.task_id}: {t.title}")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    """Runs health checks on the S-Class workspace and environment."""
    ws = os.path.abspath(args.workspace)
    paths = WorkspacePaths(ws)

    checks = []
    checks.append(("Workspace directory", os.path.isdir(ws)))
    checks.append(("S-Class directory (.sclass)", os.path.isdir(paths.sclass_dir)))
    checks.append(("SQLite database (project.db)", os.path.isfile(os.path.join(paths.state_dir, "project.db"))))

    ledger = LocalLedger(ws)
    is_chain_valid, _ = ledger.verify_integrity()
    checks.append(("Cryptographic ledger integrity", is_chain_valid))

    print(f"[S-Class Doctor] Checking environment for: {ws}")
    all_ok = True
    for name, passed in checks:
        status = "PASSED" if passed else "FAILED"
        if not passed:
            all_ok = False
        print(f"  - {name:.<40} [{status}]")

    return 0 if all_ok else 1


def cmd_task_create(args: argparse.Namespace) -> int:
    """Creates a new task in the authoritative state store."""
    ws = os.path.abspath(args.workspace)
    repo = StateRepository(ws)
    proj_name = os.path.basename(ws)

    task = Task.create(
        title=args.title,
        project_id=proj_name,
        description=args.description or "",
    )
    repo.save_task(task)
    print(f"[S-Class] Created task {task.task_id}: '{task.title}' [{task.state.value}]")
    return 0


def cmd_task_list(args: argparse.Namespace) -> int:
    """Lists all registered tasks."""
    ws = os.path.abspath(args.workspace)
    repo = StateRepository(ws)
    proj_name = os.path.basename(ws)
    tasks = repo.list_tasks(project_id=proj_name)
    if not tasks:
        print("[S-Class] No tasks found.")
        return 0
    print(f"=== S-Class Tasks ({len(tasks)}) ===")
    for t in tasks:
        print(f"  [{t.state.value.upper():^11}] {t.task_id}: {t.title}")
    return 0


def cmd_task_verify(args: argparse.Namespace) -> int:
    """Verifies state and verification status for a task."""
    ws = os.path.abspath(args.workspace)
    repo = StateRepository(ws)
    task = repo.get_task(args.task_id)
    if not task:
        print(f"[S-Class] Task '{args.task_id}' not found.")
        return 1
    print(f"Task: {task.task_id} ({task.title})")
    print(f"Status: {task.state.value}")
    if task.state == TaskState.VERIFIED:
        print(f"Verified Receipt: {task.verified_receipt_id}")
        return 0
    else:
        print("Task is NOT verified.")
        return 1


def cmd_verify(args: argparse.Namespace) -> int:
    """Verifies a claim against an observed evidence receipt."""
    ws = os.path.abspath(args.workspace)
    receipt = load_receipt(args.receipt, ws)
    if not receipt:
        print(f"[S-Class] Receipt '{args.receipt}' not found or hash corrupted.")
        return 1

    claim = Claim(
        claim_id=f"claim_{args.receipt}",
        task_id=receipt.task_id,
        statement=args.statement,
        claim_type=args.type,
    )
    result = verify_claim(claim, receipt, workspace_dir=ws)
    print(f"Verification Result: {result.status}")
    print(f"Reason: {result.reason}")
    if result.observed_exit_code is not None:
        print(f"Exit Code: {result.observed_exit_code}")
    return 0 if result.is_accepted else 1


def cmd_handoff(args: argparse.Namespace) -> int:
    """Outputs verified project state for cross-agent handoff."""
    ws = os.path.abspath(args.workspace)
    assembler = HandoffAssembler(ws)
    proj_name = os.path.basename(ws)
    ctx = assembler.assemble(project_id=proj_name, next_action=args.next)

    if args.json:
        print(json.dumps(ctx.to_dict(), indent=2))
    else:
        print(ctx.to_markdown())
    return 0


def cmd_adapter(args: argparse.Namespace) -> int:
    """Reports available platform adapters and honest status."""
    ws = os.path.abspath(args.workspace)
    adapters = [
        ("Generic Process", GenericProcessAdapter(ws)),
        ("Claude Code", ClaudeCodeAdapter(ws)),
        ("OpenAI Codex", CodexAdapter(ws)),
        ("Cursor IDE", CursorAdapter(ws)),
        ("OpenCode", OpenCodeAdapter(ws)),
    ]

    print("=== S-Class Agent Platform Adapters ===")
    for name, ad in adapters:
        status_val = ad.status.value if hasattr(ad, "status") else "SUPPORTED"
        caps = ad.capabilities.native_protocol if hasattr(ad, "capabilities") else "unknown"
        print(f"  - {name:.<25} [{status_val}] (protocol: {caps})")
    return 0


def cmd_logs(args: argparse.Namespace) -> int:
    """Displays event journal and ledger activity."""
    ws = os.path.abspath(args.workspace)
    ledger = LocalLedger(ws)
    entries = ledger.read_all_entries()
    limit = args.limit or 20
    shown = entries[-limit:]
    print(f"=== S-Class Audit Logs (Showing last {len(shown)} of {len(entries)}) ===")
    for e in shown:
        print(f"  [{e.get('sequence')}] {e.get('timestamp')[:19]} | {e.get('event'):<14} | Hash: {e.get('hash')[:12]}...")
    return 0


def cmd_trust(args: argparse.Namespace) -> int:
    """Audits local trust root and cryptographic ledger."""
    ws = os.path.abspath(args.workspace)
    audit = LedgerIntegrityAuditor.audit_workspace(ws)
    print("=== S-Class Trust Integrity Audit ===")
    print(f"Ledger Path:   {audit['ledger_path']}")
    print(f"Chain Valid:   {audit['valid']}")
    if not audit["valid"]:
        print(f"Chain Error:   {audit['error']}")
    print(f"Entry Count:   {audit['entry_count']}")
    print(f"Head Hash:     {audit['head_hash']}")
    return 0 if audit["valid"] else 1


def cmd_map(args: argparse.Namespace) -> int:
    """Builds and prints concise repository symbol map."""
    ws = os.path.abspath(args.workspace)
    from sclass.intelligence.repository import RepositoryMapBuilder
    builder = RepositoryMapBuilder(ws)
    print(builder.build_map(max_files=args.max_files, max_chars=args.max_chars))
    return 0


def cmd_impact(args: argparse.Namespace) -> int:
    """Estimates downstream impact of modifying a symbol or file."""
    ws = os.path.abspath(args.workspace)
    from sclass.intelligence.impact import SymbolImpactEstimator
    estimator = SymbolImpactEstimator(ws)
    impact = estimator.estimate_impact(args.target)
    if args.json:
        print(json.dumps(impact.to_dict(), indent=2))
    else:
        print(f"[S-Class Impact] Target: {impact.target}")
        print(f"Impacted files count: {impact.impact_count}")
        for f in impact.impacted_files:
            print(f"  - {f}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sclass", description="S-Class: The Open-Source Trust & Control Plane")
    parser.add_argument("--version", action="version", version=f"sclass {__version__}")
    subparsers = parser.add_subparsers(dest="command")

    # init
    p_init = subparsers.add_parser("init", help="Initialize S-Class workspace")
    p_init.add_argument("-w", "--workspace", default=".", help="Target workspace path")

    # status
    p_status = subparsers.add_parser("status", help="Display workspace status")
    p_status.add_argument("-w", "--workspace", default=".", help="Target workspace path")

    # doctor
    p_doc = subparsers.add_parser("doctor", help="Run workspace health checks")
    p_doc.add_argument("-w", "--workspace", default=".", help="Target workspace path")

    # task
    p_task = subparsers.add_parser("task", help="Task management")
    task_subs = p_task.add_subparsers(dest="task_command")
    
    p_tc = task_subs.add_parser("create", help="Create a task")
    p_tc.add_argument("title", help="Task title")
    p_tc.add_argument("-d", "--description", default="", help="Task description")
    p_tc.add_argument("-w", "--workspace", default=".", help="Target workspace path")

    p_tl = task_subs.add_parser("list", help="List registered tasks")
    p_tl.add_argument("-w", "--workspace", default=".", help="Target workspace path")

    p_tv = task_subs.add_parser("verify", help="Verify task status")
    p_tv.add_argument("task_id", help="Task ID to verify")
    p_tv.add_argument("-w", "--workspace", default=".", help="Target workspace path")

    # verify
    p_ver = subparsers.add_parser("verify", help="Verify claim against evidence receipt")
    p_ver.add_argument("receipt", help="Receipt ID")
    p_ver.add_argument("statement", help="Claim statement to verify")
    p_ver.add_argument("-t", "--type", default="test_pass", help="Claim type")
    p_ver.add_argument("-w", "--workspace", default=".", help="Target workspace path")

    # handoff
    p_hand = subparsers.add_parser("handoff", help="Generate cross-agent handoff context")
    p_hand.add_argument("--next", default=None, help="Next recommended action")
    p_hand.add_argument("--json", action="store_true", help="Output JSON instead of Markdown")
    p_hand.add_argument("-w", "--workspace", default=".", help="Target workspace path")

    # adapter
    p_ad = subparsers.add_parser("adapter", help="List platform adapters and status")
    p_ad.add_argument("-w", "--workspace", default=".", help="Target workspace path")

    # logs
    p_log = subparsers.add_parser("logs", help="Display event journal logs")
    p_log.add_argument("-n", "--limit", type=int, default=20, help="Number of entries to show")
    p_log.add_argument("-w", "--workspace", default=".", help="Target workspace path")

    # trust
    p_trust = subparsers.add_parser("trust", help="Audit trust ledger integrity")
    p_trust.add_argument("-w", "--workspace", default=".", help="Target workspace path")

    # map
    p_map = subparsers.add_parser("map", help="Build repository symbol map")
    p_map.add_argument("-w", "--workspace", default=".", help="Target workspace path")
    p_map.add_argument("--max-files", type=int, default=50, help="Max files to scan")
    p_map.add_argument("--max-chars", type=int, default=8000, help="Max characters in output")

    # impact
    p_imp = subparsers.add_parser("impact", help="Estimate symbol dependency impact")
    p_imp.add_argument("target", help="Target symbol or file to analyze")
    p_imp.add_argument("-w", "--workspace", default=".", help="Target workspace path")
    p_imp.add_argument("--json", action="store_true", help="Output JSON")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    dispatch = {
        "init": cmd_init,
        "status": cmd_status,
        "doctor": cmd_doctor,
        "verify": cmd_verify,
        "handoff": cmd_handoff,
        "adapter": cmd_adapter,
        "logs": cmd_logs,
        "trust": cmd_trust,
        "map": cmd_map,
        "impact": cmd_impact,
    }

    if args.command == "task":
        if getattr(args, "task_command", None) == "create":
            sys.exit(cmd_task_create(args))
        elif getattr(args, "task_command", None) == "list":
            sys.exit(cmd_task_list(args))
        elif getattr(args, "task_command", None) == "verify":
            sys.exit(cmd_task_verify(args))
        else:
            parser.parse_args(["task", "--help"])
            sys.exit(0)

    fn = dispatch.get(args.command)
    if fn:
        sys.exit(fn(args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
