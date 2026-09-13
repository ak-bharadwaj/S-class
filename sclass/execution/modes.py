"""
S-Class Execution: Execution Modes and Security Policy.
Defines authoritative execution modes (HOST_ARGV, HOST_SHELL, CONTAINER, SANDBOX)
and explicit security policy analysis for shell execution and protected resources.
"""

from __future__ import annotations
import os
import re
import shlex
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Any

from sclass.core.errors import SecurityViolationError


class ExecutionMode(str, Enum):
    """Authoritative execution environment modes."""
    HOST_ARGV = "HOST_ARGV"
    HOST_SHELL = "HOST_SHELL"
    CONTAINER = "CONTAINER"
    SANDBOX = "SANDBOX"


# Protected paths that must never be targeted or mutated by untrusted execution
PROTECTED_RESOURCE_PATTERNS = [
    r"\.sclass/trust(?:/|$)",
    r"\.sclass/state(?:/|$)",
    r"\.sclass/evidence(?:/|$)",
    r"\.sclass/config(?:/|$)",
    r"\.sclass/events(?:/|$)",
    r"\.sclass/locks(?:/|$)",
    r"\.sclass\\trust(?:\\|$)",
    r"\.sclass\\state(?:\\|$)",
    r"\.sclass\\evidence(?:\\|$)",
    r"\.sclass\\config(?:\\|$)",
    r"\.sclass\\events(?:\\|$)",
    r"\.sclass\\locks(?:\\|$)",
    r"\.agents/ledger(?:/|$)",
    r"\.agents/receipts(?:/|$)",
    r"\.agents/claims(?:/|$)",
    r"\.agents\\ledger(?:\\|$)",
    r"\.agents\\receipts(?:\\|$)",
    r"\.agents\\claims(?:\\|$)",
]


def check_protected_resource_targeting(command_or_tokens: str | List[str]) -> Tuple[bool, Optional[str]]:
    """
    Analyzes command tokens or raw command string for any reference targeting protected S-Class resources.
    """
    if isinstance(command_or_tokens, str):
        raw_cmd = command_or_tokens
        try:
            tokens = shlex.split(command_or_tokens)
        except Exception:
            tokens = command_or_tokens.split()
    else:
        tokens = list(command_or_tokens)
        raw_cmd = " ".join(tokens)

    normalized_raw = raw_cmd.replace("\\", "/")

    # Check against protected patterns in raw string
    for pat in PROTECTED_RESOURCE_PATTERNS:
        norm_pat = pat.replace("\\\\", "/")
        if re.search(norm_pat, normalized_raw, re.IGNORECASE):
            return True, f"Command references protected S-Class resource matching pattern: {norm_pat}"

    # Check individual tokens
    for t in tokens:
        norm_token = t.replace("\\", "/")
        for pat in PROTECTED_RESOURCE_PATTERNS:
            norm_pat = pat.replace("\\\\", "/")
            if re.search(norm_pat, norm_token, re.IGNORECASE):
                return True, f"Token references protected S-Class resource: {norm_token}"

    # Check for shell redirection into protected directories
    redirect_pattern = r"(?:>|>>)\s*([^\s;\|&]+)"
    matches = re.findall(redirect_pattern, raw_cmd)
    for target in matches:
        norm_target = target.replace("\\", "/")
        for pat in PROTECTED_RESOURCE_PATTERNS:
            norm_pat = pat.replace("\\\\", "/")
            if re.search(norm_pat, norm_target, re.IGNORECASE):
                return True, f"Shell redirection targets protected S-Class resource: {target}"

    return False, None


@dataclass(frozen=True)
class PolicyEvaluationResult:
    """Result of evaluating execution mode policy."""
    allowed: bool
    mode: ExecutionMode
    risk_level: str  # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    reason: str
    requires_approval: bool = False


class ExecutionPolicy:
    """
    Evaluates policy for process execution requests.
    Enforces that HOST_SHELL is gated, protected resources are safeguarded,
    and sandboxed/container modes adhere to boundaries.
    """

    @classmethod
    def evaluate(
        cls,
        mode: ExecutionMode,
        command: str | List[str],
        cwd: str,
        allow_shell: Optional[bool] = None,
        task_id: Optional[str] = None,
    ) -> PolicyEvaluationResult:
        """Evaluates whether the requested execution mode and command satisfy security policy."""
        if allow_shell is not None:
            mode = ExecutionMode.HOST_SHELL if allow_shell else ExecutionMode.HOST_ARGV

        # 1. Protected resource analysis (mandatory across all modes)
        is_targeted, target_reason = check_protected_resource_targeting(command)
        if is_targeted:
            return PolicyEvaluationResult(
                allowed=False,
                mode=mode,
                risk_level="CRITICAL",
                reason=f"SECURITY_DENY: {target_reason}",
                requires_approval=False,
            )

        # 2. Mode-specific security policies
        if mode == ExecutionMode.HOST_ARGV:
            # Check for shell metacharacters in HOST_ARGV mode
            if isinstance(command, list):
                for t in command:
                    if t in (";", "&&", "||", "|") or any(c in t for c in ("&&", "||", "`", "$(")):
                        return PolicyEvaluationResult(
                            allowed=False,
                            mode=mode,
                            risk_level="HIGH",
                            reason=f"Command token contains forbidden shell chaining characters in HOST_ARGV mode: {t}",
                        )
            elif isinstance(command, str):
                try:
                    tokens = shlex.split(command)
                    for t in tokens:
                        if t in (";", "&&", "||", "|") or any(c in t for c in ("&&", "||", "`", "$(")):
                            return PolicyEvaluationResult(
                                allowed=False,
                                mode=mode,
                                risk_level="HIGH",
                                reason=f"Command string contains shell chaining in HOST_ARGV mode: {t}",
                            )
                except Exception:
                    pass

            return PolicyEvaluationResult(
                allowed=True,
                mode=mode,
                risk_level="LOW",
                reason="HOST_ARGV execution permitted under default standard policy.",
            )

        elif mode == ExecutionMode.HOST_SHELL:
            return PolicyEvaluationResult(
                allowed=True,
                mode=mode,
                risk_level="HIGH",
                reason="HOST_SHELL execution permitted under guarded shell policy.",
                requires_approval=True,
            )

        elif mode in (ExecutionMode.CONTAINER, ExecutionMode.SANDBOX):
            return PolicyEvaluationResult(
                allowed=True,
                mode=mode,
                risk_level="LOW",
                reason=f"{mode.value} execution permitted under isolated execution policy.",
            )

        return PolicyEvaluationResult(
            allowed=False,
            mode=mode,
            risk_level="HIGH",
            reason=f"Unknown execution mode: {mode}",
        )
