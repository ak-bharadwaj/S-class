"""
S-Class EOS V11.1 — Authorized ChangeSet IR (changeset_ir.py)

Defines the authoritative ChangeSet Intermediate Representation (IR).
Every code modification in S-Class must belong to an explicitly authorized ChangeSet
that is bound to an immutable planning RepositorySnapshot (source_repository_state_hash).

Hard Invariant:
Result Snapshot == Anchor Snapshot (+) Authorized ChangeSet
No file may be created, modified, or deleted without explicit task authorization in the ChangeSet.
"""

import json
import hashlib
from datetime import datetime, timezone
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from repository_snapshot import FileClassification


class FileMutationOp(str, Enum):
    CREATE = "CREATE"
    MODIFY = "MODIFY"
    DELETE = "DELETE"


@dataclass
class AuthorizedFileChange:
    file_path: str  # Normalized relative path
    operation: FileMutationOp
    authorized_by_tasks: List[str] = field(default_factory=list)
    authorized_by_lld: Optional[str] = None
    expected_source_file_hash: Optional[str] = None
    expected_target_file_hash: Optional[str] = None
    expected_classification: FileClassification = FileClassification.SOURCE
    reason: str = "Authorized by task execution specification"

    def __post_init__(self):
        self.file_path = self.file_path.replace("\\", "/").strip().lstrip("/")
        if isinstance(self.operation, str):
            self.operation = FileMutationOp(self.operation.upper())
        if isinstance(self.expected_classification, str):
            self.expected_classification = FileClassification(self.expected_classification.lower())
        if not self.authorized_by_tasks:
            raise ValueError(f"AuthorizedFileChange for '{self.file_path}' must specify at least one authorizing task.")

    def compute_canonical_hash(self) -> str:
        payload = {
            "file_path": self.file_path,
            "operation": self.operation.value,
            "authorized_by_tasks": sorted(self.authorized_by_tasks),
            "authorized_by_lld": self.authorized_by_lld or "",
            "expected_source_file_hash": self.expected_source_file_hash or "",
            "expected_target_file_hash": self.expected_target_file_hash or "",
            "expected_classification": self.expected_classification.value,
            "reason": self.reason
        }
        canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "operation": self.operation.value,
            "authorized_by_tasks": sorted(self.authorized_by_tasks),
            "authorized_by_lld": self.authorized_by_lld,
            "expected_source_file_hash": self.expected_source_file_hash,
            "expected_target_file_hash": self.expected_target_file_hash,
            "expected_classification": self.expected_classification.value,
            "reason": self.reason
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AuthorizedFileChange":
        return cls(
            file_path=d["file_path"],
            operation=FileMutationOp(d["operation"]),
            authorized_by_tasks=list(d.get("authorized_by_tasks", [])),
            authorized_by_lld=d.get("authorized_by_lld"),
            expected_source_file_hash=d.get("expected_source_file_hash"),
            expected_target_file_hash=d.get("expected_target_file_hash"),
            expected_classification=FileClassification(d.get("expected_classification", "source")),
            reason=d.get("reason", "Authorized by task execution specification")
        )


