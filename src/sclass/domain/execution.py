"""
S-Class Domain: Execution Identity and Execution Modes.
Re-exports authoritative execution identity models and execution modes.
"""

from __future__ import annotations

from sclass.execution.modes import (
    ExecutionMode,
    ExecutionPolicy,
    PolicyEvaluationResult,
    check_protected_resource_targeting,
    PROTECTED_RESOURCE_PATTERNS,
)
from sclass.execution.identity import (
    ExecutionIdentity,
    ExecutionIdentityState,
    ExecutionChain,
    detect_execution_chain,
)

__all__ = [
    "ExecutionMode",
    "ExecutionPolicy",
    "PolicyEvaluationResult",
    "check_protected_resource_targeting",
    "PROTECTED_RESOURCE_PATTERNS",
    "ExecutionIdentity",
    "ExecutionIdentityState",
    "ExecutionChain",
    "detect_execution_chain",
]
