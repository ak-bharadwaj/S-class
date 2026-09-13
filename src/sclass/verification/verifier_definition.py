"""
S-Class Verification: Trusted Verifier Definition.
Defines explicit verifier patterns, interpreter rules, package runner rules,
and trust classification modes separating identity from automatic authorization.
"""

from __future__ import annotations
import os
from enum import Enum
from dataclasses import dataclass, field
from typing import Tuple, Dict, Any, Optional, List, Callable


class VerifierTrustMode(str, Enum):
    """Categorical trust mode for test runner binaries and verifier environments."""
    TRUSTED = "TRUSTED"
    SYSTEM_TRUSTED = "SYSTEM_TRUSTED"
    USER_TRUSTED = "USER_TRUSTED"
    WORKSPACE_TRUSTED = "WORKSPACE_TRUSTED"
    UNTRUSTED = "UNTRUSTED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class VerifierDefinition:
    """
    Authoritative definition of an acceptable test verifier.
    Instead of requiring one fixed binary hash per installation,
    it models executable patterns, interpreter flags, and trust requirements.
    """
    verifier_id: str
    executable_patterns: Tuple[str, ...] = field(default_factory=tuple)
    interpreter_rules: Tuple[str, ...] = field(default_factory=tuple)
    package_rules: Tuple[str, ...] = field(default_factory=tuple)
    version_rules: Dict[str, Any] = field(default_factory=dict)
    result_parser: Optional[Any] = None
    scope_validator: Optional[Any] = None
    default_trust_mode: VerifierTrustMode = VerifierTrustMode.SYSTEM_TRUSTED

    def matches_executable(self, exe_name: str) -> bool:
        """Checks whether the raw or resolved executable matches known verifier patterns."""
        base = os.path.basename(exe_name).lower()
        if base.endswith(".exe"):
            base = base[:-4]
        for pat in self.executable_patterns:
            pat_base = pat.lower()
            if pat_base.endswith(".exe"):
                pat_base = pat_base[:-4]
            if base == pat_base:
                return True
        return False

    def matches_interpreter(self, interpreter_name: str, args: Tuple[str, ...]) -> bool:
        """Checks if invocation matches interpreter module rules (e.g. python -m pytest)."""
        base = os.path.basename(interpreter_name).lower()
        if base.endswith(".exe"):
            base = base[:-4]
        if base in ("python", "python3", "py") or base.startswith("python3.") or base.startswith("python2.") or base.startswith("pypy"):
            for rule in self.interpreter_rules:
                rule_lower = rule.lower()
                for i, arg in enumerate(args):
                    if arg == "-m" and i + 1 < len(args) and args[i + 1].lower() == rule_lower:
                        return True
                    if arg.startswith("-m") and arg[2:].lower() == rule_lower:
                        return True
        return False

    def matches_package_script(self, runner_name: str, args: Tuple[str, ...]) -> bool:
        """Checks if invocation matches package manager runner rules (e.g. npm test)."""
        base = os.path.basename(runner_name).lower()
        if base.endswith(".exe"):
            base = base[:-4]
        if base in ("npm", "pnpm", "yarn", "bun"):
            for rule in self.package_rules:
                if len(args) > 1 and args[1].lower() == rule.lower():
                    return True
                if len(args) > 2 and args[1].lower() == "run" and args[2].lower() == rule.lower():
                    return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verifier_id": self.verifier_id,
            "executable_patterns": list(self.executable_patterns),
            "interpreter_rules": list(self.interpreter_rules),
            "package_rules": list(self.package_rules),
            "version_rules": dict(self.version_rules),
            "default_trust_mode": self.default_trust_mode.value,
        }
