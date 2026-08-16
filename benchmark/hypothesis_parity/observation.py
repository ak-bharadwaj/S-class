"""
S-Class EOS V11.2 - Hypothesis Parity Observation Data Model & Size Metrics.
Normalized representations of property testing executions without framework-specific objects.
"""

import sys
import json
import math
from dataclasses import dataclass, asdict, field
from typing import Dict, Any, Optional, List, Union, Callable


def compute_size(val: Any) -> Any:
    """
    Computes the canonical complexity size metric for a value.
    Returns a comparable metric (number, tuple, or list).
    """
    if val is None:
        return 0
    if isinstance(val, bool):
        return 0 if not val else 1
    if isinstance(val, int):
        return abs(val)
    if isinstance(val, float):
        if math.isnan(val):
            return 999999999.0
        if math.isinf(val):
            return 999999998.0
        return abs(val)
    if isinstance(val, (str, bytes)):
        ords = [ord(c) if isinstance(c, str) else int(c) for c in val]
        return [len(val), sum(ords)]
    if isinstance(val, (list, tuple)):
        items_size = [compute_size(x) for x in val]
        scalar_sum = sum(s if isinstance(s, (int, float)) else s[0] if isinstance(s, list) else 0 for s in items_size)
        return [len(val), scalar_sum]
    if isinstance(val, dict):
        k_sizes = [compute_size(k) for k in val.keys()]
        v_sizes = [compute_size(v) for v in val.values()]
        k_sum = sum(s if isinstance(s, (int, float)) else s[0] if isinstance(s, list) else 0 for s in k_sizes)
        v_sum = sum(s if isinstance(s, (int, float)) else s[0] if isinstance(s, list) else 0 for s in v_sizes)
        return [len(val), k_sum + v_sum]
    return len(str(val))


@dataclass
class ReplayOutcome:
    """Structured outcome from replaying a counterexample against a property."""
    reproduced_failure: bool
    exception_class: Optional[str] = None
    exception_message: Optional[str] = None
    unexpected_error: bool = False
    return_value: Optional[Any] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ObservationRecord:
    """Immutable normalized observation record emitted by a property verification engine."""
    engine_name: str
    verdict: str  # "PASS" | "FAIL" | "ERROR"
    cases_executed: int
    initial_counterexample: Optional[Dict[str, Any]] = None
    shrunk_counterexample: Optional[Dict[str, Any]] = None
    exception_class: Optional[str] = None
    exception_message: Optional[str] = None
    shrink_evaluations: Optional[int] = None  # None when reference does not expose an un-confounded shrink counter
    initial_size: Optional[Any] = None
    shrunk_size: Optional[Any] = None
    execution_time_ns: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def __post_init__(self):
        if self.initial_counterexample is not None and self.initial_size is None:
            self.initial_size = compute_size(self.initial_counterexample)
        if self.shrunk_counterexample is not None and self.shrunk_size is None:
            self.shrunk_size = compute_size(self.shrunk_counterexample)


@dataclass
class StrategySpec:
    """Canonical descriptor for search strategies across reference and candidate engines."""
    strategy_type: str  # "integers" | "floats" | "text" | "characters" | "emails" | "from_regex" | "sampled_from" | "tuples" | "lists"
    params: Dict[str, Any] = field(default_factory=dict)
    filter_fn: Optional[Callable[[Any], bool]] = None
    map_fn: Optional[Callable[[Any], Any]] = None
