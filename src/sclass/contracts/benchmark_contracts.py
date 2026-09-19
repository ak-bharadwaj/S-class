"""Reality Lab empirical benchmark contracts."""
from dataclasses import dataclass
from typing import Dict, Any

@dataclass(frozen=True)
class BenchmarkRunResult:
    tier: str
    scenario_id: str
    wall_clock_ms: float
    token_usage: int
    verifications_passed: int
    verifications_failed: int
    net_benefit_score: float
