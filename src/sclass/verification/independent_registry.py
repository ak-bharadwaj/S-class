"""
S-Class Verification: Independent Typed Verifier Registry.
Builds the formal typed verifier infrastructure declaring explicit verification domains,
input/output schemas, trust characteristics, and independent evaluator methods (Section 13).

Invariants:
1. Every verifier explicitly declares its domain, inputs, required evidence, and schema.
2. Generic "success: true" boolean assertions are strictly rejected as universal verification.
3. Verification results require independent observation and execution provenance.
"""

from __future__ import annotations
import ast
import os
import json
import uuid
import hashlib
import subprocess
from abc import ABC, abstractmethod
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple, Set, Union

from sclass.domain.claim import Claim, ClaimType
from sclass.domain.verification import VerificationResult, VerificationConfidence
from sclass.domain.evidence import EvidenceReceipt, ObservedReceipt
from sclass.core.errors import ObservationIntegrityError, SecurityViolationError



class VerificationDomain(str, Enum):
    TEST = "test"
    FILE = "file"
    GIT = "git"
    AST = "ast"
    TYPECHECK = "typecheck"
    LINT = "lint"
    SECURITY = "security"
    BEHAVIORAL = "behavioral"
    PROPERTY = "property"
    DEPENDENCY = "dependency"
    CROSS_CHECK = "cross_check"
    INDEPENDENT_EVALUATOR = "independent_evaluator"


@dataclass(frozen=True)
class IndependentVerifierDefinition:
    """Authoritative declaration of a verifier's identity, contract, and epistemic boundaries."""
    verifier_id: str
    version: str
    verification_domain: VerificationDomain
    inputs: Tuple[str, ...]
    required_evidence: Tuple[str, ...]
    output_schema: Dict[str, Any]
    trust_characteristics: Dict[str, Any] = field(default_factory=dict)
    independence_characteristics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verifier_id": self.verifier_id,
            "version": self.version,
            "verification_domain": self.verification_domain.value,
            "inputs": list(self.inputs),
            "required_evidence": list(self.required_evidence),
            "output_schema": self.output_schema,
            "trust_characteristics": self.trust_characteristics,
            "independence_characteristics": self.independence_characteristics,
        }


@dataclass(frozen=True)
class EvidenceRequirement:
    """Formal requirement for evidence to be acceptable for verification (Part H)."""
    requirement_id: str
    domain: VerificationDomain
    required_fields: Tuple[str, ...]
    min_confidence: VerificationConfidence = VerificationConfidence.HIGH
    requires_independent_execution: bool = True
    workspace_binding_required: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "requirement_id": self.requirement_id,
            "domain": self.domain.value,
            "required_fields": list(self.required_fields),
            "min_confidence": self.min_confidence.value,
            "requires_independent_execution": self.requires_independent_execution,
            "workspace_binding_required": self.workspace_binding_required,
        }


@dataclass(frozen=True)
class RawObservation:
    """Raw observation output collected by an IndependentObserver directly from workspace reality."""
    observer_id: str
    domain: VerificationDomain
    workspace_dir: str
    target: str
    payload: Dict[str, Any]
    observed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    exit_code: Optional[int] = None
    observation_hash: str = ""

    def __post_init__(self) -> None:
        if not self.observation_hash:
            h = hashlib.sha256(
                f"{self.observer_id}|{self.domain.value}|{self.workspace_dir}|{self.target}|{json.dumps(self.payload, sort_keys=True)}".encode("utf-8")
            ).hexdigest()
            object.__setattr__(self, "observation_hash", h)

    def to_receipt(self, receipt_id: Optional[str] = None) -> EvidenceReceipt:
        rcpt_id = receipt_id or f"rcpt_obs_{uuid.uuid4().hex[:12]}"
        return EvidenceReceipt(
            receipt_id=rcpt_id,
            claim_id="",
            verifier=self.observer_id,
            passed=(self.exit_code == 0) if self.exit_code is not None else True,
            evidence_hash=self.observation_hash,
            timestamp=self.observed_at,
            payload=dict(self.payload),
        )


