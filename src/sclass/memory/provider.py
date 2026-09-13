"""
S-Class Memory: Memory Provider Protocol and Types.
Enforces the architectural invariant:
"Memory is candidate context; S-Class verified project state is authoritative context."
Explicitly separates contextual memories (CONTEXT, HYPOTHESIS) from VERIFIED_FACT
(which strictly requires a cryptographic evidence pointer).
"""

from __future__ import annotations
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol, List, Dict, Any, Optional


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
    A memory entry stored or retrieved by an agent or system component.
    VERIFIED_FACT entries require an authentic cryptographic evidence pointer.
    """
    key: str
    content: str
    category: str = "general"  # convention, insight, decision, context
    memory_type: str = MemoryType.CONTEXT.value
    evidence_pointer: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self) -> None:
        raw_type = self.memory_type.value if isinstance(self.memory_type, MemoryType) else str(self.memory_type)
        if raw_type == MemoryType.VERIFIED_FACT.value:
            if not self.evidence_pointer or not str(self.evidence_pointer).strip():
                raise ValueError(
                    "VERIFIED_FACT memory requires a cryptographic evidence pointer "
                    "(receipt_id, receipt_hash, or verification checkpoint)."
                )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "content": self.content,
            "category": self.category,
            "memory_type": self.memory_type.value if isinstance(self.memory_type, MemoryType) else str(self.memory_type),
            "evidence_pointer": self.evidence_pointer,
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MemoryItem:
        return cls(
            key=data["key"],
            content=data["content"],
            category=data.get("category", "general"),
            memory_type=data.get("memory_type", MemoryType.CONTEXT.value),
            evidence_pointer=data.get("evidence_pointer"),
            metadata=dict(data.get("metadata", {})),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
        )


class MemoryProvider(Protocol):
    """Protocol for agent memory backends separating contextual memories from verified facts."""

    def remember(self, item: MemoryItem) -> None:
        """Stores a candidate memory item (enforcing cryptographic pointer for VERIFIED_FACT)."""
        ...

    def recall(self, key: str) -> Optional[MemoryItem]:
        """Retrieves a specific memory item by key."""
        ...

    def search(self, query: str, limit: int = 5, memory_type: Optional[str] = None) -> List[MemoryItem]:
        """Searches memory items matching query, optionally filtered by memory_type."""
        ...

    def forget(self, key: str) -> bool:
        """Removes a memory item by key."""
        ...

    def retrieve(self, query: str, limit: int = 5) -> List[MemoryItem]:
        """Backwards-compatible retrieval alias for search."""
        ...
