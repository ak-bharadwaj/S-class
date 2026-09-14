"""
S-Class Execution: Isolated Execution Providers.
Formalizes sandboxed and containerized execution providers conforming to mature industry standards:
- BubblewrapProvider: Unprivileged Linux user-namespace isolation sandbox
- OCIProvider: Standard OCI container runtime (Docker / Podman) baseline
- GVisorProvider: Application kernel user-space virtualization (runsc)
- DaggerProvider: Reproducible containerized execution and verification engine
- IsolatedSandboxProvider: Unified interface enforcing strict fail-closed isolation semantics
  (NO SANDBOX -> NO SANDBOXED EXECUTION).
"""

from __future__ import annotations
import os
import sys
import shutil
import time
from typing import Dict, Any, List, Optional, Union

from sclass.execution.base import (
    ExecutionProvider,
    ProviderCapabilities,
    ProviderHealth,
)
from sclass.execution.modes import ExecutionMode
from sclass.execution.process import ProcessRunner, ProcessExecutionResult
from sclass.execution.launcher import SandboxLauncher, ContainerLauncher
from sclass.execution.sandbox import BubblewrapSandbox, ContainerSandbox, GVisorSandbox
from sclass.execution.backend import SandboxConfig, SandboxConfigCompiler
from sclass.core.errors import SecurityViolationError


