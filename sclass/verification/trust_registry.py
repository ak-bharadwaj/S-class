"""
S-Class Verification: Verifier Trust Registry and Path Authority Policy.
Classifies execution paths into SYSTEM_TRUSTED, USER_TRUSTED, WORKSPACE_TRUSTED,
UNTRUSTED, or UNKNOWN, enforcing that malicious binaries earlier on PATH become
IDENTIFIED_AS_<RUNNER> + UNTRUSTED_BINARY rather than AUTHORIZED.
"""

from __future__ import annotations
import os
import sys
import tempfile
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Tuple, Set

from sclass.execution.identity import ExecutionIdentity
from sclass.verification.verifier_definition import VerifierDefinition, VerifierTrustMode


@dataclass
class TrustPolicy:
    """Configurable trust policy governing binary path authority."""
    system_trusted_dirs: Set[str] = field(default_factory=set)
    user_trusted_dirs: Set[str] = field(default_factory=set)
    untrusted_dirs: Set[str] = field(default_factory=set)
    untrusted_hashes: Set[str] = field(default_factory=set)
    untrusted_paths: Set[str] = field(default_factory=set)
    workspace_dirs: Set[str] = field(default_factory=set)

    def __post_init__(self):
        # Always add standard Python system prefixes
        for p in (sys.prefix, sys.base_prefix, sys.exec_prefix):
            if p:
                self.system_trusted_dirs.add(os.path.normpath(p).lower())

        # System paths on Windows
        if os.name == "nt":
            for env_var in ("SystemRoot", "windir", "ProgramFiles", "ProgramFiles(x86)"):
                val = os.environ.get(env_var)
                if val:
                    self.system_trusted_dirs.add(os.path.normpath(val).lower())
        else:
            for p in ("/bin", "/usr/bin", "/usr/local/bin", "/opt", "/usr/lib"):
                if os.path.exists(p):
                    self.system_trusted_dirs.add(os.path.normpath(p).lower())

        # Add temp directories to untrusted by default
        tmp = tempfile.gettempdir()
        if tmp:
            self.untrusted_dirs.add(os.path.normpath(tmp).lower())


