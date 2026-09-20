"""
S-Class Core: Canonical D10 End-to-End Vertical Slice Closure (sclass.core.vertical_slice).

Implements the single canonical S-Class task that actually traverses the core:
Task
 ↓
Obligation(s)
 ↓
Claim(s)
 ↓
Policy evaluation
 ↓
Controller authorization
 ↓
Action / ExecutionEnvelope
 ↓
D6 execution
 ↓
independent observation
 ↓
Evidence
 ↓
D4 assessment
 ↓
FAILURE → Recovery obligation → Planner
 ↓
Controller authorization again
 ↓
Repair execution
 ↓
Re-verification
 ↓
final ACCEPT
 ↓
durable assurance / receipt

Enforces Hard Acceptance Criteria A through J:
A. Planner cannot directly execute.
B. Controller authorization is mandatory.
C. Worker claims cannot directly become accepted truth.
D. Verification failure produces a recoverable state.
E. Recovery creates/reopens the correct obligation.
F. Repair requires a fresh authorization.
G. Old failed evidence is not reused as final proof.
H. Fresh evidence can establish the repaired claim.
I. Final acceptance is derived from canonical state, not a success flag.
J. The complete scenario is reproducible deterministically.
"""

from __future__ import annotations
import os
import sys
import uuid
import json
import time
import hmac
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, Optional, List, Tuple, Set

from sclass.storage.paths import WorkspacePaths
from sclass.storage.locks import WorkspaceLock
from sclass.domain.project import Project, ProjectBoundary
from sclass.domain.task import Task, TaskState, TaskPriority
from sclass.domain.action import ActionRequest, AuthorizationDecision, DecisionOutcome
from sclass.domain.claim import Claim, ClaimType, ClaimScope
from sclass.domain.claim_graph import CompositeClaim, EvidenceRequirement, AcceptanceDecision
from sclass.domain.evidence import (
    EvidenceReceipt,
    ObservedReceipt,
    ClaimedEvidence,
    ProposedEvidence,
)
from sclass.domain.observation import Observation
from sclass.domain.verification import VerificationResult
from sclass.control.policy import DefaultPolicyEngine
from sclass.policy.authorization_service import (
    AuthorizationService,
    verify_decision_integrity,
    compute_canonical_request_hash,
    get_authorization_secret,
)
from sclass.policy.capability_resolver import CapabilityResolver
from sclass.execution.base import ExecutionProvider, ProviderExecutionResult
from sclass.execution.native import NativeProcessProvider
from sclass.observation.factory import ObservationFactory
from sclass.observation.fingerprint import (
    compute_workspace_snapshot,
    compute_workspace_fingerprint,
)
from sclass.observation.receipt import load_receipt
from sclass.trust.ledger import LocalLedger
from sclass.verification.engine import verify_claim, check_staleness
from sclass.state.tasks import StateRepository
from sclass.state.events import EventJournal, CloudEvent
from sclass.control.token import (
    ExecutionToken,
    ExecutionAdmissionResult,
    ActionBinding,
    ExecutionContext,
    ExecutionEnvelope,
    verify_execution_envelope,
    _mint_execution_token,
    AuthoritySignerProtocol,
    D2NonceStore,
    compute_action_digest,
)
from sclass.core.errors import (
    SecurityViolationError,
    StateTransitionError,
    ObservationIntegrityError,
)


class ObligationKind(str, Enum):
    FUNCTIONAL = "functional"
    VERIFICATION = "verification"
    REPAIR = "repair"


class ObligationStatus(str, Enum):
    PENDING = "pending"
    SATISFIED = "satisfied"
    FAILED = "failed"
    REOPENED = "reopened"


@dataclass
class Obligation:
    """A concrete technical obligation derived from a canonical task."""
    obligation_id: str
    task_id: str
    kind: ObligationKind
    description: str
    target: str
    status: ObligationStatus = ObligationStatus.PENDING
    bound_claim_id: Optional[str] = None
    parent_obligation_id: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "obligation_id": self.obligation_id,
            "task_id": self.task_id,
            "kind": self.kind.value if isinstance(self.kind, ObligationKind) else str(self.kind),
            "description": self.description,
            "target": self.target,
            "status": self.status.value if isinstance(self.status, ObligationStatus) else str(self.status),
            "bound_claim_id": self.bound_claim_id,
            "parent_obligation_id": self.parent_obligation_id,
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Obligation:
        return cls(
            obligation_id=data["obligation_id"],
            task_id=data["task_id"],
            kind=ObligationKind(data.get("kind", ObligationKind.FUNCTIONAL.value)),
            description=data["description"],
            target=data.get("target", ""),
            status=ObligationStatus(data.get("status", ObligationStatus.PENDING.value)),
            bound_claim_id=data.get("bound_claim_id"),
            parent_obligation_id=data.get("parent_obligation_id"),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            metadata=dict(data.get("metadata", {})),
        )






def resolve_workspace_source_sha(workspace_dir: str) -> str:
    """Resolves real 40-character repository source SHA (not placeholder 0*40)."""
    try:
        import subprocess
        res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=workspace_dir, capture_output=True, text=True, timeout=2)
        if res.returncode == 0 and len(res.stdout.strip()) == 40:
            return res.stdout.strip()
    except Exception:
        pass
    h = hashlib.sha1()
    norm_ws = os.path.abspath(workspace_dir).replace("\\", "/")
    h.update(f"sclass:source:{norm_ws}".encode("utf-8"))
    for root, dirs, files in os.walk(workspace_dir):
        dirs.sort()
        for f in sorted(files):
            if f.endswith(".py"):
                p = os.path.join(root, f)
                try:
                    with open(p, "rb") as fp:
                        h.update(f.encode("utf-8"))
                        h.update(fp.read())
                except Exception:
                    pass
    return h.hexdigest()


class SlicePlanner:
    """
    D-Layer Planner: proposes actions to satisfy obligations.
    INVARIANT: The planner CANNOT directly execute actions (Criterion A).
    Direct invocation of execution from the planner strictly fails closed.
    """
    def __init__(self, workspace_dir: str):
        self.workspace_dir = workspace_dir

    def plan_implementation_action(self, task_id: str, buggy: bool = True) -> ActionRequest:
        """Proposes action to implement multiply(a, b)."""
        if buggy:
            code = (
                "def add(a: int, b: int) -> int:\n"
                "    return a + b\n\n"
                "def multiply(a: int, b: int) -> int:\n"
                "    # Defect: addition instead of multiplication\n"
                "    return a + b\n"
            )
        else:
            code = (
                "def add(a: int, b: int) -> int:\n"
                "    return a + b\n\n"
                "def multiply(a: int, b: int) -> int:\n"
                "    return a * b\n"
            )
        return ActionRequest(
            actor="worker_planner",
            session=task_id,
            capability="fs.write",
            action="file_edit",
            target="math_utils.py",
            parameters={"content": code, "path": "math_utils.py"},
            workspace=self.workspace_dir,
            context={
                "intent": "implement_multiplication",
                "buggy": buggy,
                "claim_id": f"claim_func_{task_id}",
                "obligation_id": f"ob_func_{task_id}",
            },
        )

    def plan_verification_action(self, task_id: str) -> ActionRequest:
        """Proposes action to run pytest test suite."""
        py_exe = sys.executable
        cmd = f'"{py_exe}" -m pytest tests/test_math_utils.py -q'
        return ActionRequest(
            actor="worker_planner",
            session=task_id,
            capability="terminal.execute",
            action="run_command",
            target=cmd,
            parameters={"command": cmd, "cwd": self.workspace_dir},
            workspace=self.workspace_dir,
            context={
                "intent": "run_test_suite",
                "claim_id": f"claim_verif_{task_id}",
                "obligation_id": f"ob_verif_{task_id}",
            },
        )

    def plan_repair_action(self, task_id: str) -> ActionRequest:
        """Proposes repair action correcting the defect."""
        code = (
            "def add(a: int, b: int) -> int:\n"
            "    return a + b\n\n"
            "def multiply(a: int, b: int) -> int:\n"
            "    # Repaired: valid multiplication\n"
            "    return a * b\n"
        )
        return ActionRequest(
            actor="worker_planner",
            session=task_id,
            capability="fs.write",
            action="file_edit",
            target="math_utils.py",
            parameters={"content": code, "path": "math_utils.py"},
            workspace=self.workspace_dir,
            context={
                "intent": "repair_multiplication",
                "repaired": True,
                "claim_id": f"claim_func_{task_id}",
                "obligation_id": f"ob_repair_{task_id}",
            },
        )

    def direct_execute(self, action: ActionRequest) -> Any:
        """
        Attempting to directly execute from the planner is strictly forbidden.
        Enforces Criterion A: Planner cannot directly execute.
        """
        raise SecurityViolationError(
            "Criterion A Violation: Planner cannot directly execute actions. "
            "All actions must be submitted to D5 Controller for authorization."
        )


