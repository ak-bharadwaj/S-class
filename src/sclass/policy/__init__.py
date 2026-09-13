"""
S-Class Policy: Policy engine and authorization rules.
"""
from sclass.control.policy import PolicyEngine, DefaultPolicyEngine, OPAEngine, PolicyContext
from sclass.domain.action import ActionRequest, AuthorizationDecision, DecisionOutcome
from sclass.control.capabilities import Capability
from sclass.control.resources import ResourceKind, classify_resource
from sclass.policy.opa import OPAInputCompiler, OPAClient, OPAPolicyAdapter
from sclass.policy.authorization_service import (
    AuthorizationService,
    compute_canonical_request_hash,
    compute_canonical_capability_hash,
    verify_decision_integrity,
    generate_integrity_token,
)

# Aliases for naming consistency
InternalPolicyEngine = DefaultPolicyEngine
OPAPolicyEngine = OPAEngine
SecurityDecision = AuthorizationDecision

__all__ = [
    "PolicyEngine",
    "DefaultPolicyEngine",
    "InternalPolicyEngine",
    "OPAEngine",
    "OPAPolicyEngine",
    "OPAInputCompiler",
    "OPAClient",
    "OPAPolicyAdapter",
    "AuthorizationService",
    "compute_canonical_request_hash",
    "compute_canonical_capability_hash",
    "verify_decision_integrity",
    "generate_integrity_token",
    "PolicyContext",
    "SecurityDecision",
    "AuthorizationDecision",
    "DecisionOutcome",
    "ActionRequest",
    "Capability",
    "ResourceKind",
    "classify_resource",
]

