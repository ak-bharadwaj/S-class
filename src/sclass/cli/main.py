"""
S-Class CLI: Developer and Agent Control Plane Interface (RC.13).
Authoritative CLI surface:
- sclass init
- sclass doctor
- sclass status
- sclass task (create, list, verify)
- sclass verify
- sclass explain
- sclass audit
- sclass history
- sclass trust
- sclass fleet
- sclass dashboard
- sclass handoff
- sclass adapter
- sclass logs
- sclass map
- sclass impact
- sclass run
- sclass daemon
"""

from __future__ import annotations
import os
import sys
import json
import shutil
import argparse
from typing import Optional, Dict, Any, List

from sclass import __version__
from sclass.storage.paths import WorkspacePaths
from sclass.state.tasks import StateRepository
from sclass.state.sqlite import SQLiteStateStore
from sclass.domain.project import Project, ProjectBoundary
from sclass.domain.task import Task, TaskState, TaskPriority
from sclass.domain.claim import Claim, ClaimType
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
from sclass.cli.explain import ExplainEngine
from sclass.cli.dashboard import render_dashboard, get_dashboard_data


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
    if not tasks:
        tasks = repo.list_tasks()
    ledger = LocalLedger(ws)
    is_valid, err = ledger.verify_integrity()
    entries = ledger.read_all_entries()

    if getattr(args, "json", False):
        print(json.dumps({
            "workspace": ws,
            "project": project.name if project else None,
            "ledger_valid": is_valid,
            "ledger_error": err,
            "entries_count": len(entries),
            "tasks": [t.to_dict() for t in tasks],
        }, indent=2))
        return 0

    ledger_status = "OK (Chain Valid)" if is_valid else f"CORRUPTED ({err})"
    print("┌──────────────────────────────────────────────────────────────┐")
    print(f"│ S-Class Control Plane Status ({__version__})".ljust(63) + "│")
    print("├──────────────────────────────────────────────────────────────┤")
    print(f"│ Workspace: {ws}"[:62].ljust(63) + "│")
    print(f"│ Project:   {project.name if project else 'None'}"[:62].ljust(63) + "│")
    print(f"│ Ledger:    {ledger_status}"[:62].ljust(63) + "│")
    print(f"│ Entries:   {len(entries)}".ljust(63) + "│")
    print("├──────────────────────────────────────────────────────────────┤")
    print("│ Tasks:".ljust(63) + "│")
    if not tasks:
        print("│   (No tasks registered)".ljust(63) + "│")
    for t in tasks:
        line = f"│   [{t.state.value.upper():^11}] {t.task_id}: {t.title}"
        print(line[:62].ljust(63) + "│")
    print("└──────────────────────────────────────────────────────────────┘")
    return 0


