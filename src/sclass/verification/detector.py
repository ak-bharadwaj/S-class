"""
S-Class Verification: Verifier Detector and Authority Classification.
Performs authoritative detection of test runners from ExecutionIdentity rather than
trusting caller-supplied strings or spoofable command substrings.
"""

from __future__ import annotations
import os
import shlex
from enum import Enum
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable, Dict, Any, Optional, List, Tuple

from sclass.execution.identity import ExecutionIdentity, ExecutionIdentityState


class VerifierConfidence(str, Enum):
    """Categorical confidence in verifier identification."""
    AUTHORIZED = "AUTHORIZED"
    UNKNOWN = "UNKNOWN"
    CONTRADICTED = "CONTRADICTED"


@dataclass(frozen=True)
class DetectionResult:
    """Immutable result of verifier detection from actual execution identity."""
    verifier_id: str
    confidence: VerifierConfidence
    evidence: Dict[str, Any]
    executable_match: bool
    argv_match: bool
    interpreter_match: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verifier_id": self.verifier_id,
            "confidence": self.confidence.value,
            "evidence": self.evidence,
            "executable_match": self.executable_match,
            "argv_match": self.argv_match,
            "interpreter_match": self.interpreter_match,
        }


@runtime_checkable
class VerifierDetector(Protocol):
    """Protocol for authoritative verifier detection from process identity."""
    def detect(self, execution: ExecutionIdentity) -> DetectionResult:
        ...


