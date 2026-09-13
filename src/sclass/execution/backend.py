"""
S-Class Execution: Execution Backend Abstraction and Sandbox Configuration Compiler.
Defines ExecutionBackend, HostProcessBackend, and SandboxBackend (anticipating Bubblewrap, gVisor, and Containers).
"""

from __future__ import annotations
import os
import shutil
import shlex
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Union

from sclass.execution.process import ProcessRunner, ProcessExecutionResult
from sclass.execution.modes import ExecutionMode
from sclass.execution.launcher import BaseLauncher, HostLauncher, SandboxLauncher, ContainerLauncher
from sclass.execution.sandbox import HostSandbox, BubblewrapSandbox, ContainerSandbox


@dataclass
class SandboxConfig:
    """Compiled isolation constraints for sandbox execution."""
    backend_type: str = "host"  # "bubblewrap", "gvisor", "container", "host"
    read_only_binds: List[str] = field(default_factory=list)
    writable_binds: List[str] = field(default_factory=list)
    network_mode: str = "none"  # "none", "host", "bridge"
    env_whitelist: Dict[str, str] = field(default_factory=dict)
    resource_limits: Dict[str, Any] = field(default_factory=dict)
    user_namespace: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "backend_type": self.backend_type,
            "read_only_binds": list(self.read_only_binds),
            "writable_binds": list(self.writable_binds),
            "network_mode": self.network_mode,
            "env_whitelist": dict(self.env_whitelist),
            "resource_limits": dict(self.resource_limits),
            "user_namespace": self.user_namespace,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SandboxConfig:
        return cls(
            backend_type=data.get("backend_type", "host"),
            read_only_binds=list(data.get("read_only_binds", [])),
            writable_binds=list(data.get("writable_binds", [])),
            network_mode=data.get("network_mode", "none"),
            env_whitelist=dict(data.get("env_whitelist", {})),
            resource_limits=dict(data.get("resource_limits", {})),
            user_namespace=data.get("user_namespace", True),
        )


class SandboxConfigCompiler:
    """
    Compiles declarative policy, ActionRequest parameters, and workspace constraints
    into concrete sandbox isolation configurations anticipating Bubblewrap, gVisor, and Containers.
    """

    @classmethod
    def compile(
        cls,
        request: Optional[Any] = None,
        capability: Optional[Any] = None,
        workspace_dir: str = "",
        backend_type: str = "bubblewrap",
    ) -> SandboxConfig:
        ws = os.path.abspath(workspace_dir or (getattr(request, "workspace", "") if request else ""))

        # 1. Determine filesystem boundaries
        ro_binds = ["/usr", "/lib", "/lib64", "/bin", "/etc/resolv.conf"]
        wr_binds = [ws] if ws else []

        # If capability restricts filesystem
        fs_level = getattr(capability, "filesystem", "read_write") if capability else "read_write"
        if fs_level == "read" and ws in wr_binds:
            wr_binds.remove(ws)
            ro_binds.append(ws)

        # 2. Determine network isolation
        net_mode = "none"
        cap_net = getattr(capability, "network", False) if capability else False
        if cap_net in (True, "host", "internet", "local"):
            net_mode = "host"

        # 3. Environment sanitization (mask secrets unless explicitly whitelisted)
        safe_env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": os.environ.get("HOME", "/tmp"),
            "LANG": os.environ.get("LANG", "en_US.UTF-8"),
            "TERM": "xterm-256color",
        }
        allowed_creds = getattr(capability, "credentials", []) if capability else []
        for cred in allowed_creds:
            if cred in os.environ:
                safe_env[cred] = os.environ[cred]

        return SandboxConfig(
            backend_type=backend_type,
            read_only_binds=ro_binds,
            writable_binds=wr_binds,
            network_mode=net_mode,
            env_whitelist=safe_env,
            resource_limits={"timeout": 60.0, "max_memory_mb": 2048},
            user_namespace=True,
        )

    @classmethod
    def compile_bubblewrap_args(cls, config: SandboxConfig, command: List[str], cwd: str) -> List[str]:
        """Compiles bubblewrap (bwrap) invocation arguments."""
        args = ["bwrap"]
        for ro in config.read_only_binds:
            args.extend(["--ro-bind", ro, ro])
        for wr in config.writable_binds:
            args.extend(["--bind", wr, wr])

        args.extend(["--proc", "/proc", "--dev", "/dev"])
        if config.user_namespace:
            args.append("--unshare-all")

        if config.network_mode != "none":
            args.append("--share-net")

        args.extend(["--chdir", cwd])
        args.extend(command)
        return args

    @classmethod
    def compile_gvisor_args(cls, config: SandboxConfig, command: List[str], cwd: str) -> List[str]:
        """Compiles gVisor (runsc) user-space virtualization invocation arguments."""
        args = [
            "runsc",
            "--rootless",
            "--network=" + ("host" if config.network_mode != "none" else "none"),
            "exec",
            "--cwd", cwd,
        ]
        args.extend(command)
        return args

    @classmethod
    def compile_container_args(cls, config: SandboxConfig, command: List[str], cwd: str, image: str = "python:3.11-slim") -> List[str]:
        """Compiles OCI container (docker/podman) invocation arguments."""
        runtime = "docker" if shutil.which("docker") else "podman"
        args = [runtime, "run", "--rm", "-w", cwd]
        if config.network_mode == "none":
            args.extend(["--network", "none"])
        else:
            args.extend(["--network", "host"])

        for wr in config.writable_binds:
            args.extend(["-v", f"{wr}:{wr}:rw"])
        for ro in config.read_only_binds:
            args.extend(["-v", f"{ro}:{ro}:ro"])

        args.append(image)
        args.extend(command)
        return args


