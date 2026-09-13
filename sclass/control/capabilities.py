"""
S-Class Control: Capability Classes.
Defines granular authorization capabilities for actions across workspace resources.
"""

from __future__ import annotations
from enum import Enum


class Capability(str, Enum):
    """Authoritative capability primitives for authorization decisions."""
    READ = "READ"
    WRITE = "WRITE"
    EXECUTE = "EXECUTE"
    DELETE = "DELETE"
    NETWORK = "NETWORK"
    ADMIN = "ADMIN"
    VERIFY = "VERIFY"
