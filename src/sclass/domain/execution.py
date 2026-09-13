"""
S-Class Domain: ExecutionIdentity.
First-class primitive for identifying running processes without spoofing.
"""

from __future__ import annotations
import os
import shutil
import hashlib
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional


class ExecutionMode(str, Enum):
    """Execution environment mode for process invocation."""
    HOST_ARGV = "HOST_ARGV"
    HOST_SHELL = "HOST_SHELL"
    CONTAINER = "CONTAINER"
    SANDBOX = "SANDBOX"


@dataclass(frozen=True)
class ExecutionIdentity:
    """
    Cryptographic and process identity of an executed binary.
    Replaces brittle command-line string matching with authentic binary provenance.
    """
    executable: str
    resolved_path: str
    executable_hash: str
    argv: tuple[str, ...]
    cwd: str
    environment_digest: str
    parent_pid: Optional[int] = None
    pid: Optional[int] = None
    start_time: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    execution_mode: str = ExecutionMode.HOST_ARGV.value

    @classmethod
    def capture(
        cls,
        command_argv: List[str],
        cwd: str,
        env: Optional[Dict[str, str]] = None,
        pid: Optional[int] = None,
        parent_pid: Optional[int] = None,
        mode: ExecutionMode | str = ExecutionMode.HOST_ARGV,
    ) -> ExecutionIdentity:
        """Captures execution identity from real process parameters and binary inspection."""
        exe_name = command_argv[0] if command_argv else ""
        resolved = shutil.which(exe_name, path=cwd + os.pathsep + os.environ.get("PATH", "")) or ""
        if not resolved and os.path.exists(exe_name):
            resolved = os.path.abspath(exe_name)

        exe_hash = ""
        if resolved and os.path.isfile(resolved):
            try:
                hasher = hashlib.sha256()
                with open(resolved, "rb") as f:
                    while chunk := f.read(65536):
                        hasher.update(chunk)
                exe_hash = hasher.hexdigest()
            except (OSError, PermissionError):
                exe_hash = "unreadable_binary"

        # Compute stable environment digest from critical environment variables
        env_dict = env or os.environ
        critical_keys = sorted(["PATH", "PYTHONPATH", "VIRTUAL_ENV", "NODE_PATH"])
        env_payload = "".join(f"{k}={env_dict.get(k, '')};" for k in critical_keys)
        env_digest = hashlib.sha256(env_payload.encode("utf-8")).hexdigest()

        mode_val = mode.value if isinstance(mode, ExecutionMode) else str(mode)

        return cls(
            executable=exe_name,
            resolved_path=resolved,
            executable_hash=exe_hash,
            argv=tuple(command_argv),
            cwd=os.path.abspath(cwd) if cwd else os.getcwd(),
            environment_digest=env_digest,
            parent_pid=parent_pid or (os.getppid() if hasattr(os, "getppid") else None),
            pid=pid or os.getpid(),
            execution_mode=mode_val,
        )

    def compute_identity_hash(self) -> str:
        """Computes canonical hash of the execution identity."""
        payload = f"{self.resolved_path}|{self.executable_hash}|{' '.join(self.argv)}|{self.cwd}|{self.environment_digest}|{self.execution_mode}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "executable": self.executable,
            "resolved_path": self.resolved_path,
            "executable_hash": self.executable_hash,
            "argv": list(self.argv),
            "cwd": self.cwd,
            "environment_digest": self.environment_digest,
            "parent_pid": self.parent_pid,
            "pid": self.pid,
            "start_time": self.start_time,
            "execution_mode": self.execution_mode,
            "identity_hash": self.compute_identity_hash(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ExecutionIdentity:
        return cls(
            executable=data.get("executable", ""),
            resolved_path=data.get("resolved_path", ""),
            executable_hash=data.get("executable_hash", ""),
            argv=tuple(data.get("argv", [])),
            cwd=data.get("cwd", ""),
            environment_digest=data.get("environment_digest", ""),
            parent_pid=data.get("parent_pid"),
            pid=data.get("pid"),
            start_time=data.get("start_time", datetime.now(timezone.utc).isoformat()),
            execution_mode=data.get("execution_mode", ExecutionMode.HOST_ARGV.value),
        )
