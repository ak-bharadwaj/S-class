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

    def should_preserve(self, capability_or_behavior: str) -> bool:
        """Check whether S-Class must preserve (not usurp/duplicate) a native behavior."""
        target = capability_or_behavior.strip().lower()
        return any(
            target in p.lower() or p.lower() in target
            for p in self.preserve
        )

    def should_compensate(self, risk_or_gap: str) -> bool:
        """Check whether S-Class must actively compensate for a weakness or risk."""
        target = risk_or_gap.strip().lower()
        return any(
            target in c.lower() or c.lower() in target
            for c in self.compensate
        )

    def should_avoid(self, anti_pattern: str) -> bool:
        """Check whether S-Class must avoid a specific interference mode."""
        target = anti_pattern.strip().lower()
        return any(
            target in a.lower() or a.lower() in target
            for a in self.avoid_interference
        )

    def permits_interruption(self, reason: str = "general") -> bool:
        """
        Evaluate if an interruption is permitted under current policy.
        """
        policy = self.interruption_policy.lower()
        if policy == InterruptionPolicy.NEVER.value:
            return False
        if policy == InterruptionPolicy.ALWAYS.value:
            return True
        reason_lower = reason.lower()
        if policy == InterruptionPolicy.FATAL_ONLY.value:
            return "fatal" in reason_lower or "crash" in reason_lower or "corruption" in reason_lower
        if policy == InterruptionPolicy.POLICY_VIOLATION_ONLY.value:
            return "violation" in reason_lower or "unauthorized" in reason_lower or "breach" in reason_lower or "fatal" in reason_lower
        if policy == InterruptionPolicy.MILESTONE_PROMPT.value:
            return "milestone" in reason_lower or "phase" in reason_lower or "handoff" in reason_lower
        return True

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