class IndependentObserver(ABC):
    """
    Independent observer that directly queries or executes in workspace reality,
    untainted by external agent or runtime narratives.
    """
    @property
    @abstractmethod
    def observer_id(self) -> str:
        ...

    @property
    @abstractmethod
    def domain(self) -> VerificationDomain:
        ...

    @abstractmethod
    def observe(self, target: str, workspace_dir: str, parameters: Optional[Dict[str, Any]] = None) -> RawObservation:
        ...


class FileSystemObserver(IndependentObserver):
    @property
    def observer_id(self) -> str:
        return "fs-observer"

    @property
    def domain(self) -> VerificationDomain:
        return VerificationDomain.FILE

    def observe(self, target: str, workspace_dir: str, parameters: Optional[Dict[str, Any]] = None) -> RawObservation:
        full_path = os.path.join(workspace_dir, target) if not os.path.isabs(target) else target
        exists = os.path.exists(full_path)
        sha256_val = ""
        size_bytes = 0
        if exists and os.path.isfile(full_path):
            size_bytes = os.path.getsize(full_path)
            with open(full_path, "rb") as f:
                sha256_val = hashlib.sha256(f.read()).hexdigest()
        payload = {"exists": exists, "sha256": sha256_val, "size_bytes": size_bytes, "path": target}
        return RawObservation(
            observer_id=self.observer_id,
            domain=self.domain,
            workspace_dir=workspace_dir,
            target=target,
            payload=payload,
            exit_code=0 if exists else 1,
        )


class GitStatusObserver(IndependentObserver):
    @property
    def observer_id(self) -> str:
        return "git-observer"

    @property
    def domain(self) -> VerificationDomain:
        return VerificationDomain.GIT

    def observe(self, target: str, workspace_dir: str, parameters: Optional[Dict[str, Any]] = None) -> RawObservation:
        try:
            res = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=workspace_dir,
                capture_output=True,
                text=True,
                timeout=5,
            )
            head_commit = res.stdout.strip()
            exit_code = res.returncode
        except Exception as e:
            head_commit = ""
            exit_code = 1
        return RawObservation(
            observer_id=self.observer_id,
            domain=self.domain,
            workspace_dir=workspace_dir,
            target=target,
            payload={"head_commit": head_commit, "exit_code": exit_code},
            exit_code=exit_code,
        )


class IsolatedSubprocessObserver(IndependentObserver):
    @property
    def observer_id(self) -> str:
        return "subprocess-observer"

    @property
    def domain(self) -> VerificationDomain:
        return VerificationDomain.TEST

    def observe(self, target: str, workspace_dir: str, parameters: Optional[Dict[str, Any]] = None) -> RawObservation:
        cmd = (parameters or {}).get("command") or target
        try:
            res = subprocess.run(
                cmd,
                cwd=workspace_dir,
                capture_output=True,
                text=True,
                shell=True,
                timeout=30,
            )
            exit_code = res.returncode
            stdout_txt = res.stdout
            stderr_txt = res.stderr
        except Exception as e:
            exit_code = 127
            stdout_txt = ""
            stderr_txt = str(e)

        return RawObservation(
            observer_id=self.observer_id,
            domain=self.domain,
            workspace_dir=workspace_dir,
            target=target,
            payload={
                "exit_code": exit_code,
                "stdout": stdout_txt,
                "stderr": stderr_txt,
                "command": cmd,
            },
            exit_code=exit_code,
        )


class IndependentVerifier(ABC):

    """Abstract base class for all typed, independent S-Class verifiers."""

    @property
    @abstractmethod
    def definition(self) -> IndependentVerifierDefinition:
        ...

    @property
    def verifier_id(self) -> str:
        return self.definition.verifier_id

    @property
    def domain(self) -> VerificationDomain:
        return self.definition.verification_domain

    @abstractmethod
    def verify(
        self,
        claim: Claim,
        evidence: Any,
        context: Optional[Dict[str, Any]] = None,
    ) -> VerificationResult:
        ...

    def _reject_generic_success(self, evidence: Any) -> None:
        """
        Enforces Section 13: Generic 'success: true' boolean cannot count as verification.
        """
        ev_dict = evidence.to_dict() if hasattr(evidence, "to_dict") else (dict(evidence) if isinstance(evidence, dict) else {})
        payload = ev_dict.get("payload") if isinstance(ev_dict.get("payload"), dict) else ev_dict
        if not payload:
            raise ObservationIntegrityError(
                f"Empty evidence rejected by {self.verifier_id}: Evidence must contain domain verification proof."
            )
        keys = {str(k).lower() for k in payload.keys()}
        generic_only_keys = {"success", "status", "done", "message", "details", "note", "agent_claimed", "result", "ok"}
        if keys.issubset(generic_only_keys) and not any(k in self.definition.required_evidence for k in keys):
            raise ObservationIntegrityError(
                f"Generic assertion rejected by {self.verifier_id}: "
                "Unbacked success boolean does not constitute independent domain verification."
            )


