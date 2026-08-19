"""Materialized State Representation for S-Class D2.

MaterializedState is an immutable, canonical snapshot of all domain entities and dependency
frontiers derived deterministically from the append-only event log.
"""

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping, Optional

from domain.models import (
    Task,
    Obligation,
    Claim,
    Policy,
    Evidence,
    AssessmentReceipt,
)
from domain.dag import ObligationGraph, FrontierSnapshot


GENESIS_PARENT_DIGEST = "0" * 64


@dataclass(frozen=True)
class MaterializedState:
    """Immutable materialized state resulting from deterministic event log reduction."""
    task: Optional[Task] = None
    obligations: Mapping[str, Obligation] = field(default_factory=dict)
    claims: Mapping[str, Claim] = field(default_factory=dict)
    policies: Mapping[str, Policy] = field(default_factory=dict)
    evidence: Mapping[str, Evidence] = field(default_factory=dict)
    assessments: Mapping[str, AssessmentReceipt] = field(default_factory=dict)
    graph: ObligationGraph = field(default_factory=ObligationGraph)
    last_event_id: Optional[str] = None
    last_sequence_number: int = 0
    last_digest: str = GENESIS_PARENT_DIGEST

    def __post_init__(self):
        # Freeze internal mappings defensively
        if not isinstance(self.obligations, MappingProxyType):
            object.__setattr__(self, "obligations", MappingProxyType(dict(self.obligations)))
        if not isinstance(self.claims, MappingProxyType):
            object.__setattr__(self, "claims", MappingProxyType(dict(self.claims)))
        if not isinstance(self.policies, MappingProxyType):
            object.__setattr__(self, "policies", MappingProxyType(dict(self.policies)))
        if not isinstance(self.evidence, MappingProxyType):
            object.__setattr__(self, "evidence", MappingProxyType(dict(self.evidence)))
        if not isinstance(self.assessments, MappingProxyType):
            object.__setattr__(self, "assessments", MappingProxyType(dict(self.assessments)))

    def get_frontier(self) -> FrontierSnapshot:
        """Returns structural frontier snapshot from the obligation graph."""
        return self.graph.get_frontier()
