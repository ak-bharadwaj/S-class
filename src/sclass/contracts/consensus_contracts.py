"""Multi-verifier consensus contracts."""
from dataclasses import dataclass
from typing import List

@dataclass(frozen=True)
class ConsensusRule:
    rule_id: str
    minimum_independent_signals: int
    required_trust_tiers: List[str]

@dataclass(frozen=True)
class ConsensusEvaluation:
    claim_id: str
    consensus_reached: bool
    corroborating_signals: int
    durable_promotion_allowed: bool