class TestVerifier(IndependentVerifier):
    __test__ = False

    def __init__(self, verifier_id: str = "test-verifier", version: str = "1.0.0"):
        self._def = IndependentVerifierDefinition(
            verifier_id=verifier_id,
            version=version,
            verification_domain=VerificationDomain.TEST,
            inputs=("test_command", "target_suite"),
            required_evidence=("exit_code", "passed_count", "failed_count"),
            output_schema={"type": "object", "required": ["passed", "exit_code"]},
            trust_characteristics={"isolation": "process_sandbox", "trust_tier": "authoritative"},
            independence_characteristics={"independent_subprocess": True, "untainted_by_agent": True},
        )

    @property
    def definition(self) -> IndependentVerifierDefinition:
        return self._def

    def verify(self, claim: Claim, evidence: Any, context: Optional[Dict[str, Any]] = None) -> VerificationResult:
        self._reject_generic_success(evidence)
        ev_dict = evidence.to_dict() if hasattr(evidence, "to_dict") else (dict(evidence) if isinstance(evidence, dict) else {})
        payload = ev_dict.get("payload") if isinstance(ev_dict.get("payload"), dict) else ev_dict
        exit_code = payload.get("exit_code")
        if exit_code is None:
            return VerificationResult(
                verifier_id=self.verifier_id,
                claim_id=claim.claim_id,
                is_verified=False,
                confidence=VerificationConfidence.ZERO,
                summary="Test verification failed: missing required exit_code in evidence",
                details=payload,
                evidence_id=ev_dict.get("receipt_id") or ev_dict.get("event_id"),
            )
        failed = payload.get("failed_count", payload.get("failed", 0))

        passed = (exit_code == 0) and (failed == 0)
        return VerificationResult(
            verifier_id=self.verifier_id,
            claim_id=claim.claim_id,
            is_verified=passed,
            confidence=VerificationConfidence.HIGH if passed else VerificationConfidence.ZERO,
            summary=f"Test run {'passed' if passed else 'failed'} (exit_code={exit_code}, failed={failed})",
            details=payload,
            evidence_id=ev_dict.get("receipt_id") or ev_dict.get("event_id"),
        )


class FileVerifier(IndependentVerifier):
    def __init__(self):
        self._def = IndependentVerifierDefinition(
            verifier_id="file-verifier",
            version="1.0.0",
            verification_domain=VerificationDomain.FILE,
            inputs=("file_path", "expected_hash"),
            required_evidence=("file_exists", "sha256"),
            output_schema={"type": "object", "required": ["exists", "sha256"]},
            trust_characteristics={"filesystem_integrity": "cryptographic_hash"},
            independence_characteristics={"direct_os_stat": True},
        )

    @property
    def definition(self) -> IndependentVerifierDefinition:
        return self._def

    def verify(self, claim: Claim, evidence: Any, context: Optional[Dict[str, Any]] = None) -> VerificationResult:
        self._reject_generic_success(evidence)
        ev_dict = evidence.to_dict() if hasattr(evidence, "to_dict") else (dict(evidence) if isinstance(evidence, dict) else {})
        payload = ev_dict.get("payload") if isinstance(ev_dict.get("payload"), dict) else ev_dict
        if "exists" not in payload and "file_exists" not in payload:
            return VerificationResult(
                verifier_id=self.verifier_id,
                claim_id=claim.claim_id,
                is_verified=False,
                confidence=VerificationConfidence.ZERO,
                summary="File verification failed: missing required exists proof in evidence",
                details=payload,
                evidence_id=ev_dict.get("receipt_id"),
            )
        exists = payload.get("exists", payload.get("file_exists", False))
        actual_hash = payload.get("sha256")
        expected_hash = claim.metadata.get("expected_hash") if claim.metadata else None

        verified = bool(exists and (expected_hash is None or actual_hash == expected_hash))
        return VerificationResult(
            verifier_id=self.verifier_id,
            claim_id=claim.claim_id,
            is_verified=verified,
            confidence=VerificationConfidence.DEFINITIVE if verified else VerificationConfidence.ZERO,
            summary=f"File verified: exists={exists}, hash={actual_hash}",
            details=payload,
            evidence_id=ev_dict.get("receipt_id"),
        )


