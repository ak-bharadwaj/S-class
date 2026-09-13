"""
S-Class Policy: Open Policy Agent (OPA) Integration Adapter.
Compiles ActionRequest and Capability contexts into structured JSON documents for Rego evaluation.
"""

from __future__ import annotations
import os
import json
import urllib.request
import urllib.error
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Union, List

from sclass.domain.action import ActionRequest, AuthorizationDecision, DecisionOutcome
from sclass.domain.capability import Capability
from sclass.control.policy import DefaultPolicyEngine


class OPAInputCompiler:
    """Compiles S-Class ActionRequest and Capability contexts into standardized OPA Rego input."""

    @classmethod
    def compile(
        cls,
        request: ActionRequest,
        workspace_dir: str = "",
        capability: Optional[Capability] = None,
        extra_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        ws = os.path.abspath(workspace_dir or request.workspace or os.getcwd())
        target_path = request.target

        is_within_ws = False
        if target_path:
            try:
                abs_target = os.path.abspath(os.path.join(ws, target_path) if not os.path.isabs(target_path) else target_path)
                ws_clean = ws.replace("\\", "/").rstrip("/")
                target_clean = abs_target.replace("\\", "/")
                is_within_ws = (target_clean == ws_clean or target_clean.startswith(ws_clean + "/"))
            except Exception:
                is_within_ws = False

        return {
            "input": {
                "request": {
                    "actor": request.actor,
                    "session": request.session,
                    "capability": request.capability,
                    "action": request.action,
                    "target": request.target,
                    "parameters": dict(request.parameters),
                    "workspace": ws,
                    "context": dict(request.context),
                    "provenance": dict(request.provenance),
                },
                "capability": capability.to_dict() if capability else None,
                "workspace": {
                    "root": ws,
                    "target_is_within": is_within_ws,
                },
                "context": dict(extra_context or {}),
                "environment": {
                    "os": os.name,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            }
        }


class OPAClient:
    """Client communicating with Open Policy Agent daemon via HTTP or local evaluation."""

    def __init__(
        self,
        endpoint_url: Optional[str] = None,
        policy_path: str = "sclass/authz",
        timeout: float = 2.0,
    ):
        base = endpoint_url or os.environ.get("SCLASS_OPA_URL", "http://localhost:8181")
        self.endpoint_url = f"{base.rstrip('/')}/v1/data/{policy_path.lstrip('/')}"
        self.timeout = timeout

    def evaluate_raw(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Posts raw input payload to OPA HTTP API."""
        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.endpoint_url,
            data=data_bytes,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)


class OPAPolicyAdapter:
    """
    S-Class PolicyEngine implementation delegating authorization decisions
    to an Open Policy Agent (OPA) server with local fail-safe fallback.
    """

    def __init__(
        self,
        client: Optional[OPAClient] = None,
        fallback_engine: Optional[Any] = None,
        allow_fallback: bool = True,
    ):
        self.client = client or OPAClient()
        self.fallback = fallback_engine or DefaultPolicyEngine()
        self.allow_fallback = allow_fallback

    def evaluate(
        self,
        request: ActionRequest,
        workspace_dir: str = "",
        capability: Optional[Capability] = None,
        mode: str = "enforce",
    ) -> AuthorizationDecision:
        ws = os.path.abspath(workspace_dir or request.workspace or os.getcwd())
        payload = OPAInputCompiler.compile(request, workspace_dir=ws, capability=capability)

        try:
            resp_data = self.client.evaluate_raw(payload)
            result = resp_data.get("result", {})

            # Support both boolean allow or dictionary result
            if isinstance(result, bool):
                allow = result
                reason = "Allowed by OPA policy" if allow else "Denied by OPA policy"
                policy_id = "OPA-AUTHZ"
            elif isinstance(result, dict):
                allow = bool(result.get("allow", True))
                reason = result.get("reason", "Allowed by OPA policy" if allow else "Denied by OPA policy")
                policy_id = result.get("policy_id", "OPA-AUTHZ")
            else:
                allow = True
                reason = "Allowed by default OPA result"
                policy_id = "OPA-AUTHZ"

            if not allow:
                return AuthorizationDecision(
                    outcome=DecisionOutcome.DENY if mode == "enforce" else DecisionOutcome.WARN,
                    policy_id=policy_id,
                    risk_level="HIGH",
                    reason=reason,
                    metadata={"opa_payload": payload},
                )

            return AuthorizationDecision(
                outcome=DecisionOutcome.ALLOW,
                policy_id=policy_id,
                risk_level="LOW",
                reason=reason,
                metadata={"opa_payload": payload},
            )

        except Exception as e:
            if self.allow_fallback:
                return self.fallback.evaluate(request, workspace_dir=ws, mode=mode)
            from sclass.core.errors import SecurityViolationError
            raise SecurityViolationError(f"OPA evaluation failed and fallback is disabled: {e}")
