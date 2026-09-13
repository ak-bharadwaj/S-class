"""
S-Class Memory: Memory Provider Protocol.
Enforces the architectural invariant:
"Memory is candidate context; S-Class verified project state is authoritative context."
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol, List, Dict, Any, Optional


@dataclass(frozen=True)
class MemoryItem:
    """Represents a candidate memory entry retrieved or remembered by an agent."""
    key: str
    content: str
    category: str = "general"  # convention, insight, decision, context
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "content": self.content,
            "category": self.category,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }


class MemoryProvider(Protocol):
    """Protocol for dynamic agent memory backends (Graphiti, Mem0, OpenMemory, Local)."""

    def remember(self, item: MemoryItem) -> None:
        """Stores candidate memory item."""
        ...

    def retrieve(self, query: str, limit: int = 5) -> List[MemoryItem]:
        """Retrieves candidate memory items matching query."""
        ...

    def forget(self, key: str) -> bool:
        """Removes memory item by key."""
        ...