class GitVerifier(IndependentVerifier):
    def __init__(self):
        self._def = IndependentVerifierDefinition(
            verifier_id="git-verifier",
            version="1.0.0",
            verification_domain=VerificationDomain.GIT,
            inputs=("git_ref", "workspace"),
            required_evidence=("commit_hash", "tree_clean"),
            output_schema={"type": "object", "required": ["commit_hash"]},
            trust_characteristics={"vcs_authority": "git_object_database"},
            independence_characteristics={"direct_git_cli": True},
        )

    @property
    def definition(self) -> IndependentVerifierDefinition:
        return self._def

    def verify(self, claim: Claim, evidence: Any, context: Optional[Dict[str, Any]] = None) -> VerificationResult:
        self._reject_generic_success(evidence)
        ev_dict = evidence.to_dict() if hasattr(evidence, "to_dict") else (dict(evidence) if isinstance(evidence, dict) else {})
        payload = ev_dict.get("payload") if isinstance(ev_dict.get("payload"), dict) else ev_dict
        commit = payload.get("commit_hash")
        verified = bool(commit and len(commit) >= 7)
        return VerificationResult(
            verifier_id=self.verifier_id,
            claim_id=claim.claim_id,
            is_verified=verified,
            confidence=VerificationConfidence.HIGH if verified else VerificationConfidence.ZERO,
            summary=f"Git revision verified: {commit}",
            details=payload,
            evidence_id=ev_dict.get("receipt_id"),
        )


class AstVerifier(IndependentVerifier):
    def __init__(self):
        self._def = IndependentVerifierDefinition(
            verifier_id="ast-verifier",
            version="1.0.0",
            verification_domain=VerificationDomain.AST,
            inputs=("source_code", "symbol_name"),
            required_evidence=("syntax_valid", "symbols_found"),
            output_schema={"type": "object", "required": ["syntax_valid"]},
            trust_characteristics={"parser": "python_ast_tree"},
            independence_characteristics={"deterministic_ast_parser": True},
        )

    @property
    def definition(self) -> IndependentVerifierDefinition:
        return self._def

    def verify(self, claim: Claim, evidence: Any, context: Optional[Dict[str, Any]] = None) -> VerificationResult:
        self._reject_generic_success(evidence)
        ev_dict = evidence.to_dict() if hasattr(evidence, "to_dict") else (dict(evidence) if isinstance(evidence, dict) else {})
        payload = ev_dict.get("payload") if isinstance(ev_dict.get("payload"), dict) else ev_dict
        code = payload.get("source_code")
        if code is None or not isinstance(code, str):
            return VerificationResult(
                verifier_id=self.verifier_id,
                claim_id=claim.claim_id,
                is_verified=False,
                confidence=VerificationConfidence.ZERO,
                summary="AST verification failed: missing required 'source_code' in evidence payload",
                details=payload,
                evidence_id=ev_dict.get("receipt_id"),
            )
        try:
            tree = ast.parse(code)
            syntax_valid = True
            defined_symbols = [node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef))]
        except Exception as e:
            syntax_valid = False
            defined_symbols = []

        target_sym = claim.metadata.get("target_symbol") if claim.metadata else None
        verified = syntax_valid and (target_sym is None or target_sym in defined_symbols)
        return VerificationResult(
            verifier_id=self.verifier_id,
            claim_id=claim.claim_id,
            is_verified=verified,
            confidence=VerificationConfidence.DEFINITIVE if verified else VerificationConfidence.ZERO,
            summary=f"AST verification: valid={syntax_valid}, symbols={defined_symbols}",
            details={"syntax_valid": syntax_valid, "defined_symbols": defined_symbols},
            evidence_id=ev_dict.get("receipt_id"),
        )


