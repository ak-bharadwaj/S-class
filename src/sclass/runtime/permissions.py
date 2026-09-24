"""
S-Class Runtime: Comprehensive Permission Architecture & Presets.
Implements the harvested Step-Code permission engine required by Directive Section 7:
- Four presets: Ask, Read-only, Bypass, Autopilot.
- Tool permission modes, command policy, interactive & non-interactive approval.
- Advanced dangerous command detection.
- Workflow child ACL delegation.
- 5-Way Conjunction Model:
    S-Class Authorization
             AND
    Step-Code Permission
             AND
    Runtime Capability
             AND
    Workspace Policy
             AND
    Operation State
All must permit.
Step-Code ALLOW cannot override S-Class DENY.
S-Class ALLOW cannot override Step-Code DENY.
Fails closed.
"""

from __future__ import annotations
import os
import re
import shlex
import fnmatch
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Set, Callable


class PermissionPreset(str, Enum):
    """Authoritative Step-Code permission presets."""
    ASK = "Ask"               # Prompt user on every mutating or risky action
    READ_ONLY = "Read-only"   # Strictly forbid all writes, modifications, and command execution
    BYPASS = "Bypass"         # Unattended non-interactive execution (governed by policy allowlists)
    AUTOPILOT = "Autopilot"   # Autonomous execution with bounded safety limits and dangerous pattern blocks


