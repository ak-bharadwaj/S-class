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
- project truth snapshot (RC.8)
- active leases & pending claims (RC.8)
- evidence graph (RC.8)
- incremental checkpointing & deltas (RC.8)
Guarantees verified project continuity across agents and sessions with durable SQLite persistence.
"""

from __future__ import annotations
import os
import json
import sqlite3
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple, Union

from sclass.observation.fingerprint import compute_workspace_snapshot, compute_workspace_fingerprint
from sclass.trust.ledger import LocalLedger
from sclass.state.tasks import StateRepository
from sclass.core.lifecycle import TaskState
from sclass.core.errors import HandoffIntegrityError


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
    project_truth: Optional[Dict[str, Any]] = None
    active_leases: Tuple[Dict[str, Any], ...] = ()
    pending_claims: Tuple[Dict[str, Any], ...] = ()
    evidence_graph: Dict[str, Any] = field(default_factory=dict)
    parent_checkpoint_id: Optional[str] = None
    is_incremental: bool = False
    delta: Dict[str, Any] = field(default_factory=dict)

    def verify_integrity(self) -> bool:
        """Verifies cryptographic hash binding across checkpoint fields."""
        # Standard base payload
        payload = (
            f"{self.checkpoint_id}|{self.repo_head}|{self.working_tree_fingerprint}|"
            f"{self.ledger_head}|{self.active_task_id}|{','.join(self.verified_tasks)}|"
            f"{','.join(self.blockers)}|{','.join(self.relevant_files)}|{self.next_action}"
        )
        expected = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        if self.checkpoint_hash == expected:
            return True

        # Extended payload for incremental/deep checkpoints
        ext_payload = f"{payload}|{self.parent_checkpoint_id}|{self.is_incremental}"
        ext_expected = hashlib.sha256(ext_payload.encode("utf-8")).hexdigest()
        return self.checkpoint_hash == ext_expected

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
            "project_truth": self.project_truth,
            "active_leases": list(self.active_leases),
            "pending_claims": list(self.pending_claims),
            "evidence_graph": dict(self.evidence_graph),
            "parent_checkpoint_id": self.parent_checkpoint_id,
            "is_incremental": self.is_incremental,
            "delta": dict(self.delta),
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
            project_truth=data.get("project_truth"),
            active_leases=tuple(data.get("active_leases", [])),
            pending_claims=tuple(data.get("pending_claims", [])),
            evidence_graph=dict(data.get("evidence_graph", {})),
            parent_checkpoint_id=data.get("parent_checkpoint_id"),
            is_incremental=bool(data.get("is_incremental", False)),
            delta=dict(data.get("delta", {})),
        )


class DurableCheckpointStore:
    """ACID SQLite storage for durable checkpoints."""

    def __init__(self, workspace_dir: str, db_path: Optional[str] = None):
        self.workspace_dir = os.path.abspath(workspace_dir)
        self.db_path = db_path or os.path.join(self.workspace_dir, ".sclass", "checkpoints", "checkpoints.db")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        return conn

    def _init_db(self) -> None:
        try:
            with self._get_conn() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS checkpoints (
                        checkpoint_id TEXT PRIMARY KEY,
                        repo_head TEXT,
                        working_tree_fingerprint TEXT,
                        ledger_head TEXT,
                        active_task_id TEXT,
                        verified_tasks TEXT,
                        failed_claims TEXT,
                        blockers TEXT,
                        relevant_files TEXT,
                        next_action TEXT,
                        constraints TEXT,
                        checkpoint_hash TEXT,
                        project_truth TEXT,
                        active_leases TEXT,
                        pending_claims TEXT,
                        evidence_graph TEXT,
                        parent_checkpoint_id TEXT,
                        is_incremental INTEGER DEFAULT 0,
                        delta TEXT,
                        created_at TEXT
                    );
                """)
        except sqlite3.Error as e:
            raise HandoffIntegrityError(f"Failed to initialize checkpoint database schema at '{self.db_path}': {e}") from e

    def save(self, chk: ProjectCheckpoint) -> None:
        try:
            with self._get_conn() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO checkpoints (
                        checkpoint_id, repo_head, working_tree_fingerprint, ledger_head,
                        active_task_id, verified_tasks, failed_claims, blockers,
                        relevant_files, next_action, constraints, checkpoint_hash,
                        project_truth, active_leases, pending_claims, evidence_graph,
                        parent_checkpoint_id, is_incremental, delta, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    chk.checkpoint_id,
                    chk.repo_head,
                    chk.working_tree_fingerprint,
                    chk.ledger_head,
                    chk.active_task_id,
                    json.dumps(list(chk.verified_tasks)),
                    json.dumps(list(chk.failed_claims)),
                    json.dumps(list(chk.blockers)),
                    json.dumps(list(chk.relevant_files)),
                    chk.next_action,
                    json.dumps(list(chk.constraints)),
                    chk.checkpoint_hash,
                    json.dumps(chk.project_truth) if chk.project_truth is not None else None,
                    json.dumps(list(chk.active_leases)),
                    json.dumps(list(chk.pending_claims)),
                    json.dumps(chk.evidence_graph),
                    chk.parent_checkpoint_id,
                    1 if chk.is_incremental else 0,
                    json.dumps(chk.delta),
                    chk.created_at,
                ))
        except sqlite3.Error as e:
            raise HandoffIntegrityError(f"Failed to save checkpoint '{chk.checkpoint_id}' to SQLite: {e}") from e

    def get(self, checkpoint_id: str) -> Optional[ProjectCheckpoint]:
        try:
            with self._get_conn() as conn:
                row = conn.execute(
                    "SELECT * FROM checkpoints WHERE checkpoint_id = ?", (checkpoint_id,)
                ).fetchone()
                if not row:
                    return None
                return self._row_to_checkpoint(row)
        except sqlite3.Error as e:
            raise HandoffIntegrityError(f"Failed to retrieve checkpoint '{checkpoint_id}': {e}") from e

    def list_all(self) -> List[ProjectCheckpoint]:
        try:
            with self._get_conn() as conn:
                rows = conn.execute("SELECT * FROM checkpoints ORDER BY created_at ASC, ROWID ASC").fetchall()
                return [self._row_to_checkpoint(r) for r in rows]
        except sqlite3.Error as e:
            raise HandoffIntegrityError(f"Failed to list checkpoints: {e}") from e

    def get_latest(self) -> Optional[ProjectCheckpoint]:
        checkpoints = self.list_all()
        return checkpoints[-1] if checkpoints else None

    def _row_to_checkpoint(self, row: sqlite3.Row) -> ProjectCheckpoint:
        pt_raw = row["project_truth"]
        project_truth = json.loads(pt_raw) if pt_raw else None
        delta_raw = row["delta"]
        delta = json.loads(delta_raw) if delta_raw else {}
        evidence_graph_raw = row["evidence_graph"]
        evidence_graph = json.loads(evidence_graph_raw) if evidence_graph_raw else {}

        return ProjectCheckpoint(
            checkpoint_id=row["checkpoint_id"],
            repo_head=row["repo_head"] or "HEAD",
            working_tree_fingerprint=row["working_tree_fingerprint"] or "",
            ledger_head=row["ledger_head"] or "",
            active_task_id=row["active_task_id"],
            verified_tasks=tuple(json.loads(row["verified_tasks"] or "[]")),
            failed_claims=tuple(json.loads(row["failed_claims"] or "[]")),
            blockers=tuple(json.loads(row["blockers"] or "[]")),
            relevant_files=tuple(json.loads(row["relevant_files"] or "[]")),
            next_action=row["next_action"],
            constraints=tuple(json.loads(row["constraints"] or "[]")),
            checkpoint_hash=row["checkpoint_hash"] or "",
            created_at=row["created_at"] or "",
            project_truth=project_truth,
            active_leases=tuple(json.loads(row["active_leases"] or "[]")),
            pending_claims=tuple(json.loads(row["pending_claims"] or "[]")),
            evidence_graph=evidence_graph,
            parent_checkpoint_id=row["parent_checkpoint_id"],
            is_incremental=bool(row["is_incremental"]),
            delta=delta,
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
        project_truth: Optional[Union[Dict[str, Any], Any]] = None,
        active_leases: Optional[List[Dict[str, Any]]] = None,
        pending_claims: Optional[List[Dict[str, Any]]] = None,
        evidence_graph: Optional[Dict[str, Any]] = None,
        persist: bool = True,
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
        except Exception as e:
            raise HandoffIntegrityError(f"Ledger access failure while creating checkpoint in '{workspace_dir}': {e}") from e

        # 3. Verified tasks from state repository
        verified_task_ids = []
        try:
            repo = StateRepository(ws)
            tasks = repo.list_tasks()
            verified_task_ids = [t.task_id for t in tasks if getattr(t, "state", None) in (TaskState.VERIFIED, "VERIFIED", "verified")]
        except Exception as e:
            raise HandoffIntegrityError(f"Database access failure while creating checkpoint in '{workspace_dir}': {e}") from e

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

        # Handle project_truth if passed as ProjectTruth instance
        truth_dict = None
        if project_truth is not None:
            if hasattr(project_truth, "to_dict"):
                truth_dict = project_truth.to_dict()
            elif isinstance(project_truth, dict):
                truth_dict = project_truth

        chk = ProjectCheckpoint(
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
            project_truth=truth_dict,
            active_leases=tuple(active_leases or []),
            pending_claims=tuple(pending_claims or []),
            evidence_graph=evidence_graph or {},
        )

        if persist:
            store = DurableCheckpointStore(ws)
            store.save(chk)

        return chk

    @classmethod
    def save_checkpoint(cls, workspace_dir: str, checkpoint: ProjectCheckpoint) -> None:
        """Persists a ProjectCheckpoint directly to SQLite store."""
        store = DurableCheckpointStore(workspace_dir)
        store.save(checkpoint)

    @classmethod
    def get_checkpoint(cls, workspace_dir: str, checkpoint_id: str) -> Optional[ProjectCheckpoint]:
        """Loads a checkpoint from SQLite store by ID."""
        store = DurableCheckpointStore(workspace_dir)
        return store.get(checkpoint_id)

    @classmethod
    def list_checkpoints(cls, workspace_dir: str) -> List[ProjectCheckpoint]:
        """Lists all checkpoints from SQLite store in chronological order."""
        store = DurableCheckpointStore(workspace_dir)
        return store.list_all()

    @classmethod
    def create_incremental_checkpoint(
        cls,
        workspace_dir: str,
        base_checkpoint_id: str,
        checkpoint_id: str = "",
        active_task_id: Optional[str] = None,
        blockers: Optional[List[str]] = None,
        relevant_files: Optional[List[str]] = None,
        next_action: Optional[str] = None,
        constraints: Optional[List[str]] = None,
        repo_head: str = "HEAD",
        project_truth: Optional[Union[Dict[str, Any], Any]] = None,
        active_leases: Optional[List[Dict[str, Any]]] = None,
        pending_claims: Optional[List[Dict[str, Any]]] = None,
        evidence_graph: Optional[Dict[str, Any]] = None,
    ) -> ProjectCheckpoint:
        """Creates an incremental checkpoint storing only deltas from a base checkpoint."""
        ws = os.path.abspath(workspace_dir)
        base = cls.get_checkpoint(ws, base_checkpoint_id)
        if not base:
            raise HandoffIntegrityError(f"Base checkpoint '{base_checkpoint_id}' not found for incremental checkpoint.")

        # Reconstruct base if it was incremental
        resolved_base = cls.resolve_checkpoint(ws, base_checkpoint_id)

        cid = checkpoint_id or f"chk_inc_{hashlib.sha256(os.urandom(16)).hexdigest()[:12]}"
        snapshot = compute_workspace_snapshot(ws)
        fp = compute_workspace_fingerprint(snapshot)

        ledger_head = ""
        try:
            ledger = LocalLedger(workspace_dir=ws)
            ledger_head = ledger.get_head_hash() or ""
        except Exception:
            ledger_head = resolved_base.ledger_head

        # Derive verified tasks
        verified_task_ids = []
        try:
            repo = StateRepository(ws)
            tasks = repo.list_tasks()
            verified_task_ids = [t.task_id for t in tasks if getattr(t, "state", None) in (TaskState.VERIFIED, "VERIFIED", "verified")]
        except Exception:
            verified_task_ids = list(resolved_base.verified_tasks)

        blks = tuple(blockers if blockers is not None else list(resolved_base.blockers))
        rel_files = tuple(relevant_files if relevant_files is not None else list(resolved_base.relevant_files))
        cons = tuple(constraints if constraints is not None else list(resolved_base.constraints))
        v_tasks = tuple(verified_task_ids)

        truth_dict = None
        if project_truth is not None:
            if hasattr(project_truth, "to_dict"):
                truth_dict = project_truth.to_dict()
            elif isinstance(project_truth, dict):
                truth_dict = project_truth

        # Compute delta
        base_v_tasks = set(resolved_base.verified_tasks)
        new_v_tasks = [t for t in v_tasks if t not in base_v_tasks]

        base_files = set(resolved_base.relevant_files)
        new_files = [f for f in rel_files if f not in base_files]

        delta = {
            "new_verified_tasks": new_v_tasks,
            "new_files": new_files,
            "fingerprint_change": (resolved_base.working_tree_fingerprint != fp),
        }

        payload = (
            f"{cid}|{repo_head}|{fp}|"
            f"{ledger_head}|{active_task_id}|{','.join(v_tasks)}|"
            f"{','.join(blks)}|{','.join(rel_files)}|{next_action}|{base_checkpoint_id}|True"
        )
        chk_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

        chk = ProjectCheckpoint(
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
            project_truth=truth_dict,
            active_leases=tuple(active_leases or []),
            pending_claims=tuple(pending_claims or []),
            evidence_graph=evidence_graph or {},
            parent_checkpoint_id=base_checkpoint_id,
            is_incremental=True,
            delta=delta,
        )

        store = DurableCheckpointStore(ws)
        store.save(chk)
        return chk

    @classmethod
    def resolve_checkpoint(cls, workspace_dir: str, checkpoint_id: str) -> ProjectCheckpoint:
        """
        Resolves an incremental checkpoint by recursively walking parent checkpoints
        and reconstructing the complete state.
        """
        ws = os.path.abspath(workspace_dir)
        chk = cls.get_checkpoint(ws, checkpoint_id)
        if not chk:
            raise HandoffIntegrityError(f"Checkpoint '{checkpoint_id}' not found.")

        if not chk.is_incremental or not chk.parent_checkpoint_id:
            return chk

        # Reconstruct from parent
        parent = cls.resolve_checkpoint(ws, chk.parent_checkpoint_id)

        # Merge verified tasks
        merged_v_tasks = list(parent.verified_tasks)
        for t in chk.delta.get("new_verified_tasks", []):
            if t not in merged_v_tasks:
                merged_v_tasks.append(t)
        for t in chk.verified_tasks:
            if t not in merged_v_tasks:
                merged_v_tasks.append(t)

        # Merge files
        merged_files = list(parent.relevant_files)
        for f in chk.delta.get("new_files", []):
            if f not in merged_files:
                merged_files.append(f)
        for f in chk.relevant_files:
            if f not in merged_files:
                merged_files.append(f)

        # Merge blockers
        merged_blockers = list(chk.blockers or parent.blockers)

        # Truth
        resolved_truth = chk.project_truth or parent.project_truth

        return ProjectCheckpoint(
            checkpoint_id=chk.checkpoint_id,
            repo_head=chk.repo_head or parent.repo_head,
            working_tree_fingerprint=chk.working_tree_fingerprint,
            ledger_head=chk.ledger_head or parent.ledger_head,
            active_task_id=chk.active_task_id,
            verified_tasks=tuple(merged_v_tasks),
            failed_claims=chk.failed_claims or parent.failed_claims,
            blockers=tuple(merged_blockers),
            relevant_files=tuple(merged_files),
            next_action=chk.next_action or parent.next_action,
            constraints=chk.constraints or parent.constraints,
            checkpoint_hash=chk.checkpoint_hash,
            created_at=chk.created_at,
            project_truth=resolved_truth,
            active_leases=chk.active_leases or parent.active_leases,
            pending_claims=chk.pending_claims or parent.pending_claims,
            evidence_graph=chk.evidence_graph or parent.evidence_graph,
            parent_checkpoint_id=chk.parent_checkpoint_id,
            is_incremental=chk.is_incremental,
            delta=chk.delta,
        )