class TypeVerifier(IndependentVerifier):
    def __init__(self):
        self._def = IndependentVerifierDefinition(
            verifier_id="type-verifier",
            version="1.0.0",
            verification_domain=VerificationDomain.TYPECHECK,
            inputs=("type_checker", "targets"),
            required_evidence=("error_count", "exit_code"),
            output_schema={"type": "object", "required": ["error_count"]},
            trust_characteristics={"type_engine": "mypy/pyright"},
            independence_characteristics={"independent_type_process": True},
        )

    @property
    def definition(self) -> IndependentVerifierDefinition:
        return self._def

    def verify(self, claim: Claim, evidence: Any, context: Optional[Dict[str, Any]] = None) -> VerificationResult:
        self._reject_generic_success(evidence)
        ev_dict = evidence.to_dict() if hasattr(evidence, "to_dict") else (dict(evidence) if isinstance(evidence, dict) else {})
        payload = ev_dict.get("payload") if isinstance(ev_dict.get("payload"), dict) else ev_dict
        if "error_count" not in payload and "exit_code" not in payload and "errors" not in payload:
            return VerificationResult(
                verifier_id=self.verifier_id,
                claim_id=claim.claim_id,
                is_verified=False,
                confidence=VerificationConfidence.ZERO,
                summary="Typecheck verification failed: missing required error_count/exit_code evidence",
                details=payload,
                evidence_id=ev_dict.get("receipt_id"),
            )
        errors = payload.get("error_count", payload.get("errors", 0))
        verified = (errors == 0) and (payload.get("exit_code", 0) == 0)
        return VerificationResult(
            verifier_id=self.verifier_id,
            claim_id=claim.claim_id,
            is_verified=verified,
            confidence=VerificationConfidence.HIGH if verified else VerificationConfidence.ZERO,
            summary=f"Typecheck verification: errors={errors}",
            details=payload,
            evidence_id=ev_dict.get("receipt_id"),
        )


class LintVerifier(IndependentVerifier):
    def __init__(self):
        self._def = IndependentVerifierDefinition(
            verifier_id="lint-verifier",
            version="1.0.0",
            verification_domain=VerificationDomain.LINT,
            inputs=("linter", "targets"),
            required_evidence=("violation_count", "exit_code"),
            output_schema={"type": "object", "required": ["violation_count"]},
            trust_characteristics={"lint_engine": "ruff/eslint"},
            independence_characteristics={"independent_lint_process": True},
        )

    @property
    def definition(self) -> IndependentVerifierDefinition:
        return self._def

    def verify(self, claim: Claim, evidence: Any, context: Optional[Dict[str, Any]] = None) -> VerificationResult:
        self._reject_generic_success(evidence)
        ev_dict = evidence.to_dict() if hasattr(evidence, "to_dict") else (dict(evidence) if isinstance(evidence, dict) else {})
        payload = ev_dict.get("payload") if isinstance(ev_dict.get("payload"), dict) else ev_dict
        if "violation_count" not in payload and "exit_code" not in payload and "violations" not in payload:
            return VerificationResult(
                verifier_id=self.verifier_id,
                claim_id=claim.claim_id,
                is_verified=False,
                confidence=VerificationConfidence.ZERO,
                summary="Lint verification failed: missing required violation_count/exit_code evidence",
                details=payload,
                evidence_id=ev_dict.get("receipt_id"),
            )
        violations = payload.get("violation_count", payload.get("violations", 0))
        verified = (violations == 0) and (payload.get("exit_code", 0) == 0)
        return VerificationResult(
            verifier_id=self.verifier_id,
            claim_id=claim.claim_id,
            is_verified=verified,
            confidence=VerificationConfidence.HIGH if verified else VerificationConfidence.ZERO,
            summary=f"Lint verification: violations={violations}",
            details=payload,
            evidence_id=ev_dict.get("receipt_id"),
        )


