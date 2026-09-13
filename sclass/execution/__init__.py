"""
S-Class Execution: Process execution, identity capture, and sandbox management.
"""

from sclass.execution.process import ProcessRunner, ProcessExecutionResult
from sclass.execution.sandbox import (
    SandboxBackend,
    HostSandbox,
    BubblewrapSandbox,
    ContainerSandbox,
    get_sandbox_backend,
)

__all__ = [
    "ProcessRunner",
    "ProcessExecutionResult",
    "SandboxBackend",
    "HostSandbox",
    "BubblewrapSandbox",
    "ContainerSandbox",
    "get_sandbox_backend",
]
