"""
S-Class Compensation Policy (B.3.2)

Defines what S-Class should PRESERVE, COMPENSATE for, and AVOID INTERFERING with.
The core architectural primitive:
Where should S-Class intervene, and where should it deliberately stay out of the way?
"""

from __future__ import annotations
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional, Set, Union


class ObservationLevel(str, Enum):
    """How deeply S-Class monitors the platform's internal actions."""
    PASSIVE = "passive"              # Non-intrusive stream capture, zero interruption
    SAMPLED = "sampled"              # Milestone-based or probabilistic observation
    FULL = "full"                    # Comprehensive action/tool receipt recording
    STRICT = "strict"                # Synchronous barrier on every state transition


class VerificationLevel(str, Enum):
    """Rigor of verification gating applied by S-Class."""
    MINIMAL = "minimal"              # Basic exit-code verification
    STANDARD = "standard"            # Structured test results + file integrity
    THOROUGH = "thorough"            # Mutation testing, scope proofs, lint/type checks
    CONTINUOUS = "continuous"        # Asynchronous background regression verification
    EPISTEMIC = "epistemic"          # Cryptographic claim proof required before proceeding


class CheckpointLevel(str, Enum):
    """Frequency and granularity of S-Class state checkpoints."""
    NONE = "none"                    # No checkpoints introduced by S-Class
    MILESTONE_ONLY = "milestone_only"# Only at task boundaries or explicit milestones
    ACTION_BOUNDARY = "action_boundary"# Before destructive/irreversible operations
    STATE_CHANGE = "state_change"    # On file tree mutation
    CONTINUOUS = "continuous"        # On every command tick


class InterruptionPolicy(str, Enum):
    """When S-Class is allowed to interrupt host agent execution."""
    NEVER = "never"                  # Autonomous execution, zero interruptions/prompts
    FATAL_ONLY = "fatal_only"        # Interrupt only on unrecoverable fatal failure
    POLICY_VIOLATION_ONLY = "policy_violation_only" # Interrupt only on authority boundary breach
    MILESTONE_PROMPT = "milestone_prompt" # Prompt only at milestone transitions
    ALWAYS = "always"                # Require approval on all actions


class EscalationPolicy(str, Enum):
    """Action taken when risk or policy violation is detected."""
    FAIL_CLOSED = "fail_closed"      # Halt execution immediately
    HUMAN_APPROVAL = "human_approval"# Suspend and prompt human operator
    QUARANTINE_SUBAGENT = "quarantine_subagent"# Isolate offending subagent, allow others to continue
    COMPENSATING_ACTION = "compensating_action"# Run automated rollback or fix
    WARN_AND_AUDIT = "warn_and_audit"# Emit warning to ledger and continue


