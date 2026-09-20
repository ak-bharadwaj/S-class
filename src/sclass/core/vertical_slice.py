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
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, Optional, List, Tuple, Set

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
from sclass.control.authorization import authorize
from sclass.control.policy import DefaultPolicyEngine
from sclass.execution.base import ExecutionProvider, ProviderExecutionResult
from sclass.execution.native import NativeProcessProvider
from sclass.observation.factory import ObservationFactory
from sclass.observation.fingerprint import (
    compute_workspace_snapshot,
    compute_workspace_fingerprint,
)
from sclass.trust.ledger import LocalLedger
from sclass.verification.engine import verify_claim, check_staleness
from sclass.state.tasks import StateRepository
from sclass.state.events import EventJournal, CloudEvent
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


@dataclass(frozen=True)
class ExecutionEnvelope:
    """
    Mandatory controller authorization envelope required for D6 execution.
    Direct planner execution is impossible without this envelope.
    Enforces Criterion A (Planner cannot directly execute) & B (Controller authorization is mandatory).
    """
    envelope_id: str
    task_id: str
    action_request: ActionRequest
    authorization_decision: AuthorizationDecision
    issued_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    signature: str = ""

    def verify(self) -> bool:
        """Verifies envelope authorization, validity, and cryptographic signature."""
        if not self.authorization_decision or not self.authorization_decision.is_allowed:
            return False
        if not self.envelope_id:
            return False
        if not self.signature or not self.action_request:
            return False
        expected_sig = hashlib.sha256(
            f"{self.envelope_id}:{self.action_request.target}:{self.authorization_decision.evaluated_at}".encode("utf-8")
        ).hexdigest()
        if self.signature != expected_sig:
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "envelope_id": self.envelope_id,
            "task_id": self.task_id,
            "action_request": self.action_request.to_dict(),
            "authorization_decision": self.authorization_decision.to_dict(),
            "issued_at": self.issued_at,
            "signature": self.signature,
        }


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
            context={"intent": "implement_multiplication", "buggy": buggy},
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
            context={"intent": "run_test_suite"},
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
            context={"intent": "repair_multiplication", "repaired": True},
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
    D5 Controller: Authorizes ActionRequests and issues single-use ExecutionEnvelopes.
    Enforces Criterion B: Controller authorization is mandatory.
    Enforces Criterion F: Repair requires a fresh authorization (envelopes are single-use).
    """
    def __init__(self, workspace_dir: str):
        self.workspace_dir = workspace_dir
        self.consumed_envelopes: Set[str] = set()

    def authorize(self, request: ActionRequest) -> ExecutionEnvelope:
        """Evaluates D3 policy and issues a single-use ExecutionEnvelope."""
        decision = authorize(request, mode="enforce", workspace_dir=self.workspace_dir)
        if not decision.is_allowed:
            raise SecurityViolationError(f"Controller rejected action [{decision.policy_id}]: {decision.reason}")

        envelope_id = f"env_{uuid.uuid4().hex[:12]}"
        sig = hashlib.sha256(f"{envelope_id}:{request.target}:{decision.evaluated_at}".encode("utf-8")).hexdigest()
        return ExecutionEnvelope(
            envelope_id=envelope_id,
            task_id=request.task_id or "task_default",
            action_request=request,
            authorization_decision=decision,
            signature=sig,
        )

    def validate_and_consume(self, envelope: ExecutionEnvelope) -> None:
        """Validates envelope and marks it consumed. Replay strictly fails closed."""
        if not envelope or not isinstance(envelope, ExecutionEnvelope):
            raise SecurityViolationError(
                "Criterion B Violation: Controller authorization is mandatory. No valid ExecutionEnvelope provided."
            )
        if not envelope.verify():
            raise SecurityViolationError("ExecutionEnvelope verification failed: AuthorizationDecision not allowed.")
        if envelope.envelope_id in self.consumed_envelopes:
            raise SecurityViolationError(
                f"Criterion F Violation: Repair requires fresh authorization. "
                f"ExecutionEnvelope '{envelope.envelope_id}' has already been consumed."
            )
        self.consumed_envelopes.add(envelope.envelope_id)


class SliceExecutor:
    """
    D6 Execution Provider Gateway:
    Executes authorized ExecutionEnvelopes using existing NativeProcessProvider.
    Do not introduce a second executor.
    """
    def __init__(
        self,
        workspace_dir: str,
        controller: SliceController,
        provider: Optional[ExecutionProvider] = None,
    ):
        self.workspace_dir = workspace_dir
        self.controller = controller
        self.provider = provider or NativeProcessProvider()

    def execute_envelope(
        self,
        envelope: ExecutionEnvelope,
        ledger: Optional[LocalLedger] = None,
    ) -> ProviderExecutionResult:
        """Executes an authorized envelope under independent S-Class observation."""
        # Enforce Controller Authorization Gate (Criterion B & F)
        self.controller.validate_and_consume(envelope)

        req = envelope.action_request
        l = ledger or LocalLedger(workspace_dir=self.workspace_dir)

        if req.action == "file_edit" or req.capability == "fs.write":
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
                authorization_decision=envelope.authorization_decision,
                ledger=l,
                task_id=envelope.task_id,
                require_authorization=True,
            )
        else:
            # Command execution via canonical D6 NativeProcessProvider
            result = self.provider.execute(
                command=req,
                cwd=self.workspace_dir,
                request=req,
                authorization_decision=envelope.authorization_decision,
                ledger=l,
                task_id=envelope.task_id,
                require_authorization=True,
            )
            return result


def verify_canonical_acceptance(task_id: str, workspace_dir: str) -> Dict[str, Any]:
    """
    Derives acceptance strictly from canonical state (SQLite, Ledger, Journal).
    Rejects any unverified success flag (Criterion I).
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

    # 2. Local ledger cryptographic integrity and receipt provenance
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

    # 3. Verification event recorded in ledger
    has_verif_event = any(
        entry.get("event") == "verification" and entry.get("payload", {}).get("receipt_id") == task.verified_receipt_id
        for entry in ledger.read_all_entries()
    )
    if not has_verif_event:
        return {"accepted": False, "reason": "No verification event for receipt in ledger"}

    # 4. CloudEvents Journal record
    journal = EventJournal(ws)
    events = journal.read_all()
    has_cloud_event = any(
        evt.type in ("sclass.task.verified", "sclass.verification.accepted") and evt.subject == f"task:{task_id}"
        for evt in events
    )
    if not has_cloud_event:
        return {"accepted": False, "reason": "CloudEvent journal lacks sclass.task.verified event"}

    return {
        "accepted": True,
        "task_id": task_id,
        "verified_receipt_id": task.verified_receipt_id,
        "receipt_hash": payload.get("receipt_hash"),
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
        self.initial_envelope = self.controller.authorize(action_req)

        # 6 & 7. D6 execution applies implementation
        impl_res = self.executor.execute_envelope(self.initial_envelope, ledger=self.ledger)
        self.initial_receipt = impl_res.evidence_receipt

        # Planner proposes test execution; Controller authorizes test envelope
        test_action_req = self.planner.plan_verification_action(self.task.task_id)
        self.initial_test_envelope = self.controller.authorize(test_action_req)

        # D6 executes pytest under independent observation
        test_exec_result = self.executor.execute_envelope(self.initial_test_envelope, ledger=self.ledger)
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
        self.repair_envelope = self.controller.authorize(repair_action_req)

        # D6 executes repair
        result = self.executor.execute_envelope(self.repair_envelope, ledger=self.ledger)
        self.repair_receipt = result.evidence_receipt
        return result

    def run_reverification_and_acceptance(self) -> Tuple[ObservedReceipt, VerificationResult, AcceptanceDecision]:
        """
        10. Final verification: Run pytest again, establish repaired claim from fresh evidence.
        11. Durability: Persist final state/evidence/receipt to SQLite, EventJournal, and LocalLedger.
        """
        # Planner proposes test execution; Controller authorizes
        test_action_req = self.planner.plan_verification_action(self.task.task_id)
        self.reverify_envelope = self.controller.authorize(test_action_req)

        # D6 executes pytest under independent observation
        test_exec_result = self.executor.execute_envelope(self.reverify_envelope, ledger=self.ledger)
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