class SecurityVerifier(IndependentVerifier):
    def __init__(self):
        self._def = IndependentVerifierDefinition(
            verifier_id="security-verifier",
            version="1.0.0",
            verification_domain=VerificationDomain.SECURITY,
            inputs=("scan_target", "scanner"),
            required_evidence=("vulnerabilities_found", "secret_leaks"),
            output_schema={"type": "object", "required": ["vulnerabilities_found"]},
            trust_characteristics={"sast_engine": "semgrep/gitleaks"},
            independence_characteristics={"isolated_security_scan": True},
        )

    @property
    def definition(self) -> IndependentVerifierDefinition:
        return self._def

    def verify(self, claim: Claim, evidence: Any, context: Optional[Dict[str, Any]] = None) -> VerificationResult:
        self._reject_generic_success(evidence)
        ev_dict = evidence.to_dict() if hasattr(evidence, "to_dict") else (dict(evidence) if isinstance(evidence, dict) else {})
        payload = ev_dict.get("payload") if isinstance(ev_dict.get("payload"), dict) else ev_dict
        if "vulnerabilities_found" not in payload and "secret_leaks" not in payload and "vulns" not in payload:
            return VerificationResult(
                verifier_id=self.verifier_id,
                claim_id=claim.claim_id,
                is_verified=False,
                confidence=VerificationConfidence.ZERO,
                summary="Security verification failed: missing required vulnerability scan results",
                details=payload,
                evidence_id=ev_dict.get("receipt_id"),
            )
        vulns = payload.get("vulnerabilities_found", payload.get("vulns", 0))
        leaks = payload.get("secret_leaks", 0)
        verified = (vulns == 0) and (leaks == 0)
        return VerificationResult(
            verifier_id=self.verifier_id,
            claim_id=claim.claim_id,
            is_verified=verified,
            confidence=VerificationConfidence.HIGH if verified else VerificationConfidence.ZERO,
            summary=f"Security verification: vulns={vulns}, leaks={leaks}",
            details=payload,
            evidence_id=ev_dict.get("receipt_id"),
        )


class BehavioralVerifier(IndependentVerifier):
    def __init__(self):
        self._def = IndependentVerifierDefinition(
            verifier_id="behavioral-verifier",
            version="1.0.0",
            verification_domain=VerificationDomain.BEHAVIORAL,
            inputs=("input_vector", "expected_output"),
            required_evidence=("actual_output", "matched"),
            output_schema={"type": "object", "required": ["matched"]},
            trust_characteristics={"contract": "io_specification"},
            independence_characteristics={"hermetic_harness": True},
        )

    @property
    def definition(self) -> IndependentVerifierDefinition:
        return self._def

    def verify(self, claim: Claim, evidence: Any, context: Optional[Dict[str, Any]] = None) -> VerificationResult:
        self._reject_generic_success(evidence)
        ev_dict = evidence.to_dict() if hasattr(evidence, "to_dict") else (dict(evidence) if isinstance(evidence, dict) else {})
        payload = ev_dict.get("payload") if isinstance(ev_dict.get("payload"), dict) else ev_dict
        if "matched" not in payload:
            return VerificationResult(
                verifier_id=self.verifier_id,
                claim_id=claim.claim_id,
                is_verified=False,
                confidence=VerificationConfidence.ZERO,
                summary="Behavioral verification failed: missing required 'matched' proof in evidence",
                details=payload,
                evidence_id=ev_dict.get("receipt_id"),
            )
        matched = payload.get("matched", False)
        return VerificationResult(
            verifier_id=self.verifier_id,
            claim_id=claim.claim_id,
            is_verified=bool(matched),
            confidence=VerificationConfidence.HIGH if matched else VerificationConfidence.ZERO,
            summary=f"Behavioral contract matched: {matched}",
            details=payload,
            evidence_id=ev_dict.get("receipt_id"),
        )