@dataclass(frozen=True)
class CompensationPolicy:
    """
    S-Class Compensation Policy primitive.
    
    Explicitly articulates where S-Class intervenes and where it deliberately
    stays out of the way of the native host platform.
    """
    preserve: List[str] = field(default_factory=list)
    compensate: List[str] = field(default_factory=list)
    avoid_interference: List[str] = field(default_factory=list)
    observation_level: str = ObservationLevel.SAMPLED.value
    verification_level: str = VerificationLevel.STANDARD.value
    checkpoint_level: str = CheckpointLevel.MILESTONE_ONLY.value
    context_budget: int = 4096       # Max token overhead allowed for S-Class injected context
    interruption_policy: str = InterruptionPolicy.FATAL_ONLY.value
    escalation_policy: str = EscalationPolicy.FAIL_CLOSED.value
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.context_budget < 0:
            object.__setattr__(self, "context_budget", max(0, int(self.context_budget)))

    def should_preserve(self, capability_or_behavior: str) -> bool:
        """Check whether S-Class must preserve (not usurp/duplicate) a native behavior."""
        if not capability_or_behavior or not str(capability_or_behavior).strip():
            return False
        target = str(capability_or_behavior).strip().lower().replace("-", "_").replace(" ", "_")
        for p in self.preserve:
            norm_p = str(p).strip().lower().replace("-", "_").replace(" ", "_")
            if target == norm_p or norm_p in target:
                return True
            if target in norm_p and len(target) >= 4:
                return True
        return False

    def should_compensate(self, risk_or_gap: str) -> bool:
        """Check whether S-Class must actively compensate for a weakness or risk."""
        if not risk_or_gap or not str(risk_or_gap).strip():
            return False
        target = str(risk_or_gap).strip().lower().replace("-", "_").replace(" ", "_")
        for c in self.compensate:
            norm_c = str(c).strip().lower().replace("-", "_").replace(" ", "_")
            if target == norm_c or norm_c in target:
                return True
            if target in norm_c and len(target) >= 4:
                return True
        return False

    def should_avoid(self, anti_pattern: str) -> bool:
        """Check whether S-Class must avoid a specific interference mode."""
        if not anti_pattern or not str(anti_pattern).strip():
            return False
        target = str(anti_pattern).strip().lower().replace("-", "_").replace(" ", "_")
        for a in self.avoid_interference:
            norm_a = str(a).strip().lower().replace("-", "_").replace(" ", "_")
            if target == norm_a or norm_a in target:
                return True
            if target in norm_a and len(target) >= 4:
                return True
        return False

    def should_stay_out_of_way(self, action_or_area: str) -> bool:
        """
        Evaluate if S-Class should deliberately stay out of the way for an action or domain.
        Returns True if the behavior should be preserved or the interference avoided.
        """
        if not action_or_area or not str(action_or_area).strip():
            return False
        return self.should_preserve(action_or_area) or self.should_avoid(action_or_area)

    def should_intervene(self, action_or_area: str) -> bool:
        """
        Evaluate if S-Class should intervene in an action or domain.
        Returns True if the gap or risk is explicitly earmarked for compensation.
        """
        if not action_or_area or not str(action_or_area).strip():
            return False
        return self.should_compensate(action_or_area)

    def permits_interruption(self, reason: Optional[str] = "general") -> bool:
        """
        Evaluate if an interruption is permitted under current policy.
        """
        policy = self.interruption_policy.lower()
        if policy == InterruptionPolicy.NEVER.value:
            return False
        if policy == InterruptionPolicy.ALWAYS.value:
            return True
        if not reason or not str(reason).strip():
            return False
        reason_lower = str(reason).lower()
        if policy == InterruptionPolicy.FATAL_ONLY.value:
            return any(k in reason_lower for k in ("fatal", "crash", "corruption", "unrecoverable"))
        if policy == InterruptionPolicy.POLICY_VIOLATION_ONLY.value:
            return any(k in reason_lower for k in ("violation", "unauthorized", "breach", "fatal", "crash"))
        if policy == InterruptionPolicy.MILESTONE_PROMPT.value:
            return any(k in reason_lower for k in ("milestone", "phase", "handoff"))
        return False

    def clone_with(self, **overrides) -> CompensationPolicy:
        """Create a modified copy of this policy."""
        data = self.to_dict()
        data.update(overrides)
        return CompensationPolicy.from_dict(data)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize compensation policy to dictionary."""
        return {
            "preserve": list(self.preserve),
            "compensate": list(self.compensate),
            "avoid_interference": list(self.avoid_interference),
            "observation_level": str(self.observation_level),
            "verification_level": str(self.verification_level),
            "checkpoint_level": str(self.checkpoint_level),
            "context_budget": int(self.context_budget),
            "interruption_policy": str(self.interruption_policy),
            "escalation_policy": str(self.escalation_policy),
            "metadata": dict(self.metadata),
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize compensation policy to JSON formatted string."""
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> CompensationPolicy:
        """Construct CompensationPolicy from dictionary."""
        return cls(
            preserve=list(d.get("preserve", [])),
            compensate=list(d.get("compensate", [])),
            avoid_interference=list(d.get("avoid_interference", [])),
            observation_level=str(d.get("observation_level", ObservationLevel.SAMPLED.value)),
            verification_level=str(d.get("verification_level", VerificationLevel.STANDARD.value)),
            checkpoint_level=str(d.get("checkpoint_level", CheckpointLevel.MILESTONE_ONLY.value)),
            context_budget=int(d.get("context_budget", 4096)),
            interruption_policy=str(d.get("interruption_policy", InterruptionPolicy.FATAL_ONLY.value)),
            escalation_policy=str(d.get("escalation_policy", EscalationPolicy.FAIL_CLOSED.value)),
            metadata=dict(d.get("metadata", {})),
        )

    @classmethod
    def from_json(cls, s: str) -> CompensationPolicy:
        """Construct CompensationPolicy from JSON string."""
        return cls.from_dict(json.loads(s))
