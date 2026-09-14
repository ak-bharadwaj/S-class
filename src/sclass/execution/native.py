"""
S-Class Execution: Native Process Execution Provider.
Deterministic baseline host execution provider operating under independent S-Class observation.
"""

from __future__ import annotations
import os
import sys
import time
from typing import Dict, Any, List, Optional

from sclass.execution.base import (
    ExecutionProvider,
    ProviderCapabilities,
    ProviderHealth,
)
from sclass.execution.modes import ExecutionMode
from sclass.execution.process import ProcessRunner, ProcessExecutionResult
from sclass.execution.sandbox import HostSandbox
from sclass.execution.launcher import HostLauncher


class NativeProcessProvider(ExecutionProvider):
    """
    Standard host process execution provider.
    Runs commands directly on the developer machine under S-Class process monitoring,
    identity capture, and cryptographic receipt emission.
    """

    def __init__(self):
        self._sandbox = HostSandbox()
        self._launcher = HostLauncher()
        self._runner = ProcessRunner(sandbox=self._sandbox, launcher=self._launcher)

    @property
    def name(self) -> str:
        return "native"

    @property
    def provider_type(self) -> str:
        return "host"

    def is_available(self) -> bool:
        return True

    def inspect_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            provider_name=self.name,
            provider_type=self.provider_type,
            network_isolation=False,
            filesystem_isolation=False,
            resource_limits=False,
            user_namespace=False,
            supported_modes=["host_argv", "host_shell"],
            runtime_path=sys.executable,
            version=sys.version.split()[0],
            metadata={
                "os": os.name,
                "platform": sys.platform,
                "architecture": sys.byteorder,
            },
        )

    def health_check(self) -> ProviderHealth:
        t0 = time.perf_counter()
        try:
            # Deterministic, non-destructive probe verifying process creation and exit capture
            res = self._runner.run(
                command=[sys.executable, "-c", "import sys; sys.exit(0)"],
                cwd=os.getcwd(),
                timeout=5.0,
                mode=ExecutionMode.HOST_ARGV,
            )
            latency = (time.perf_counter() - t0) * 1000.0
            if res.exit_code == 0:
                return ProviderHealth(
                    provider_name=self.name,
                    status="healthy",
                    is_healthy=True,
                    latency_ms=latency,
                    details={"exit_code": 0, "probe": "python_interpreter_ok"},
                )
            else:
                return ProviderHealth(
                    provider_name=self.name,
                    status="degraded",
                    is_healthy=False,
                    latency_ms=latency,
                    details={"exit_code": res.exit_code, "stderr": res.stderr},
                )
        except Exception as e:
            latency = (time.perf_counter() - t0) * 1000.0
            return ProviderHealth(
                provider_name=self.name,
                status="failed",
                is_healthy=False,
                latency_ms=latency,
                details={"error": str(e)},
            )

    def execute_raw(
        self,
        command: List[str],
        cwd: str,
        env: Optional[Dict[str, str]] = None,
        timeout: float = 60.0,
        mode: ExecutionMode = ExecutionMode.HOST_ARGV,
        task_id: Optional[str] = None,
        config: Optional[Any] = None,
        **kwargs,
    ) -> ProcessExecutionResult:
        return self._runner.run(
            command=command,
            cwd=cwd,
            env=env,
            timeout=timeout,
            mode=mode,
            task_id=task_id,
            config=config,
        )
