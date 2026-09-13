"""
S-Class Memory: Candidate memory abstractions and providers.
"""

from sclass.memory.provider import MemoryProvider, MemoryItem
from sclass.memory.local import LocalMemoryProvider
from sclass.memory.external import ExternalMemoryProvider

__all__ = [
    "MemoryProvider",
    "MemoryItem",
    "LocalMemoryProvider",
    "ExternalMemoryProvider",
]