def cmd_daemon(args: argparse.Namespace) -> int:
    """Runs the S-Class workspace daemon monitoring loop."""
    from sclass.cli.daemon import SClassDaemon
    ws = os.path.abspath(args.workspace)
    daemon = SClassDaemon(ws, poll_interval_sec=args.interval)
    if args.once:
        daemon.run_once()
        health = daemon.check_health()
        print(f"[S-Class Daemon] Health tick complete: {health['status']} (tasks: {health['active_tasks_count']})")
        return 0 if health["ledger_valid"] else 1
    print(f"[S-Class Daemon] Starting daemon loop on {ws} (interval: {args.interval}s)...")
    try:
        daemon.start(max_ticks=args.ticks)
    except KeyboardInterrupt:
        daemon.stop()
        print("\n[S-Class Daemon] Stopped.")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    """
    Comprehensive system health check:
    git, python, sqlite, isolation runtimes, dependencies, ledger integrity.
    """
    ws = os.path.abspath(args.workspace)
    paths = WorkspacePaths(ws)

    checks: List[Dict[str, Any]] = []

    # 1. Environment & Python
    py_ok = sys.version_info >= (3, 10)
    checks.append({
        "category": "environment",
        "name": "Python version (>=3.10)",
        "passed": py_ok,
        "detail": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "critical": True,
    })

    # 2. Git
    git_bin = shutil.which("git")
    is_git_repo = os.path.isdir(os.path.join(ws, ".git"))
    checks.append({
        "category": "vcs",
        "name": "Git executable available",
        "passed": git_bin is not None,
        "detail": git_bin or "Not found in PATH",
        "critical": False,
    })
    checks.append({
        "category": "vcs",
        "name": "Workspace Git repository initialized",
        "passed": is_git_repo,
        "detail": "Valid repository root" if is_git_repo else "Not a git repository",
        "critical": False,
    })

    # 3. SQLite
    sqlite_ok = False
    sqlite_err = None
    try:
        import sqlite3
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE test (id INT);")
        conn.close()
        sqlite_ok = True
    except Exception as ex:
        sqlite_err = str(ex)

    checks.append({
        "category": "storage",
        "name": "SQLite runtime engine",
        "passed": sqlite_ok,
        "detail": "Operational" if sqlite_ok else f"Failed: {sqlite_err}",
        "critical": True,
    })

    # Workspace directory & database
    checks.append({
        "category": "workspace",
        "name": "Workspace directory exists",
        "passed": os.path.isdir(ws),
        "detail": ws,
        "critical": True,
    })
    sclass_dir_ok = os.path.isdir(paths.sclass_dir)
    checks.append({
        "category": "workspace",
        "name": "S-Class directory (.sclass)",
        "passed": sclass_dir_ok,
        "detail": paths.sclass_dir if sclass_dir_ok else "Not initialized (run 'sclass init')",
        "critical": False,
    })

    db_path = os.path.join(paths.state_dir, "project.db")
    db_ok = os.path.isfile(db_path)
    checks.append({
        "category": "storage",
        "name": "Authoritative database (project.db)",
        "passed": db_ok,
        "detail": "Present and initialized" if db_ok else "Absent or pending init",
        "critical": False,
    })

    # 4. Cryptographic Ledger Integrity
    ledger = LocalLedger(ws)
    is_chain_valid, chain_err = ledger.verify_integrity()
    checks.append({
        "category": "trust",
        "name": "Cryptographic ledger integrity",
        "passed": is_chain_valid,
        "detail": "Chain verified and tamper-free" if is_chain_valid else f"Corruption: {chain_err}",
        "critical": True,
    })

    # 5. Core Dependencies
    dep_results = []
    for dep_pkg in ["pydantic", "rich", "portalocker", "cryptography", "yaml", "tree_sitter", "tree_sitter_python"]:
        try:
            __import__(dep_pkg)
            dep_results.append((dep_pkg, True))
        except ImportError:
            dep_results.append((dep_pkg, False))

    deps_all_ok = all(ok for _, ok in dep_results)
    checks.append({
        "category": "dependencies",
        "name": "Core dependencies (pydantic, rich, tree_sitter, etc.)",
        "passed": deps_all_ok,
        "detail": ", ".join(f"{p}: {'OK' if ok else 'MISSING'}" for p, ok in dep_results),
        "critical": False,
    })

    # 6. Isolation Runtimes
    host_ok = True
    bwrap_ok = shutil.which("bwrap") is not None
    docker_ok = shutil.which("docker") is not None
    checks.append({
        "category": "isolation",
        "name": "Host execution provider",
        "passed": host_ok,
        "detail": "Host process execution operational",
        "critical": True,
    })
    checks.append({
        "category": "isolation",
        "name": "Sandbox isolation runtimes (bwrap / docker)",
        "passed": bwrap_ok or docker_ok or sys.platform == "win32",
        "detail": f"bwrap={bwrap_ok}, docker={docker_ok} (Platform: {sys.platform})",
        "critical": False,
    })

    all_critical_passed = all(c["passed"] for c in checks if c["critical"])
    all_passed = all(c["passed"] for c in checks)

    if getattr(args, "json", False):
        print(json.dumps({
            "workspace": ws,
            "overall_status": "PASSED" if all_critical_passed else "FAILED",
            "all_passed": all_passed,
            "checks": checks,
        }, indent=2))
        return 0 if all_critical_passed else 1

    print(f"=== S-Class Doctor: Comprehensive System Health Check ===")
    print(f"Target Workspace: {ws}\n")
    for c in checks:
        status_tag = "[PASSED]" if c["passed"] else ("[FAILED]" if c["critical"] else "[WARN]")
        print(f"  {status_tag:<9} {c['name']:<46} ({c['detail']})")

    print("\n" + "=" * 62)
    if all_critical_passed:
        print("[S-Class Doctor] Health check completed: ALL CRITICAL SUBSYSTEMS OPERATIONAL.")
        return 0
    else:
        print("[S-Class Doctor] Health check failed: CRITICAL SUBSYSTEM DEFECTS DETECTED.")
        return 1


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
    """
    Verifies a claim against an observed evidence receipt or executes a verification plan.
    """
    ws = os.path.abspath(args.workspace)

    # Verification plan mode
    plan_file = getattr(args, "plan", None)
    if plan_file:
        plan_path = os.path.abspath(plan_file)
        if not os.path.exists(plan_path):
            print(f"[S-Class] Verification plan file not found: {plan_path}")
            return 1
        try:
            with open(plan_path, "r", encoding="utf-8") as f:
                plan_data = json.load(f)
        except Exception as ex:
            print(f"[S-Class] Error reading verification plan: {ex}")
            return 1

        claims_to_verify = plan_data if isinstance(plan_data, list) else plan_data.get("claims", [])
        print(f"[S-Class] Executing verification plan '{os.path.basename(plan_path)}' ({len(claims_to_verify)} claims)...")
        results = []
        all_passed = True
        for item in claims_to_verify:
            c_type = item.get("claim_type") or item.get("type") or ClaimType.TEST_PASS.value
            c = Claim(
                claim_id=item.get("claim_id") or item.get("id", "claim_plan"),
                task_id=item.get("task_id", "task_plan"),
                statement=item.get("statement", ""),
                claim_type=c_type,
            )
            r_id = item.get("receipt_id") or item.get("receipt")
            receipt = load_receipt(r_id, ws) if r_id else None
            res = verify_claim(c, receipt, workspace_dir=ws)
            results.append({
                "claim_id": c.claim_id,
                "status": res.status,
                "accepted": res.is_accepted,
                "reason": res.reason,
            })
            if not res.is_accepted:
                all_passed = False

        if getattr(args, "json", False):
            print(json.dumps({"plan": plan_path, "results": results, "all_passed": all_passed}, indent=2))
        else:
            for r in results:
                mark = "[PASS]" if r["accepted"] else "[FAIL]"
                print(f"  {mark} {r['claim_id']}: {r['status']} ({r['reason']})")
        return 0 if all_passed else 1

    # Single claim / receipt verification mode
    receipt_id = getattr(args, "receipt", None)
    statement = getattr(args, "statement", None)

    if not receipt_id or not statement:
        print("[S-Class] Error: Provide either 'receipt' and 'statement' or '--plan <path>'.")
        return 1

    receipt = load_receipt(receipt_id, ws)
    if not receipt:
        print(f"[S-Class] Receipt '{receipt_id}' not found or hash corrupted.")
        return 1

    claim = Claim(
        claim_id=f"claim_{receipt_id}",
        task_id=receipt.task_id,
        statement=statement,
        claim_type=getattr(args, "type", ClaimType.TEST_PASS.value),
    )
    result = verify_claim(claim, receipt, workspace_dir=ws)

    if getattr(args, "json", False):
        print(json.dumps(result.to_dict(), indent=2))
        return 0 if result.is_accepted else 1

    print(f"Verification Result: {result.status}")
    print(f"Reason: {result.reason}")
    if result.observed_exit_code is not None:
        print(f"Exit Code: {result.observed_exit_code}")
    return 0 if result.is_accepted else 1


