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
    ) -> List[str]:
        if not self.is_available():
            return list(command)

        args = [
            "bwrap",
            "--ro-bind", "/usr", "/usr",
            "--ro-bind", "/lib", "/lib",
            "--ro-bind", "/lib64", "/lib64",
            "--ro-bind", "/bin", "/bin",
            "--ro-bind", "/etc/resolv.conf", "/etc/resolv.conf",
            "--proc", "/proc",
            "--dev", "/dev",
            "--unshare-all",
            "--share-net",
            "--bind", cwd, cwd,
            "--chdir", cwd,
        ]
        if writable_paths:
            for p in writable_paths:
                args.extend(["--bind", p, p])
        if readonly_paths:
            for p in readonly_paths:
                args.extend(["--ro-bind", p, p])

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
    ) -> List[str]:
        runtime = "docker" if shutil.which("docker") else "podman"
        if not self.is_available():
            from sclass.core.errors import SecurityViolationError
            raise SecurityViolationError(
                f"Container runtime ({runtime}) is not installed or available on this system."
            )

        args = [
            runtime, "run", "--rm",
            "-v", f"{os.path.abspath(cwd)}:{os.path.abspath(cwd)}:rw",
            "-w", os.path.abspath(cwd),
            "--network", "host",
            self.image,
        ]
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
    ) -> List[str]:
        if not self.is_available():
            from sclass.core.errors import SecurityViolationError
            raise SecurityViolationError(
                "gVisor (runsc) sandbox is not installed or available on this system. "
                "Fail-closed policy prevents uncontained execution."
            )
        args = [
            "runsc",
            "--rootless",
            f"--network={self.network}",
            "exec",
            "--cwd", os.path.abspath(cwd),
        ]
        args.extend(command)
        return args


def get_sandbox_backend(name: str = "host", allow_fallback: bool = False) -> SandboxBackend:
    """Factory retrieving requested sandbox backend without silent host fallback."""
    name_clean = name.lower()
    if name_clean in ("bwrap", "bubblewrap"):
        bw = BubblewrapSandbox()
        if bw.is_available() or not allow_fallback:
            return bw
    elif name_clean in ("gvisor", "runsc"):
        gv = GVisorSandbox()
        if gv.is_available() or not allow_fallback:
            return gv
    elif name_clean in ("docker", "container", "podman"):
        cont = ContainerSandbox()
        if cont.is_available() or not allow_fallback:
            return cont
    elif name_clean in ("host", "direct", "native"):
        return HostSandbox()

    if allow_fallback:
        return HostSandbox()

    from sclass.core.errors import SecurityViolationError
    raise SecurityViolationError(f"Requested sandbox backend '{name}' is not supported or available.")

