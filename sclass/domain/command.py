"""
S-Class Domain: Command and CommandRef.
"""

from __future__ import annotations
import shlex
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass(frozen=True)
class CommandRef:
    """Canonical security reference to a command invocation."""
    argv: tuple[str, ...]
    cwd: str
    executable: str
    environment_digest: str = ""
    allow_shell: bool = False

    @classmethod
    def from_string(cls, command_str: str, cwd: str, environment_digest: str = "", allow_shell: bool = False) -> CommandRef:
        tokens = tuple(shlex.split(command_str)) if command_str else tuple()
        exe = tokens[0] if tokens else ""
        return cls(
            argv=tokens,
            cwd=cwd,
            executable=exe,
            environment_digest=environment_digest,
            allow_shell=allow_shell,
        )


@dataclass
class Command:
    """An executable command request."""
    command_str: str
    argv: List[str] = field(default_factory=list)
    cwd: str = ""
    env: Dict[str, str] = field(default_factory=dict)
    timeout: float = 60.0
    allow_shell: bool = False

    def __post_init__(self) -> None:
        if not self.argv and self.command_str:
            try:
                self.argv = shlex.split(self.command_str)
            except ValueError:
                self.argv = self.command_str.split()

    @property
    def executable(self) -> str:
        return self.argv[0] if self.argv else ""
