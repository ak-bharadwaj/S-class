"""Shared gate vocabulary for S-Class product layer.

Provides the canonical, authoritative GateState enum and GateOutput dataclass
shared across all product evaluation boundaries (F2, F3, F6, F7, and Block 2).
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class GateState(str, enum.Enum):
    """Authoritative F5 Gate State Vocabulary."""

    SATISFIED = "SATISFIED"
    MISSING = "MISSING"
    BLOCKED_ON_HUMAN = "BLOCKED_ON_HUMAN"


@dataclass(frozen=True)
class GateOutput:
    """F5 Gate Output structure compliant with gate_output.json schema.

    Superset implementation unifying F2 (predicate_evaluator) and F3 (trust_model)
    definitions, preserving string representations, equality semantics, failures,
    explain payloads, and to_dict() serialization.
    """

    state: GateState
    must_id: Optional[str] = None
    detail: Optional[str] = None
    failures: List[str] = field(default_factory=list)
    explain: Dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        if self.state == GateState.SATISFIED:
            return "SATISFIED"
        if self.must_id:
            return f"{self.state.value}[{self.must_id}]"
        return self.state.value

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, str):
            return str(self) == other
        if isinstance(other, GateOutput):
            return self.state == other.state and self.must_id == other.must_id
        return False

    def to_dict(self) -> Dict[str, Any]:
        """Serializes to dictionary conforming to gate_output.json schema."""
        fails = list(self.failures)
        if not fails and self.must_id:
            fails.append(str(self))
        exp = dict(self.explain)
        if self.detail and "detail" not in exp:
            exp["detail"] = self.detail
        return {
            "state": self.state.value,
            "failures": fails,
            "explain": exp,
        }
