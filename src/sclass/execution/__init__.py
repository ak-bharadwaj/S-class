"""
S-Class Execution: Process execution, identity capture, sandbox management, and execution backends.
"""

from sclass.execution.process import ProcessRunner, ProcessExecutionResult
from sclass.execution.sandbox import (
    SandboxBackend as SandboxProtocol,
    HostSandbox,
    BubblewrapSandbox,
    ContainerSandbox,
    get_sandbox_backend,
)
from sclass.execution.backend import (
    ExecutionBackend,
    HostProcessBackend,
    SandboxBackend,
    SandboxConfig,
    SandboxConfigCompiler,
    get_execution_backend,
)

__all__ = [
    "ProcessRunner",
    "ProcessExecutionResult",
    "SandboxBackend",
    "SandboxProtocol",
    "HostSandbox",
    "BubblewrapSandbox",
    "ContainerSandbox",
    "get_sandbox_backend",
    "ExecutionBackend",
    "HostProcessBackend",
    "SandboxConfig",
    "SandboxConfigCompiler",
    "get_execution_backend",
]
