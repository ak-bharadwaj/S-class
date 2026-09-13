"""
S-Class Control: Canonical Authorization Entrypoint.
"""

from __future__ import annotations
import os
from typing import Optional

from sclass.domain.action import ActionRequest, AuthorizationDecision
from sclass.control.policy import PolicyEngine, DefaultPolicyEngine
from sclass.state.events import EventJournal


_GLOBAL_POLICY_ENGINE: Optional[PolicyEngine] = None


def get_policy_engine() -> PolicyEngine:
    global _GLOBAL_POLICY_ENGINE
    if _GLOBAL_POLICY_ENGINE is None:
        _GLOBAL_POLICY_ENGINE = DefaultPolicyEngine()
    return _GLOBAL_POLICY_ENGINE


def set_policy_engine(engine: PolicyEngine) -> None:
    global _GLOBAL_POLICY_ENGINE
    _GLOBAL_POLICY_ENGINE = engine


def authorize(
    request: ActionRequest,
    mode: str = "enforce",
    workspace_dir: Optional[str] = None,
    engine: Optional[PolicyEngine] = None,
) -> AuthorizationDecision:
    """
    Authoritatively evaluates an ActionRequest and returns an AuthorizationDecision.
    Audit mode records decisions without interfering; enforce mode enforces decisions.
    """
    ws = os.path.abspath(workspace_dir or request.workspace or os.getcwd())
    evaluator = engine or get_policy_engine()
    decision = evaluator.evaluate(request, workspace_dir=ws, mode=mode)

    # Record authorization CloudEvent in journal
    try:
        journal = EventJournal(ws)
        event_type = "sclass.action.authorized" if decision.is_allowed else "sclass.action.denied"
        journal.append(
            event_type=event_type,
            subject=f"action:{request.tool}:{request.action}",
            data={
                "request": request.to_dict(),
                "decision": decision.to_dict(),
                "mode": mode,
            },
        )
    except Exception:
        pass

    return decision
