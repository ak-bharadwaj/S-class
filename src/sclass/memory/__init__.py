"""
S-Class Memory: Candidate memory abstractions and providers.
Enforces Invariant L10: Memory is contextual, never authoritative.
"""

from sclass.memory.provider import MemoryProvider, MemoryItem, MemoryType, MemoryScope
from sclass.memory.local import LocalMemoryProvider
from sclass.memory.external import ExternalMemoryProvider
from sclass.memory.mem0_provider import Mem0Provider

__all__ = [
    "MemoryProvider",
    "MemoryItem",
    "MemoryType",
    "MemoryScope",
    "LocalMemoryProvider",
    "ExternalMemoryProvider",
    "Mem0Provider",
]
