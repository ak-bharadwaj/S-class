"""
S-Class Policy: Policy engine and authorization rules.
"""
from sclass.control.policy import PolicyEngine, DefaultPolicyEngine, OPAEngine, PolicyContext
from sclass.domain.action import ActionRequest, AuthorizationDecision, DecisionOutcome
from sclass.control.capabilities import Capability
from sclass.control.resources import ResourceKind, classify_resource

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
    "PolicyContext",
    "SecurityDecision",
    "AuthorizationDecision",
    "DecisionOutcome",
    "ActionRequest",
    "Capability",
    "ResourceKind",
    "classify_resource",
]
