"""
S-Class EOS V11.2 - D6 Execution Fabric Vertical Slice (§8.1, §8.3).
"""

from execution.models import (
    ExecutionStatus,
    TerminationReason,
    ResourceUsage,
    ExecutionObservation,
)
from execution.workspace import IsolatedWorkspace
from execution.backend import ExecutionBackend, BackendProcessResult
from execution.local_backend import LocalProcessBackend
from execution.provider import D6ExecutionProvider, D6ProviderRegistry
from execution.adapters.pytest_adapter import PytestExecutionProvider
from execution.gateway import D6ExecutionGateway

__all__ = [
    "ExecutionStatus",
    "TerminationReason",
    "ResourceUsage",
    "ExecutionObservation",
    "IsolatedWorkspace",
    "ExecutionBackend",
    "BackendProcessResult",
    "LocalProcessBackend",
    "D6ExecutionProvider",
    "D6ProviderRegistry",
    "PytestExecutionProvider",
    "D6ExecutionGateway",
]