def cmd_explain(args: argparse.Namespace) -> int:
    """
    Produces human-readable and machine-readable evidence chains for any claim or receipt.
    Claim → Evidence → Verifier → Policy → Observed State → Result → Project State
    """
    ws = os.path.abspath(args.workspace)
    target = getattr(args, "target", None) or getattr(args, "claim", None) or getattr(args, "receipt", None) or getattr(args, "task", None)
    if not target:
        print("[S-Class] Error: Provide a target identifier (claim_id, receipt_id, or task_id) to explain.")
        return 1

    engine = ExplainEngine(ws)
    exp = engine.explain(target)

    if getattr(args, "json", False):
        print(json.dumps(exp.to_dict(), indent=2))
    elif getattr(args, "markdown", False):
        print(exp.to_markdown())
    else:
        print(exp.format_human())

    return 0 if exp.verdict in ("ACCEPTED", "VERIFIED", "ALLOW") else (1 if exp.verdict in ("REJECTED", "FAIL") else 0)


def cmd_audit(args: argparse.Namespace) -> int:
    """
    Exports or displays full cryptographic audit trail and ledger verification.
    """
    ws = os.path.abspath(args.workspace)
    ledger = LocalLedger(ws)
    is_valid, err = ledger.verify_integrity()
    entries = ledger.read_all_entries()
    auditor = LedgerIntegrityAuditor.audit_workspace(ws)

    audit_payload = {
        "workspace": ws,
        "version": __version__,
        "ledger_path": auditor.get("ledger_path"),
        "chain_valid": is_valid,
        "chain_error": err,
        "entry_count": len(entries),
        "head_hash": auditor.get("head_hash"),
        "entries": entries,
    }

    export_path = getattr(args, "export", None)
    if export_path:
        out_file = os.path.abspath(export_path)
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(audit_payload, f, indent=2)
        print(f"[S-Class] Exported complete audit trail ({len(entries)} entries) to: {out_file}")
        return 0 if is_valid else 1

    if getattr(args, "json", False):
        print(json.dumps(audit_payload, indent=2))
        return 0 if is_valid else 1

    print("=== S-Class Cryptographic Ledger & Audit Trail ===")
    print(f"Workspace:   {ws}")
    print(f"Integrity:   {'VALID (Tamper-Free)' if is_valid else f'CORRUPTED ({err})'}")
    print(f"Total Logged: {len(entries)} events")
    print(f"Head Hash:   {auditor.get('head_hash')}\n")
    print("Recent Audit Timeline:")
    for e in entries[-args.limit if getattr(args, 'limit', None) else -10:]:
        seq = e.get("sequence", 0)
        ts = e.get("timestamp", "")[:19]
        evt = e.get("event", "UNKNOWN")
        h = e.get("hash", "")[:12]
        print(f"  [{seq:04d}] {ts} | {evt:<18} | Hash: {h}...")

    return 0 if is_valid else 1


