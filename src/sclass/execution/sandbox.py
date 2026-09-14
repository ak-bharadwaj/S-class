"""
S-Class Execution: Sandbox Backend Abstraction.
Supports Host, Bubblewrap, and Container isolation for unprivileged agent executions.
"""

from __future__ import annotations
import os
import shutil
from typing import Protocol, List, Optional
from dataclasses import dataclass


class SandboxBackend(Protocol):
    """Protocol for command execution isolation layers."""
    @property
    def name(self) -> str: ...
    def is_available(self) -> bool: ...
    def wrap_command(
        self,
        command: List[str],
        cwd: str,
        writable_paths: Optional[List[str]] = None,
        readonly_paths: Optional[List[str]] = None,
    ) -> List[str]: ...


class HostSandbox:
    """Direct host process execution without containment overhead."""
    @property
    def name(self) -> str:
        return "host"

    def is_available(self) -> bool:
        return True

    def wrap_command(
        self,
        command: List[str],
        cwd: str,
        writable_paths: Optional[List[str]] = None,
        readonly_paths: Optional[List[str]] = None,
    ) -> List[str]:
        return list(command)


class BubblewrapSandbox:
    """Linux bubblewrap (bwrap) unprivileged user namespace sandbox."""
    @property
    def name(self) -> str:
        return "bubblewrap"

    def is_available(self) -> bool:
        return shutil.which("bwrap") is not None

    def wrap_command(
        self,
        command: List[str],
        cwd: str,
        writable_paths: Optional[List[str]] = None,
        readonly_paths: Optional[List[str]] = None,
        config: Optional[Any] = None,
    ) -> List[str]:
        if not self.is_available():
            from sclass.core.errors import SecurityViolationError
            raise SecurityViolationError(
                "NO SANDBOX -> NO SANDBOXED EXECUTION: Bubblewrap (bwrap) is not installed or available on this system. "
                "Fail-closed: cannot wrap command without sandbox containment."
            )

        net_mode = getattr(config, "network_mode", "none") if config else "none"
        ro_binds = list(getattr(config, "read_only_binds", [])) if config else ["/usr", "/lib", "/lib64", "/bin", "/etc/resolv.conf"]
        wr_binds = list(getattr(config, "writable_binds", [])) if config else [cwd]

        if readonly_paths:
            ro_binds.extend(readonly_paths)
        if writable_paths:
            wr_binds.extend(writable_paths)

        args = ["bwrap"]
        for ro in sorted(set(ro_binds)):
            if os.path.exists(ro):
                args.extend(["--ro-bind", ro, ro])

        for wr in sorted(set(wr_binds)):
            if os.path.exists(wr):
                args.extend(["--bind", wr, wr])

        args.extend(["--proc", "/proc", "--dev", "/dev", "--unshare-all"])
        if net_mode == "host":
            args.append("--share-net")
        else:
            args.append("--unshare-net")

        args.extend(["--chdir", cwd])
        args.extend(command)
        return args


class ContainerSandbox:
    """Container-based isolation (Docker or Podman)."""
    def __init__(self, image: str = "python:3.11-slim"):
        self.image = image

    @property
    def name(self) -> str:
        return "container"

    def is_available(self) -> bool:
        return shutil.which("docker") is not None or shutil.which("podman") is not None

    def wrap_command(
        self,
        command: List[str],
        cwd: str,
        writable_paths: Optional[List[str]] = None,
        readonly_paths: Optional[List[str]] = None,
        config: Optional[Any] = None,
    ) -> List[str]:
        runtime = "docker" if shutil.which("docker") else "podman"
        if not self.is_available():
            from sclass.core.errors import SecurityViolationError
            raise SecurityViolationError(
                f"NO SANDBOX -> NO SANDBOXED EXECUTION: Container runtime ({runtime}) is not installed or available on this system. "
                "Fail-closed: cannot wrap command without sandbox containment."
            )

        net_mode = getattr(config, "network_mode", "none") if config else "none"
        ro_binds = list(getattr(config, "read_only_binds", [])) if config else []
        wr_binds = list(getattr(config, "writable_binds", [])) if config else [os.path.abspath(cwd)]

        if readonly_paths:
            ro_binds.extend(readonly_paths)
        if writable_paths:
            wr_binds.extend(writable_paths)

        args = [
            runtime, "run", "--rm",
            "-w", os.path.abspath(cwd),
        ]

        if net_mode == "host":
            args.extend(["--network", "host"])
        else:
            args.extend(["--network", "none"])

        for wr in sorted(set(wr_binds)):
            abs_wr = os.path.abspath(wr)
            args.extend(["-v", f"{abs_wr}:{abs_wr}:rw"])

        for ro in sorted(set(ro_binds)):
            if os.path.exists(ro):
                abs_ro = os.path.abspath(ro)
                args.extend(["-v", f"{abs_ro}:{abs_ro}:ro"])

        # Resource limits from SandboxConfig
        res_limits = getattr(config, "resource_limits", {}) if config else {}
        if isinstance(res_limits, dict):
            if "max_memory_mb" in res_limits:
                args.extend(["--memory", f"{res_limits['max_memory_mb']}m"])

        args.append(self.image)
        args.extend(command)
        return args


class GVisorSandbox:
    """gVisor (runsc) user-space virtualization application kernel sandbox."""
    def __init__(self, platform: str = "ptrace", network: str = "none"):
        self.platform = platform
        self.network = network

    @property
    def name(self) -> str:
        return "gvisor"

    def is_available(self) -> bool:
        return shutil.which("runsc") is not None

    def wrap_command(
        self,
        command: List[str],
        cwd: str,
        writable_paths: Optional[List[str]] = None,
        readonly_paths: Optional[List[str]] = None,
        config: Optional[Any] = None,
    ) -> List[str]:
        if not self.is_available():
            from sclass.core.errors import SecurityViolationError
            raise SecurityViolationError(
                "NO SANDBOX -> NO SANDBOXED EXECUTION: gVisor (runsc) sandbox is not installed or available on this system. "
                "Fail-closed policy prevents uncontained execution."
            )
        net_mode = getattr(config, "network_mode", self.network) if config else self.network
        final_net = "host" if net_mode == "host" else "none"
        args = [
            "runsc",
            "--rootless",
            f"--network={final_net}",
            "exec",
            "--cwd", os.path.abspath(cwd),
        ]
        args.extend(command)
        return args



def get_sandbox_backend(name: str = "bubblewrap") -> SandboxBackend:
    """Factory retrieving requested sandbox backend. Strictly fails closed without host degradation."""
    name_clean = name.lower()
    if name_clean in ("bwrap", "bubblewrap"):
        return BubblewrapSandbox()
    elif name_clean in ("gvisor", "runsc"):
        return GVisorSandbox()
    elif name_clean in ("docker", "container", "podman"):
        return ContainerSandbox()
    elif name_clean in ("host", "direct", "native"):
        return HostSandbox()

    from sclass.core.errors import SecurityViolationError
    raise SecurityViolationError(f"UNKNOWN BACKEND -> NO EXECUTION: Requested sandbox backend '{name}' is not supported.")

