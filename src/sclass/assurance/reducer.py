"""
S-Class Assurance: Canonical State Reducer.
Governs state reduction from independent evidence receipts to verified claims.
Direct promotion without fresh evidence receipts is strictly prevented.
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional
from sclass.domain.project import VerifiedProjectState
from sclass.trust.state_reducer import StateReducer

__all__ = ["VerifiedProjectState", "StateReducer"]