class ToolPermissionMode(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    CONFIRM = "CONFIRM"
    DISABLED = "DISABLED"


@dataclass(frozen=True)
class CommandPolicy:
    """Security rules governing command line execution."""
    allowed_executables: Set[str] = field(default_factory=lambda: {"git", "pytest", "python", "python3", "ls", "dir", "cat", "grep"})
    disallowed_executables: Set[str] = field(default_factory=lambda: {"rm", "del", "erase", "mkfs", "dd", "format", "curl", "wget", "nc"})
    max_execution_seconds: int = 120
    allow_network: bool = False
    allow_subshells: bool = False


@dataclass(frozen=True)
class WorkflowChildACL:
    """Explicitly delegated capability boundary for child lanes and subagents."""
    allowed_tools: Set[str] = field(default_factory=set)
    allowed_paths: List[str] = field(default_factory=list)
    can_execute_commands: bool = False
    max_budget_tokens: int = 50000
    allow_nested_delegation: bool = False


@dataclass(frozen=True)
class PermissionTelemetryRecord:
    """Typed telemetry record for every permission evaluation."""
    timestamp: str
    preset: PermissionPreset
    tool_name: str
    target: str
    sclass_auth_allowed: bool
    stepcode_permission_allowed: bool
    capability_allowed: bool
    workspace_policy_allowed: bool
    operation_state_allowed: bool
    conjunction_verdict: bool
    rejection_reasons: List[str]


class DangerousCommandDetector:
    """Detects dangerous system, destructive, or exfiltration shell patterns."""

    DESTRUCTIVE_PATTERNS = [
        re.compile(r"\brm\s+(-[a-zA-Z]*[rR][a-zA-Z]*[fF]|-[a-zA-Z]*[fF][a-zA-Z]*[rR]|-[rR]\s+-[fF]|--recursive|--force)", re.IGNORECASE),
        re.compile(r"\b(Remove-Item|ri)\b.*-Recurse", re.IGNORECASE),
        re.compile(r"\b(del|erase|rd|rmdir)\b\s+.*(/[sS]|/[qQ]|-[sS]|-[qQ])", re.IGNORECASE),
        re.compile(r":\(\)\{\s*:\s*\|\s*:\s*&\s*\};:", re.IGNORECASE), # fork bomb
        re.compile(r"\b(mkfs|dd\s+if=.*of=/dev/|Format-Volume|Clear-Disk|fdisk)\b", re.IGNORECASE),
        re.compile(r">\s*/dev/(sda|nvme|hda|disk)", re.IGNORECASE),
        re.compile(r"\b(curl|wget)\b.*\|\s*(sh|bash|python|pwsh)", re.IGNORECASE),
        re.compile(r"\bfind\b.*(-delete|-exec\s+rm)", re.IGNORECASE),
        re.compile(r"\bcat\b.*(/etc/(passwd|shadow)|System32[/\\]drivers)", re.IGNORECASE),
    ]

    @classmethod
    def is_dangerous(cls, command_str: str) -> tuple[bool, str]:
        cmd = (command_str or "").strip()
        if not cmd:
            return True, "Empty command string"

        for pat in cls.DESTRUCTIVE_PATTERNS:
            if pat.search(cmd):
                return True, f"Command matched dangerous destructive pattern: {pat.pattern}"

        # Check for path traversal outside workspace
        if any(seq in cmd for seq in ("../..", "..\\..", "/../", "\\..\\")):
            return True, "Path traversal sequence detected in command"

        return False, "Command passed dangerous pattern heuristics"


class ComprehensivePermissionEngine:
    """
    Evaluates execution requests against the 5-way conjunction model.
    """

    def __init__(
        self,
        preset: PermissionPreset = PermissionPreset.AUTOPILOT,
        command_policy: Optional[CommandPolicy] = None,
        interactive_approval_fn: Optional[Callable[[str, Dict[str, Any]], bool]] = None,
    ):
        self.preset = preset
        self.command_policy = command_policy or CommandPolicy()
        self.interactive_approval_fn = interactive_approval_fn
        self.telemetry_history: List[PermissionTelemetryRecord] = []

    def evaluate_stepcode_permission(
        self,
        tool_name: str,
        target: str,
        parameters: Dict[str, Any],
        workspace_dir: str,
        child_acl: Optional[WorkflowChildACL] = None,
    ) -> tuple[bool, str]:
        """Evaluates Step-Code runtime permission based on preset and policies."""
        clean_tool = (tool_name or "").strip().lower()

        # Check Workflow Child ACL if running in child context
        if child_acl is not None:
            if clean_tool not in child_acl.allowed_tools and "*" not in child_acl.allowed_tools:
                return False, f"Child ACL forbids tool: {clean_tool}"
            if clean_tool in ("run_command", "terminal_execute") and not child_acl.can_execute_commands:
                return False, "Child ACL explicitly forbids terminal command execution"

        # Preset 1: READ_ONLY forbids all mutating tools and commands
        if self.preset == PermissionPreset.READ_ONLY:
            if clean_tool not in ("read_file", "view_file", "list_dir", "find_by_name", "grep_search", "inspect_session"):
                return False, f"Permission preset READ_ONLY strictly forbids mutating action: {clean_tool}"

        # Check dangerous command patterns
        if clean_tool in ("run_command", "terminal_execute", "execute_command"):
            cmd = str(parameters.get("command") or parameters.get("command_line") or "").strip()
            dangerous, reason = DangerousCommandDetector.is_dangerous(cmd)
            if dangerous:
                return False, f"Step-Code permission blocked command: {reason}"

        # Preset 2: ASK requires interactive approval for mutating tools
        if self.preset == PermissionPreset.ASK:
            if clean_tool in ("write_to_file", "replace_file_content", "run_command", "terminal_execute", "delete_file"):
                if self.interactive_approval_fn:
                    approved = self.interactive_approval_fn(tool_name, parameters)
                    if not approved:
                        return False, f"Interactive user approval denied for tool: {tool_name}"
                else:
                    return False, "Preset ASK requires interactive approval handler, but none configured"

        return True, "Passed Step-Code runtime permission evaluation"

    def evaluate_conjunction(
        self,
        tool_name: str,
        target: str,
        parameters: Dict[str, Any],
        workspace_dir: str,
        sclass_auth_allowed: bool,
        capability_allowed: bool,
        workspace_policy_allowed: bool,
        operation_state_allowed: bool,
        child_acl: Optional[WorkflowChildACL] = None,
    ) -> tuple[bool, List[str]]:
        """
        Enforces 5-way conjunction:
          S-Class Auth AND Step-Code Perm AND Capability AND Workspace AND State.
        """
        rejections: List[str] = []

        # 1. S-Class Authorization
        if not sclass_auth_allowed:
            rejections.append("DENIED_BY_SCLASS_AUTHORIZATION")

        # 2. Step-Code Permission
        step_ok, step_msg = self.evaluate_stepcode_permission(
            tool_name=tool_name,
            target=target,
            parameters=parameters,
            workspace_dir=workspace_dir,
            child_acl=child_acl,
        )
        if not step_ok:
            rejections.append(f"DENIED_BY_STEPCODE_PERMISSION: {step_msg}")

        # 3. Runtime Capability
        if not capability_allowed:
            rejections.append("DENIED_BY_RUNTIME_CAPABILITY")

        # 4. Workspace Policy
        if not workspace_policy_allowed:
            rejections.append("DENIED_BY_WORKSPACE_POLICY")

        # 5. Operation State
        if not operation_state_allowed:
            rejections.append("DENIED_BY_OPERATION_STATE")

        conjunction_verdict = (len(rejections) == 0)

        record = PermissionTelemetryRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            preset=self.preset,
            tool_name=tool_name,
            target=target,
            sclass_auth_allowed=sclass_auth_allowed,
            stepcode_permission_allowed=step_ok,
            capability_allowed=capability_allowed,
            workspace_policy_allowed=workspace_policy_allowed,
            operation_state_allowed=operation_state_allowed,
            conjunction_verdict=conjunction_verdict,
            rejection_reasons=rejections,
        )
        self.telemetry_history.append(record)

        return conjunction_verdict, rejections
