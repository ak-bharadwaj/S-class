"""
Deterministic Replay & Audit Engine for S-Class EOS

Enforces Guarantee #6: Deterministic Replay Guarantee.
Records and verifies the immutable orchestration history log (triggering event,
verified evidence, decisions, timestamps, and resulting state) to allow complete
auditability and replay verification.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import os
import json
import logging

logger = logging.getLogger("sclass_replay")


@dataclass
class TransitionRecord:
    stepIndex: int
    fromState: str
    toState: str
    eventFired: str
    workflowProfile: str
    evidenceVerified: List[Dict[str, Any]]
    decision: Dict[str, Any]
    timestamp: str
    agent: str = "sclass_runtime"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stepIndex": self.stepIndex,
            "fromState": self.fromState,
            "toState": self.toState,
            "eventFired": self.eventFired,
            "workflowProfile": self.workflowProfile,
            "evidenceVerified": self.evidenceVerified,
            "decision": self.decision,
            "timestamp": self.timestamp,
            "agent": self.agent,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TransitionRecord":
        return cls(
            stepIndex=data["stepIndex"],
            fromState=data["fromState"],
            toState=data["toState"],
            eventFired=data["eventFired"],
            workflowProfile=data.get("workflowProfile", "full"),
            evidenceVerified=data.get("evidenceVerified", []),
            decision=data.get("decision", {}),
            timestamp=data["timestamp"],
            agent=data.get("agent", "sclass_runtime"),
        )


@dataclass
class ReplayReport:
    valid_sequence: bool
    total_steps: int
    profile_used: str
    unbroken_trajectory: bool
    evidence_verified_count: int
    errors: List[str] = field(default_factory=list)


class ReplayEngine:
    """Audits and exports deterministic replay trajectories."""

    @staticmethod
    def audit_replay(workspace_dir: Optional[str] = None) -> ReplayReport:
        """Audits the transitionHistory inside orchestration_state.json for unbroken sequence continuity."""
        cwd = workspace_dir if workspace_dir else os.getcwd()
        state_file = os.path.join(cwd, ".agents", "orchestration_state.json")

        if not os.path.exists(state_file):
            return ReplayReport(
                valid_sequence=False,
                total_steps=0,
                profile_used="unknown",
                unbroken_trajectory=False,
                evidence_verified_count=0,
                errors=[f"State file missing: {state_file}"]
            )

        try:
            with open(state_file, "r", encoding="utf-8") as f:
                sdict = json.load(f)

            history = sdict.get("transitionHistory", [])
            profile = sdict.get("workflowProfile", "full")
            errors = []
            evidence_count = 0
            unbroken = True

            prev_state = None
            for idx, rec_dict in enumerate(history):
                rec = TransitionRecord.from_dict(rec_dict)
                evidence_count += len(rec.evidenceVerified)

                # Check step index continuity
                if rec.stepIndex != idx + 1:
                    errors.append(f"Step index mismatch at index {idx}: expected {idx + 1}, got {rec.stepIndex}")
                    unbroken = False

                # Check state continuity
                if prev_state and rec.fromState != prev_state:
                    errors.append(f"State discontinuity at step {rec.stepIndex}: previous resulted in '{prev_state}', but step started from '{rec.fromState}'")
                    unbroken = False

                prev_state = rec.toState

            valid = len(errors) == 0
            return ReplayReport(
                valid_sequence=valid,
                total_steps=len(history),
                profile_used=profile,
                unbroken_trajectory=unbroken,
                evidence_verified_count=evidence_count,
                errors=errors
            )
        except Exception as e:
            return ReplayReport(
                valid_sequence=False,
                total_steps=0,
                profile_used="unknown",
                unbroken_trajectory=False,
                evidence_verified_count=0,
                errors=[f"Failed to parse transition history: {e}"]
            )

    @staticmethod
    def export_audit_trail_markdown(workspace_dir: Optional[str] = None) -> str:
        """Exports a human-readable Markdown audit report of the entire execution trajectory."""
        cwd = workspace_dir if workspace_dir else os.getcwd()
        state_file = os.path.join(cwd, ".agents", "orchestration_state.json")

        if not os.path.exists(state_file):
            return "# Execution Audit Report\n\n**Status:** State file not initialized."

        try:
            with open(state_file, "r", encoding="utf-8") as f:
                sdict = json.load(f)

            task_id = sdict.get("taskId", "N/A")
            current_phase = sdict.get("currentPhase", "N/A")
            profile = sdict.get("workflowProfile", "full")
            history = sdict.get("transitionHistory", [])

            lines = [
                "# S-Class EOS Execution Audit Trail",
                f"**Task ID:** `{task_id}`  ",
                f"**Current State:** `{current_phase}`  ",
                f"**Active Workflow Profile:** `{profile.upper()}`  ",
                f"**Total Transition Steps:** {len(history)}\n",
                "## State Transition History Log\n",
                "| Step | From State | Event Fired | To State | Evidence Verified | Timestamp |",
                "| :--- | :--- | :--- | :--- | :--- | :--- |"
            ]

            for rec_dict in history:
                rec = TransitionRecord.from_dict(rec_dict)
                ev_types = [e.get("artifact_type", "unknown") for e in rec.evidenceVerified]
                ev_str = ", ".join(ev_types) if ev_types else "None"
                lines.append(f"| {rec.stepIndex} | `{rec.fromState}` | `{rec.eventFired}` | `{rec.toState}` | `{ev_str}` | {rec.timestamp} |")

            return "\n".join(lines)
        except Exception as e:
            return f"# Execution Audit Report\n\n**Error:** Failed to generate report: {e}"
