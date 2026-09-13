"""
S-Class Context: Project Continuity and Cross-Agent Handoff.
Provides verified project state transitions across agents without chat transcript bloat.
Authoritatively derives verified tasks, rejected claims, blocked tasks, recent authorization
decisions, relevant evidence refs, ledger head, and workspace checkpoint directly from persisted
SQLite state and the append-only LocalLedger.
"""

from __future__ import annotations
import os
import json
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

from sclass.domain.task import Task, TaskState
from sclass.state.tasks import StateRepository
from sclass.trust.ledger import LocalLedger
from sclass.core.errors import HandoffIntegrityError


@dataclass
class HandoffContext:
    """Structured, verified state handed to a new agent session."""
    project_id: str
    active_task: Optional[Dict[str, Any]]
    verified_tasks: List[Dict[str, Any]]
    failed_attempts: List[Dict[str, Any]]
    relevant_files: List[str]
    recent_decisions: List[Dict[str, Any]]
    next_action: Optional[str] = None
    blocked_tasks: List[Dict[str, Any]] = field(default_factory=list)
    ledger_head: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_id": self.project_id,
            "active_task": self.active_task,
            "verified_tasks": self.verified_tasks,
            "failed_attempts": self.failed_attempts,
            "blocked_tasks": self.blocked_tasks,
            "relevant_files": list(self.relevant_files),
            "recent_decisions": self.recent_decisions,
            "ledger_head": self.ledger_head,
            "next_action": self.next_action,
            "created_at": self.created_at,
        }

    def to_markdown(self) -> str:
        """Renders human/agent-readable handoff summary."""
        lines = [
            f"# S-Class Project Handoff ({self.project_id})",
            f"Generated: {self.created_at}",
            f"Ledger Head: `{self.ledger_head}`" if self.ledger_head else "",
            "",
            "## Active Focus",
        ]
        if self.active_task:
            lines.append(f"- **Task ID**: `{self.active_task.get('task_id')}`")
            lines.append(f"- **Title**: {self.active_task.get('title')}")
            lines.append(f"- **State**: {self.active_task.get('state')}")
        else:
            lines.append("- No active task in progress.")

        lines.extend(["", "## Verified Prior Work"])
        if self.verified_tasks:
            for t in self.verified_tasks:
                lines.append(f"- [x] `{t.get('task_id')}`: {t.get('title')} (verified by `{t.get('verified_receipt_id')}`)")
        else:
            lines.append("- No tasks verified yet.")

        lines.extend(["", "## Known Failure Modes & Rejections"])
        if self.failed_attempts:
            for f in self.failed_attempts:
                status = f.get("status", "FAILED")
                reason = f.get("reason", "Verification rejected")
                code = f.get("observed_exit_code")
                code_str = f" (exit_code: {code})" if code is not None else ""
                lines.append(f"- [!] [{status}] {reason}{code_str}")
        else:
            lines.append("- Zero recorded failures.")

        if self.blocked_tasks:
            lines.extend(["", "## Blocked Tasks"])
            for b in self.blocked_tasks:
                lines.append(f"- [-] `{b.get('task_id')}`: {b.get('title')}")

        if self.next_action:
            lines.extend(["", "## Next Action", f"> {self.next_action}"])

        return "\n".join(line for line in lines if line is not None)


