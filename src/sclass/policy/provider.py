"""
S-Class Policy: Policy Provider Protocol and Abstract Base Class.
Defines the authoritative contract between S-Class control plane and policy backends.

Architecture:
S-Class
   │
   ▼
PolicyProvider
   │
   ▼
OPAProvider
   │
   ▼
real OPA

S-Class owns:
- request identity
- capability identity
- policy identity
- policy version
- decision provenance
- fail-closed semantics

OPA owns:
- Rego evaluation
- policy bundles
- policy distribution
- policy evaluation
"""

from __future__ import annotations
from typing import Protocol, runtime_checkable, Optional, Dict, Any
from dataclasses import dataclass

from sclass.domain.action import ActionRequest, AuthorizationDecision
from sclass.domain.capability import Capability


@dataclass(frozen=True)
class PolicyEvaluationResult:
    """Raw evaluation response from a policy provider before S-Class integrity sealing."""
    allow: bool
    policy_id: str
    policy_version: str
    risk_level: str = "LOW"
    reason: str = ""
    remediation: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@runtime_checkable
class PolicyProvider(Protocol):
    """
    Authoritative Policy Provider interface.
    Connects S-Class authorization pipeline to external policy engines (e.g. Open Policy Agent).
    Guarantees fail-closed semantics across all evaluation paths.
    """

    @property
    def provider_name(self) -> str:
        """Canonical name of the policy provider backend (e.g., 'opa', 'local')."""
        ...

    @property
    def provider_version(self) -> str:
        """Version identifier of the policy provider backend."""
        ...

    def evaluate(
        self,
        request: ActionRequest,
        workspace_dir: str = "",
        capability: Optional[Capability] = None,
        expected_policy_version: Optional[str] = None,
        mode: str = "enforce",
        timeout: Optional[float] = None,
    ) -> AuthorizationDecision:
        """
        Evaluates an ActionRequest and returns an AuthorizationDecision.
        Must enforce fail-closed semantics (ANY error, timeout, version mismatch -> DENY).
        """
        ...

    def is_healthy(self) -> bool:
        """Returns True if the backend policy service is active and responsive."""
        ...