@dataclass
class AuthorizedChangeSet:
    changeset_id: str
    source_repository_state_hash: str  # Must strictly match planning snapshot repository_state_hash
    source_execution_plan_hash: str   # Must strictly match planning execution plan hash
    source_task_hashes: Dict[str, str]  # Mapping task_id -> task_content_hash
    authorized_changes: Dict[str, AuthorizedFileChange] = field(default_factory=dict)
    source_snapshot_id: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat() + "Z")
    changeset_hash: str = ""

    def __post_init__(self):
        if not self.source_repository_state_hash:
            raise ValueError("AuthorizedChangeSet must carry non-empty source_repository_state_hash.")
        if not self.source_execution_plan_hash:
            raise ValueError("AuthorizedChangeSet must carry non-empty source_execution_plan_hash.")
        if not self.source_task_hashes:
            raise ValueError("AuthorizedChangeSet must carry non-empty source_task_hashes.")
        if not self.changeset_hash:
            self.changeset_hash = self.compute_canonical_hash()

    def add_change(self, change: AuthorizedFileChange) -> None:
        norm_path = change.file_path.replace("\\", "/").strip().lstrip("/")
        self.authorized_changes[norm_path] = change
        self.changeset_hash = self.compute_canonical_hash()

    def compute_canonical_hash(self) -> str:
        sorted_keys = sorted(self.authorized_changes.keys())
        change_hashes = [
            {"path": k, "change_hash": self.authorized_changes[k].compute_canonical_hash()}
            for k in sorted_keys
        ]
        sorted_task_hashes = {k: self.source_task_hashes[k] for k in sorted(self.source_task_hashes.keys())}
        payload = {
            "changeset_id": self.changeset_id,
            "source_repository_state_hash": self.source_repository_state_hash,
            "source_execution_plan_hash": self.source_execution_plan_hash,
            "source_task_hashes": sorted_task_hashes,
            "source_snapshot_id": self.source_snapshot_id or "",
            "changes": change_hashes
        }
        canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "changeset_id": self.changeset_id,
            "source_repository_state_hash": self.source_repository_state_hash,
            "source_execution_plan_hash": self.source_execution_plan_hash,
            "source_task_hashes": {k: self.source_task_hashes[k] for k in sorted(self.source_task_hashes.keys())},
            "source_snapshot_id": self.source_snapshot_id,
            "created_at": self.created_at,
            "changeset_hash": self.changeset_hash or self.compute_canonical_hash(),
            "authorized_changes": {
                k: v.to_dict() for k, v in sorted(self.authorized_changes.items())
            }
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AuthorizedChangeSet":
        changes = {}
        raw_changes = d.get("authorized_changes", {})
        for k, v in raw_changes.items():
            norm_k = k.replace("\\", "/").strip().lstrip("/")
            changes[norm_k] = AuthorizedFileChange.from_dict(v)

        for req in ["changeset_id", "source_repository_state_hash", "source_execution_plan_hash", "source_task_hashes"]:
            if req not in d:
                raise ValueError(f"AuthorizedChangeSet missing mandatory field '{req}'")

        obj = cls(
            changeset_id=d["changeset_id"],
            source_repository_state_hash=d["source_repository_state_hash"],
            source_execution_plan_hash=d["source_execution_plan_hash"],
            source_task_hashes=dict(d["source_task_hashes"]),
            authorized_changes=changes,
            source_snapshot_id=d.get("source_snapshot_id"),
            created_at=d.get("created_at", datetime.now(timezone.utc).isoformat() + "Z"),
            changeset_hash=d.get("changeset_hash", "")
        )
        return obj

    @classmethod
    def from_governed_dict(cls, d: Dict[str, Any], strict_governance: bool = True) -> "AuthorizedChangeSet":
        """
        Fail-closed deserializer that authoritatively recomputes and checks changeset_hash and mandatory lineage.
        """
        if not isinstance(d, dict):
            raise ValueError(f"Governed AuthorizedChangeSet must be a dictionary, got {type(d)}")
        for req in ["changeset_id", "source_repository_state_hash", "source_execution_plan_hash", "source_task_hashes", "authorized_changes"]:
            if req not in d:
                raise ValueError(f"Governed AuthorizedChangeSet missing mandatory field '{req}'")

        if strict_governance:
            if "changeset_hash" not in d or not d["changeset_hash"]:
                raise ValueError("Governed AuthorizedChangeSet missing mandatory 'changeset_hash'")

        obj = cls.from_dict(d)
        if strict_governance:
            recomputed = obj.compute_canonical_hash()
            stored = d.get("changeset_hash", "")
            if stored != recomputed:
                raise ValueError(
                    f"AuthorizedChangeSet integrity violation: stored changeset_hash '{stored}' "
                    f"does not match recomputed canonical hash '{recomputed}'"
                )
        return obj