class SliceController:
    """
    D5 Controller: Authorizes ActionRequests using canonical D5 AuthorizationService
    and issues single-use ExecutionEnvelopes sealed with HMAC integrity tokens.
    Enforces Criterion B: Controller authorization is mandatory.
    Enforces Criterion F: Repair requires a fresh authorization (envelopes are single-use).
    Durable single-use protection persists across controller/process restarts.
    """
    def __init__(
        self,
        workspace_dir: str,
        auth_service: Optional[AuthorizationService] = None,
        secret_key: Optional[bytes] = None,
    ):
        self.workspace_dir = os.path.abspath(workspace_dir)
        self.secret_key = secret_key or get_authorization_secret()
        self.auth_service = auth_service or AuthorizationService(
            secret_key=self.secret_key,
            capability_registry=CapabilityResolver.get_global_registry(),
        )
        self.consumed_envelopes: Set[str] = set()
        self.nonce_store = D2NonceStore(workspace_dir=self.workspace_dir)
        self._decisions: Dict[str, AuthorizationDecision] = {}
        self._requests: Dict[str, ActionRequest] = {}
        self._load_consumed_envelopes()

    def _get_consumed_file_path(self) -> str:
        paths = WorkspacePaths(self.workspace_dir)
        paths.ensure_directories()
        return os.path.join(paths.trust_dir, "consumed_admissions.jsonl")

    def _get_decisions_file_path(self) -> str:
        paths = WorkspacePaths(self.workspace_dir)
        paths.ensure_directories()
        return os.path.join(paths.trust_dir, "authorized_decisions.jsonl")

    def _load_consumed_envelopes(self) -> None:
        """Loads consumed envelope IDs from persistent storage (EventJournal and trust store). Fails closed if corrupt."""
        # 1. From EventJournal
        try:
            journal = EventJournal(self.workspace_dir)
            for evt in journal.read_all():
                if evt.type == "sclass.admission.consumed":
                    env_id = evt.data.get("envelope_id") if isinstance(evt.data, dict) else None
                    if not env_id:
                        raise SecurityViolationError("Malformed admission event in EventJournal: missing 'envelope_id'.")
                    self.consumed_envelopes.add(env_id)
        except SecurityViolationError:
            raise
        except Exception as e:
            raise SecurityViolationError(f"Event journal is corrupt or unreadable: {e}") from e

        # 2. From persistent trust file
        try:
            consumed_file = self._get_consumed_file_path()
            if os.path.exists(consumed_file):
                with open(consumed_file, "r", encoding="utf-8") as f:
                    for line_num, line in enumerate(f, start=1):
                        line = line.strip()
                        if line:
                            data = json.loads(line)
                            if not isinstance(data, dict) or "envelope_id" not in data or not data["envelope_id"]:
                                raise SecurityViolationError(f"Malformed consumed record in admission store at line {line_num}: missing 'envelope_id'.")
                            self.consumed_envelopes.add(data["envelope_id"])
        except SecurityViolationError:
            raise
        except Exception as e:
            raise SecurityViolationError(f"Durable admission store is corrupt or unreadable: {e}") from e

    def is_consumed(self, envelope_id: str) -> bool:
        """Checks if an envelope ID has been consumed (re-checking persistent storage)."""
        self._load_consumed_envelopes()
        return envelope_id in self.consumed_envelopes

    def _mark_consumed_locked(self, envelope_id: str, request_hash: str = "") -> None:
        """Internal helper to mark envelope consumed while caller holds WorkspaceLock. Fails closed on I/O error."""
        now_iso = datetime.now(timezone.utc).isoformat()

        # 1. Append to EventJournal (must commit before execution)
        try:
            journal = EventJournal(self.workspace_dir)
            journal.append(
                event_type="sclass.admission.consumed",
                subject=f"admission:{envelope_id}",
                data={
                    "envelope_id": envelope_id,
                    "request_hash": request_hash,
                    "consumed_at": now_iso,
                },
            )
        except Exception as e:
            raise SecurityViolationError(f"Failed to persist consumed admission to EventJournal: {e}") from e

        # 2. Append to persistent trust file (must commit before execution)
        try:
            consumed_file = self._get_consumed_file_path()
            with open(consumed_file, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "envelope_id": envelope_id,
                    "request_hash": request_hash,
                    "consumed_at": now_iso,
                }) + "\n")
                f.flush()
                os.fsync(f.fileno())
        except Exception as e:
            raise SecurityViolationError(f"Failed to persist consumed admission to trust store: {e}") from e

        # In-memory record updated only after durable persistence successfully commits
        self.consumed_envelopes.add(envelope_id)
        if self.nonce_store:
            self.nonce_store.reserve_nonce(f"ADMIT:{envelope_id}")

    def mark_consumed(self, envelope_id: str, request_hash: str = "") -> None:
        """Atomically marks an envelope as consumed under WorkspaceLock."""
        with WorkspaceLock(self.workspace_dir, lock_name="admission"):
            self._mark_consumed_locked(envelope_id, request_hash)

    def _persist_decision(
        self,
        decision_id: str,
        decision: AuthorizationDecision,
        request: ActionRequest,
        token_id: str = "",
        execution_nonce: str = "",
    ) -> None:
        try:
            dec_file = self._get_decisions_file_path()
            with open(dec_file, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "decision_id": decision_id,
                    "token_id": token_id,
                    "execution_nonce": execution_nonce,
                    "decision": decision.to_dict(),
                    "request": request.to_dict(),
                }) + "\n")
                f.flush()
                os.fsync(f.fileno())
        except Exception:
            pass

    def get_decision(self, decision_id: str) -> Optional[AuthorizationDecision]:
        if decision_id in self._decisions:
            return self._decisions[decision_id]
        dec_file = self._get_decisions_file_path()
        if os.path.exists(dec_file):
            try:
                with open(dec_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            rec = json.loads(line)
                            if rec.get("decision_id") == decision_id:
                                dec = AuthorizationDecision.from_dict(rec.get("decision", {}))
                                self._decisions[decision_id] = dec
                                return dec
            except Exception:
                pass
        return None

    def get_request(self, token_or_nonce: str) -> Optional[ActionRequest]:
        if token_or_nonce in self._requests:
            return self._requests[token_or_nonce]
        dec_file = self._get_decisions_file_path()
        if os.path.exists(dec_file):
            try:
                with open(dec_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            rec = json.loads(line)
                            if (rec.get("token_id") == token_or_nonce or 
                                rec.get("execution_nonce") == token_or_nonce or 
                                rec.get("decision_id") == token_or_nonce):
                                req = ActionRequest.from_dict(rec.get("request", {}))
                                self._requests[token_or_nonce] = req
                                return req
            except Exception:
                pass
        return None

    def authorize(
        self,
        request: ActionRequest,
        obligation_id: Optional[str] = None,
        source_sha: Optional[str] = None,
    ) -> ExecutionEnvelope:
        decision = self.auth_service.authorize(request, workspace_dir=self.workspace_dir)
        if not decision.is_allowed:
            raise SecurityViolationError(f"Controller rejected action [{decision.policy_id}]: {decision.reason}")

        resolved_obligation = (
            obligation_id
            or (request.context.get("obligation_id") if request.context else None)
            or f"ob_{request.session or 'default'}"
        )
        resolved_source_sha = source_sha or resolve_workspace_source_sha(self.workspace_dir)

        purpose = request.context.get("intent", "execute_action") if request.context else "execute_action"
        action_binding = ActionBinding(
            action_type=request.action,
            target=request.target,
            purpose=purpose,
            parameters=dict(request.parameters or {}),
        )
        ctx = ExecutionContext(
            provider_id="provider_local",
            sandbox_profile_id="sandbox_none",
            workspace_id=self.workspace_dir,
            resource_profile_id="res_default",
            capability_set=[request.capability],
        )
        now_iso = datetime.now(timezone.utc).isoformat()
        from datetime import timedelta
        exp_iso = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        import uuid

        signer = AuthoritySignerProtocol(secret_key=self.secret_key)
        token_id = f"TOK-{uuid.uuid4().hex[:12].upper()}"
        decision_id = (
            getattr(decision, "decision_id", None)
            or (decision.metadata.get("decision_id") if isinstance(decision.metadata, dict) else None)
            or f"DEC-{uuid.uuid4().hex[:12].upper()}"
        )

        token = _mint_execution_token(
            token_id=token_id,
            decision_id=decision_id,
            obligation_id=resolved_obligation,
            proposal_id=request.session or "task_default",
            action_digest=action_binding.action_digest,
            context_digest=ctx.context_digest,
            source_sha=resolved_source_sha,
            policy_version=1,
            issued_at=now_iso,
            expires_at=exp_iso,
            authority_signer=signer,
            owner_id=request.actor,
        )

        from sclass.control.token import _build_admission_payload, _compute_admission_canonical_bytes
        ad_payload = _build_admission_payload(
            token_id=token.token_id,
            execution_nonce=token.execution_nonce,
            obligation_id=token.obligation_id,
            action_digest=token.action_digest,
            context_digest=token.context_digest,
            source_sha=token.source_sha,
            policy_version=token.policy_version,
            decision_id=token.decision_id,
            admitted_at=now_iso,
            owner_id=request.actor,
        )
        canonical_bytes = _compute_admission_canonical_bytes(ad_payload)
        sig = signer.sign_payload(canonical_bytes, "Gate3AuthoritativeVerifier", now_iso)

        admission = ExecutionAdmissionResult(
            token_id=token.token_id,
            execution_nonce=token.execution_nonce,
            obligation_id=token.obligation_id,
            action_digest=token.action_digest,
            context_digest=token.context_digest,
            source_sha=token.source_sha,
            policy_version=token.policy_version,
            decision_id=token.decision_id,
            admitted_at=now_iso,
            is_admitted=True,
            owner_id=request.actor,
            signature=sig,
        )

        env = ExecutionEnvelope(
            token=token,
            admission=admission,
            action_binding=action_binding,
            execution_context=ctx,
        )

        self._decisions[token.decision_id] = decision
        self._requests[token.token_id] = request
        self._requests[token.execution_nonce] = request
        self._requests[token.decision_id] = request
        self._persist_decision(
            decision_id=token.decision_id,
            decision=decision,
            request=request,
            token_id=token.token_id,
            execution_nonce=token.execution_nonce,
        )

        return env

    def validate_and_consume(
        self,
        envelope: ExecutionEnvelope,
        request: Optional[ActionRequest] = None,
        decision: Optional[AuthorizationDecision] = None,
    ) -> None:
        if not envelope or not isinstance(envelope, ExecutionEnvelope):
            raise SecurityViolationError("Criterion B Violation: Controller authorization is mandatory. No valid ExecutionEnvelope provided.")

        with WorkspaceLock(self.workspace_dir, lock_name="admission"):
            if self.is_consumed(envelope.token.execution_nonce):
                raise SecurityViolationError(
                    f"Criterion F Violation: Repair requires fresh authorization. "
                    f"ExecutionEnvelope '{envelope.token.execution_nonce}' has already been consumed."
                )

            current_gen = getattr(getattr(self.auth_service, "capability_registry", None), "generation", None)
            if current_gen is None:
                current_gen = CapabilityResolver.get_global_registry().generation
            current_pol_ver = getattr(self.auth_service, "policy_version", None) or "1.0.0"

            dec = decision or self.get_decision(envelope.token.decision_id)
            if dec:
                if getattr(dec, "capability_registry_generation", 0) != current_gen:
                    raise SecurityViolationError("Registry generation mismatch")
                if getattr(dec, "policy_version", "1.0.0") != current_pol_ver:
                    raise SecurityViolationError("Policy version mismatch")
                req = request or self.get_request(envelope.token.token_id) or self.get_request(envelope.token.execution_nonce)
                if req:
                    is_valid, reason = verify_decision_integrity(
                        decision=dec,
                        request=req,
                        expected_registry_generation=current_gen,
                        expected_policy_version=current_pol_ver,
                        secret_key=self.secret_key,
                    )
                    if not is_valid:
                        raise SecurityViolationError(f"Decision integrity failed: {reason}")

            signer = AuthoritySignerProtocol(secret_key=self.secret_key)
            valid = verify_execution_envelope(
                envelope=envelope,
                expected_source_sha=envelope.token.source_sha,
                expected_policy_version=envelope.token.policy_version,
                current_time_iso=datetime.now(timezone.utc).isoformat(),
                authority_signer=signer,
                nonce_store=self.nonce_store,
            )
            if not valid:
                raise SecurityViolationError("ExecutionEnvelope verification failed")

            req_hash = dec.request_hash if dec else envelope.token.action_digest
            self._mark_consumed_locked(envelope.token.execution_nonce, req_hash)


class SliceExecutor:
    """
    D6 Execution Provider Gateway:
    Executes authorized ExecutionEnvelopes using existing NativeProcessProvider.
    Do not introduce a second executor.
    Independently verifies authoritative authorization artifact before executing:
    - authority authenticity and cryptographic integrity
    - exact action binding
    - exact execution-context binding
    - policy/capability/version binding
    - single-use/replay protection
    """
    def __init__(
        self,
        workspace_dir: str,
        controller: Optional[SliceController] = None,
        provider: Optional[ExecutionProvider] = None,
        secret_key: Optional[bytes] = None,
    ):
        self.workspace_dir = os.path.abspath(workspace_dir)
        self.secret_key = secret_key or get_authorization_secret()
        self.controller = controller or SliceController(self.workspace_dir, secret_key=self.secret_key)
        self.provider = provider or NativeProcessProvider()

    def verify_authorization_artifact(
        self,
        envelope: ExecutionEnvelope,
        request: Optional[ActionRequest] = None,
        decision: Optional[AuthorizationDecision] = None,
        expected_obligation_id: Optional[str] = None,
    ) -> None:
        if not envelope or not isinstance(envelope, ExecutionEnvelope):
            raise SecurityViolationError("Criterion B Violation: Controller authorization is mandatory. No valid ExecutionEnvelope provided.")

        # Single-use check
        if self.controller.is_consumed(envelope.token.execution_nonce):
            raise SecurityViolationError(
                f"Criterion F Violation: Repair requires fresh authorization. "
                f"ExecutionEnvelope '{envelope.token.execution_nonce}' has already been consumed."
            )

        dec = decision or self.controller.get_decision(envelope.token.decision_id)
        if dec is None:
            raise SecurityViolationError("Canonical authorization decision required for execution.")

        req = request or self.controller.get_request(envelope.token.token_id) or self.controller.get_request(envelope.token.execution_nonce)
        if req is None:
            req = ActionRequest(
                actor=envelope.token.owner_id or "agent",
                session=envelope.token.proposal_id,
                capability=envelope.execution_context.capability_set[0] if envelope.execution_context.capability_set else "terminal.execute",
                action=envelope.action_binding.action_type,
                target=envelope.action_binding.target,
                parameters=dict(envelope.action_binding.parameters or {}),
                workspace=envelope.execution_context.workspace_id,
                context={"intent": envelope.action_binding.purpose},
            )

        # 1. Recompute canonical action digest directly from actual executed ActionRequest (Requirement 5)
        purpose = req.context.get("intent", "execute_action") if req.context else "execute_action"
        actual_action_digest = compute_action_digest(
            action_type=req.action,
            target=req.target,
            purpose=purpose,
            parameters=req.parameters,
        )
        if not (actual_action_digest == envelope.action_binding.action_digest == envelope.token.action_digest == envelope.admission.action_digest):
            raise SecurityViolationError(
                f"Action digest mismatch at D6 boundary: actual request digest '{actual_action_digest}' != "
                f"binding '{envelope.action_binding.action_digest}' or token '{envelope.token.action_digest}'."
            )

        # 2. Canonical decision verification at D5->D6 boundary using verify_decision_integrity (Requirement 7)
        current_gen = getattr(getattr(self.controller.auth_service, "capability_registry", None), "generation", CapabilityResolver.get_global_registry().generation)
        current_pol_ver = getattr(self.controller.auth_service, "policy_version", "1.0.0")

        is_valid, reason = verify_decision_integrity(
            decision=dec,
            request=req,
            expected_registry_generation=current_gen,
            expected_policy_version=current_pol_ver,
            secret_key=self.secret_key,
        )
        if not is_valid:
            raise SecurityViolationError(f"Authorization decision verification failed at D6 boundary: {reason}")

        if not dec.is_allowed:
            raise SecurityViolationError(f"Decision outcome is not allowed: {dec.reason}")

        if envelope.token.decision_id != getattr(dec, "decision_id", envelope.token.decision_id):
            raise SecurityViolationError("Token decision_id mismatch with authorization decision.")

        # 3. Obligation check
        if expected_obligation_id and envelope.token.obligation_id != expected_obligation_id:
            raise SecurityViolationError(
                f"Obligation ID mismatch at D6 boundary: envelope bound to '{envelope.token.obligation_id}', expected '{expected_obligation_id}'."
            )

        # 4. Cryptographic envelope verification
        signer = AuthoritySignerProtocol(secret_key=self.secret_key)
        valid = verify_execution_envelope(
            envelope=envelope,
            expected_source_sha=envelope.token.source_sha,
            expected_policy_version=envelope.token.policy_version,
            current_time_iso=datetime.now(timezone.utc).isoformat(),
            authority_signer=signer,
            nonce_store=self.controller.nonce_store,
        )
        if not valid:
            raise SecurityViolationError("ExecutionEnvelope cryptographic verification failed.")

    def execute_envelope(
        self,
        envelope: ExecutionEnvelope,
        request: Optional[ActionRequest] = None,
        decision: Optional[AuthorizationDecision] = None,
        ledger: Optional[LocalLedger] = None,
        expected_obligation_id: Optional[str] = None,
    ) -> ProviderExecutionResult:
        """Executes an authorized envelope under independent S-Class observation."""
        # Enforce D6 Independent Verification Gate
        self.verify_authorization_artifact(
            envelope=envelope,
            request=request,
            decision=decision,
            expected_obligation_id=expected_obligation_id,
        )

        # Atomically validate and mark consumed (fails closed on concurrent replay)
        self.controller.validate_and_consume(
            envelope=envelope,
            request=request,
            decision=decision,
        )

        req = request or self.controller.get_request(envelope.token.token_id) or self.controller.get_request(envelope.token.execution_nonce)
        if req is None:
            req = ActionRequest(
                actor=envelope.token.owner_id or "agent",
                session=envelope.token.proposal_id,
                capability=envelope.execution_context.capability_set[0] if envelope.execution_context.capability_set else "terminal.execute",
                action=envelope.action_binding.action_type,
                target=envelope.action_binding.target,
                parameters=dict(envelope.action_binding.parameters or {}),
                workspace=envelope.execution_context.workspace_id,
                context={"intent": envelope.action_binding.purpose},
            )
        dec = decision or self.controller.get_decision(envelope.token.decision_id)
        l = ledger or LocalLedger(workspace_dir=self.workspace_dir)

        if req.action == "file_edit" or req.capability in ("fs.write", "filesystem.write"):
            target_rel = req.target or req.parameters.get("path", "math_utils.py")
            content = req.parameters.get("content", "")
            import base64
            b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
            py_exe = sys.executable
            # Execute file modification via D6 NativeProcessProvider to guarantee authentic process observation
            cmd = f'"{py_exe}" -c "import base64, pathlib; p = pathlib.Path(\'{target_rel}\'); p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(base64.b64decode(\'{b64}\'))"'
            return self.provider.execute(
                command=cmd,
                cwd=self.workspace_dir,
                request=req,
                authorization_decision=dec,
                ledger=l,
                task_id=envelope.token.proposal_id,
                require_authorization=True,
            )
        else:
            # Command execution via canonical D6 NativeProcessProvider
            result = self.provider.execute(
                command=req,
                cwd=self.workspace_dir,
                request=req,
                authorization_decision=dec,
                ledger=l,
                task_id=envelope.token.proposal_id,
                require_authorization=True,
            )
            return result


def verify_canonical_acceptance(
    task_id: str,
    workspace_dir: str,
    claim_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Derives acceptance strictly from canonical state (SQLite, Ledger, Journal).
    Rejects any unverified success flag (Criterion I).
    Binds acceptance to:
    - exact task ID
    - exact claim ID
    - final observed receipt ID
    - receipt hash and provenance
    - fresh workspace evidence (rejects stale/mutated evidence)
    - accepted verification result in StateRepository
    - final composite acceptance decision
    """
    ws = os.path.abspath(workspace_dir)

    # 1. State repository check (SQLite)
    repo = StateRepository(ws)
    task = repo.get_task(task_id)
    if not task:
        return {"accepted": False, "reason": "Task not found in StateRepository"}
    if task.state != TaskState.VERIFIED:
        return {"accepted": False, "reason": f"Task state is {task.state.value}, not verified"}
    if not task.verified_receipt_id:
        return {"accepted": False, "reason": "Task lacks verified_receipt_id in canonical state"}

    # 2. Canonical claim check
    target_claim = None
    if claim_id:
        target_claim = repo.get_claim(claim_id)
        if not target_claim or target_claim.task_id != task_id:
            return {"accepted": False, "reason": f"Claim '{claim_id}' not found or does not match task '{task_id}'"}
    else:
        with repo.store.get_connection() as conn:
            rows = conn.execute("SELECT claim_id FROM claims WHERE task_id = ?", (task_id,)).fetchall()
            if not rows:
                return {"accepted": False, "reason": f"No claims found for task '{task_id}'"}
            for r in rows:
                c = repo.get_claim(r["claim_id"])
                if c and (c.claim_type == ClaimType.TEST_PASS.value or "verif" in c.claim_id):
                    target_claim = c
                    break
            if not target_claim and rows:
                target_claim = repo.get_claim(rows[0]["claim_id"])

    if not target_claim:
        return {"accepted": False, "reason": f"No canonical claim could be resolved for task '{task_id}'"}

    # 3. Accepted verification result in SQLite state repository
    with repo.store.get_connection() as conn:
        verif_rows = conn.execute(
            "SELECT * FROM verifications WHERE claim_id = ? AND receipt_id = ? AND status IN ('ACCEPT', 'CLAIM_VERIFIED')",
            (target_claim.claim_id, task.verified_receipt_id),
        ).fetchall()
        if not verif_rows:
            return {
                "accepted": False,
                "reason": f"No accepted verification found in StateRepository for claim '{target_claim.claim_id}' and receipt '{task.verified_receipt_id}'",
            }

    # 4. Local ledger cryptographic integrity and receipt provenance
    ledger = LocalLedger(ws)
    is_valid, err = ledger.verify_integrity()
    if not is_valid:
        return {"accepted": False, "reason": f"Ledger integrity compromised: {err}"}

    matching_entry = None
    for entry in ledger.read_all_entries():
        if entry.get("event") == "OBSERVATION" and entry.get("payload", {}).get("receipt_id") == task.verified_receipt_id:
            matching_entry = entry
            break
    if not matching_entry:
        return {"accepted": False, "reason": f"Receipt {task.verified_receipt_id} not found in ledger OBSERVATION records"}

    payload = matching_entry.get("payload", {})
    if payload.get("exit_code") != 0:
        return {"accepted": False, "reason": f"Ledger receipt exit code is {payload.get('exit_code')}, expected 0"}

    # Receipt provenance: task_id binding in ledger
    if payload.get("task_id") and payload.get("task_id") != task_id:
        return {"accepted": False, "reason": f"Receipt task_id '{payload.get('task_id')}' does not match task '{task_id}'"}

    all_entries = ledger.read_all_entries()

    # Verification event recorded in ledger corresponding to exact claim/receipt pair
    has_verif_event = any(
        entry.get("event") == "verification"
        and entry.get("payload", {}).get("receipt_id") == task.verified_receipt_id
        and entry.get("payload", {}).get("claim_id") == target_claim.claim_id
        and entry.get("payload", {}).get("result") in ("ACCEPT", "CLAIM_VERIFIED")
        for entry in all_entries
    )
    if not has_verif_event:
        return {"accepted": False, "reason": f"No verification event for claim '{target_claim.claim_id}' and receipt '{task.verified_receipt_id}' in ledger"}

    # Authoritative acceptance facts anchored in existing ledger mechanism (rejects unauthenticated journal-only ACCEPT)
    has_ledger_acceptance = any(
        entry.get("event") in ("acceptance", "composite_acceptance")
        and entry.get("payload", {}).get("task_id") == task_id
        and entry.get("payload", {}).get("claim_id") == target_claim.claim_id
        and entry.get("payload", {}).get("receipt_id") == task.verified_receipt_id
        and entry.get("payload", {}).get("decision") == "ACCEPT"
        and (not entry.get("payload", {}).get("receipt_hash") or entry.get("payload", {}).get("receipt_hash") == payload.get("receipt_hash"))
        for entry in all_entries
    )
    if not has_ledger_acceptance:
        return {
            "accepted": False,
            "reason": f"No authentic acceptance record anchored in ledger for claim '{target_claim.claim_id}'",
        }

    # 5. Fresh workspace evidence: load receipt and test staleness
    receipt_obj = load_receipt(task.verified_receipt_id, ws)
    if receipt_obj is None:
        return {"accepted": False, "reason": f"Verified receipt '{task.verified_receipt_id}' not found in workspace"}

    # Receipt binding and integrity checks
    if receipt_obj.receipt_id != task.verified_receipt_id:
        return {"accepted": False, "reason": "Receipt ID mismatch on loaded receipt artifact"}
    if receipt_obj.task_id and receipt_obj.task_id != task_id:
        return {"accepted": False, "reason": f"Receipt task_id '{receipt_obj.task_id}' does not match task '{task_id}'"}
    if receipt_obj.claim_id and receipt_obj.claim_id != target_claim.claim_id and receipt_obj.claim_id != f"claim_{task_id}":
        return {"accepted": False, "reason": f"Receipt claim_id '{receipt_obj.claim_id}' does not match canonical claim '{target_claim.claim_id}'"}
    if receipt_obj.exit_code != 0:
        return {"accepted": False, "reason": f"Receipt exit code is {receipt_obj.exit_code}, expected 0"}

    expected_rcpt_hash = receipt_obj.compute_hash()
    if receipt_obj.receipt_hash and receipt_obj.receipt_hash != expected_rcpt_hash:
        return {"accepted": False, "reason": "Evidence receipt hash mismatch: receipt has been tampered with"}

    if payload.get("receipt_hash") and receipt_obj.receipt_hash != payload.get("receipt_hash"):
        return {"accepted": False, "reason": "Evidence receipt hash does not match ledger provenance record"}

    is_fresh, staleness_err = check_staleness(receipt_obj, ws)
    if not is_fresh:
        return {"accepted": False, "reason": f"Evidence is stale: {staleness_err}"}

    # 6. CloudEvents Journal record and final composite acceptance decision bound to exact claim
    journal = EventJournal(ws)
    events = journal.read_all()
    composite_accepted = False
    matching_journal_dec = None
    for evt in events:
        if evt.type == "sclass.task.verified" and evt.subject == f"task:{task_id}":
            if evt.data.get("verified_receipt_id") != task.verified_receipt_id:
                continue
            if evt.data.get("receipt_hash") and evt.data.get("receipt_hash") != receipt_obj.receipt_hash:
                continue
            acc_dec = evt.data.get("acceptance_decision")
            if not acc_dec:
                continue
            # Require AcceptanceDecision.claim_id == target_claim.claim_id
            if acc_dec.get("claim_id") != target_claim.claim_id:
                continue
            if acc_dec.get("decision") != "ACCEPT" and not acc_dec.get("is_accepted"):
                continue
            if acc_dec.get("unsatisfied_requirements"):
                continue
            composite_accepted = True
            matching_journal_dec = acc_dec
            break

    if not composite_accepted or not matching_journal_dec:
        return {"accepted": False, "reason": f"No accepted composite decision in CloudEvents journal for claim '{target_claim.claim_id}'"}

    return {
        "accepted": True,
        "task_id": task_id,
        "claim_id": target_claim.claim_id,
        "verified_receipt_id": task.verified_receipt_id,
        "receipt_hash": payload.get("receipt_hash"),
        "fresh_evidence": True,
        "composite_decision": "ACCEPT",
        "timestamp": task.completed_at,
    }


class CanonicalVerticalSlice:
    """
    Canonical S-Class D10 End-to-End Vertical Slice Coordinator.
    Traverses the core without bypassing any layer.
    """
    def __init__(self, workspace_dir: str):
        self.workspace_dir = os.path.abspath(workspace_dir)
        self.planner = SlicePlanner(self.workspace_dir)
        self.controller = SliceController(self.workspace_dir)
        self.executor = SliceExecutor(self.workspace_dir, self.controller)
        self.state_repo = StateRepository(self.workspace_dir)
        self.ledger = LocalLedger(self.workspace_dir)
        self.event_journal = EventJournal(self.workspace_dir)

        self.project: Optional[Project] = None
        self.task: Optional[Task] = None
        self.ob_func: Optional[Obligation] = None
        self.ob_verif: Optional[Obligation] = None
        self.ob_repair: Optional[Obligation] = None
        self.claim_func: Optional[Claim] = None
        self.claim_verif: Optional[Claim] = None

        self.initial_envelope: Optional[ExecutionEnvelope] = None
        self.initial_test_envelope: Optional[ExecutionEnvelope] = None
        self.failed_receipt: Optional[ObservedReceipt] = None
        self.failed_verdict: Optional[VerificationResult] = None

        self.repair_envelope: Optional[ExecutionEnvelope] = None
        self.reverify_envelope: Optional[ExecutionEnvelope] = None
        self.initial_receipt: Optional[ObservedReceipt] = None
        self.repair_receipt: Optional[ObservedReceipt] = None
        self.passed_receipt: Optional[ObservedReceipt] = None
        self.passed_verdict: Optional[VerificationResult] = None
        self.passed_func_verdict: Optional[VerificationResult] = None

    def setup_scenario(self) -> None:
        """Sets up a real Python repository fixture."""
        os.makedirs(self.workspace_dir, exist_ok=True)
        tests_dir = os.path.join(self.workspace_dir, "tests")
        os.makedirs(tests_dir, exist_ok=True)

        # Baseline module math_utils.py with add(a, b)
        math_utils_path = os.path.join(self.workspace_dir, "math_utils.py")
        with open(math_utils_path, "w", encoding="utf-8") as f:
            f.write(
                "def add(a: int, b: int) -> int:\n"
                "    return a + b\n"
            )

        # Test suite testing both add and multiply
        test_math_path = os.path.join(tests_dir, "test_math_utils.py")
        with open(test_math_path, "w", encoding="utf-8") as f:
            f.write(
                "from math_utils import add, multiply\n\n"
                "def test_add():\n"
                "    assert add(2, 3) == 5\n\n"
                "def test_multiply():\n"
                "    assert multiply(2, 3) == 6\n"
                "    assert multiply(-1, 5) == -5\n"
                "    assert multiply(0, 10) == 0\n"
            )

        proj_id = "canonical_d10_project"
        self.project = Project(
            project_id=proj_id,
            name="Canonical D10 Python Repo",
            boundary=ProjectBoundary(self.workspace_dir),
        )
        self.state_repo.save_project(self.project)

    def initialize_task(self) -> Task:
        """
        1. Task: Canonical D0 Task created with repository context and constraints.
        2. Obligations: Functional and verification obligations derived.
        3. Claims: Bound to obligations using existing D0 claim/evidence semantics.
        """
        if not self.project:
            self.setup_scenario()

        # 1. Canonical D0 Task
        self.task = Task.create(
            title="Add multiply(a, b) to an existing module and make the test suite pass.",
            project_id=self.project.project_id,
            description="Implement arithmetic multiply in math_utils.py and achieve 100% test suite pass.",
            priority=TaskPriority.HIGH,
        )
        self.task.metadata["repo_context"] = {
            "module": "math_utils.py",
            "test_file": "tests/test_math_utils.py",
        }
        self.task.metadata["constraints"] = [
            "no_network",
            "strict_verification",
            "controller_gated",
        ]
        self.task.transition_to(TaskState.READY)
        self.task.transition_to(TaskState.IN_PROGRESS)
        self.state_repo.save_task(self.task)

        # 2. Obligations derived
        self.ob_func = Obligation(
            obligation_id=f"ob_func_{self.task.task_id}",
            task_id=self.task.task_id,
            kind=ObligationKind.FUNCTIONAL,
            description="Add multiply(a, b) to math_utils.py",
            target="math_utils.py",
        )
        self.ob_verif = Obligation(
            obligation_id=f"ob_verif_{self.task.task_id}",
            task_id=self.task.task_id,
            kind=ObligationKind.VERIFICATION,
            description="Ensure test suite passes via pytest",
            target="tests/test_math_utils.py",
        )

        # 3. Claims bound to obligations
        self.claim_func = Claim(
            claim_id=f"claim_func_{self.task.task_id}",
            task_id=self.task.task_id,
            statement="multiply(a, b) implemented in math_utils.py",
            claim_type=ClaimType.FILE_CHANGE.value,
            target_files=("math_utils.py",),
            scope=ClaimScope(paths=("math_utils.py",)),
            metadata={"obligation_id": self.ob_func.obligation_id},
        )
        self.claim_verif = Claim(
            claim_id=f"claim_verif_{self.task.task_id}",
            task_id=self.task.task_id,
            statement="pytest test suite passes",
            claim_type=ClaimType.TEST_PASS.value,
            verifier="pytest",
            requested_verifier="pytest",
            target_files=("tests/test_math_utils.py", "math_utils.py"),
            scope=ClaimScope(test_targets=("tests/test_math_utils.py",)),
            metadata={"obligation_id": self.ob_verif.obligation_id},
        )

        self.ob_func.bound_claim_id = self.claim_func.claim_id
        self.ob_verif.bound_claim_id = self.claim_verif.claim_id

        self.task.transition_to(TaskState.CLAIMED)
        self.state_repo.save_task(self.task)
        self.state_repo.save_claim(self.claim_func)
        self.state_repo.save_claim(self.claim_verif)
        return self.task

    def attempt_initial_implementation(self, inject_defect: bool = True) -> Tuple[ObservedReceipt, VerificationResult]:
        """
        4. Policy evaluation.
        5. Controller authorization.
        6. D6 execution.
        7. Independent observation.
        8. Failure: Injected defect causes pytest to fail, evidence records failure, claim rejected.
        """
        if not self.task:
            self.initialize_task()

        # 4 & 5. Planner proposes action; Controller evaluates policy & authorizes envelope
        action_req = self.planner.plan_implementation_action(self.task.task_id, buggy=inject_defect)
        self.initial_envelope = self.controller.authorize(action_req, obligation_id=self.ob_func.obligation_id)

        # 6 & 7. D6 execution applies implementation
        impl_res = self.executor.execute_envelope(self.initial_envelope, request=action_req, ledger=self.ledger, expected_obligation_id=self.ob_func.obligation_id)
        self.initial_receipt = impl_res.evidence_receipt

        # Planner proposes test execution; Controller authorizes test envelope
        test_action_req = self.planner.plan_verification_action(self.task.task_id)
        self.initial_test_envelope = self.controller.authorize(test_action_req, obligation_id=self.ob_verif.obligation_id)

        # D6 executes pytest under independent observation
        test_exec_result = self.executor.execute_envelope(self.initial_test_envelope, request=test_action_req, ledger=self.ledger, expected_obligation_id=self.ob_verif.obligation_id)
        self.failed_receipt = test_exec_result.evidence_receipt

        # 8. Failure: pytest failed
        self.task.transition_to(TaskState.VERIFYING)
        self.failed_verdict = verify_claim(
            self.claim_verif,
            self.failed_receipt,
            workspace_dir=self.workspace_dir,
            ledger=self.ledger,
        )

        assert self.failed_verdict.is_rejected is True
        assert self.failed_verdict.status == "REJECT"

        # Claim becomes contradicted / unsatisfied -> task transitions to REJECTED
        self.task.transition_to(TaskState.REJECTED)
        self.ob_verif.status = ObligationStatus.FAILED

        self.state_repo.save_task(self.task)
        self.state_repo.save_claim(self.claim_verif)
        self.state_repo.save_verification(self.failed_verdict)

        return self.failed_receipt, self.failed_verdict

    def trigger_recovery(self) -> Obligation:
        """
        9. Recovery: Create the repair obligation through existing recovery path
        and reopen task state.
        """
        if not self.task or self.task.state != TaskState.REJECTED:
            raise StateTransitionError("Recovery requires a rejected/failed task state.")

        # Derive repair obligation
        self.ob_repair = Obligation(
            obligation_id=f"ob_repair_{self.task.task_id}",
            task_id=self.task.task_id,
            kind=ObligationKind.REPAIR,
            description="Repair multiply(a, b) logic to return product a * b",
            target="math_utils.py",
            parent_obligation_id=self.ob_verif.obligation_id,
            status=ObligationStatus.PENDING,
        )

        # Transition task back to recoverable working state (Criterion D)
        self.task.transition_to(TaskState.READY)
        self.task.transition_to(TaskState.IN_PROGRESS)
        self.state_repo.save_task(self.task)
        return self.ob_repair

    def execute_repair(self) -> ProviderExecutionResult:
        """
        9b. Send repair action through planner/controller boundary.
        Fresh authorization is mandatory (Criterion F).
        """
        if not self.ob_repair or self.ob_repair.status != ObligationStatus.PENDING:
            self.trigger_recovery()

        # Planner plans repair
        repair_action_req = self.planner.plan_repair_action(self.task.task_id)

        # Controller authorizes fresh action
        self.repair_envelope = self.controller.authorize(repair_action_req, obligation_id=self.ob_repair.obligation_id)

        # D6 executes repair
        result = self.executor.execute_envelope(self.repair_envelope, request=repair_action_req, ledger=self.ledger, expected_obligation_id=self.ob_repair.obligation_id)
        self.repair_receipt = result.evidence_receipt
        return result

    def run_reverification_and_acceptance(self) -> Tuple[ObservedReceipt, VerificationResult, AcceptanceDecision]:
        """
        10. Final verification: Run pytest again, establish repaired claim from fresh evidence.
        11. Durability: Persist final state/evidence/receipt to SQLite, EventJournal, and LocalLedger.
        """
        # Planner proposes test execution; Controller authorizes
        test_action_req = self.planner.plan_verification_action(self.task.task_id)
        self.reverify_envelope = self.controller.authorize(test_action_req, obligation_id=self.ob_verif.obligation_id)

        # D6 executes pytest under independent observation
        test_exec_result = self.executor.execute_envelope(self.reverify_envelope, request=test_action_req, ledger=self.ledger, expected_obligation_id=self.ob_verif.obligation_id)
        self.passed_receipt = test_exec_result.evidence_receipt

        # Ensure passing execution
        assert self.passed_receipt.exit_code == 0, (
            f"Re-verification failed: exit_code={self.passed_receipt.exit_code}\n"
            f"STDOUT: {test_exec_result.stdout}\n"
            f"STDERR: {test_exec_result.stderr}"
        )

        # Advance task lifecycle
        self.task.transition_to(TaskState.CLAIMED)
        self.task.transition_to(TaskState.VERIFYING)

        # 10. Final verification via D4 assessment
        self.passed_verdict = verify_claim(
            self.claim_verif,
            self.passed_receipt,
            workspace_dir=self.workspace_dir,
            ledger=self.ledger,
        )

        assert self.passed_verdict.is_accepted is True

        # Verify functional claim with authentic repair receipt
        if self.repair_receipt:
            self.passed_func_verdict = verify_claim(
                self.claim_func,
                self.repair_receipt,
                workspace_dir=self.workspace_dir,
                ledger=self.ledger,
            )
            assert self.passed_func_verdict.is_accepted is True

        # Obligations satisfied
        self.ob_repair.status = ObligationStatus.SATISFIED
        self.ob_verif.status = ObligationStatus.SATISFIED
        self.ob_func.status = ObligationStatus.SATISFIED

        # Final ACCEPT
        self.task.verified_receipt_id = self.passed_receipt.receipt_id
        self.task.transition_to(TaskState.VERIFIED)

        # Composite Claim evaluation
        composite = CompositeClaim(claim=self.claim_verif)
        composite.add_requirement(
            EvidenceRequirement(
                requirement_id="req_func",
                kind="FILE_CHANGE",
                description="math_utils.py contains multiply",
            )
        )
        composite.add_requirement(
            EvidenceRequirement(
                requirement_id="req_test",
                kind="UNIT_TESTS",
                description="pytest test suite passes",
                expected_verifier="pytest",
            )
        )
        acceptance = composite.evaluate({
            "req_func": self.repair_receipt or self.passed_receipt,
            "req_test": self.passed_receipt,
        })
        assert acceptance.is_accepted is True

        # 11. Durability: Persist to SQLite, EventJournal, and Ledger
        self.state_repo.save_task(self.task)
        self.state_repo.save_claim(self.claim_verif)
        if self.claim_func:
            self.state_repo.save_claim(self.claim_func)
        self.state_repo.save_verification(self.passed_verdict)
        if self.passed_func_verdict:
            self.state_repo.save_verification(self.passed_func_verdict)

        # Authoritative anchor in LocalLedger for composite acceptance
        self.ledger.append(
            event="composite_acceptance",
            payload={
                "task_id": self.task.task_id,
                "claim_id": self.claim_verif.claim_id,
                "receipt_id": self.passed_receipt.receipt_id,
                "receipt_hash": self.passed_receipt.receipt_hash,
                "decision": acceptance.decision,
                "satisfied_requirements": list(acceptance.satisfied_requirements),
            },
        )

        self.event_journal.append(
            event_type="sclass.task.verified",
            subject=f"task:{self.task.task_id}",
            data={
                "task_id": self.task.task_id,
                "verified_receipt_id": self.passed_receipt.receipt_id,
                "receipt_hash": self.passed_receipt.receipt_hash,
                "acceptance_decision": acceptance.to_dict(),
            },
        )
        self.event_journal.append(
            event_type="sclass.verification.accepted",
            subject=f"task:{self.task.task_id}",
            data=self.passed_verdict.to_dict(),
        )

        return self.passed_receipt, self.passed_verdict, acceptance

    def run_full_slice(self) -> Dict[str, Any]:
        """Runs the entire canonical vertical slice end-to-end."""
        self.setup_scenario()
        self.initialize_task()
        self.attempt_initial_implementation(inject_defect=True)
        self.trigger_recovery()
        self.execute_repair()
        receipt, verdict, acceptance = self.run_reverification_and_acceptance()
        canonical_status = verify_canonical_acceptance(self.task.task_id, self.workspace_dir)
        return {
            "task_id": self.task.task_id,
            "receipt": receipt,
            "verdict": verdict,
            "acceptance": acceptance,
            "canonical_status": canonical_status,
        }

    def get_canonical_trace(self) -> Dict[str, Any]:
        """
        Derives normalized, deterministic semantic trace of the slice execution:
        task -> obligations -> claims -> authorized action digests -> observed exit codes ->
        verification verdicts -> recovery transition -> final accepted claim.
        Filters out runtime-only non-deterministic values (PID, wall-clock timestamps,
        workspace absolute paths, and random UUID components).
        """
        def normalize_str(s: str) -> str:
            if not s:
                return s
            norm_ws = self.workspace_dir.replace("\\", "/")
            norm_py = sys.executable.replace("\\", "/")
            res = s.replace("\\", "/")
            import re
            if norm_ws.lower() in res.lower():
                res = re.sub(re.escape(norm_ws), "<WORKSPACE>", res, flags=re.IGNORECASE)
            if norm_py.lower() in res.lower():
                res = re.sub(re.escape(norm_py), "<PYTHON>", res, flags=re.IGNORECASE)
            return res

        def normalize_action(env: Optional[ExecutionEnvelope]) -> Optional[Dict[str, Any]]:
            if not env:
                return None
            action_binding = env.action_binding
            clean_params = {}
            for k, v in sorted(action_binding.parameters.items()):
                if isinstance(v, str):
                    clean_params[k] = normalize_str(v)
                else:
                    clean_params[k] = v

            target = normalize_str(action_binding.target)
            dec = self.controller.get_decision(env.token.decision_id)
            policy_id = dec.policy_id if dec else "UNKNOWN"
            outcome = (
                dec.outcome.value
                if hasattr(dec.outcome, "value")
                else str(dec.outcome)
            ) if dec else "ALLOW"

            cap = env.execution_context.capability_set[0] if env.execution_context.capability_set else "terminal.execute"
            norm_dict = {
                "actor": env.token.owner_id or "worker_planner",
                "capability": cap,
                "action": action_binding.action_type,
                "target": target,
                "policy_id": policy_id,
                "outcome": outcome,
                "parameters_hash": hashlib.sha256(json.dumps(clean_params, sort_keys=True).encode()).hexdigest(),
            }
            return norm_dict

        obligations = []
        for ob in (self.ob_func, self.ob_verif, self.ob_repair):
            if ob:
                obligations.append({
                    "kind": ob.kind.value if isinstance(ob.kind, ObligationKind) else str(ob.kind),
                    "description": ob.description,
                    "target": ob.target,
                    "status": ob.status.value if isinstance(ob.status, ObligationStatus) else str(ob.status),
                })

        claims = []
        for c in (self.claim_func, self.claim_verif):
            if c:
                claims.append({
                    "claim_type": c.claim_type,
                    "statement": c.statement,
                    "target_files": sorted(list(c.target_files)),
                    "verifier": c.verifier,
                })

        authorized_actions = []
        authorized_action_digests = []
        for env in (self.initial_envelope, self.initial_test_envelope, self.repair_envelope, self.reverify_envelope):
            if env:
                norm_act = normalize_action(env)
                if norm_act:
                    authorized_actions.append(norm_act)
                # Expose canonical D5 action-binding digest directly from authoritative authorization decision
                if hasattr(env, "token") and env.token.action_digest:
                    authorized_action_digests.append(env.token.action_digest)

        observed_exit_codes = []
        if self.failed_receipt:
            observed_exit_codes.append(self.failed_receipt.exit_code)
        if self.passed_receipt:
            observed_exit_codes.append(self.passed_receipt.exit_code)

        verification_verdicts = []
        if self.failed_verdict:
            verification_verdicts.append({
                "verdict_type": "initial_verification",
                "status": self.failed_verdict.status,
                "is_rejected": self.failed_verdict.is_rejected,
                "is_accepted": self.failed_verdict.is_accepted,
            })
        if self.passed_verdict:
            verification_verdicts.append({
                "verdict_type": "reverification",
                "status": self.passed_verdict.status,
                "is_rejected": self.passed_verdict.is_rejected,
                "is_accepted": self.passed_verdict.is_accepted,
            })

        recovery_transition = None
        if self.ob_repair:
            recovery_transition = {
                "recovery_obligation_kind": self.ob_repair.kind.value if isinstance(self.ob_repair.kind, ObligationKind) else str(self.ob_repair.kind),
                "recovery_target": self.ob_repair.target,
                "parent_obligation_matches": bool(self.ob_verif and self.ob_repair.parent_obligation_id == self.ob_verif.obligation_id),
            }

        steps = []
        if self.failed_receipt and self.failed_verdict:
            steps.append({
                "step": "initial_verification_defect",
                "exit_code": self.failed_receipt.exit_code,
                "verdict_status": self.failed_verdict.status,
                "is_rejected": self.failed_verdict.is_rejected,
                "is_accepted": self.failed_verdict.is_accepted,
            })

        if self.ob_repair:
            steps.append({
                "step": "recovery_transition",
                "recovery_obligation_kind": self.ob_repair.kind.value if isinstance(self.ob_repair.kind, ObligationKind) else str(self.ob_repair.kind),
                "recovery_target": self.ob_repair.target,
                "parent_obligation_matches": bool(self.ob_verif and self.ob_repair.parent_obligation_id == self.ob_verif.obligation_id),
            })

        if self.passed_receipt and self.passed_verdict:
            steps.append({
                "step": "reverification_pass",
                "exit_code": self.passed_receipt.exit_code,
                "verdict_status": self.passed_verdict.status,
                "is_rejected": self.passed_verdict.is_rejected,
                "is_accepted": self.passed_verdict.is_accepted,
            })

        final_claim = None
        if self.claim_verif:
            final_claim = {
                "statement": self.claim_verif.statement,
                "claim_type": self.claim_verif.claim_type,
                "accepted_receipt_exit_code": self.passed_receipt.exit_code if self.passed_receipt else None,
                "composite_decision": "ACCEPT",
            }

        return {
            "task": {
                "title": self.task.title if self.task else "",
                "description": self.task.description if self.task else "",
                "priority": self.task.priority.value if self.task else "",
                "final_state": self.task.state.value if self.task else "",
            },
            "obligations": obligations,
            "claims": claims,
            "authorized_actions": authorized_actions,
            "authorized_action_digests": authorized_action_digests,
            "observed_steps": steps,
            "observed_exit_codes": observed_exit_codes,
            "verification_verdicts": verification_verdicts,
            "recovery_transition": recovery_transition,
            "final_accepted_claim": final_claim,
        }
