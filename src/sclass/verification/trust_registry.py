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
    trusted_paths: Set[str] = field(default_factory=set)
    trusted_hashes: Set[str] = field(default_factory=set)

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
            try:
                self.untrusted_dirs.add(os.path.normcase(os.path.realpath(tmp)))
            except Exception:
                pass
            # Also add common temp locations on Linux/macOS
            for t in ("/tmp", "/var/tmp", "/private/tmp"):
                if os.path.exists(t):
                    self.untrusted_dirs.add(os.path.normpath(t).lower())
                    try:
                        self.untrusted_dirs.add(os.path.normcase(os.path.realpath(t)))
                    except Exception:
                        pass



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

    def mark_trusted_path(self, path: str) -> None:
        """Explicitly flags a path as trusted."""
        if path:
            self.policy.trusted_paths.add(os.path.normpath(path).lower())

    def mark_trusted_hash(self, binary_hash: str) -> None:
        """Explicitly flags a binary hash as trusted."""
        if binary_hash:
            self.policy.trusted_hashes.add(binary_hash.lower())

    def _is_within_dir(self, target_path: str, base_dir: str) -> bool:
        """Authoritatively checks if target_path is within base_dir, preventing prefix collisions."""
        if not target_path or not base_dir:
            return False
        try:
            norm_t = os.path.normcase(os.path.realpath(os.path.abspath(target_path)))
            norm_b = os.path.normcase(os.path.realpath(os.path.abspath(base_dir)))
            if norm_b in ("/", "\\") or (os.name == "nt" and len(norm_b) <= 3 and norm_b.endswith(":\\")):
                return norm_t == norm_b
            return norm_t == norm_b or norm_t.startswith(norm_b.rstrip(os.sep) + os.sep)
        except Exception:
            return False

    def classify_binary_trust(
        self,
        executable_path: str = "",
        workspace_dir: str = "",
        binary_hash: str = "",
        execution: Optional[ExecutionIdentity] = None,
    ) -> VerifierTrustMode:
        """
        Determines the authoritative trust mode of an executable binary or ExecutionIdentity.
        Hierarchy:
        - Explicit compromised/untrusted -> UNTRUSTED
        - Explicit trusted path/hash    -> TRUSTED
        - Workspace trusted             -> WORKSPACE_TRUSTED
        - User trusted                  -> USER_TRUSTED
        - System allowlisted            -> SYSTEM_TRUSTED
        - Unrecognized binary           -> UNKNOWN (fail-closed, NEVER SYSTEM_TRUSTED)
        """
        if execution is not None:
            executable_path = execution.executable_path or (execution.actual_argv[0] if execution.actual_argv else "")
            binary_hash = binary_hash or execution.executable_hash
            workspace_dir = workspace_dir or execution.cwd

        if not executable_path:
            return VerifierTrustMode.UNKNOWN

        norm_path = os.path.normpath(executable_path)
        norm_case = os.path.normcase(norm_path)

        # 0. Reject NTFS Alternate Data Streams (ADS) and path colon injection (e.g. file.txt:evil.exe)
        drive, rest = os.path.splitdrive(norm_path)
        if ":" in rest:
            return VerifierTrustMode.UNKNOWN

        # 1. Explicit compromised / untrusted check
        if norm_case in self.policy.untrusted_paths or norm_path in self.policy.untrusted_paths:
            return VerifierTrustMode.UNTRUSTED

        if binary_hash and binary_hash.lower() in self.policy.untrusted_hashes:
            return VerifierTrustMode.UNTRUSTED

        # 2. Explicit trusted check
        if norm_case in self.policy.trusted_paths or norm_path in self.policy.trusted_paths:
            return VerifierTrustMode.TRUSTED

        if binary_hash and binary_hash.lower() in self.policy.trusted_hashes:
            return VerifierTrustMode.TRUSTED

        ws = os.path.abspath(workspace_dir) if workspace_dir else ""

        for udir in self.policy.untrusted_dirs:
            if self._is_within_dir(norm_path, udir):
                # If untrusted dir is broad OS temp, but workspace is placed in temp
                # (e.g. CI sandbox) and the executable is within workspace:
                if ws and self._is_within_dir(norm_path, ws):
                    if self._is_within_dir(ws, udir) and not self._is_within_dir(udir, ws):
                        continue
                return VerifierTrustMode.UNTRUSTED

        # 3. Workspace trust (strictly within workspace_dir or policy.workspace_dirs)
        if ws and self._is_within_dir(norm_path, ws):
            return VerifierTrustMode.WORKSPACE_TRUSTED

        for wdir in self.policy.workspace_dirs:
            if self._is_within_dir(norm_path, wdir):
                return VerifierTrustMode.WORKSPACE_TRUSTED

        # 4. User trusted
        for udir in self.policy.user_trusted_dirs:
            if self._is_within_dir(norm_path, udir):
                return VerifierTrustMode.USER_TRUSTED

        # 5. System allowlisted
        for sdir in self.policy.system_trusted_dirs:
            if self._is_within_dir(norm_path, sdir):
                return VerifierTrustMode.SYSTEM_TRUSTED

        # If it is sys.executable or in sys.prefix
        if os.path.normcase(os.path.abspath(norm_path)) == os.path.normcase(os.path.abspath(sys.executable)):
            return VerifierTrustMode.SYSTEM_TRUSTED

        # 6. Fail-closed default fallback: unrecognized binary is UNKNOWN (NEVER SYSTEM_TRUSTED)
        return VerifierTrustMode.UNKNOWN

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

        if trust_mode == VerifierTrustMode.UNKNOWN:
            return matched_defn, trust_mode, f"IDENTIFIED_AS_{vid}+UNKNOWN_BINARY"

        return matched_defn, trust_mode, f"AUTHORIZED_{vid}"


_GLOBAL_TRUST_REGISTRY: Optional[TrustRegistry] = None


def get_trust_registry() -> TrustRegistry:
    global _GLOBAL_TRUST_REGISTRY
    if _GLOBAL_TRUST_REGISTRY is None:
        _GLOBAL_TRUST_REGISTRY = TrustRegistry()
    return _GLOBAL_TRUST_REGISTRY
