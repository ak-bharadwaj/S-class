"""
S-Class Context: Project Continuity and Cross-Agent Handoff.
Provides verified project state transitions across agents without chat transcript bloat.
"""

from __future__ import annotations
import os
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

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
    """Assembles authoritative HandoffContext from SQLite state store and local ledger."""

    def __init__(self, workspace_dir: str):
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