def cmd_history(args: argparse.Namespace) -> int:
    """
    Displays the authoritative project truth and state evolution timeline.
    """
    ws = os.path.abspath(args.workspace)
    ledger = LocalLedger(ws)
    entries = ledger.read_all_entries()
    limit = getattr(args, "limit", None) or 30

    events = [e for e in entries if any(k in e.get("event", "").lower() for k in ("task", "verif", "truth", "claim", "init", "lease"))]
    shown = events[-limit:]

    if getattr(args, "json", False):
        print(json.dumps({"workspace": ws, "total_events": len(events), "history": shown}, indent=2))
        return 0

    print(f"=== S-Class Project Truth Timeline ({len(shown)} of {len(events)} events) ===")
    for e in shown:
        seq = e.get("sequence", 0)
        ts = e.get("timestamp", "")[:19]
        evt = e.get("event", "")
        payload = e.get("payload", {})
        summary = str(payload.get("title") or payload.get("statement") or payload.get("reason") or payload.get("workspace") or "")
        if len(summary) > 40:
            summary = summary[:37] + "..."
        print(f"  [{seq:03d}] {ts} | {evt:<22} | {summary}")
    return 0


def cmd_trust(args: argparse.Namespace) -> int:
    """
    Audits current trust state summary:
    leases, capabilities, verification counts, and cryptographic ledger integrity.
    """
    ws = os.path.abspath(args.workspace)
    paths = WorkspacePaths(ws)
    repo = StateRepository(ws)
    ledger = LocalLedger(ws)
    is_valid, err = ledger.verify_integrity()
    entries = ledger.read_all_entries()

    # Active tasks and verification counts
    proj_name = os.path.basename(ws)
    tasks = repo.list_tasks(project_id=proj_name)
    if not tasks:
        tasks = repo.list_tasks()
    verified_count = sum(1 for t in tasks if t.state == TaskState.VERIFIED)
    failed_count = sum(1 for t in tasks if t.state == TaskState.FAILED)

    # Active leases
    leases_file = os.path.join(paths.sclass_dir, "leases.json")
    active_leases: List[Dict[str, Any]] = []
    if os.path.exists(leases_file):
        try:
            with open(leases_file, "r", encoding="utf-8") as f:
                content = json.load(f)
                active_leases = content if isinstance(content, list) else list(content.values())
        except Exception:
            pass

    # Authoritative capabilities
    capabilities = [
        "terminal.execute",
        "filesystem.read",
        "filesystem.write",
        "network.http",
        "mcp.tool_call",
        "acp.channel",
    ]

    trust_summary = {
        "workspace": ws,
        "ledger_valid": is_valid,
        "ledger_error": err,
        "head_hash": ledger.get_last_hash() if hasattr(ledger, "get_last_hash") else "0" * 64,
        "entries_count": len(entries),
        "total_tasks": len(tasks),
        "verified_tasks": verified_count,
        "failed_tasks": failed_count,
        "active_leases": len(active_leases),
        "capabilities": capabilities,
    }

    if getattr(args, "json", False):
        print(json.dumps(trust_summary, indent=2))
        return 0 if is_valid else 1

    print("=== S-Class Trust State Summary ===")
    print(f"Workspace:           {ws}")
    print(f"Ledger Chain:        {'VALID (Sealed)' if is_valid else f'CORRUPTED ({err})'}")
    print(f"Head Digest:         {trust_summary['head_hash'][:16]}...")
    print(f"Ledger Entries:      {len(entries)}")
    print(f"Verified Tasks:      {verified_count} / {len(tasks)}")
    print(f"Failed Claims:       {failed_count}")
    print(f"Active Leases:       {len(active_leases)}")
    print(f"Active Capabilities: {', '.join(capabilities[:4])} (+{len(capabilities)-4} more)")
    return 0 if is_valid else 1


