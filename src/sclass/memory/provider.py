"""
S-Class Memory: Memory Provider Protocol and Types.
Enforces the architectural invariant L10:
"Memory is candidate context, never authoritative; S-Class verified project state is authoritative."
Explicitly separates contextual memories (CONTEXT, HYPOTHESIS) from VERIFIED_FACT
(which strictly requires a cryptographic evidence pointer). Memory can suggest context,
but cannot assert or certify verified project truth.
"""

from __future__ import annotations
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Protocol, List, Dict, Any, Optional, runtime_checkable


class MemoryScope(str, Enum):
    WORKSPACE = "workspace"
    PROJECT = "project"
    SESSION = "session"
    GLOBAL = "global"


class MemoryType(str, Enum):
    CONTEXT = "context"
    HYPOTHESIS = "hypothesis"
    VERIFIED_FACT = "verified_fact"


@dataclass(frozen=True)
class MemoryItem:
    """
    A candidate memory entry stored or retrieved by an agent or system component.
    VERIFIED_FACT entries require an authentic cryptographic evidence pointer.
    Memory is strictly non-authoritative (Invariant L10).
    """
    key: str
    content: str
    category: str = "general"  # convention, insight, decision, context
    memory_type: str = MemoryType.CONTEXT.value
    evidence_pointer: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    ttl_seconds: Optional[int] = None
    expires_at: Optional[str] = None
    relevance_score: float = 1.0
    is_authoritative: bool = False

    def __post_init__(self) -> None:
        # Invariant L10: Memory is contextual, never authoritative.
        if self.is_authoritative:
            raise ValueError(
                "L10 Invariant Violation: Memory is contextual, never authoritative. "
                "Memory cannot assert or certify verified project truth."
            )

        raw_type = self.memory_type.value if isinstance(self.memory_type, MemoryType) else str(self.memory_type)
        if raw_type == MemoryType.VERIFIED_FACT.value:
            if not self.evidence_pointer or not str(self.evidence_pointer).strip():
                raise ValueError(
                    "VERIFIED_FACT memory requires a cryptographic evidence pointer "
                    "(receipt_id, receipt_hash, or verification checkpoint)."
                )

        # Calculate expires_at from ttl_seconds if not explicitly provided
        if self.ttl_seconds is not None and self.expires_at is None:
            try:
                base_dt = datetime.fromisoformat(self.created_at.replace("Z", "+00:00"))
            except Exception:
                base_dt = datetime.now(timezone.utc)
            exp = base_dt + timedelta(seconds=max(0, int(self.ttl_seconds)))
            object.__setattr__(self, "expires_at", exp.astimezone(timezone.utc).isoformat())
        elif self.expires_at is not None:
            try:
                exp_dt = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
                if exp_dt.tzinfo is None:
                    exp_dt = exp_dt.replace(tzinfo=timezone.utc)
                else:
                    exp_dt = exp_dt.astimezone(timezone.utc)
                object.__setattr__(self, "expires_at", exp_dt.isoformat())
            except Exception:
                pass

    def is_expired(self, now_iso: Optional[str] = None) -> bool:
        """Check if this memory item has expired according to its TTL/expires_at."""
        if not self.expires_at:
            return False
        try:
            exp_dt = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
            now_dt = datetime.fromisoformat(now_iso.replace("Z", "+00:00")) if now_iso else datetime.now(timezone.utc)
            if exp_dt.tzinfo is None:
                exp_dt = exp_dt.replace(tzinfo=timezone.utc)
            if now_dt.tzinfo is None:
                now_dt = now_dt.replace(tzinfo=timezone.utc)
            return now_dt >= exp_dt
        except Exception:
            return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "content": self.content,
            "category": self.category,
            "memory_type": self.memory_type.value if isinstance(self.memory_type, MemoryType) else str(self.memory_type),
            "evidence_pointer": self.evidence_pointer,
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
            "ttl_seconds": self.ttl_seconds,
            "expires_at": self.expires_at,
            "relevance_score": float(self.relevance_score if self.relevance_score is not None else 1.0),
            "is_authoritative": False,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MemoryItem:
        rel_score = data.get("relevance_score")
        return cls(
            key=data["key"],
            content=data["content"],
            category=data.get("category", "general"),
            memory_type=data.get("memory_type", MemoryType.CONTEXT.value),
            evidence_pointer=data.get("evidence_pointer"),
            metadata=dict(data.get("metadata", {})),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            ttl_seconds=data.get("ttl_seconds"),
            expires_at=data.get("expires_at"),
            relevance_score=float(rel_score) if rel_score is not None else 1.0,
            is_authoritative=False,
        )


@runtime_checkable
class MemoryProvider(Protocol):
    """
    Formal protocol for S-Class memory backends.
    Strictly separates contextual memories from verified project truth (Invariant L10).
    """

    def store(self, item: MemoryItem) -> None:
        """Stores a candidate memory item (enforcing cryptographic pointer for VERIFIED_FACT)."""
        ...

    def query(
        self,
        query: str,
        limit: int = 5,
        memory_type: Optional[str] = None,
        min_relevance: float = 0.0,
    ) -> List[MemoryItem]:
        """Queries memory items matching text query, filtered by memory_type and min_relevance."""
        ...

    def invalidate(self, key_or_pattern: str) -> int:
        """Removes memory item(s) by key or glob pattern (e.g. 'auth_*'). Returns deleted count."""
        ...

    def prune(self, before_timestamp: Optional[str] = None, expired_only: bool = True) -> int:
        """Prunes expired or obsolete memories. Returns deleted count."""
        ...

    def health(self) -> Dict[str, Any]:
        """Returns provider health status, operational metrics, and connectivity."""
        ...

    # Backwards-compatibility aliases
    def remember(self, item: MemoryItem) -> None:
        """Stores a candidate memory item (alias for store)."""
        ...

    def recall(self, key: str) -> Optional[MemoryItem]:
        """Retrieves a specific memory item by exact key."""
        ...

    def search(self, query: str, limit: int = 5, memory_type: Optional[str] = None) -> List[MemoryItem]:
        """Searches memory items matching query (alias for query)."""
        ...

    def forget(self, key: str) -> bool:
        """Removes a memory item by exact key. Returns True if deleted."""
        ...

    def retrieve(self, query: str, limit: int = 5) -> List[MemoryItem]:
        """Backwards-compatible retrieval alias for search/query."""
        ...