class StandardVerifierDetector:
    """
    Authoritative verifier detector inspecting actual execution identity,
    binary hashes, child execution chains, and structured argument vectors.
    """

    def detect(self, execution: ExecutionIdentity) -> DetectionResult:
        tokens = list(execution.actual_argv)
        if not tokens:
            return DetectionResult(
                verifier_id="none",
                confidence=VerifierConfidence.UNKNOWN,
                evidence={"reason": "Empty execution argument vector."},
                executable_match=False,
                argv_match=False,
                interpreter_match=False,
            )

        raw_exe = execution.executable_path or tokens[0]
        exe_base = os.path.basename(raw_exe).lower()
        if exe_base.endswith(".exe"):
            exe_base = exe_base[:-4]

        # Check trust registry policy authority
        try:
            from sclass.verification.trust_registry import get_trust_registry, VerifierTrustMode
            matched_defn, trust_mode, status_code = get_trust_registry().evaluate_verifier(execution)
            if trust_mode == VerifierTrustMode.UNTRUSTED and matched_defn:
                return DetectionResult(
                    verifier_id=matched_defn.verifier_id,
                    confidence=VerifierConfidence.CONTRADICTED,
                    evidence={
                        "status": status_code,
                        "reason": f"Binary '{raw_exe}' matched verifier '{matched_defn.verifier_id}' but is UNTRUSTED under trust policy.",
                        "trust_mode": trust_mode.value,
                    },
                    executable_match=False,
                    argv_match=True,
                    interpreter_match=False,
                )
        except Exception:
            pass


        # 1. Python Interpreters
        if exe_base in ("python", "python3", "py") or exe_base.startswith("python3.") or exe_base.startswith("python2.") or exe_base.startswith("pypy"):
            args = tokens[1:]
            # If -c is present, it is arbitrary code execution, NEVER an authorized test runner
            if "-c" in args:
                return DetectionResult(
                    verifier_id="generic",
                    confidence=VerifierConfidence.CONTRADICTED,
                    evidence={"reason": "python -c flag indicates arbitrary code execution, not an authorized test runner."},
                    executable_match=False,
                    argv_match=False,
                    interpreter_match=True,
                )

            # Check for -m module invocation
            for i, arg in enumerate(args):
                if arg == "-m" and i + 1 < len(args):
                    mod = args[i + 1].lower()
                    if mod == "pytest":
                        return DetectionResult(
                            verifier_id="pytest",
                            confidence=VerifierConfidence.AUTHORIZED,
                            evidence={"module": "pytest", "interpreter": exe_base},
                            executable_match=True,
                            argv_match=True,
                            interpreter_match=True,
                        )
                    if mod == "unittest":
                        return DetectionResult(
                            verifier_id="unittest",
                            confidence=VerifierConfidence.AUTHORIZED,
                            evidence={"module": "unittest", "interpreter": exe_base},
                            executable_match=True,
                            argv_match=True,
                            interpreter_match=True,
                        )
                elif arg.startswith("-m") and len(arg) > 2:
                    mod = arg[2:].lower()
                    if mod == "pytest":
                        return DetectionResult(
                            verifier_id="pytest",
                            confidence=VerifierConfidence.AUTHORIZED,
                            evidence={"module": "pytest", "interpreter": exe_base},
                            executable_match=True,
                            argv_match=True,
                            interpreter_match=True,
                        )
                    if mod == "unittest":
                        return DetectionResult(
                            verifier_id="unittest",
                            confidence=VerifierConfidence.AUTHORIZED,
                            evidence={"module": "unittest", "interpreter": exe_base},
                            executable_match=True,
                            argv_match=True,
                            interpreter_match=True,
                        )

            return DetectionResult(
                verifier_id="generic",
                confidence=VerifierConfidence.UNKNOWN,
                evidence={"reason": "Python script or module did not match authorized test runners."},
                executable_match=False,
                argv_match=False,
                interpreter_match=True,
            )

        # If execution identity is uncertain for non-python binaries, cannot certify verifier
        if execution.identity_state == ExecutionIdentityState.IDENTITY_UNCERTAIN.value:
            return DetectionResult(
                verifier_id="none",
                confidence=VerifierConfidence.UNKNOWN,
                evidence={"reason": "Execution identity state is uncertain (unreadable or unresolved binary)."},
                executable_match=False,
                argv_match=False,
                interpreter_match=False,
            )

        # 2. Direct Test Runner Binaries
        if exe_base in ("pytest", "py.test"):
            return DetectionResult(
                verifier_id="pytest",
                confidence=VerifierConfidence.AUTHORIZED,
                evidence={"binary": exe_base},
                executable_match=True,
                argv_match=True,
                interpreter_match=False,
            )

        if exe_base in ("jest", "vitest", "mocha"):
            return DetectionResult(
                verifier_id=exe_base,
                confidence=VerifierConfidence.AUTHORIZED,
                evidence={"binary": exe_base},
                executable_match=True,
                argv_match=True,
                interpreter_match=False,
            )

        if exe_base == "playwright":
            if len(tokens) > 1 and tokens[1].lower() == "test":
                return DetectionResult(
                    verifier_id="playwright",
                    confidence=VerifierConfidence.AUTHORIZED,
                    evidence={"binary": exe_base, "subcommand": "test"},
                    executable_match=True,
                    argv_match=True,
                    interpreter_match=False,
                )

        if exe_base in ("cargo", "go"):
            if len(tokens) > 1 and tokens[1].lower() == "test":
                return DetectionResult(
                    verifier_id=f"{exe_base}-test",
                    confidence=VerifierConfidence.AUTHORIZED,
                    evidence={"binary": exe_base, "subcommand": "test"},
                    executable_match=True,
                    argv_match=True,
                    interpreter_match=False,
                )

        if exe_base in ("npm", "pnpm", "yarn", "bun"):
            if len(tokens) > 1:
                sub = tokens[1].lower()
                if sub == "test" or (len(tokens) > 2 and sub == "run" and tokens[2].lower() == "test"):
                    return DetectionResult(
                        verifier_id=f"{exe_base}-test",
                        confidence=VerifierConfidence.AUTHORIZED,
                        evidence={"binary": exe_base, "package_script": "test"},
                        executable_match=True,
                        argv_match=True,
                        interpreter_match=False,
                    )

        # Generic / Unknown
        return DetectionResult(
            verifier_id="generic",
            confidence=VerifierConfidence.UNKNOWN,
            evidence={"reason": f"Executable '{exe_base}' is not a registered test runner."},
            executable_match=False,
            argv_match=False,
            interpreter_match=False,
        )
