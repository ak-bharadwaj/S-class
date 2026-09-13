"""
S-Class Control Plane.
Authorization, Policy, Authority Boundaries, and Secret Redaction.
"""

from sclass.control.authority import PathAuthority, PathAuthorityLevel, ResourceRef, get_path_authority
from sclass.control.secret_scanner import SecretScanner
from sclass.control.policy import PolicyEngine, DefaultPolicyEngine
from sclass.control.authorization import authorize, get_policy_engine, set_policy_engine

__all__ = [
    "PathAuthority",
    "PathAuthorityLevel",
    "ResourceRef",
    "get_path_authority",
    "SecretScanner",
    "PolicyEngine",
    "DefaultPolicyEngine",
    "authorize",
    "get_policy_engine",
    "set_policy_engine",
]