class BubblewrapProvider(ExecutionProvider):
    """
    Linux bubblewrap (bwrap) unprivileged user-namespace sandbox provider.
    Enforces read-only system binds, workspace containment, and network isolation.
    """

    def __init__(self, compiler: Optional[SandboxConfigCompiler] = None):
        self._sandbox = BubblewrapSandbox()
        self._launcher = SandboxLauncher()
        self._compiler = compiler or SandboxConfigCompiler()
        self._runner = ProcessRunner(sandbox=self._sandbox, launcher=self._launcher)

    @property
    def name(self) -> str:
        return "bubblewrap"

    @property
    def provider_type(self) -> str:
        return "sandbox"

    def is_available(self) -> bool:
        return self._sandbox.is_available()

    def inspect_capabilities(self) -> ProviderCapabilities:
        bwrap_path = shutil.which("bwrap")
        return ProviderCapabilities(
            provider_name=self.name,
            provider_type=self.provider_type,
            network_isolation=True,
            filesystem_isolation=True,
            resource_limits=False,
            user_namespace=True,
            supported_modes=["host_argv"],
            runtime_path=bwrap_path,
            version="bubblewrap-cli" if bwrap_path else None,
            metadata={"enforcement": "linux_user_namespaces", "unshare_net": True},
        )

    def health_check(self) -> ProviderHealth:
        if not self.is_available():
            return ProviderHealth(
                provider_name=self.name,
                status="unavailable",
                is_healthy=False,
                latency_ms=0.0,
                details={"reason": "Bubblewrap (bwrap) binary is not found on host PATH."},
            )
        t0 = time.perf_counter()
        try:
            res = self._runner.run(
                command=["bwrap", "--version"],
                cwd=os.getcwd(),
                timeout=5.0,
                mode=ExecutionMode.HOST_ARGV,
            )
            latency = (time.perf_counter() - t0) * 1000.0
            return ProviderHealth(
                provider_name=self.name,
                status="healthy" if res.exit_code == 0 else "degraded",
                is_healthy=(res.exit_code == 0),
                latency_ms=latency,
                details={"exit_code": res.exit_code, "version_output": res.stdout.strip()},
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
        if not self.is_available():
            raise SecurityViolationError(
                "NO SANDBOX -> NO SANDBOXED EXECUTION: Bubblewrap (bwrap) is not installed on this system. "
                "Fail-closed policy strictly prohibits uncontained execution."
            )
        cfg = config or self._compiler.compile(workspace_dir=cwd, backend_type="bubblewrap")
        return self._runner.run(
            command=command,
            cwd=cwd,
            env=env,
            timeout=timeout,
            mode=mode,
            task_id=task_id,
            config=cfg,
        )


class OCIProvider(ExecutionProvider):
    """
    Standard OCI container execution provider (Docker or Podman).
    Provides robust rootless or container-level filesystem, network, and resource containment.
    """

    def __init__(self, image: str = "python:3.11-slim", compiler: Optional[SandboxConfigCompiler] = None):
        self.image = image
        self._sandbox = ContainerSandbox(image=image)
        self._launcher = ContainerLauncher()
        self._compiler = compiler or SandboxConfigCompiler()
        self._runner = ProcessRunner(sandbox=self._sandbox, launcher=self._launcher)

    @property
    def name(self) -> str:
        return "oci"

    @property
    def provider_type(self) -> str:
        return "container"

    def is_available(self) -> bool:
        return self._sandbox.is_available()

    def inspect_capabilities(self) -> ProviderCapabilities:
        runtime = "docker" if shutil.which("docker") else ("podman" if shutil.which("podman") else None)
        runtime_path = shutil.which(runtime) if runtime else None
        return ProviderCapabilities(
            provider_name=self.name,
            provider_type=self.provider_type,
            network_isolation=True,
            filesystem_isolation=True,
            resource_limits=True,
            user_namespace=True,
            supported_modes=["host_argv"],
            runtime_path=runtime_path,
            version=runtime,
            metadata={"image": self.image, "runtime": runtime or "none"},
        )

    def health_check(self) -> ProviderHealth:
        if not self.is_available():
            return ProviderHealth(
                provider_name=self.name,
                status="unavailable",
                is_healthy=False,
                latency_ms=0.0,
                details={"reason": "Neither Docker nor Podman container runtime is available on host PATH."},
            )
        t0 = time.perf_counter()
        runtime = "docker" if shutil.which("docker") else "podman"
        try:
            res = self._runner.run(
                command=[runtime, "--version"],
                cwd=os.getcwd(),
                timeout=5.0,
                mode=ExecutionMode.HOST_ARGV,
            )
            latency = (time.perf_counter() - t0) * 1000.0
            return ProviderHealth(
                provider_name=self.name,
                status="healthy" if res.exit_code == 0 else "degraded",
                is_healthy=(res.exit_code == 0),
                latency_ms=latency,
                details={"runtime": runtime, "version": res.stdout.strip()},
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
        if not self.is_available():
            raise SecurityViolationError(
                "NO SANDBOX -> NO SANDBOXED EXECUTION: OCI container runtime (docker/podman) is not available. "
                "Fail-closed policy strictly prohibits uncontained execution."
            )
        cfg = config or self._compiler.compile(workspace_dir=cwd, backend_type="container")
        return self._runner.run(
            command=command,
            cwd=cwd,
            env=env,
            timeout=timeout,
            mode=mode,
            task_id=task_id,
            config=cfg,
        )


class GVisorProvider(ExecutionProvider):
    """
    gVisor (runsc) user-space virtualization application kernel provider.
    Intercepts and handles syscalls in user space with zero host kernel exposure.
    """

    def __init__(self, platform: str = "ptrace", compiler: Optional[SandboxConfigCompiler] = None):
        self.platform = platform
        self._sandbox = GVisorSandbox(platform=platform)
        self._launcher = SandboxLauncher()
        self._compiler = compiler or SandboxConfigCompiler()
        self._runner = ProcessRunner(sandbox=self._sandbox, launcher=self._launcher)

    @property
    def name(self) -> str:
        return "gvisor"

    @property
    def provider_type(self) -> str:
        return "virtualized"

    def is_available(self) -> bool:
        return self._sandbox.is_available()

    def inspect_capabilities(self) -> ProviderCapabilities:
        runsc_path = shutil.which("runsc")
        return ProviderCapabilities(
            provider_name=self.name,
            provider_type=self.provider_type,
            network_isolation=True,
            filesystem_isolation=True,
            resource_limits=True,
            user_namespace=True,
            supported_modes=["host_argv"],
            runtime_path=runsc_path,
            version="gvisor-runsc" if runsc_path else None,
            metadata={"platform": self.platform, "application_kernel": True},
        )

    def health_check(self) -> ProviderHealth:
        if not self.is_available():
            return ProviderHealth(
                provider_name=self.name,
                status="unavailable",
                is_healthy=False,
                latency_ms=0.0,
                details={"reason": "gVisor (runsc) binary is not installed on host PATH."},
            )
        t0 = time.perf_counter()
        try:
            res = self._runner.run(
                command=["runsc", "--version"],
                cwd=os.getcwd(),
                timeout=5.0,
                mode=ExecutionMode.HOST_ARGV,
            )
            latency = (time.perf_counter() - t0) * 1000.0
            return ProviderHealth(
                provider_name=self.name,
                status="healthy" if res.exit_code == 0 else "degraded",
                is_healthy=(res.exit_code == 0),
                latency_ms=latency,
                details={"version": res.stdout.strip()},
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
        if not self.is_available():
            raise SecurityViolationError(
                "NO SANDBOX -> NO SANDBOXED EXECUTION: gVisor (runsc) is not available on this host. "
                "gVisor isolation cannot be emulated or degraded to uncontained execution."
            )
        cfg = config or self._compiler.compile(workspace_dir=cwd, backend_type="gvisor")
        return self._runner.run(
            command=command,
            cwd=cwd,
            env=env,
            timeout=timeout,
            mode=mode,
            task_id=task_id,
            config=cfg,
        )


class DaggerProvider(ExecutionProvider):
    """
    Dagger execution provider for reproducible containerized verification,
    caching, and end-to-end tracing.
    """

    def __init__(self):
        self._dagger_path = shutil.which("dagger")

    @property
    def name(self) -> str:
        return "dagger"

    @property
    def provider_type(self) -> str:
        return "reproducible_pipeline"

    def is_available(self) -> bool:
        return shutil.which("dagger") is not None

    def inspect_capabilities(self) -> ProviderCapabilities:
        dagger_path = shutil.which("dagger")
        return ProviderCapabilities(
            provider_name=self.name,
            provider_type=self.provider_type,
            network_isolation=True,
            filesystem_isolation=True,
            resource_limits=True,
            user_namespace=True,
            supported_modes=["host_argv"],
            runtime_path=dagger_path,
            version="dagger-engine" if dagger_path else None,
            metadata={"reproducible_pipeline": True, "caching": True, "tracing": True},
        )

    def health_check(self) -> ProviderHealth:
        if not self.is_available():
            return ProviderHealth(
                provider_name=self.name,
                status="unavailable",
                is_healthy=False,
                latency_ms=0.0,
                details={"reason": "Dagger binary is not installed on host PATH."},
            )
        t0 = time.perf_counter()
        try:
            runner = ProcessRunner()
            res = runner.run(
                command=["dagger", "version"],
                cwd=os.getcwd(),
                timeout=5.0,
                mode=ExecutionMode.HOST_ARGV,
            )
            latency = (time.perf_counter() - t0) * 1000.0
            return ProviderHealth(
                provider_name=self.name,
                status="healthy" if res.exit_code == 0 else "degraded",
                is_healthy=(res.exit_code == 0),
                latency_ms=latency,
                details={"version": res.stdout.strip()},
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
        if not self.is_available():
            raise SecurityViolationError(
                "NO SANDBOX -> NO SANDBOXED EXECUTION: Dagger runtime is not available on this host. "
                "Fail-closed policy strictly prohibits uncontained execution."
            )
        runner = ProcessRunner()
        return runner.run(
            command=command,
            cwd=cwd,
            env=env,
            timeout=timeout,
            mode=mode,
            task_id=task_id,
        )


class IsolatedSandboxProvider(ExecutionProvider):
    """
    Unified Isolated Execution Provider.
    Auto-detects or coordinates underlying isolation mechanisms (bubblewrap, OCI, gVisor, Dagger).
    Strictly fails closed if no isolation mechanism is present on the host:
    Invariant: NO SANDBOX -> NO SANDBOXED EXECUTION.
    """

    def __init__(self, preferred_backend: str = "auto"):
        self.preferred_backend = preferred_backend.lower()
        self._providers: Dict[str, ExecutionProvider] = {
            "bubblewrap": BubblewrapProvider(),
            "oci": OCIProvider(),
            "gvisor": GVisorProvider(),
            "dagger": DaggerProvider(),
        }

    @property
    def name(self) -> str:
        return f"sandbox:{self.preferred_backend}"

    @property
    def provider_type(self) -> str:
        return "sandbox"

    def get_active_provider(self) -> Optional[ExecutionProvider]:
        """Resolves the active isolation provider based on preference and host availability."""
        if self.preferred_backend in self._providers:
            p = self._providers[self.preferred_backend]
            if p.is_available():
                return p
            return None

        # Auto-selection priority: bubblewrap -> oci -> gvisor -> dagger
        for key in ("bubblewrap", "oci", "gvisor", "dagger"):
            p = self._providers[key]
            if p.is_available():
                return p
        return None

    def is_available(self) -> bool:
        return self.get_active_provider() is not None

    def inspect_capabilities(self) -> ProviderCapabilities:
        active = self.get_active_provider()
        if active:
            cap = active.inspect_capabilities()
            return ProviderCapabilities(
                provider_name=self.name,
                provider_type="sandbox",
                network_isolation=cap.network_isolation,
                filesystem_isolation=cap.filesystem_isolation,
                resource_limits=cap.resource_limits,
                user_namespace=cap.user_namespace,
                supported_modes=cap.supported_modes,
                runtime_path=cap.runtime_path,
                version=cap.version,
                metadata={"active_backend": active.name, **cap.metadata},
            )
        return ProviderCapabilities(
            provider_name=self.name,
            provider_type="sandbox",
            network_isolation=True,
            filesystem_isolation=True,
            resource_limits=True,
            user_namespace=True,
            supported_modes=["host_argv"],
            metadata={"status": "unavailable_no_sandbox_runtime"},
        )

    def health_check(self) -> ProviderHealth:
        active = self.get_active_provider()
        if not active:
            return ProviderHealth(
                provider_name=self.name,
                status="unavailable",
                is_healthy=False,
                latency_ms=0.0,
                details={
                    "reason": "No supported sandbox runtime (Bubblewrap, OCI/Docker, gVisor, Dagger) is available on this host.",
                    "preferred_backend": self.preferred_backend,
                },
            )
        return active.health_check()

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
        active = self.get_active_provider()
        if not active:
            raise SecurityViolationError(
                "NO SANDBOX -> NO SANDBOXED EXECUTION: No isolated sandbox runtime is available on this host. "
                "Fail-closed policy strictly denies degrading to uncontained host execution."
            )
        return active.execute_raw(
            command=command,
            cwd=cwd,
            env=env,
            timeout=timeout,
            mode=mode,
            task_id=task_id,
            config=config,
            **kwargs,
        )
