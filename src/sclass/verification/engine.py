"""Multi-Engine Verification Plane (05-VERIFICATION).

Executes unit (pytest), property (Hypothesis), and static analysis (ruff) verifiers
against workspace changes, capturing exact tool versions, timing, and raw stdout/stderr
digests, emitting authentic Ed25519 SignedEvidencePayload receipts and binding them into EvidenceClosures.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import time
from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from sclass.workspace.environment import make_minimal_environment
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sclass_runtime_v6_0_1 import (
    EvidenceReceipt,
    SignedEvidencePayload,
    _stable_id,
)
from sclass_semantics_v6_0_1 import (
    AcceptanceContract,
    Admissibility,
    ClosureVerdict,
    Digest,
    EngineeringState,
    EvidenceClosure,
    EvidenceDependencySet,
    EvidenceKind,
    FrozenMap,
    Obligation,
    RequirementResult,
    SignatureBlock,
    TargetSnapshot,
    UtcInstant,
    VerificationPlan,
    VerificationStatus,
    VerificationStep,
    digest,
    signature_preimage,
)


@dataclass(frozen=True)
class VerifierExecutionRecord:
    """Raw observation record emitted by a verification engine invocation."""

    verifier_id: str
    version: str
    passed: bool
    returncode: int
    duration_ms: int
    stdout: bytes
    stderr: bytes
    stdout_digest: Digest
    stderr_digest: Digest
    started_at: UtcInstant
    ended_at: UtcInstant


def compute_sha256(data: bytes) -> Digest:
    """Compute standard SHA-256 Digest."""
    return Digest(f"sha256:{hashlib.sha256(data).hexdigest()}")


def sanitize_targets(targets: Sequence[str]) -> tuple[str, ...]:
    """Sanitize target file/directory paths against argument and flag injection."""
    sanitized: list[str] = []
    for t in targets:
        if not isinstance(t, str):
            raise TypeError(f"Target path must be a string, got {type(t).__name__}")
        cleaned = t.strip()
        if not cleaned:
            continue
        if cleaned.startswith("-"):
            raise ValueError(f"Flag argument injection rejected in target collections: {t!r}")
        sanitized.append(cleaned)
    return tuple(sanitized)


class VerifierEngine(ABC):
    """Abstract base class for modular verification engines."""

    @property
    @abstractmethod
    def verifier_id(self) -> str:
        """Engine identifier (e.g., 'pytest', 'ruff', 'hypothesis')."""

    @property
    @abstractmethod
    def evidence_kind(self) -> EvidenceKind:
        """Canonical evidence kind produced by this verifier."""

    @abstractmethod
    def get_version(self) -> str:
        """Returns the exact installed version of the underlying tool."""

    @abstractmethod
    def run(
        self,
        workspace_root: Path,
        targets: Sequence[str] = (),
        timeout_ms: int = 30000,
    ) -> VerifierExecutionRecord:
        """Executes verification and returns the raw execution record."""


class PytestVerifier(VerifierEngine):
    """Unit test verifier engine executing pytest."""

    @property
    def verifier_id(self) -> str:
        return "pytest"

    @property
    def evidence_kind(self) -> EvidenceKind:
        return EvidenceKind.BEHAVIORAL

    def get_version(self) -> str:
        try:
            import pytest

            return pytest.__version__
        except (ImportError, FileNotFoundError, subprocess.SubprocessError, OSError):
            try:
                res = subprocess.run(
                    [sys.executable, "-m", "pytest", "--version"],
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    text=True,
                    check=False,
                    env=make_minimal_environment(Path.cwd()),
                )
                return res.stdout.strip() or "8.0.0"
            except (FileNotFoundError, subprocess.SubprocessError, OSError):
                return "8.0.0"

    def run(
        self,
        workspace_root: Path,
        targets: Sequence[str] = (),
        timeout_ms: int = 30000,
    ) -> VerifierExecutionRecord:
        clean_targets = sanitize_targets(targets)
        start_ns = time.time_ns()
        start_instant = UtcInstant(start_ns // 1000)

        cmd = [sys.executable, "-m", "pytest", "-q"]
        if clean_targets:
            cmd.extend(clean_targets)
        else:
            cmd.append("tests")

        timeout_sec = max(1.0, timeout_ms / 1000.0)
        env = make_minimal_environment(workspace_root)
        src_path = workspace_root / "src"
        if src_path.is_dir():
            env["PYTHONPATH"] = str(src_path)

        try:
            res = subprocess.run(
                cmd,
                cwd=str(workspace_root),
                stdin=subprocess.DEVNULL,
                capture_output=True,
                env=env,
                check=False,
                timeout=timeout_sec,
            )
            passed = (res.returncode == 0)
            returncode = res.returncode
            stdout_bytes = res.stdout
            stderr_bytes = res.stderr
        except subprocess.TimeoutExpired as exc:
            passed = False
            returncode = -1
            stdout_bytes = exc.stdout or b""
            stderr_bytes = (exc.stderr or b"") + b"\nVerification timed out"
        except (FileNotFoundError, OSError) as exc:
            passed = False
            returncode = 127
            stdout_bytes = b""
            stderr_bytes = f"Verifier tool binary not found: {exc}".encode()

        end_ns = time.time_ns()
        end_instant = UtcInstant(end_ns // 1000)
        duration_ms = max(1, (end_ns - start_ns) // 1_000_000)

        stdout_dig = Digest(f"sha256:{hashlib.sha256(stdout_bytes).hexdigest()}")
        stderr_dig = Digest(f"sha256:{hashlib.sha256(stderr_bytes).hexdigest()}")

        return VerifierExecutionRecord(
            verifier_id=self.verifier_id,
            version=self.get_version(),
            passed=passed,
            returncode=returncode,
            duration_ms=duration_ms,
            stdout=stdout_bytes,
            stderr=stderr_bytes,
            stdout_digest=stdout_dig,
            stderr_digest=stderr_dig,
            started_at=start_instant,
            ended_at=end_instant,
        )


class HypothesisVerifier(VerifierEngine):
    """Property-based verification engine using Hypothesis."""

    @property
    def verifier_id(self) -> str:
        return "hypothesis"

    @property
    def evidence_kind(self) -> EvidenceKind:
        return EvidenceKind.PROPERTY

    def get_version(self) -> str:
        try:
            import hypothesis

            return hypothesis.__version__
        except (ImportError, FileNotFoundError, subprocess.SubprocessError, OSError):
            return "6.100.0"

    def run(
        self,
        workspace_root: Path,
        targets: Sequence[str] = (),
        timeout_ms: int = 30000,
    ) -> VerifierExecutionRecord:
        clean_targets = sanitize_targets(targets)
        start_ns = time.time_ns()
        start_instant = UtcInstant(start_ns // 1000)

        cmd = [sys.executable, "-m", "pytest", "-q"]
        if clean_targets:
            cmd.extend(clean_targets)
        else:
            cmd.extend(["-m", "hypothesis"])

        timeout_sec = max(1.0, timeout_ms / 1000.0)
        env = make_minimal_environment(workspace_root)
        src_path = workspace_root / "src"
        if src_path.is_dir():
            env["PYTHONPATH"] = str(src_path)

        try:
            res = subprocess.run(
                cmd,
                cwd=str(workspace_root),
                stdin=subprocess.DEVNULL,
                capture_output=True,
                env=env,
                check=False,
                timeout=timeout_sec,
            )
            passed = (res.returncode == 0)
            returncode = res.returncode
            stdout_bytes = res.stdout
            stderr_bytes = res.stderr
        except subprocess.TimeoutExpired as exc:
            passed = False
            returncode = -1
            stdout_bytes = exc.stdout or b""
            stderr_bytes = (exc.stderr or b"") + b"\nVerification timed out"
        except (FileNotFoundError, OSError) as exc:
            passed = False
            returncode = 127
            stdout_bytes = b""
            stderr_bytes = f"Verifier tool binary not found: {exc}".encode()

        end_ns = time.time_ns()
        end_instant = UtcInstant(end_ns // 1000)
        duration_ms = max(1, (end_ns - start_ns) // 1_000_000)

        stdout_dig = Digest(f"sha256:{hashlib.sha256(stdout_bytes).hexdigest()}")
        stderr_dig = Digest(f"sha256:{hashlib.sha256(stderr_bytes).hexdigest()}")

        return VerifierExecutionRecord(
            verifier_id=self.verifier_id,
            version=self.get_version(),
            passed=passed,
            returncode=returncode,
            duration_ms=duration_ms,
            stdout=stdout_bytes,
            stderr=stderr_bytes,
            stdout_digest=stdout_dig,
            stderr_digest=stderr_dig,
            started_at=start_instant,
            ended_at=end_instant,
        )


class RuffVerifier(VerifierEngine):
    """Static analysis and lint verification engine executing ruff."""

    @property
    def verifier_id(self) -> str:
        return "ruff"

    @property
    def evidence_kind(self) -> EvidenceKind:
        return EvidenceKind.STATIC

    def get_version(self) -> str:
        try:
            res = subprocess.run(
                [sys.executable, "-m", "ruff", "--version"],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                check=False,
                env=make_minimal_environment(Path.cwd()),
            )
            return res.stdout.strip().split()[-1] if res.stdout else "0.8.0"
        except (FileNotFoundError, subprocess.SubprocessError, OSError):
            return "0.8.0"

    def run(
        self,
        workspace_root: Path,
        targets: Sequence[str] = (),
        timeout_ms: int = 30000,
    ) -> VerifierExecutionRecord:
        clean_targets = sanitize_targets(targets)
        start_ns = time.time_ns()
        start_instant = UtcInstant(start_ns // 1000)

        cmd = [sys.executable, "-m", "ruff", "check"]
        if clean_targets:
            cmd.extend(clean_targets)
        else:
            cmd.append(".")

        timeout_sec = max(1.0, timeout_ms / 1000.0)
        try:
            res = subprocess.run(
                cmd,
                cwd=str(workspace_root),
                stdin=subprocess.DEVNULL,
                capture_output=True,
                env=make_minimal_environment(workspace_root),
                check=False,
                timeout=timeout_sec,
            )
            passed = (res.returncode == 0)
            returncode = res.returncode
            stdout_bytes = res.stdout
            stderr_bytes = res.stderr
        except subprocess.TimeoutExpired as exc:
            passed = False
            returncode = -1
            stdout_bytes = exc.stdout or b""
            stderr_bytes = (exc.stderr or b"") + b"\nVerification timed out"
        except (FileNotFoundError, OSError) as exc:
            passed = False
            returncode = 127
            stdout_bytes = b""
            stderr_bytes = f"Verifier tool binary not found: {exc}".encode()

        end_ns = time.time_ns()
        end_instant = UtcInstant(end_ns // 1000)
        duration_ms = max(1, (end_ns - start_ns) // 1_000_000)

        stdout_dig = Digest(f"sha256:{hashlib.sha256(stdout_bytes).hexdigest()}")
        stderr_dig = Digest(f"sha256:{hashlib.sha256(stderr_bytes).hexdigest()}")

        return VerifierExecutionRecord(
            verifier_id=self.verifier_id,
            version=self.get_version(),
            passed=passed,
            returncode=returncode,
            duration_ms=duration_ms,
            stdout=stdout_bytes,
            stderr=stderr_bytes,
            stdout_digest=stdout_dig,
            stderr_digest=stderr_dig,
            started_at=start_instant,
            ended_at=end_instant,
        )


class MultiEngineVerificationPlane:
    """Dispatches verification engines and emits authentic signed evidence receipts."""

    def __init__(
        self,
        private_key: Ed25519PrivateKey | None = None,
        key_id: str = "verifier-plane-key-1",
        trust_root: str = "sclass-trust-root-v1",
    ):
        self.private_key = private_key or Ed25519PrivateKey.generate()
        self.key_id = key_id
        self.trust_root = trust_root
        self._engines: dict[str, VerifierEngine] = {}

        # Register default engines
        self.register_engine(PytestVerifier())
        self.register_engine(HypothesisVerifier())
        self.register_engine(RuffVerifier())

    def register_engine(self, engine: VerifierEngine) -> None:
        """Register or override a verification engine."""
        self._engines[engine.verifier_id] = engine

    def verify_step(
        self,
        workspace_root: Path,
        step: VerificationStep,
        obligation: Obligation,
        target_snapshot: TargetSnapshot,
        observation_id: str = "obs-1",
        objective_revision: str = "rev-1",
        targets: Sequence[str] = (),
    ) -> EvidenceReceipt:
        """Execute a verification step and emit an authentic Ed25519 signed evidence receipt."""
        engine = self._engines.get(step.verifier_id)
        if engine is None:
            raise ValueError(f"Unknown verification engine: {step.verifier_id}")

        record = engine.run(workspace_root, targets=targets, timeout_ms=step.timeout_ms)
        is_tool_unavailable = (
            record.returncode in (127, -2)
            or b"unavailable" in record.stderr.lower()
            or b"not found" in record.stderr.lower()
        )

        if is_tool_unavailable:
            status = VerificationStatus.ERROR
            effective_obs_id = "TOOL_UNAVAILABLE"
        elif record.returncode == -1:
            status = VerificationStatus.TIMEOUT
            effective_obs_id = observation_id
        elif record.passed:
            status = VerificationStatus.PASS
            effective_obs_id = observation_id
        else:
            status = VerificationStatus.FAIL
            effective_obs_id = observation_id

        raw_output_digest = digest("sclass/verifier-output/v1", (record.stdout, record.stderr))
        zero_dig = Digest("sha256:" + "0" * 64)

        payload = SignedEvidencePayload(
            serialization_version="c1",
            signer_identity=self.key_id,
            verification_step_id=step.step_id,
            evidence_kind=step.evidence_kind,
            obligation_id=obligation.obligation_id,
            requirement_key=f"req-{step.verifier_id}",
            observation_id=effective_obs_id,
            target_snapshot_digest=target_snapshot.workspace_state_digest,
            objective_revision=objective_revision,
            acceptance_contract_revision=1,
            verification_plan_revision=1,
            dependency_set_digest=digest("sclass/dependency-set/v1", ()),
            result_status=status,
            input_digest=raw_output_digest,
            policy_digest=zero_dig,
            artifact_digest=raw_output_digest,
            environment_digest=target_snapshot.environment_digest,
            tool_identity=engine.verifier_id,
            tool_version=record.version,
            issued_at=record.ended_at,
            dependency_entries=(),
        )

        receipt_id = _stable_id("receipt", (obligation.obligation_id, step.step_id, str(raw_output_digest)))
        preimage = signature_preimage("sclass/evidence-signed-payload/v1", payload)
        sig_bytes = self.private_key.sign(preimage)
        signature = SignatureBlock("ed25519", self.key_id, self.trust_root, "c1", sig_bytes)

        return EvidenceReceipt(
            receipt_id=receipt_id,
            evidence_kind=step.evidence_kind,
            payload=payload,
            signature=signature,
        )

    def verify_plan(
        self,
        workspace_root: Path,
        plan: VerificationPlan,
        obligation: Obligation,
        target_snapshot: TargetSnapshot,
        observation_id: str = "obs-1",
        objective_revision: str = "rev-1",
        targets: Sequence[str] = (),
    ) -> tuple[EvidenceReceipt, ...]:
        """Execute all steps in a canonical verification plan."""
        receipts: list[EvidenceReceipt] = []
        for step in plan.steps:
            receipt = self.verify_step(
                workspace_root=workspace_root,
                step=step,
                obligation=obligation,
                target_snapshot=target_snapshot,
                observation_id=observation_id,
                objective_revision=objective_revision,
                targets=targets,
            )
            receipts.append(receipt)
        return tuple(receipts)

    def create_evidence_closure(
        self,
        obligation: Obligation,
        receipts: Sequence[EvidenceReceipt],
        state: EngineeringState,
        plan: VerificationPlan,
        contract: AcceptanceContract,
    ) -> EvidenceClosure:
        """Bind collected receipts into a canonical EvidenceClosure."""
        all_passed = bool(receipts) and all(
            r.payload.result_status == VerificationStatus.PASS for r in receipts
        )
        closure_verdict = ClosureVerdict.SATISFIED if all_passed else ClosureVerdict.UNSATISFIED

        req_results: list[RequirementResult] = []
        for req in contract.required_evidence:
            matching = [r.receipt_id for r in receipts if r.payload.requirement_key == req.requirement_key]
            matching_pass = any(
                r.payload.result_status == VerificationStatus.PASS
                for r in receipts
                if r.payload.requirement_key == req.requirement_key
            )
            req_results.append(
                RequirementResult(
                    requirement_key=req.requirement_key,
                    receipt_ids=tuple(matching),
                    admissibility=Admissibility.ADMISSIBLE if matching else Admissibility.INADMISSIBLE,
                    passed=matching_pass,
                )
            )

        dep_set = EvidenceDependencySet(
            file_digests=FrozenMap.from_items(),
            artifact_digests=(),
            whole_snapshot_bound=True,
        )

        receipt_ids = tuple(r.receipt_id for r in receipts)
        closure_id = _stable_id("closure", (obligation.obligation_id, receipt_ids))

        return EvidenceClosure(
            evidence_id=closure_id,
            obligation_id=obligation.obligation_id,
            observation_ids=(receipts[0].payload.observation_id,) if receipts else ("obs-none",),
            workspace_snapshot_id=state.workspace_snapshot_id,
            target_snapshot_digest=state.target_snapshot.workspace_state_digest,
            workspace_hash=state.target_snapshot.workspace_state_digest,
            event_sequence=state.event_sequence,
            policy_version=state.policy_version,
            objective_revision=state.objective.revisions[-1].revision_id,
            world_model_revision=state.world_model_revision,
            verification_plan_revision=plan.revision,
            acceptance_contract_revision=contract.revision,
            verifier_config_digest=Digest("sha256:" + "0" * 64),
            environment_digest=state.target_snapshot.environment_digest,
            dependency_set=dep_set,
            evidence_receipts=tuple(receipts),
            requirement_results=tuple(req_results),
            composition=contract.composition,
            verdict=closure_verdict,
        )
