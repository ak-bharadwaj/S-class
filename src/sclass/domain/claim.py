"""
S-Class Domain: Claim and ClaimType.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, Optional, List


class ClaimType(str, Enum):
    TEST_PASS = "test_pass"
    FEATURE = "feature"
    BUG_FIX = "bug_fix"
    DOCUMENTATION = "documentation"
    COMPLETION = "completion"
    FILE_CHANGE = "file_change"


@dataclass(frozen=True)
class Claim:
    """An agent-asserted proposition regarding task completion or work done."""
    claim_id: str
    task_id: str
    statement: str
    claim_type: str = ClaimType.TEST_PASS.value
    verifier: Optional[str] = None
    target_files: tuple[str, ...] = field(default_factory=tuple)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "task_id": self.task_id,
            "statement": self.statement,
            "claim_type": self.claim_type,
            "verifier": self.verifier,
            "target_files": list(self.target_files),
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Claim:
        return cls(
            claim_id=data["claim_id"],
            task_id=data.get("task_id", "task_default"),
            statement=data.get("statement", ""),
            claim_type=data.get("claim_type", ClaimType.TEST_PASS.value),
            verifier=data.get("verifier"),
            target_files=tuple(data.get("target_files", [])),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            metadata=dict(data.get("metadata", {})),
        )