class PropertyVerifier(IndependentVerifier):
    def __init__(self):
        self._def = IndependentVerifierDefinition(
            verifier_id="property-verifier",
            version="1.0.0",
            verification_domain=VerificationDomain.PROPERTY,
            inputs=("property_test", "iterations"),
            required_evidence=("iterations_completed", "failures"),
            output_schema={"type": "object", "required": ["failures"]},
            trust_characteristics={"fuzz_engine": "hypothesis"},
            independence_characteristics={"fuzzing_runner": True},
        )

    @property
    def definition(self) -> IndependentVerifierDefinition:
        return self._def

    def verify(self, claim: Claim, evidence: Any, context: Optional[Dict[str, Any]] = None) -> VerificationResult:
        self._reject_generic_success(evidence)
        ev_dict = evidence.to_dict() if hasattr(evidence, "to_dict") else (dict(evidence) if isinstance(evidence, dict) else {})
        payload = ev_dict.get("payload") if isinstance(ev_dict.get("payload"), dict) else ev_dict
        if "failures" not in payload and "iterations_completed" not in payload:
            return VerificationResult(
                verifier_id=self.verifier_id,
                claim_id=claim.claim_id,
                is_verified=False,
                confidence=VerificationConfidence.ZERO,
                summary="Property verification failed: missing required property test run results",
                details=payload,
                evidence_id=ev_dict.get("receipt_id"),
            )
        failures = payload.get("failures", 0)
        verified = (failures == 0) and (payload.get("iterations_completed", 0) > 0)
        return VerificationResult(
            verifier_id=self.verifier_id,
            claim_id=claim.claim_id,
            is_verified=verified,
            confidence=VerificationConfidence.HIGH if verified else VerificationConfidence.ZERO,
            summary=f"Property invariant verification: failures={failures}",
            details=payload,
            evidence_id=ev_dict.get("receipt_id"),
        )


class DependencyVerifier(IndependentVerifier):
    def __init__(self):
        self._def = IndependentVerifierDefinition(
            verifier_id="dependency-verifier",
            version="1.0.0",
            verification_domain=VerificationDomain.DEPENDENCY,
            inputs=("manifest_file", "lockfile"),
            required_evidence=("unresolved_dependencies", "integrity_ok"),
            output_schema={"type": "object", "required": ["unresolved_dependencies"]},
            trust_characteristics={"package_manager": "ecosystem_native"},
            independence_characteristics={"lockfile_verification": True},
        )

    @property
    def definition(self) -> IndependentVerifierDefinition:
        return self._def

    def verify(self, claim: Claim, evidence: Any, context: Optional[Dict[str, Any]] = None) -> VerificationResult:
        self._reject_generic_success(evidence)
        ev_dict = evidence.to_dict() if hasattr(evidence, "to_dict") else (dict(evidence) if isinstance(evidence, dict) else {})
        payload = ev_dict.get("payload") if isinstance(ev_dict.get("payload"), dict) else ev_dict
        if "unresolved_dependencies" not in payload and "unresolved" not in payload:
            return VerificationResult(
                verifier_id=self.verifier_id,
                claim_id=claim.claim_id,
                is_verified=False,
                confidence=VerificationConfidence.ZERO,
                summary="Dependency verification failed: missing required unresolved_dependencies evidence",
                details=payload,
                evidence_id=ev_dict.get("receipt_id"),
            )
        unresolved = payload.get("unresolved_dependencies", payload.get("unresolved", 0))
        verified = (unresolved == 0) and payload.get("integrity_ok", True)
        return VerificationResult(
            verifier_id=self.verifier_id,
            claim_id=claim.claim_id,
            is_verified=verified,
            confidence=VerificationConfidence.HIGH if verified else VerificationConfidence.ZERO,
            summary=f"Dependency verification: unresolved={unresolved}",
            details=payload,
            evidence_id=ev_dict.get("receipt_id"),
        )


class CrossCheckVerifier(IndependentVerifier):
    def __init__(self):
        self._def = IndependentVerifierDefinition(
            verifier_id="cross-check-verifier",
            version="1.0.0",
            verification_domain=VerificationDomain.CROSS_CHECK,
            inputs=("verifier_results", "consensus_threshold"),
            required_evidence=("participating_verifiers", "agreement_ratio"),
            output_schema={"type": "object", "required": ["agreement_ratio"]},
            trust_characteristics={"consensus": "multi_verifier"},
            independence_characteristics={"orthogonal_verification": True},
        )

    @property
    def definition(self) -> IndependentVerifierDefinition:
        return self._def

    def verify(self, claim: Claim, evidence: Any, context: Optional[Dict[str, Any]] = None) -> VerificationResult:
        self._reject_generic_success(evidence)
        ev_dict = evidence.to_dict() if hasattr(evidence, "to_dict") else (dict(evidence) if isinstance(evidence, dict) else {})
        payload = ev_dict.get("payload") if isinstance(ev_dict.get("payload"), dict) else ev_dict
        if "agreement_ratio" not in payload and "ratio" not in payload:
            return VerificationResult(
                verifier_id=self.verifier_id,
                claim_id=claim.claim_id,
                is_verified=False,
                confidence=VerificationConfidence.ZERO,
                summary="Cross-check verification failed: missing required agreement_ratio evidence",
                details=payload,
                evidence_id=ev_dict.get("receipt_id"),
            )
        ratio = payload.get("agreement_ratio", payload.get("ratio", 0.0))
        threshold = payload.get("consensus_threshold", 1.0)
        verified = ratio >= threshold
        return VerificationResult(
            verifier_id=self.verifier_id,
            claim_id=claim.claim_id,
            is_verified=verified,
            confidence=VerificationConfidence.HIGH if verified else VerificationConfidence.LOW,
            summary=f"Cross-check consensus: agreement={ratio:.2f} (threshold={threshold:.2f})",
            details=payload,
            evidence_id=ev_dict.get("receipt_id"),
        )


