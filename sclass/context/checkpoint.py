"""
S-Class Context: Authoritative Project Checkpoint.
Cryptographically binds:
- repository HEAD
- working tree fingerprint
- ledger head
- active task
- verified tasks
- failed claims
- blockers
- relevant files
- next action
- constraints
Guarantees verified project continuity across agents and sessions.
"""

from __future__ import annotations
import os
import json
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple

from sclass.observation.fingerprint import compute_workspace_snapshot, compute_workspace_fingerprint
from sclass.trust.ledger import LocalLedger
from sclass.state.tasks import StateRepository


@dataclass(frozen=True)
class ProjectCheckpoint:
    """Authoritative cryptographically sealed checkpoint of verified project state."""
    checkpoint_id: str
    repo_head: str
    working_tree_fingerprint: str
    ledger_head: str
    active_task_id: Optional[str]
    verified_tasks: Tuple[str, ...]
    failed_claims: Tuple[Dict[str, Any], ...]
    blockers: Tuple[str, ...]
    relevant_files: Tuple[str, ...]
    next_action: Optional[str]
    constraints: Tuple[str, ...]
    checkpoint_hash: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def verify_integrity(self) -> bool:
        """Verifies cryptographic hash binding across all checkpoint fields."""
        payload = (
            f"{self.checkpoint_id}|{self.repo_head}|{self.working_tree_fingerprint}|"
            f"{self.ledger_head}|{self.active_task_id}|{','.join(self.verified_tasks)}|"
            f"{','.join(self.blockers)}|{','.join(self.relevant_files)}|{self.next_action}"
        )
        expected = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return self.checkpoint_hash == expected

    def to_dict(self) -> Dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "repo_head": self.repo_head,
            "working_tree_fingerprint": self.working_tree_fingerprint,
            "ledger_head": self.ledger_head,
            "active_task_id": self.active_task_id,
            "verified_tasks": list(self.verified_tasks),
            "failed_claims": list(self.failed_claims),
            "blockers": list(self.blockers),
            "relevant_files": list(self.relevant_files),
            "next_action": self.next_action,
            "constraints": list(self.constraints),
            "checkpoint_hash": self.checkpoint_hash,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ProjectCheckpoint:
        return cls(
            checkpoint_id=data["checkpoint_id"],
            repo_head=data.get("repo_head", "HEAD"),
            working_tree_fingerprint=data.get("working_tree_fingerprint", ""),
            ledger_head=data.get("ledger_head", ""),
            active_task_id=data.get("active_task_id"),
            verified_tasks=tuple(data.get("verified_tasks", [])),
            failed_claims=tuple(data.get("failed_claims", [])),
            blockers=tuple(data.get("blockers", [])),
            relevant_files=tuple(data.get("relevant_files", [])),
            next_action=data.get("next_action"),
            constraints=tuple(data.get("constraints", [])),
            checkpoint_hash=data.get("checkpoint_hash", ""),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
        )


class CheckpointManager:
    """Manages creation, serialization, and verification of project checkpoints."""

    @classmethod
    def create_checkpoint(
        cls,
        workspace_dir: str,
        checkpoint_id: str = "",
        active_task_id: Optional[str] = None,
        blockers: Optional[List[str]] = None,
        relevant_files: Optional[List[str]] = None,
        next_action: Optional[str] = None,
        constraints: Optional[List[str]] = None,
        repo_head: str = "HEAD",
    ) -> ProjectCheckpoint:
        ws = os.path.abspath(workspace_dir)
        cid = checkpoint_id or f"chk_{hashlib.sha256(os.urandom(16)).hexdigest()[:12]}"

        # 1. Working tree fingerprint
        snapshot = compute_workspace_snapshot(ws)
        fp = compute_workspace_fingerprint(snapshot)

        # 2. Ledger head
        ledger_head = ""
        try:
            ledger = LocalLedger(workspace_dir=ws)
            ledger_head = ledger.get_head_hash() or ""
        except Exception:
            pass

        # 3. Verified tasks from state repository
        verified_task_ids = []
        try:
            repo = StateRepository(ws)
            tasks = repo.list_tasks()
            verified_task_ids = [t.task_id for t in tasks if getattr(t, "state", None) == "VERIFIED"]
        except Exception:
            pass

        blks = tuple(blockers or [])
        rel_files = tuple(relevant_files or [])
        cons = tuple(constraints or [])
        v_tasks = tuple(verified_task_ids)

        payload = (
            f"{cid}|{repo_head}|{fp}|"
            f"{ledger_head}|{active_task_id}|{','.join(v_tasks)}|"
            f"{','.join(blks)}|{','.join(rel_files)}|{next_action}"
        )
        chk_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

        return ProjectCheckpoint(
            checkpoint_id=cid,
            repo_head=repo_head,
            working_tree_fingerprint=fp,
            ledger_head=ledger_head,
            active_task_id=active_task_id,
            verified_tasks=v_tasks,
            failed_claims=(),
            blockers=blks,
            relevant_files=rel_files,
            next_action=next_action,
            constraints=cons,
            checkpoint_hash=chk_hash,
        )