class ExecutionBackend(ABC):
    """
    Abstract interface for all process execution environments in S-Class.
    Decouples policy evaluation from execution isolation mechanisms.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the execution backend."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Returns True if required system dependencies for this backend are present."""
        ...

    @abstractmethod
    def execute(
        self,
        command: Union[str, List[str]],
        cwd: str,
        request: Optional[Any] = None,
        capability: Optional[Any] = None,
        env: Optional[Dict[str, str]] = None,
        timeout: float = 60.0,
        mode: ExecutionMode = ExecutionMode.HOST_ARGV,
        allow_shell: Optional[bool] = None,
        task_id: Optional[str] = None,
        **kwargs,
    ) -> ProcessExecutionResult:
        """
        Executes the command in this backend and returns authentic ProcessExecutionResult.
        """
        ...


class HostProcessBackend(ExecutionBackend):
    """
    Standard host process execution backend.
    Executes commands on the developer workstation under S-Class process monitoring.
    """

    def __init__(self, launcher: Optional[BaseLauncher] = None):
        self.launcher = launcher or HostLauncher()
        self.runner = ProcessRunner(sandbox=HostSandbox(), launcher=self.launcher)

    @property
    def name(self) -> str:
        return "host"

    def is_available(self) -> bool:
        return True

    def execute(
        self,
        command: Union[str, List[str]],
        cwd: str,
        request: Optional[Any] = None,
        capability: Optional[Any] = None,
        env: Optional[Dict[str, str]] = None,
        timeout: float = 60.0,
        mode: ExecutionMode = ExecutionMode.HOST_ARGV,
        allow_shell: Optional[bool] = None,
        task_id: Optional[str] = None,
        **kwargs,
    ) -> ProcessExecutionResult:
        t_id = task_id or (getattr(request, "session", None) if request else None)
        return self.runner.run(
            command=command,
            cwd=cwd,
            env=env,
            timeout=timeout,
            mode=mode,
            allow_shell=allow_shell,
            task_id=t_id,
        )


class SandboxBackend(ExecutionBackend):
    """
    Sandboxed execution backend.
    Uses SandboxConfigCompiler to isolate filesystem, network, and execution environment
    anticipating bubblewrap, gVisor, or containers with safe fallback.
    """

    def __init__(
        self,
        backend_type: str = "bubblewrap",
        compiler: Optional[SandboxConfigCompiler] = None,
        fallback_to_host: bool = True,
    ):
        self.backend_type = backend_type.lower()
        self.compiler = compiler or SandboxConfigCompiler()
        self.fallback_to_host = fallback_to_host

        if self.backend_type in ("bubblewrap", "bwrap"):
            self._underlying_sandbox = BubblewrapSandbox()
            self._launcher = SandboxLauncher()
        elif self.backend_type in ("container", "docker", "podman"):
            self._underlying_sandbox = ContainerSandbox()
            self._launcher = ContainerLauncher()
        else:
            self._underlying_sandbox = HostSandbox()
            self._launcher = HostLauncher()

        self.runner = ProcessRunner(sandbox=self._underlying_sandbox, launcher=self._launcher)

    @property
    def name(self) -> str:
        return f"sandbox:{self.backend_type}"

    def is_available(self) -> bool:
        return self._underlying_sandbox.is_available()

    def compile_config(
        self,
        request: Optional[Any] = None,
        capability: Optional[Any] = None,
        workspace_dir: str = "",
    ) -> SandboxConfig:
        return self.compiler.compile(
            request=request,
            capability=capability,
            workspace_dir=workspace_dir,
            backend_type=self.backend_type,
        )

    def execute(
        self,
        command: Union[str, List[str]],
        cwd: str,
        request: Optional[Any] = None,
        capability: Optional[Any] = None,
        env: Optional[Dict[str, str]] = None,
        timeout: float = 60.0,
        mode: ExecutionMode = ExecutionMode.HOST_ARGV,
        allow_shell: Optional[bool] = None,
        task_id: Optional[str] = None,
        **kwargs,
    ) -> ProcessExecutionResult:
        t_id = task_id or (getattr(request, "session", None) if request else None)

        # If chosen sandbox is not available on host OS (e.g., bwrap on Windows)
        if not self.is_available():
            if self.fallback_to_host:
                host_runner = ProcessRunner(sandbox=HostSandbox(), launcher=HostLauncher())
                return host_runner.run(
                    command=command,
                    cwd=cwd,
                    env=env,
                    timeout=timeout,
                    mode=mode,
                    allow_shell=allow_shell,
                    task_id=t_id,
                )
            else:
                from sclass.core.errors import SecurityViolationError
                raise SecurityViolationError(
                    f"Requested sandbox backend '{self.backend_type}' is not available on this host."
                )

        return self.runner.run(
            command=command,
            cwd=cwd,
            env=env,
            timeout=timeout,
            mode=mode,
            allow_shell=allow_shell,
            task_id=t_id,
        )


def get_execution_backend(name: str = "host", **kwargs) -> ExecutionBackend:
    """Factory retrieving requested execution backend."""
    name_clean = name.lower()
    if name_clean in ("host", "direct", "native"):
        return HostProcessBackend()
    elif name_clean in ("bubblewrap", "bwrap", "sandbox"):
        return SandboxBackend(backend_type="bubblewrap", **kwargs)
    elif name_clean in ("container", "docker", "podman"):
        return SandboxBackend(backend_type="container", **kwargs)
    elif name_clean in ("gvisor", "runsc"):
        return SandboxBackend(backend_type="gvisor", **kwargs)
    return HostProcessBackend()
