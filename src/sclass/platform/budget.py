"""
S-Class Performance Budget & Net Utility Ratio (Phase 3)

Every S-Class intervention has an overhead cost:
S-Class overhead
├── latency (ms)
├── tokens (count)
├── context (bytes)
├── tool calls (count)
├── checkpoints (count)
├── interruptions (count)
└── compute (cpu sec)

The objective is:
useful reliability gained
─────────────────────────
     S-Class overhead

not merely maximum security controls.
This is the metric that proves S-Class improves the host platform.
"""

from __future__ import annotations
import json
import math
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Union


@dataclass
class OverheadConsumption:
    """Tracks S-Class overhead consumed during task execution."""
    latency_ms: float = 0.0
    tokens: int = 0
    context_bytes: int = 0
    tool_calls: int = 0
    checkpoints: int = 0
    interruptions: int = 0
    compute_cpu_sec: float = 0.0

    def add(
        self,
        latency_ms: float = 0.0,
        tokens: int = 0,
        context_bytes: int = 0,
        tool_calls: int = 0,
        checkpoints: int = 0,
        interruptions: int = 0,
        compute_cpu_sec: float = 0.0,
    ) -> None:
        """Accumulate overhead consumption."""
        self.latency_ms += max(0.0, float(latency_ms))
        self.tokens += max(0, int(tokens))
        self.context_bytes += max(0, int(context_bytes))
        self.tool_calls += max(0, int(tool_calls))
        self.checkpoints += max(0, int(checkpoints))
        self.interruptions += max(0, int(interruptions))
        self.compute_cpu_sec += max(0.0, float(compute_cpu_sec))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "latency_ms": round(self.latency_ms, 3),
            "tokens": self.tokens,
            "context_bytes": self.context_bytes,
            "tool_calls": self.tool_calls,
            "checkpoints": self.checkpoints,
            "interruptions": self.interruptions,
            "compute_cpu_sec": round(self.compute_cpu_sec, 4),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> OverheadConsumption:
        return cls(
            latency_ms=float(d.get("latency_ms", 0.0)),
            tokens=int(d.get("tokens", 0)),
            context_bytes=int(d.get("context_bytes", 0)),
            tool_calls=int(d.get("tool_calls", 0)),
            checkpoints=int(d.get("checkpoints", 0)),
            interruptions=int(d.get("interruptions", 0)),
            compute_cpu_sec=float(d.get("compute_cpu_sec", 0.0)),
        )


@dataclass
class ReliabilityGain:
    """Tracks useful reliability outcomes delivered by S-Class."""
    regressions_prevented: int = 0
    verification_passes: int = 0
    security_violations_blocked: int = 0
    scope_drifts_corrected: int = 0
    state_conflicts_resolved: int = 0
    accuracy_gain: float = 0.0  # 0.0 to 1.0 (e.g., 0.15 = 15% improvement in accuracy)

    def add(
        self,
        regressions_prevented: int = 0,
        verification_passes: int = 0,
        security_violations_blocked: int = 0,
        scope_drifts_corrected: int = 0,
        state_conflicts_resolved: int = 0,
        accuracy_gain: float = 0.0,
    ) -> None:
        """Accumulate reliability gains."""
        self.regressions_prevented += max(0, int(regressions_prevented))
        self.verification_passes += max(0, int(verification_passes))
        self.security_violations_blocked += max(0, int(security_violations_blocked))
        self.scope_drifts_corrected += max(0, int(scope_drifts_corrected))
        self.state_conflicts_resolved += max(0, int(state_conflicts_resolved))
        self.accuracy_gain = min(1.0, max(0.0, self.accuracy_gain + float(accuracy_gain)))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "regressions_prevented": self.regressions_prevented,
            "verification_passes": self.verification_passes,
            "security_violations_blocked": self.security_violations_blocked,
            "scope_drifts_corrected": self.scope_drifts_corrected,
            "state_conflicts_resolved": self.state_conflicts_resolved,
            "accuracy_gain": round(self.accuracy_gain, 4),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> ReliabilityGain:
        return cls(
            regressions_prevented=int(d.get("regressions_prevented", 0)),
            verification_passes=int(d.get("verification_passes", 0)),
            security_violations_blocked=int(d.get("security_violations_blocked", 0)),
            scope_drifts_corrected=int(d.get("scope_drifts_corrected", 0)),
            state_conflicts_resolved=int(d.get("state_conflicts_resolved", 0)),
            accuracy_gain=float(d.get("accuracy_gain", 0.0)),
        )


