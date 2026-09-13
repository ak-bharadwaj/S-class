"""
S-Class Execution: Launcher Abstractions and Wrapper Detection.
Provides launcher implementations (Host, Sandbox, Container) and wrapper detection.
"""

from __future__ import annotations
import os
import sys
import subprocess
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass

from sclass.execution.modes import ExecutionMode


def detect_wrapper_executable(executable_path: str) -> Tuple[bool, Optional[str]]:
    """
    Detects if an executable is a wrapper script (e.g. .bat, .cmd, shell script)
    that invokes another process underneath.
    """
    if not executable_path or not os.path.isfile(executable_path):
        return False, None

    ext = os.path.splitext(executable_path)[1].lower()
    if ext in (".bat", ".cmd", ".ps1", ".sh", ".bash"):
        return True, f"script_wrapper:{ext[1:]}"

    # Check for shebang in extensionless files
    if not ext:
        try:
            with open(executable_path, "rb") as f:
                header = f.read(2)
                if header == b"#!":
                    first_line = f.readline().decode("utf-8", errors="replace").strip()
                    return True, f"shebang_wrapper:{first_line}"
        except Exception:
            pass

    return False, None


@dataclass(frozen=True)
class LauncherIdentity:
    """Identity record of the launcher component."""
    launcher_type: str
    wrapper: Optional[str] = None
    isolation_tier: str = "host"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "launcher_type": self.launcher_type,
            "wrapper": self.wrapper,
            "isolation_tier": self.isolation_tier,
        }


class BaseLauncher:
    """Base process launcher."""

    def __init__(self, name: str = "HostLauncher", isolation_tier: str = "host"):
        self.name = name
        self.isolation_tier = isolation_tier

    def launch(
        self,
        args: List[str] | str,
        cwd: str,
        env: Dict[str, str],
        shell: bool = False,
    ) -> Tuple[subprocess.Popen, LauncherIdentity]:
        """Launches process and returns Popen instance along with LauncherIdentity."""
        # Detect wrapper on executable if list args
        wrapper_id = None
        if isinstance(args, list) and args:
            is_wrap, wrap_info = detect_wrapper_executable(args[0])
            if is_wrap:
                wrapper_id = wrap_info

        launcher_id = LauncherIdentity(
            launcher_type=self.name,
            wrapper=wrapper_id,
            isolation_tier=self.isolation_tier,
        )

        proc = subprocess.Popen(
            args,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace",
            shell=shell,
            env=env,
        )
        return proc, launcher_id


class HostLauncher(BaseLauncher):
    """Standard host environment launcher."""
    def __init__(self):
        super().__init__(name="HostLauncher", isolation_tier="host")


class SandboxLauncher(BaseLauncher):
    """Restricted sandbox launcher."""
    def __init__(self):
        super().__init__(name="SandboxLauncher", isolation_tier="sandboxed")


class ContainerLauncher(BaseLauncher):
    """Containerized environment launcher."""
    def __init__(self):
        super().__init__(name="ContainerLauncher", isolation_tier="container")