class HandoffAssembler:
    """Assembles authoritative HandoffContext and HandoffPackage from state and local ledger."""

    def __init__(
        self,
        workspace_dir: str,
        repo: Optional[StateRepository] = None,
        ledger: Optional[LocalLedger] = None,
    ):
        self.workspace_dir = os.path.abspath(workspace_dir)
        try:
            self.repo = repo or StateRepository(workspace_dir)
        except Exception as e:
            raise HandoffIntegrityError(f"Failed to initialize state repository for handoff: {e}") from e
        try:
            self.ledger = ledger or LocalLedger(workspace_dir)
        except Exception as e:
            raise HandoffIntegrityError(f"Failed to initialize ledger for handoff: {e}") from e

    def assemble(self, project_id: str, next_action: Optional[str] = None) -> HandoffContext:
        """
        Authoritatively derives verified state, failed claims, blocked tasks,
        recent decisions, and ledger head from SQLite store and LocalLedger.
        """
        try:
            tasks = self.repo.list_tasks(project_id=project_id)
        except Exception as e:
            raise HandoffIntegrityError(f"Database access failure while listing tasks for project '{project_id}': {e}") from e

        verified = [t.to_dict() for t in tasks if t.state == TaskState.VERIFIED]
        blocked = [t.to_dict() for t in tasks if t.state == TaskState.BLOCKED]
        in_progress = next(
            (t.to_dict() for t in tasks if t.state in (TaskState.IN_PROGRESS, TaskState.CLAIMED, TaskState.VERIFYING)),
            None,
        )

        # 1. Authoritatively retrieve rejected/failed verification attempts from SQLite verifications table
        failed_attempts: List[Dict[str, Any]] = []
        try:
            with self.repo.store.get_connection() as conn:
                query = """
                SELECT v.verification_id, v.claim_id, v.status, v.reason,
                       v.observed_exit_code, v.passed_tests, v.failed_tests, v.verification_time,
                       c.task_id, c.statement, c.claim_type
                FROM verifications v
                JOIN claims c ON v.claim_id = c.claim_id
                JOIN tasks t ON c.task_id = t.task_id
                WHERE t.project_id = ? AND v.status IN ('REJECT', 'INCONCLUSIVE', 'FAILED')
                ORDER BY v.verification_time DESC
                """
                rows = conn.execute(query, (project_id,)).fetchall()
                for r in rows:
                    failed_attempts.append({
                        "verification_id": r["verification_id"],
                        "claim_id": r["claim_id"],
                        "task_id": r["task_id"],
                        "statement": r["statement"],
                        "status": r["status"],
                        "reason": r["reason"],
                        "observed_exit_code": r["observed_exit_code"],
                        "failed_tests": r["failed_tests"],
                        "verification_time": r["verification_time"],
                    })
        except Exception as e:
            raise HandoffIntegrityError(f"Database access failure while retrieving verification history: {e}") from e

        # Also incorporate any blocked tasks into known failure modes if not duplicate
        for bt in blocked:
            if not any(f.get("task_id") == bt.get("task_id") for f in failed_attempts):
                failed_attempts.append({
                    "task_id": bt.get("task_id"),
                    "statement": bt.get("title"),
                    "status": "BLOCKED",
                    "reason": bt.get("metadata", {}).get("blocked_reason", f"Task '{bt.get('title')}' is blocked"),
                    "observed_exit_code": bt.get("metadata", {}).get("exit_code"),
                })

        # 2. Derive relevant files across active focus, blocked tasks, and verified tasks
        files: List[str] = []
        if in_progress and "metadata" in in_progress:
            files.extend(in_progress["metadata"].get("target_files", []))
        for bt in blocked:
            if "metadata" in bt:
                files.extend(bt["metadata"].get("target_files", []))
        for vt in verified:
            if "metadata" in vt:
                files.extend(vt["metadata"].get("target_files", []))
        # Deduplicate while preserving order
        deduped_files = list(dict.fromkeys(files))

        # 3. Derive recent decisions and cryptographic ledger head from LocalLedger
        recent_decisions: List[Dict[str, Any]] = []
        ledger_head = self.ledger.get_last_hash()
        try:
            target_ledger = self.ledger.ledger_file if os.path.exists(self.ledger.ledger_file) else self.ledger.legacy_ledger_file
            if os.path.exists(target_ledger):
                with open(target_ledger, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    for line in reversed(lines[-20:]):
                        if not line.strip():
                            continue
                        try:
                            entry = json.loads(line.strip())
                            evt = entry.get("event", "")
                            if evt in ("AUTHORIZATION", "DECISION", "POLICY", "VERIFICATION", "OBSERVATION"):
                                payload = entry.get("payload", {})
                                recent_decisions.append({
                                    "sequence": entry.get("sequence"),
                                    "event": evt,
                                    "timestamp": entry.get("timestamp"),
                                    "outcome": payload.get("outcome") or payload.get("status"),
                                    "reason": payload.get("reason"),
                                    "policy_id": payload.get("policy_id"),
                                    "hash": entry.get("hash"),
                                })
                        except Exception:
                            continue
        except Exception as e:
            raise HandoffIntegrityError(f"Ledger access failure while reading decisions in '{self.workspace_dir}': {e}") from e

        return HandoffContext(
            project_id=project_id,
            active_task=in_progress,
            verified_tasks=verified,
            failed_attempts=failed_attempts,
            relevant_files=deduped_files,
            recent_decisions=recent_decisions,
            next_action=next_action,
            blocked_tasks=blocked,
            ledger_head=ledger_head,
        )

    def assemble_package(
        self,
        project_id: str,
        next_action: Optional[str] = None,
        blockers: Optional[List[str]] = None,
    ) -> HandoffPackage:
        """Assembles authoritative HandoffPackage with ProjectCheckpoint."""
        from sclass.context.checkpoint import CheckpointManager
        ctx = self.assemble(project_id, next_action)
        act_task = ctx.active_task or {}
        act_id = act_task.get("task_id")

        # Automatically derive blockers if none provided
        resolved_blockers = blockers or [
            f"Task {b.get('task_id')}: {b.get('title')}" for b in ctx.blocked_tasks
        ]

        chk = CheckpointManager.create_checkpoint(
            workspace_dir=self.workspace_dir,
            active_task_id=act_id,
            blockers=resolved_blockers,
            relevant_files=ctx.relevant_files,
            next_action=next_action,
        )

        v_refs = tuple(
            str(t.get("verified_receipt_id") or t.get("task_id") or "")
            for t in ctx.verified_tasks
            if (t.get("verified_receipt_id") or t.get("task_id"))
        )
        rej_claims = tuple(ctx.failed_attempts)
        files = tuple(ctx.relevant_files)

        pkg_payload = f"{chk.checkpoint_hash}|{act_id}|{','.join(v_refs)}|{next_action}|{ctx.ledger_head}"
        pkg_hash = hashlib.sha256(pkg_payload.encode("utf-8")).hexdigest()

        return HandoffPackage(
            checkpoint=chk,
            task_context=act_task,
            verified_evidence_refs=v_refs,
            rejected_claims=rej_claims,
            relevant_files=files,
            next_action=next_action,
            package_hash=pkg_hash,
            blocked_tasks=tuple(ctx.blocked_tasks),
            recent_decisions=tuple(ctx.recent_decisions),
            ledger_head=ctx.ledger_head,
        )


@dataclass(frozen=True)
class HandoffPackage:
    """
    Authoritative cross-agent handoff bundle binding ProjectCheckpoint, TaskContext,
    verified evidence references, rejected claims, relevant files, and exact next action.
    """
    checkpoint: Any
    task_context: Dict[str, Any]
    verified_evidence_refs: Tuple[str, ...]
    rejected_claims: Tuple[Dict[str, Any], ...]
    relevant_files: Tuple[str, ...]
    next_action: Optional[str]
    package_hash: str
    blocked_tasks: Tuple[Dict[str, Any], ...] = ()
    recent_decisions: Tuple[Dict[str, Any], ...] = ()
    ledger_head: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def package_id(self) -> str:
        return self.package_hash

    def to_dict(self) -> Dict[str, Any]:
        return {
            "checkpoint": self.checkpoint.to_dict() if hasattr(self.checkpoint, "to_dict") else self.checkpoint,
            "task_context": self.task_context,
            "verified_evidence_refs": list(self.verified_evidence_refs),
            "rejected_claims": list(self.rejected_claims),
            "blocked_tasks": list(self.blocked_tasks),
            "recent_decisions": list(self.recent_decisions),
            "relevant_files": list(self.relevant_files),
            "ledger_head": self.ledger_head,
            "next_action": self.next_action,
            "package_hash": self.package_hash,
            "package_id": self.package_id,
            "created_at": self.created_at,
        }
