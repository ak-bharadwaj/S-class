"""
S-Class Integration: Open Policy Agent (OPA) / Rego Client.
Provides declarative Policy-as-Code evaluation with seamless local fallback.
"""

from __future__ import annotations
import os
import json
import logging
from typing import Optional, Dict, Any
import requests

from sclass.domain.action import ActionRequest, AuthorizationDecision, DecisionOutcome
from sclass.control.policy import PolicyEngine

logger = logging.getLogger("sclass.integrations.opa")


class OPAPolicyEngine(PolicyEngine):
    """
    Evaluates policy against an OPA server (http://localhost:8181/v1/data/sclass/authz)
    or falls back to local declarative rules if the OPA server is unreachable.
    """

    def __init__(
        self,
        endpoint_url: str = "http://localhost:8181/v1/data/sclass/authz",
        timeout: float = 2.0,
        fallback_engine: Optional[PolicyEngine] = None,
    ):
        self.endpoint_url = os.environ.get("SCLASS_OPA_URL", endpoint_url)
        self.timeout = timeout
        self.fallback_engine = fallback_engine

    def evaluate(self, request: ActionRequest, mode: str = "enforce") -> AuthorizationDecision:
        """Evaluates an ActionRequest against OPA / Rego policies."""
        payload = {
            "input": {
                "agent": request.agent,
                "platform": request.platform,
                "action": request.action,
                "tool": request.tool,
                "target": request.target,
                "parameters": request.parameters,
                "workspace": request.workspace,
                "task_id": request.task_id,
                "mode": mode,
            }
        }

        try:
            resp = requests.post(self.endpoint_url, json=payload, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json().get("result", {})
                allow = data.get("allow", True)
                reason = data.get("reason", "Allowed by OPA policy")
                policy_id = data.get("policy_id", "OPA-POLICY-001")
                risk = data.get("risk_level", "low")

                if not allow:
                    outcome = DecisionOutcome.WARN if mode == "audit" else DecisionOutcome.DENY
                else:
                    outcome = DecisionOutcome.ALLOW

                return AuthorizationDecision(
                    outcome=outcome,
                    policy_id=policy_id,
                    risk_level=risk,
                    reason=reason,
                    remediation=data.get("remediation"),
                )
        except Exception as err:
            logger.debug(f"OPA server query failed: {err}. Falling back to default policy engine.")

        # Fallback to local default engine if configured
        if self.fallback_engine:
            return self.fallback_engine.evaluate(request, mode=mode)

        # Default permissive fallback if no engine provided
        return AuthorizationDecision(
            outcome=DecisionOutcome.ALLOW,
            policy_id="OPA-FALLBACK-ALLOW",
            risk_level="low",
            reason="OPA offline; permissive fallback evaluated",
        )
