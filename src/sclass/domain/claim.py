"""
S-Class Domain: Claim, ClaimType, and ClaimScope.
Represents agent-asserted propositions and their explicit target boundaries.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, Optional, List, Tuple, Union


class ClaimType(str, Enum):
    """Explicit claim categories per S-Class verification matrix."""
    EXECUTION = "execution"
    FILE_CHANGE = "file_change"
    BUILD = "build"
    TEST_PASS = "test_pass"
    TEST_COVERAGE = "test_coverage"
    TYPECHECK = "typecheck"
    LINT = "lint"
    SECURITY = "security"
    BEHAVIOR = "behavior"
    FEATURE = "feature"
    CORRECTNESS = "correctness"
    DOCUMENTATION = "documentation"
    DEPLOYMENT = "deployment"
    GIT = "git"
    # Legacy compatibility aliases
    BUG_FIX = "bug_fix"
    COMPLETION = "completion"


class ClaimStatus(str, Enum):
    """Authoritative lifecycle state of a claim (Section 14)."""
    PROPOSED = "PROPOSED"
    SUPPORTED = "SUPPORTED"
    VERIFIED = "VERIFIED"
    STALE = "STALE"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    SUPERSEDED = "SUPERSEDED"


_VALID_CLAIM_TRANSITIONS = {
    ClaimStatus.PROPOSED: {ClaimStatus.SUPPORTED, ClaimStatus.BLOCKED, ClaimStatus.FAILED, ClaimStatus.SUPERSEDED, ClaimStatus.VERIFIED},
    ClaimStatus.SUPPORTED: {ClaimStatus.VERIFIED, ClaimStatus.FAILED, ClaimStatus.BLOCKED, ClaimStatus.SUPERSEDED, ClaimStatus.STALE},
    ClaimStatus.VERIFIED: {ClaimStatus.STALE, ClaimStatus.SUPERSEDED, ClaimStatus.FAILED},
    ClaimStatus.STALE: {ClaimStatus.SUPPORTED, ClaimStatus.PROPOSED, ClaimStatus.FAILED, ClaimStatus.SUPERSEDED, ClaimStatus.VERIFIED},
    ClaimStatus.FAILED: {ClaimStatus.PROPOSED, ClaimStatus.SUPPORTED, ClaimStatus.SUPERSEDED},
    ClaimStatus.BLOCKED: {ClaimStatus.PROPOSED, ClaimStatus.SUPPORTED, ClaimStatus.SUPERSEDED},
    ClaimStatus.SUPERSEDED: set(),
}


def validate_claim_transition(current: Union[ClaimStatus, str], target: Union[ClaimStatus, str]) -> None:
    c = ClaimStatus(current) if isinstance(current, str) else current
    t = ClaimStatus(target) if isinstance(target, str) else target
    if c == t:
        return
    allowed = _VALID_CLAIM_TRANSITIONS.get(c, set())
    if t not in allowed:
        from sclass.core.errors import SecurityViolationError
        raise SecurityViolationError(f"Invalid claim transition from {c.value} to {t.value}")



@dataclass(frozen=True)
class ClaimScope:
    """Explicit target paths and test targets that the claim purports to cover."""
    paths: tuple[str, ...] = field(default_factory=tuple)
    test_targets: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "paths": list(self.paths),
            "test_targets": list(self.test_targets),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ClaimScope:
        return cls(
            paths=tuple(data.get("paths", [])),
            test_targets=tuple(data.get("test_targets", [])),
        )


@dataclass(frozen=True)
class Claim:
    """An agent-asserted proposition regarding task completion or work done."""
    claim_id: str
    task_id: str
    statement: str
    claim_type: str = ClaimType.TEST_PASS.value
    requested_verifier: Optional[str] = None
    target_files: tuple[str, ...] = field(default_factory=tuple)
    scope: Optional[ClaimScope] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)
    verifier: Optional[str] = None
    status: ClaimStatus = ClaimStatus.PROPOSED
    evidence_receipt_ids: tuple[str, ...] = field(default_factory=tuple)
    dependencies: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self):
        # Bi-directional sync for verifier and requested_verifier
        if self.requested_verifier is None and self.verifier is not None:
            object.__setattr__(self, "requested_verifier", self.verifier)
        elif self.verifier is None and self.requested_verifier is not None:
            object.__setattr__(self, "verifier", self.requested_verifier)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "task_id": self.task_id,
            "statement": self.statement,
            "claim_type": self.claim_type,
            "verifier": self.verifier,
            "requested_verifier": self.requested_verifier,
            "status": self.status.value if isinstance(self.status, ClaimStatus) else str(self.status),
            "evidence_receipt_ids": list(self.evidence_receipt_ids),
            "dependencies": list(self.dependencies),
            "target_files": list(self.target_files),
            "scope": self.scope.to_dict() if self.scope else None,
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Claim:
        scope_data = data.get("scope")
        scope = ClaimScope.from_dict(scope_data) if scope_data else None
        st_val = data.get("status", ClaimStatus.PROPOSED.value)
        status = ClaimStatus(st_val) if st_val in ClaimStatus._value2member_map_ else ClaimStatus.PROPOSED
        return cls(
            claim_id=data["claim_id"],
            task_id=data.get("task_id", "task_default"),
            statement=data.get("statement", ""),
            claim_type=data.get("claim_type", ClaimType.TEST_PASS.value),
            verifier=data.get("verifier"),
            requested_verifier=data.get("requested_verifier", data.get("verifier")),
            status=status,
            evidence_receipt_ids=tuple(data.get("evidence_receipt_ids", [])),
            dependencies=tuple(data.get("dependencies", [])),
            target_files=tuple(data.get("target_files", [])),
            scope=scope,
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            metadata=dict(data.get("metadata", {})),
        )