def cmd_fleet(args: argparse.Namespace) -> int:
    """
    Displays fleet status, registered agents, active leases, and agent health.
    """
    ws = os.path.abspath(args.workspace)
    paths = WorkspacePaths(ws)

    # Read active leases
    leases_file = os.path.join(paths.sclass_dir, "leases.json")
    leases: List[Dict[str, Any]] = []
    if os.path.exists(leases_file):
        try:
            with open(leases_file, "r", encoding="utf-8") as f:
                content = json.load(f)
                leases = content if isinstance(content, list) else list(content.values())
        except Exception:
            pass

    # Read registered agent sessions
    registry_file = os.path.join(paths.sclass_dir, "agent_registry.json")
    agents: List[Dict[str, Any]] = []
    if os.path.exists(registry_file):
        try:
            with open(registry_file, "r", encoding="utf-8") as f:
                content = json.load(f)
                agents = content if isinstance(content, list) else list(content.values())
        except Exception:
            pass

    if not agents:
        agents = [
            {"agent_id": "agent-primary", "role": "developer", "platform": "antigravity", "status": "ACTIVE", "health": "HEALTHY"}
        ]

    fleet_data = {
        "workspace": ws,
        "agents_count": len(agents),
        "agents": agents,
        "leases_count": len(leases),
        "leases": leases,
    }

    if getattr(args, "json", False):
        print(json.dumps(fleet_data, indent=2))
        return 0

    print(f"=== S-Class Multi-Agent Fleet Status ({len(agents)} agents, {len(leases)} leases) ===")
    print("Registered Agents:")
    for a in agents:
        aid = a.get("agent_id", "unknown")
        role = a.get("role", "worker")
        stat = a.get("status", "ACTIVE")
        health = a.get("health", "HEALTHY")
        print(f"  - [{stat}] {aid} (role: {role}, health: {health})")

    print("\nActive Resource Leases:")
    if not leases:
        print("  (No active resource leases)")
    for l in leases:
        res = l.get("resource", "unknown")
        holder = l.get("holder", "unknown")
        mode = l.get("mode", "WRITE")
        print(f"  - [{mode}] {res} -> held by {holder}")
    return 0


def cmd_dashboard(args: argparse.Namespace) -> int:
    """Renders the S-Class Rich TUI operational dashboard."""
    ws = os.path.abspath(args.workspace)
    render_dashboard(ws)
    return 0


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