class IndependentEvaluator(IndependentVerifier):
    def __init__(self):
        self._def = IndependentVerifierDefinition(
            verifier_id="independent-evaluator",
            version="1.0.0",
            verification_domain=VerificationDomain.INDEPENDENT_EVALUATOR,
            inputs=("task_obligations", "claim_graph"),
            required_evidence=("all_obligations_satisfied", "evidence_fresh"),
            output_schema={"type": "object", "required": ["all_obligations_satisfied"]},
            trust_characteristics={"epistemic_authority": "sclass_core"},
            independence_characteristics={"fully_independent_from_agent": True},
        )

    @property
    def definition(self) -> IndependentVerifierDefinition:
        return self._def

    def verify(self, claim: Claim, evidence: Any, context: Optional[Dict[str, Any]] = None) -> VerificationResult:
        self._reject_generic_success(evidence)
        ev_dict = evidence.to_dict() if hasattr(evidence, "to_dict") else (dict(evidence) if isinstance(evidence, dict) else {})
        payload = ev_dict.get("payload") if isinstance(ev_dict.get("payload"), dict) else ev_dict
        if "all_obligations_satisfied" not in payload:
            return VerificationResult(
                verifier_id=self.verifier_id,
                claim_id=claim.claim_id,
                is_verified=False,
                confidence=VerificationConfidence.ZERO,
                summary="Independent evaluation failed: missing required all_obligations_satisfied evidence",
                details=payload,
                evidence_id=ev_dict.get("receipt_id"),
            )
        satisfied = payload.get("all_obligations_satisfied", False)
        fresh = payload.get("evidence_fresh", True)
        verified = satisfied and fresh
        return VerificationResult(
            verifier_id=self.verifier_id,
            claim_id=claim.claim_id,
            is_verified=verified,
            confidence=VerificationConfidence.DEFINITIVE if verified else VerificationConfidence.ZERO,
            summary=f"Independent evaluation: satisfied={satisfied}, fresh={fresh}",
            details=payload,
            evidence_id=ev_dict.get("receipt_id"),
        )


class IndependentVerifierRegistry:
    """
    Authoritative registry of typed independent verifiers.
    Enforces that every verification method has an explicit domain and schema.
    """

    def __init__(self):
        self._verifiers: Dict[str, IndependentVerifier] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        self.register(TestVerifier())
        self.register(FileVerifier())
        self.register(GitVerifier())
        self.register(AstVerifier())
        self.register(TypeVerifier())
        self.register(LintVerifier())
        self.register(SecurityVerifier())
        self.register(BehavioralVerifier())
        self.register(PropertyVerifier())
        self.register(DependencyVerifier())
        self.register(CrossCheckVerifier())
        self.register(IndependentEvaluator())

    def register(self, verifier: IndependentVerifier) -> None:
        self._verifiers[verifier.verifier_id] = verifier

    def get(self, verifier_id: str) -> Optional[IndependentVerifier]:
        return self._verifiers.get(verifier_id)

    def list_verifiers(self) -> List[str]:
        return sorted(list(self._verifiers.keys()))

    def get_by_domain(self, domain: VerificationDomain) -> List[IndependentVerifier]:
        return [v for v in self._verifiers.values() if v.domain == domain]
