"""
S-Class Execution: Process execution, identity capture, sandbox management, execution backends,
and execution providers.
"""

from sclass.execution.process import ProcessRunner, ProcessExecutionResult
from sclass.execution.sandbox import (
    SandboxBackend as SandboxProtocol,
    HostSandbox,
    BubblewrapSandbox,
    ContainerSandbox,
    GVisorSandbox,
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
from sclass.execution.base import (
    ExecutionProvider,
    ProviderCapabilities,
    ProviderHealth,
    ProviderExecutionResult,
)
from sclass.execution.native import NativeProcessProvider
from sclass.execution.isolated import (
    BubblewrapProvider,
    OCIProvider,
    GVisorProvider,
    DaggerProvider,
    IsolatedSandboxProvider,
)
from sclass.execution.registry import (
    ExecutionProviderRegistry,
    get_provider_registry,
    reset_provider_registry,
    get_execution_provider,
)

from sclass.execution.operations import (
    ReplayClass,
    OperationState,
    DurableOperation,
    OperationMetadata,
    CrossRuntimeOperation,
    CanonicalOperationStore,
    classify_replay_safety,
    compute_action_hash,
)
from sclass.execution.events import RuntimeEvent
from sclass.execution.harness import (
    RuntimeHarness,
    StepCodeHarness,
    StepCodeRpcHarness,
    ReferenceMockHarness,
    NativeHarness,
    StepCodeCommandAnalyzer,
)


__all__ = [
    "ProcessRunner",
    "ProcessExecutionResult",
    "SandboxBackend",
    "SandboxProtocol",
    "HostSandbox",
    "BubblewrapSandbox",
    "ContainerSandbox",
    "GVisorSandbox",
    "get_sandbox_backend",
    "ExecutionBackend",
    "HostProcessBackend",
    "SandboxConfig",
    "SandboxConfigCompiler",
    "get_execution_backend",
    "ExecutionProvider",
    "ProviderCapabilities",
    "ProviderHealth",
    "ProviderExecutionResult",
    "NativeProcessProvider",
    "BubblewrapProvider",
    "OCIProvider",
    "GVisorProvider",
    "DaggerProvider",
    "IsolatedSandboxProvider",
    "ExecutionProviderRegistry",
    "get_provider_registry",
    "reset_provider_registry",
    "get_execution_provider",
    "ReplayClass",
    "OperationState",
    "DurableOperation",
    "OperationMetadata",
    "CrossRuntimeOperation",
    "CanonicalOperationStore",
    "classify_replay_safety",
    "compute_action_hash",
    "RuntimeEvent",
    "RuntimeHarness",
    "StepCodeHarness",
    "StepCodeRpcHarness",
    "ReferenceMockHarness",
    "NativeHarness",
    "StepCodeCommandAnalyzer",
]

