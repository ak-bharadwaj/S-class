"""
S-Class Context: Project Continuity and Cross-Agent Handoff.
Provides verified project state transitions across agents without chat transcript bloat.
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
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_id": self.project_id,
            "active_task": self.active_task,
            "verified_tasks": self.verified_tasks,
            "failed_attempts": self.failed_attempts,
            "relevant_files": list(self.relevant_files),
            "recent_decisions": self.recent_decisions,
            "next_action": self.next_action,
            "created_at": self.created_at,
        }

    def to_markdown(self) -> str:
        """Renders human/agent-readable handoff summary."""
        lines = [
            f"# S-Class Project Handoff ({self.project_id})",
            f"Generated: {self.created_at}",
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
                lines.append(f"- [!] {f.get('reason')} (exit_code: {f.get('observed_exit_code')})")
        else:
            lines.append("- Zero recorded failures.")

        if self.next_action:
            lines.extend(["", "## Next Action", f"> {self.next_action}"])

        return "\n".join(lines)


class HandoffAssembler:
    """Assembles authoritative HandoffContext and HandoffPackage from state and local ledger."""

    def __init__(self, workspace_dir: str):
        self.workspace_dir = os.path.abspath(workspace_dir)
        self.repo = StateRepository(workspace_dir)

    def assemble(self, project_id: str, next_action: Optional[str] = None) -> HandoffContext:
        tasks = self.repo.list_tasks(project_id=project_id)
        verified = [t.to_dict() for t in tasks if t.state == TaskState.VERIFIED]
        in_progress = next((t.to_dict() for t in tasks if t.state in (TaskState.IN_PROGRESS, TaskState.CLAIMED, TaskState.VERIFYING)), None)

        # Collect relevant files
        files: List[str] = []
        if in_progress and "metadata" in in_progress:
            files = in_progress["metadata"].get("target_files", [])

        return HandoffContext(
            project_id=project_id,
            active_task=in_progress,
            verified_tasks=verified,
            failed_attempts=[],
            relevant_files=files,
            recent_decisions=[],
            next_action=next_action,
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

        chk = CheckpointManager.create_checkpoint(
            workspace_dir=self.workspace_dir,
            active_task_id=act_id,
            blockers=blockers,
            relevant_files=ctx.relevant_files,
            next_action=next_action,
        )

        v_refs = tuple(t.get("verified_receipt_id", t.get("task_id", "")) for t in ctx.verified_tasks if t.get("verified_receipt_id") or t.get("task_id"))
        rej_claims = tuple(ctx.failed_attempts)
        files = tuple(ctx.relevant_files)

        pkg_payload = f"{chk.checkpoint_hash}|{act_id}|{','.join(v_refs)}|{next_action}"
        pkg_hash = hashlib.sha256(pkg_payload.encode("utf-8")).hexdigest()

        return HandoffPackage(
            checkpoint=chk,
            task_context=act_task,
            verified_evidence_refs=v_refs,
            rejected_claims=rej_claims,
            relevant_files=files,
            next_action=next_action,
            package_hash=pkg_hash,
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

    @property
    def package_id(self) -> str:
        return self.package_hash
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "checkpoint": self.checkpoint.to_dict() if hasattr(self.checkpoint, "to_dict") else self.checkpoint,
            "task_context": self.task_context,
            "verified_evidence_refs": list(self.verified_evidence_refs),
            "rejected_claims": list(self.rejected_claims),
            "relevant_files": list(self.relevant_files),
            "next_action": self.next_action,
            "package_hash": self.package_hash,
            "created_at": self.created_at,
        }

