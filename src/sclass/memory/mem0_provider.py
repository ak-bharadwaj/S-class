"""
S-Class Memory: Mem0 / OpenMemory Provider Integration.
Wraps Mem0 behind the S-Class MemoryProvider interface with graceful offline/local fallback.
Enforces Invariant L10: Memory is candidate context, never authoritative.
"""

from __future__ import annotations
import os
import logging
from typing import List, Dict, Any, Optional

from sclass.memory.provider import MemoryProvider, MemoryItem, MemoryType
from sclass.memory.local import LocalMemoryProvider

logger = logging.getLogger("sclass.memory.mem0")


class Mem0Provider(MemoryProvider):
    """
    Adapter for Mem0 / OpenMemory backends.
    Gracefully falls back to LocalMemoryProvider when Mem0 is not installed or offline.
    Guarantees L10: items extracted from Mem0 are candidate context only and never authoritative.
    """

    def __init__(
        self,
        workspace_dir: str,
        config: Optional[Dict[str, Any]] = None,
        client: Optional[Any] = None,
    ):
        self.workspace_dir = os.path.abspath(workspace_dir)
        self.config = config or {}
        self._fallback = LocalMemoryProvider(workspace_dir)
        self.is_fallback = False
        self.client = client

        if self.client is None:
            try:
                # Attempt to import and instantiate official Mem0 SDK
                import mem0
                memory_cls = getattr(mem0, "Memory", None)
                if memory_cls:
                    self.client = memory_cls.from_config(self.config) if self.config else memory_cls()
                else:
                    self.is_fallback = True
            except (ImportError, Exception) as exc:
                logger.debug(f"Mem0 not installed or initialization failed: {exc}. Operating in graceful fallback mode.")
                self.is_fallback = True
        else:
            self.is_fallback = False

    def store(self, item: MemoryItem) -> None:
        """Stores a candidate memory item. Invariant L10: never authoritative."""
        if item.is_authoritative:
            raise ValueError("L10 Invariant Violation: Memory cannot assert authoritative project truth.")

        # Always store in local SQLite fallback as durable backing and cache
        self._fallback.store(item)

        if not self.is_fallback and self.client is not None:
            try:
                # Add to Mem0 client
                messages = [{"role": "user", "content": item.content}]
                meta = dict(item.metadata)
                meta["key"] = item.key
                meta["category"] = item.category
                meta["memory_type"] = item.memory_type
                if item.evidence_pointer:
                    meta["evidence_pointer"] = item.evidence_pointer
                self.client.add(messages, user_id=meta.get("user_id", "sclass"), metadata=meta)
            except Exception as exc:
                logger.warning(f"Mem0 client add failed: {exc}, relied on local fallback.")

    def remember(self, item: MemoryItem) -> None:
        """Alias for store()."""
        self.store(item)

    def recall(self, key: str) -> Optional[MemoryItem]:
        """Retrieves a specific memory item by key."""
        return self._fallback.recall(key)

    def query(
        self,
        query: str,
        limit: int = 5,
        memory_type: Optional[str] = None,
        min_relevance: float = 0.0,
    ) -> List[MemoryItem]:
        """Queries memories. Falls back to local SQLite provider or uses Mem0 search if available."""
        if not self.is_fallback and self.client is not None:
            try:
                raw_results = self.client.search(query, user_id=self.config.get("user_id", "sclass"), limit=limit)
                items: List[MemoryItem] = []
                if isinstance(raw_results, list):
                    for r in raw_results:
                        if isinstance(r, dict):
                            content = r.get("memory", r.get("text", r.get("content", "")))
                            meta = r.get("metadata", {})
                            key = meta.get("key", r.get("id", f"mem_{hash(content)}"))
                            cat = meta.get("category", "general")
                            m_type = meta.get("memory_type", MemoryType.CONTEXT.value)
                            ev_ptr = meta.get("evidence_pointer")
                            items.append(
                                MemoryItem(
                                    key=key,
                                    content=content,
                                    category=cat,
                                    memory_type=m_type,
                                    evidence_pointer=ev_ptr,
                                    metadata=meta,
                                    is_authoritative=False,  # L10 enforced
                                )
                            )
                if items:
                    if memory_type:
                        m_type_val = memory_type.value if isinstance(memory_type, MemoryType) else str(memory_type)
                        items = [it for it in items if it.memory_type == m_type_val]
                    return items[:limit]
            except Exception as exc:
                logger.warning(f"Mem0 client search failed: {exc}, falling back to local SQLite.")

        return self._fallback.query(
            query=query,
            limit=limit,
            memory_type=memory_type,
            min_relevance=min_relevance,
        )

    def search(
        self,
        query: str,
        limit: int = 5,
        memory_type: Optional[str] = None,
    ) -> List[MemoryItem]:
        """Alias for query()."""
        return self.query(query=query, limit=limit, memory_type=memory_type)

    def retrieve(self, query: str, limit: int = 5) -> List[MemoryItem]:
        """Alias for query()."""
        return self.query(query=query, limit=limit)

    def invalidate(self, key_or_pattern: str) -> int:
        """Invalidates memories matching key or pattern."""
        count = self._fallback.invalidate(key_or_pattern)
        if not self.is_fallback and self.client is not None:
            try:
                if hasattr(self.client, "delete"):
                    self.client.delete(memory_id=key_or_pattern)
            except Exception as exc:
                logger.debug(f"Mem0 delete failed: {exc}")
        return count

    def forget(self, key: str) -> bool:
        """Removes a memory item by exact key."""
        return self.invalidate(key) > 0

    def prune(self, before_timestamp: Optional[str] = None, expired_only: bool = True) -> int:
        """Prunes expired or old memories via fallback SQLite storage."""
        return self._fallback.prune(before_timestamp=before_timestamp, expired_only=expired_only)

    def health(self) -> Dict[str, Any]:
        """Returns health report indicating whether Mem0 is native or running in local fallback."""
        fb_health = self._fallback.health()
        return {
            "status": "ok" if not self.is_fallback else "fallback_offline",
            "provider": "mem0",
            "is_fallback": self.is_fallback,
            "mem0_installed": not self.is_fallback,
            "backend": "mem0_client" if not self.is_fallback else "local_sqlite",
            "healthy": True,
            "item_count": fb_health.get("item_count", 0),
            "db_path": fb_health.get("db_path"),
        }
