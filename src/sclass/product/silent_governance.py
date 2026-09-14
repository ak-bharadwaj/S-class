"""
S-Class Silent Governance Mode (RC.12).

Runs S-Class transparently underneath the developer's normal workflow.
Features:
- Configurable notification thresholds: only surface to developer when risk exceeds threshold.
- Noise event suppression: filters out routine read actions, heartbeats, and non-breaking diagnostics.
- Transparent authorization interception: executes security checks and evidence recording silently.
"""

from __future__ import annotations
import os
import time
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

from sclass.domain.action import ActionRequest, AuthorizationDecision
from sclass.control.authorization import authorize


class SilentGovernanceMode(str, Enum):
    """Operational mode for developer visibility."""
    SILENT = "silent"                    # Complete silence; only surface fatal invariant breaches
    SURFACE_ANOMALIES = "surface_anomalies" # Default; surface only when risk >= threshold or action denied
    INTERACTIVE = "interactive"          # Surface prompts for every approval boundary


@dataclass
class GovernanceEvent:
    """Record of a governed action."""
    action: str
    target: str
    decision: str
    risk_score: float
    surfaced: bool
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    reason: Optional[str] = None


class SilentGovernanceController:
    """
    Transparent governance controller that intercepts actions and filters noise,
    alerting the user only when risk demands attention.
    """

    def __init__(
        self,
        workspace_dir: str,
        mode: SilentGovernanceMode = SilentGovernanceMode.SURFACE_ANOMALIES,
        risk_threshold: float = 0.6,
    ):
        self.workspace_dir = os.path.abspath(workspace_dir)
        self.mode = mode if isinstance(mode, SilentGovernanceMode) else SilentGovernanceMode(mode)
        self.risk_threshold = float(risk_threshold)

        self.total_actions: int = 0
        self.silenced_actions: int = 0
        self.surfaced_actions: int = 0
        self.blocked_actions: int = 0
        self.noise_events_suppressed: int = 0
        self.audit_trail: List[GovernanceEvent] = []

    def suppress_noise(self, event_type: str, payload: Optional[Dict[str, Any]] = None) -> bool:
        """
        Determines if a low-value event (e.g. heartbeat, routine file read, debug ping)
        should be suppressed from user notifications.
        """
        evt = str(event_type).strip().lower()
        payload = payload or {}

        noise_keywords = [
            "heartbeat", "liveness", "ping", "read_file", "dir_list",
            "git_status", "status_check", "view_file", "query_search"
        ]
        if any(k in evt for k in noise_keywords):
            self.noise_events_suppressed += 1
            return True

        if payload.get("is_read_only", False) or payload.get("risk_level") == "low":
            self.noise_events_suppressed += 1
            return True

        return False

    def should_surface(
        self,
        action_request: ActionRequest,
        decision: AuthorizationDecision,
        risk_score: float = 0.0,
    ) -> bool:
        """
        Evaluates whether an action decision should surface to the user.
        """
        # If action was blocked / denied
        is_denied = not decision.allow

        if self.mode == SilentGovernanceMode.SILENT:
            # Only surface fatal / critical safety stops
            return is_denied and risk_score >= 0.8

        if self.mode == SilentGovernanceMode.SURFACE_ANOMALIES:
            # Surface if blocked, or if risk exceeds threshold
            if is_denied:
                return True
            if risk_score >= self.risk_threshold:
                return True
            # Surface destructive commands
            target_str = f"{action_request.action} {action_request.target}".lower()
            if any(k in target_str for k in ("rm -rf", "delete_all", "drop table", "truncate", "format")):
                return True
            return False

        if self.mode == SilentGovernanceMode.INTERACTIVE:
            return is_denied or risk_score >= 0.2

        return False

    def govern_action(
        self,
        action_request: ActionRequest,
        risk_score: float = 0.0,
    ) -> Tuple[AuthorizationDecision, bool, Optional[str]]:
        """
        Silently governs an incoming ActionRequest.
        Returns:
            (AuthorizationDecision, surfaced_to_user: bool, notification_message: Optional[str])
        """
        self.total_actions += 1

        # Transparently authorize
        decision = authorize(action_request, mode="enforce", workspace_dir=self.workspace_dir)

        if not decision.allow:
            self.blocked_actions += 1

        # Check surfacing policy
        surfaced = self.should_surface(action_request, decision, risk_score)

        notification_msg: Optional[str] = None
        if surfaced:
            self.surfaced_actions += 1
            if not decision.allow:
                notification_msg = (
                    f"[S-Class Alert] Action BLOCKED: '{action_request.action} {action_request.target}'. "
                    f"Reason: {decision.reason or 'Policy boundary violation'}"
                )
            else:
                notification_msg = (
                    f"[S-Class Notice] Elevated risk action executed (risk={risk_score:.2f}): "
                    f"'{action_request.action} {action_request.target}'"
                )
        else:
            self.silenced_actions += 1

        # Record in audit trail
        record = GovernanceEvent(
            action=action_request.action,
            target=action_request.target,
            decision="ALLOW" if decision.allow else "DENY",
            risk_score=risk_score,
            surfaced=surfaced,
            reason=decision.reason,
        )
        self.audit_trail.append(record)

        return decision, surfaced, notification_msg

    def get_governance_metrics(self) -> Dict[str, Any]:
        """Returns governance operational metrics and noise suppression ratio."""
        suppression_ratio = (
            round(self.silenced_actions / self.total_actions, 4)
            if self.total_actions > 0 else 1.0
        )
        return {
            "total_actions": self.total_actions,
            "silenced_actions": self.silenced_actions,
            "surfaced_actions": self.surfaced_actions,
            "blocked_actions": self.blocked_actions,
            "noise_events_suppressed": self.noise_events_suppressed,
            "suppression_ratio": suppression_ratio,
            "mode": self.mode.value,
            "risk_threshold": self.risk_threshold,
        }