@dataclass(frozen=True)
class BudgetLimits:
    """Maximum permitted overhead ceilings for S-Class interventions."""
    max_latency_ms: float = 100.0
    max_tokens: int = 8192
    max_context_bytes: int = 65536
    max_tool_calls: int = 15
    max_checkpoints: int = 5
    max_interruptions: int = 2
    max_compute_cpu_sec: float = 5.0
    min_utility_ratio: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_latency_ms": self.max_latency_ms,
            "max_tokens": self.max_tokens,
            "max_context_bytes": self.max_context_bytes,
            "max_tool_calls": self.max_tool_calls,
            "max_checkpoints": self.max_checkpoints,
            "max_interruptions": self.max_interruptions,
            "max_compute_cpu_sec": self.max_compute_cpu_sec,
            "min_utility_ratio": self.min_utility_ratio,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> BudgetLimits:
        return cls(
            max_latency_ms=float(d.get("max_latency_ms", 100.0)),
            max_tokens=int(d.get("max_tokens", 8192)),
            max_context_bytes=int(d.get("max_context_bytes", 65536)),
            max_tool_calls=int(d.get("max_tool_calls", 15)),
            max_checkpoints=int(d.get("max_checkpoints", 5)),
            max_interruptions=int(d.get("max_interruptions", 2)),
            max_compute_cpu_sec=float(d.get("max_compute_cpu_sec", 5.0)),
            min_utility_ratio=float(d.get("min_utility_ratio", 1.0)),
        )


