"""
S-Class Memory: External Provider Adapter (Graphiti, Mem0, OpenMemory).
"""

from __future__ import annotations
import logging
import requests
from typing import List, Optional

from sclass.memory.provider import MemoryProvider, MemoryItem

logger = logging.getLogger("sclass.memory.external")


class ExternalMemoryProvider(MemoryProvider):
    """Integrates external memory engines like Graphiti or Mem0 over HTTP."""

    def __init__(self, endpoint_url: str, api_key: Optional[str] = None, timeout: float = 3.0):
        self.endpoint_url = endpoint_url
        self.api_key = api_key
        self.timeout = timeout

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def remember(self, item: MemoryItem) -> None:
        try:
            requests.post(
                f"{self.endpoint_url}/remember",
                json=item.to_dict(),
                headers=self._headers(),
                timeout=self.timeout,
            )
        except Exception as exc:
            logger.debug(f"External memory store failed: {exc}")

    def retrieve(self, query: str, limit: int = 5) -> List[MemoryItem]:
        try:
            resp = requests.post(
                f"{self.endpoint_url}/retrieve",
                json={"query": query, "limit": limit},
                headers=self._headers(),
                timeout=self.timeout,
            )
            if resp.status_code == 200:
                data = resp.json().get("items", [])
                return [
                    MemoryItem(
                        key=d["key"],
                        content=d["content"],
                        category=d.get("category", "general"),
                        metadata=d.get("metadata", {}),
                        created_at=d.get("created_at"),
                    )
                    for d in data
                ]
        except Exception as exc:
            logger.debug(f"External memory retrieval failed: {exc}")
        return []

    def forget(self, key: str) -> bool:
        try:
            resp = requests.post(
                f"{self.endpoint_url}/forget",
                json={"key": key},
                headers=self._headers(),
                timeout=self.timeout,
            )
            return resp.status_code == 200
        except Exception:
            return False
