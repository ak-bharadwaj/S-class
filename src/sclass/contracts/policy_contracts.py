"""Policy contracts and evaluation dataclasses."""
from dataclasses import dataclass
from typing import Dict, Any, List

@dataclass(frozen=True)
class AuthorizationRequest:
    actor_id: str
    action_type: str
    target_resource: str
    context_attributes: Dict[str, Any]

@dataclass(frozen=True)
class AuthorizationDecision:
    allowed: bool
    reason: str
    matched_policies: List[str]
    audit_hash: str