class PerformanceBudget:
    """
    S-Class Performance Budget Manager.
    
    Balances security and verification rigor against operational overhead.
    Computes Net Utility Ratio:
        Ratio = Useful Reliability Gained / S-Class Overhead
    """
    def __init__(
        self,
        limits: Optional[BudgetLimits] = None,
        consumption: Optional[OverheadConsumption] = None,
        reliability_gain: Optional[ReliabilityGain] = None,
    ):
        self.limits = limits or BudgetLimits()
        self.consumption = consumption or OverheadConsumption()
        self.reliability_gain = reliability_gain or ReliabilityGain()

    def record_overhead(
        self,
        latency_ms: float = 0.0,
        tokens: int = 0,
        context_bytes: int = 0,
        tool_calls: int = 0,
        checkpoints: int = 0,
        interruptions: int = 0,
        compute_cpu_sec: float = 0.0,
    ) -> None:
        """Record consumed S-Class overhead."""
        self.consumption.add(
            latency_ms=latency_ms,
            tokens=tokens,
            context_bytes=context_bytes,
            tool_calls=tool_calls,
            checkpoints=checkpoints,
            interruptions=interruptions,
            compute_cpu_sec=compute_cpu_sec,
        )

    def record_reliability_gain(
        self,
        regressions_prevented: int = 0,
        verification_passes: int = 0,
        security_violations_blocked: int = 0,
        scope_drifts_corrected: int = 0,
        state_conflicts_resolved: int = 0,
        accuracy_gain: float = 0.0,
    ) -> None:
        """Record verified positive reliability outcomes."""
        self.reliability_gain.add(
            regressions_prevented=regressions_prevented,
            verification_passes=verification_passes,
            security_violations_blocked=security_violations_blocked,
            scope_drifts_corrected=scope_drifts_corrected,
            state_conflicts_resolved=state_conflicts_resolved,
            accuracy_gain=accuracy_gain,
        )

    def compute_reliability_score(self) -> float:
        """
        Calculates composite useful reliability score.
        Weighted by impact:
        - Security violation blocked: 30.0
        - Regression prevented: 25.0
        - Scope drift corrected: 15.0
        - State conflict resolved: 15.0
        - Verification pass: 5.0
        - Accuracy gain: 100.0 * delta (e.g. +10% = 10.0 pts)
        """
        score = (
            self.reliability_gain.security_violations_blocked * 30.0 +
            self.reliability_gain.regressions_prevented * 25.0 +
            self.reliability_gain.scope_drifts_corrected * 15.0 +
            self.reliability_gain.state_conflicts_resolved * 15.0 +
            self.reliability_gain.verification_passes * 5.0 +
            self.reliability_gain.accuracy_gain * 100.0
        )
        return float(round(score, 3))

    def compute_overhead_score(self) -> float:
        """
        Calculates composite S-Class overhead score.
        Normalized weights:
        - Latency: 0.1 per ms (10ms = 1.0)
        - Tokens: 0.01 per token (100 tokens = 1.0)
        - Context bytes: 0.0005 per byte (2KB = 1.0)
        - Tool calls: 2.0 per tool call
        - Checkpoints: 5.0 per checkpoint
        - Interruptions: 20.0 per interruption (interruptions are expensive!)
        - Compute CPU sec: 10.0 per second
        """
        overhead = (
            self.consumption.latency_ms * 0.1 +
            self.consumption.tokens * 0.01 +
            self.consumption.context_bytes * 0.0005 +
            self.consumption.tool_calls * 2.0 +
            self.consumption.checkpoints * 5.0 +
            self.consumption.interruptions * 20.0 +
            self.consumption.compute_cpu_sec * 10.0
        )
        return float(round(overhead, 3))

    def compute_net_utility_ratio(self) -> float:
        """
        Computes Net Utility Ratio:
            useful_reliability_gained / S-Class overhead
            
        Returns ratio >= 0.0.
        If overhead is 0 and reliability > 0, returns high capped ratio (100.0).
        If both are 0, returns baseline break-even (1.0).
        """
        rel = self.compute_reliability_score()
        ovh = self.compute_overhead_score()
        if ovh <= 1e-6:
            return 100.0 if rel > 0.0 else 1.0
        return float(round(rel / ovh, 4))

    def is_within_budget(self) -> bool:
        """Returns True if all overhead dimensions are within limits."""
        return len(self.exceeded_dimensions()) == 0

    def exceeded_dimensions(self) -> List[str]:
        """Returns list of dimensions where consumption exceeded limits."""
        exceeded: List[str] = []
        if self.consumption.latency_ms > self.limits.max_latency_ms:
            exceeded.append("latency_ms")
        if self.consumption.tokens > self.limits.max_tokens:
            exceeded.append("tokens")
        if self.consumption.context_bytes > self.limits.max_context_bytes:
            exceeded.append("context_bytes")
        if self.consumption.tool_calls > self.limits.max_tool_calls:
            exceeded.append("tool_calls")
        if self.consumption.checkpoints > self.limits.max_checkpoints:
            exceeded.append("checkpoints")
        if self.consumption.interruptions > self.limits.max_interruptions:
            exceeded.append("interruptions")
        if self.consumption.compute_cpu_sec > self.limits.max_compute_cpu_sec:
            exceeded.append("compute_cpu_sec")
        return exceeded

    def budget_headroom_pct(self) -> Dict[str, float]:
        """Calculates remaining percentage headroom for each dimension."""
        headroom: Dict[str, float] = {}
        headroom["latency"] = max(0.0, 100.0 * (1.0 - (self.consumption.latency_ms / max(1.0, self.limits.max_latency_ms))))
        headroom["tokens"] = max(0.0, 100.0 * (1.0 - (self.consumption.tokens / max(1, self.limits.max_tokens))))
        headroom["context"] = max(0.0, 100.0 * (1.0 - (self.consumption.context_bytes / max(1, self.limits.max_context_bytes))))
        headroom["tool_calls"] = max(0.0, 100.0 * (1.0 - (self.consumption.tool_calls / max(1, self.limits.max_tool_calls))))
        headroom["checkpoints"] = max(0.0, 100.0 * (1.0 - (self.consumption.checkpoints / max(1, self.limits.max_checkpoints))))
        headroom["interruptions"] = max(0.0, 100.0 * (1.0 - (self.consumption.interruptions / max(1, self.limits.max_interruptions))))
        headroom["compute"] = max(0.0, 100.0 * (1.0 - (self.consumption.compute_cpu_sec / max(0.001, self.limits.max_compute_cpu_sec))))
        return {k: round(v, 1) for k, v in headroom.items()}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "limits": self.limits.to_dict(),
            "consumption": self.consumption.to_dict(),
            "reliability_gain": self.reliability_gain.to_dict(),
            "reliability_score": self.compute_reliability_score(),
            "overhead_score": self.compute_overhead_score(),
            "net_utility_ratio": self.compute_net_utility_ratio(),
            "is_within_budget": self.is_within_budget(),
            "exceeded_dimensions": self.exceeded_dimensions(),
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> PerformanceBudget:
        limits = BudgetLimits.from_dict(d.get("limits", {}))
        consumption = OverheadConsumption.from_dict(d.get("consumption", {}))
        reliability_gain = ReliabilityGain.from_dict(d.get("reliability_gain", {}))
        return cls(limits=limits, consumption=consumption, reliability_gain=reliability_gain)