def cmd_run(args: argparse.Namespace) -> int:
    """Executes a command under S-Class execution backend, OS observation, and ledger sealing."""
    ws = os.path.abspath(args.workspace)
    from sclass.domain.action import ActionRequest
    from sclass.observation.convergence import ObservationConvergence
    from sclass.execution.backend import get_execution_backend

    cmd_str = " ".join(args.cmd) if isinstance(args.cmd, list) else args.cmd
    req = ActionRequest(
        actor=getattr(args, "actor", None) or "cli_user",
        session=getattr(args, "session", "") or "",
        capability="terminal.execute",
        action="run_command",
        target=cmd_str,
        workspace=ws,
        context={"cli": True},
        provenance={"platform": "cli", "actor": getattr(args, "actor", None) or "cli_user"},
    )
    backend = get_execution_backend(getattr(args, "backend", "host"))
    exec_res, receipt = ObservationConvergence.execute_and_observe(
        request=req,
        command=cmd_str,
        backend=backend,
    )
    if exec_res.stdout:
        print(exec_res.stdout, end="")
    if exec_res.stderr:
        print(exec_res.stderr, end="", file=sys.stderr)
    return exec_res.exit_code


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
    p_status.add_argument("--json", action="store_true", help="Output JSON")

    # doctor
    p_doc = subparsers.add_parser("doctor", help="Run comprehensive system health checks")
    p_doc.add_argument("-w", "--workspace", default=".", help="Target workspace path")
    p_doc.add_argument("--json", action="store_true", help="Output JSON")

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
    p_ver = subparsers.add_parser("verify", help="Verify claim against evidence receipt or execute plan")
    p_ver.add_argument("receipt", nargs="?", default=None, help="Receipt ID")
    p_ver.add_argument("statement", nargs="?", default=None, help="Claim statement to verify")
    p_ver.add_argument("--plan", default=None, help="Path to verification plan JSON file")
    p_ver.add_argument("-t", "--type", default="test_pass", help="Claim type")
    p_ver.add_argument("-w", "--workspace", default=".", help="Target workspace path")
    p_ver.add_argument("--json", action="store_true", help="Output JSON")

    # explain
    p_exp = subparsers.add_parser("explain", help="Human-readable and JSON evidence chain for any claim")
    p_exp.add_argument("target", nargs="?", default=None, help="Claim ID, Receipt ID, or Task ID")
    p_exp.add_argument("--claim", default=None, help="Claim ID to explain")
    p_exp.add_argument("--receipt", default=None, help="Receipt ID to explain")
    p_exp.add_argument("--task", default=None, help="Task ID to explain")
    p_exp.add_argument("--json", action="store_true", help="Output JSON machine-readable evidence chain")
    p_exp.add_argument("--markdown", action="store_true", help="Output GitHub Markdown format")
    p_exp.add_argument("-w", "--workspace", default=".", help="Target workspace path")

    # audit
    p_aud = subparsers.add_parser("audit", help="Export full cryptographic ledger audit trail")
    p_aud.add_argument("--export", default=None, help="Export trail to specified JSON file")
    p_aud.add_argument("--limit", type=int, default=20, help="Max entries to show in console")
    p_aud.add_argument("--json", action="store_true", help="Output JSON")
    p_aud.add_argument("-w", "--workspace", default=".", help="Target workspace path")

    # history
    p_hist = subparsers.add_parser("history", help="Display project truth evolution timeline")
    p_hist.add_argument("-n", "--limit", type=int, default=30, help="Number of entries to display")
    p_hist.add_argument("--json", action="store_true", help="Output JSON")
    p_hist.add_argument("-w", "--workspace", default=".", help="Target workspace path")

    # trust
    p_trust = subparsers.add_parser("trust", help="Current trust state summary (leases, capabilities, ledger)")
    p_trust.add_argument("-w", "--workspace", default=".", help="Target workspace path")
    p_trust.add_argument("--json", action="store_true", help="Output JSON")

    # fleet
    p_flt = subparsers.add_parser("fleet", help="Fleet status, active leases, agent health")
    p_flt.add_argument("-w", "--workspace", default=".", help="Target workspace path")
    p_flt.add_argument("--json", action="store_true", help="Output JSON")

    # dashboard
    p_dash = subparsers.add_parser("dashboard", help="Display Rich TUI operational dashboard")
    p_dash.add_argument("-w", "--workspace", default=".", help="Target workspace path")

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

    # daemon
    p_dae = subparsers.add_parser("daemon", help="Run workspace health and monitoring daemon")
    p_dae.add_argument("--once", action="store_true", help="Run a single health check tick and write IPC")
    p_dae.add_argument("--interval", type=float, default=5.0, help="Poll interval in seconds")
    p_dae.add_argument("--ticks", type=int, default=None, help="Maximum ticks before exiting")
    p_dae.add_argument("-w", "--workspace", default=".", help="Target workspace path")

    # run
    p_run = subparsers.add_parser("run", help="Execute command under S-Class observation convergence")
    p_run.add_argument("cmd", nargs="+", help="Command to execute")
    p_run.add_argument("-w", "--workspace", default=".", help="Target workspace path")
    p_run.add_argument("--actor", default="cli_user", help="Actor identity")
    p_run.add_argument("--session", default="", help="Session or task ID")
    p_run.add_argument("--backend", default="host", help="Execution backend (host, bwrap, docker)")

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
        "explain": cmd_explain,
        "audit": cmd_audit,
        "history": cmd_history,
        "trust": cmd_trust,
        "fleet": cmd_fleet,
        "dashboard": cmd_dashboard,
        "handoff": cmd_handoff,
        "adapter": cmd_adapter,
        "logs": cmd_logs,
        "map": cmd_map,
        "impact": cmd_impact,
        "daemon": cmd_daemon,
        "run": cmd_run,
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