class TrustRegistry:
    """
    Central registry for verifier definitions and process trust classification.
    Prevents path hijacking, wrapper substitution, and unauthorized shadow binaries.
    """

    def __init__(self, policy: Optional[TrustPolicy] = None):
        self.policy = policy or TrustPolicy()
        self._definitions: Dict[str, VerifierDefinition] = {}
        self._bootstrap_default_definitions()

    def _bootstrap_default_definitions(self) -> None:
        """Registers standard ecosystem verifier definitions."""
        self.register_definition(VerifierDefinition(
            verifier_id="pytest",
            executable_patterns=("pytest", "py.test"),
            interpreter_rules=("pytest",),
            default_trust_mode=VerifierTrustMode.SYSTEM_TRUSTED,
        ))
        self.register_definition(VerifierDefinition(
            verifier_id="unittest",
            executable_patterns=(),
            interpreter_rules=("unittest",),
            default_trust_mode=VerifierTrustMode.SYSTEM_TRUSTED,
        ))
        self.register_definition(VerifierDefinition(
            verifier_id="jest",
            executable_patterns=("jest",),
            default_trust_mode=VerifierTrustMode.SYSTEM_TRUSTED,
        ))
        self.register_definition(VerifierDefinition(
            verifier_id="vitest",
            executable_patterns=("vitest",),
            default_trust_mode=VerifierTrustMode.SYSTEM_TRUSTED,
        ))
        self.register_definition(VerifierDefinition(
            verifier_id="mocha",
            executable_patterns=("mocha",),
            default_trust_mode=VerifierTrustMode.SYSTEM_TRUSTED,
        ))
        self.register_definition(VerifierDefinition(
            verifier_id="playwright",
            executable_patterns=("playwright",),
            package_rules=("test",),
            default_trust_mode=VerifierTrustMode.SYSTEM_TRUSTED,
        ))
        self.register_definition(VerifierDefinition(
            verifier_id="cargo-test",
            executable_patterns=("cargo",),
            package_rules=("test",),
            default_trust_mode=VerifierTrustMode.SYSTEM_TRUSTED,
        ))
        self.register_definition(VerifierDefinition(
            verifier_id="go-test",
            executable_patterns=("go",),
            package_rules=("test",),
            default_trust_mode=VerifierTrustMode.SYSTEM_TRUSTED,
        ))
        for pkg_runner in ("npm", "pnpm", "yarn", "bun"):
            self.register_definition(VerifierDefinition(
                verifier_id=f"{pkg_runner}-test",
                executable_patterns=(pkg_runner,),
                package_rules=("test",),
                default_trust_mode=VerifierTrustMode.SYSTEM_TRUSTED,
            ))

    def register_definition(self, definition: VerifierDefinition) -> None:
        self._definitions[definition.verifier_id] = definition

    def get_definition(self, verifier_id: str) -> Optional[VerifierDefinition]:
        return self._definitions.get(verifier_id)

    def mark_untrusted_path(self, path: str) -> None:
        """Explicitly flags a path as untrusted/malicious."""
        if path:
            self.policy.untrusted_paths.add(os.path.normpath(path).lower())

    def mark_untrusted_hash(self, binary_hash: str) -> None:
        """Explicitly flags a binary hash as compromised or untrusted."""
        if binary_hash:
            self.policy.untrusted_hashes.add(binary_hash.lower())

    def classify_binary_trust(
        self,
        executable_path: str,
        workspace_dir: str = "",
        binary_hash: str = "",
    ) -> VerifierTrustMode:
        """
        Determines the authoritative trust mode of an executable binary.
        """
        if not executable_path:
            return VerifierTrustMode.UNKNOWN

        norm_path = os.path.normpath(executable_path).lower()

        # 1. Explicit untrusted check
        if norm_path in self.policy.untrusted_paths:
            return VerifierTrustMode.UNTRUSTED

        if binary_hash and binary_hash.lower() in self.policy.untrusted_hashes:
            return VerifierTrustMode.UNTRUSTED

        for udir in self.policy.untrusted_dirs:
            if norm_path.startswith(udir) or (norm_path + os.sep).startswith(udir + os.sep):
                return VerifierTrustMode.UNTRUSTED

        # 2. Workspace trust
        ws = os.path.normpath(workspace_dir).lower() if workspace_dir else ""
        if ws and norm_path.startswith(ws):
            # Binary located directly within workspace or workspace venv
            return VerifierTrustMode.WORKSPACE_TRUSTED

        for wdir in self.policy.workspace_dirs:
            if norm_path.startswith(wdir):
                return VerifierTrustMode.WORKSPACE_TRUSTED

        # 3. User trusted
        for udir in self.policy.user_trusted_dirs:
            if norm_path.startswith(udir):
                return VerifierTrustMode.USER_TRUSTED

        # 4. System trusted
        for sdir in self.policy.system_trusted_dirs:
            if norm_path.startswith(sdir):
                return VerifierTrustMode.SYSTEM_TRUSTED

        # If it is sys.executable or in sys.prefix
        if norm_path == os.path.normpath(sys.executable).lower():
            return VerifierTrustMode.SYSTEM_TRUSTED

        # Default fallback
        return VerifierTrustMode.SYSTEM_TRUSTED if os.path.isabs(norm_path) else VerifierTrustMode.UNKNOWN

    def evaluate_verifier(
        self,
        execution: ExecutionIdentity,
        workspace_dir: str = "",
    ) -> Tuple[Optional[VerifierDefinition], VerifierTrustMode, str]:
        """
        Evaluates execution against registered definitions and trust policy.
        Returns (definition, trust_mode, status_code).
        Example status: 'IDENTIFIED_AS_PYTEST+UNTRUSTED_BINARY' vs 'AUTHORIZED_PYTEST'.
        """
        tokens = list(execution.actual_argv)
        if not tokens:
            return None, VerifierTrustMode.UNKNOWN, "NO_ARGV"

        raw_exe = execution.executable_path or tokens[0]
        trust_mode = self.classify_binary_trust(
            executable_path=raw_exe,
            workspace_dir=workspace_dir or execution.cwd,
            binary_hash=execution.executable_hash,
        )

        # Match against definitions
        matched_defn: Optional[VerifierDefinition] = None
        args = tuple(tokens[1:])

        for defn in self._definitions.values():
            if defn.matches_executable(raw_exe):
                matched_defn = defn
                break
            if defn.matches_interpreter(raw_exe, args):
                matched_defn = defn
                break
            if defn.matches_package_script(raw_exe, args):
                matched_defn = defn
                break

        if not matched_defn:
            return None, trust_mode, "UNKNOWN_VERIFIER"

        vid = matched_defn.verifier_id.upper().replace("-", "_")

        if trust_mode == VerifierTrustMode.UNTRUSTED:
            return matched_defn, trust_mode, f"IDENTIFIED_AS_{vid}+UNTRUSTED_BINARY"

        return matched_defn, trust_mode, f"AUTHORIZED_{vid}"


_GLOBAL_TRUST_REGISTRY: Optional[TrustRegistry] = None


def get_trust_registry() -> TrustRegistry:
    global _GLOBAL_TRUST_REGISTRY
    if _GLOBAL_TRUST_REGISTRY is None:
        _GLOBAL_TRUST_REGISTRY = TrustRegistry()
    return _GLOBAL_TRUST_REGISTRY
