"""
S-Class Execution: Runtime Harness Abstraction & Step-Code Runtime Adapter.
Provides a stable, runtime-neutral abstraction separating external execution engines
(Step-Code, Claude Code, Codex, Custom) from S-Class assurance and canonical project truth.

Enforces:
1. Dual-layer authorization: S-Class Policy + Runtime Permission Analysis (Section 10).
2. Action modification protection: action hash verification blocks altered parameters.
3. Explicit replay semantics: NEVER operations fail closed on automated replay attempts.
4. Independent execution ledger: runtime truth is tracked separately from assurance truth.
5. All runtime goal completions and tool outputs are untrusted proposals (Laws L1 & L2).
"""

from __future__ import annotations
import os
import re
import uuid
import json
import hashlib
import logging

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Callable, Set, Union

from sclass.domain.action import ActionRequest, AuthorizationDecision, DecisionOutcome
from sclass.execution.operations import (
    DurableOperation,
    OperationMetadata,
    OperationState,
    ReplayClass,
    classify_replay_safety,
    compute_action_hash,
)
from sclass.execution.events import RuntimeEvent
from sclass.core.errors import SecurityViolationError, ObservationIntegrityError

logger = logging.getLogger("sclass.execution.harness")


class StepCodeCommandAnalyzer:
    """
    Lower runtime safety layer adapting Step-Code's command permission analysis
    (docs/command-permissions.md).
    Validates command line safety, prohibited shell patterns, and path traversal.
    """
    BLOCKED_PATTERNS = [
        re.compile(r"\brm\s+(-[a-zA-Z]*[rR][a-zA-Z]*[fF]|-[a-zA-Z]*[fF][a-zA-Z]*[rR]|-[rR]\s+-[fF]|-[fF]\s+-[rR]|--recursive|--force).*\s+[\"']?([/~]|\*|[a-zA-Z]:[\\/])", re.IGNORECASE),
        re.compile(r"\brm\s+-[rR]f\b", re.IGNORECASE),
        re.compile(r"\b(Remove-Item|ri)\b.*(-[rR]ecurse|-[fF]orce)", re.IGNORECASE),
        re.compile(r"\b(del|erase|rd|rmdir)\b\s+.*(/[sS]|/[qQ]|-[sS]|-[qQ]|\\|[a-zA-Z]:[\\/])", re.IGNORECASE),
        re.compile(r":\(\)\{\s*:\s*\|\s*:\s*&\s*\};:", re.IGNORECASE), # fork bomb
        re.compile(r"\b(mkfs|dd\s+if=.*of=/dev/|Format-Volume|Clear-Disk|Initialize-Disk|fdisk|parted)\b", re.IGNORECASE),
        re.compile(r">\s*/dev/(sda|nvme|hda|disk)", re.IGNORECASE),
        re.compile(r"\b(curl|wget)\b.*\|\s*(\S+[\\/])?(sh|bash|python|python3|pwsh|powershell|cmd)", re.IGNORECASE),
        re.compile(r"\bfind\b.*(-delete|-exec\s+rm)", re.IGNORECASE),
    ]

    @classmethod
    def analyze_command(cls, command: str, workspace_dir: str = "") -> Dict[str, Any]:
        """Analyzes a terminal command string against Step-Code permission rules."""
        cmd_clean = (command or "").strip()
        if not cmd_clean:
            return {"allowed": False, "reason": "Empty command string", "risk_level": "CRITICAL"}

        for pattern in cls.BLOCKED_PATTERNS:
            if pattern.search(cmd_clean):
                return {
                    "allowed": False,
                    "reason": f"Command matches blocked destructive pattern: {pattern.pattern}",
                    "risk_level": "CRITICAL",
                }

        # Check for path traversal outside workspace if workspace_dir given (handling both POSIX and Windows separators)
        if workspace_dir:
            if any(sep in cmd_clean for sep in ("../..", "..\\..", "/../", "\\..\\")) or cmd_clean.startswith("../") or cmd_clean.startswith("..\\"):
                return {
                    "allowed": False,
                    "reason": "Command contains potential path traversal outside workspace",
                    "risk_level": "HIGH",
                }

        return {"allowed": True, "reason": "Command passed runtime permission analysis", "risk_level": "LOW"}


class RuntimeHarness(ABC):
    """
    Stable runtime harness contract for external coding agent execution planes.
    Runtime harnesses own:
    - agent execution loops
    - tool execution lifecycles
    - sessions & subagents
    - runtime retries
    - runtime permissions
    """

    @property
    @abstractmethod
    def runtime_name(self) -> str:
        """Name of the execution runtime (e.g. 'step-code', 'claude-code', 'codex', 'native')."""
        ...

    @abstractmethod
    def start_operation(self, intent: Dict[str, Any]) -> DurableOperation:
        """Initializes a durable operation for a planned action intent."""
        ...

    @abstractmethod
    def submit_action(
        self,
        action: ActionRequest,
        authorization: AuthorizationDecision,
        operation: Optional[DurableOperation] = None,
    ) -> Dict[str, Any]:
        """
        Submits an authorized action to the execution harness.
        Must verify S-Class authorization AND runtime permissions.
        """
        ...

    @abstractmethod
    def observe_operation(self, operation_id: str) -> Dict[str, Any]:
        """Observes current runtime effect state of an operation."""
        ...

    @abstractmethod
    def get_execution_state(self, operation_id: str) -> OperationState:
        """Queries execution state of an operation."""
        ...

    @abstractmethod
    def cancel_operation(self, operation_id: str, reason: str = "") -> bool:
        """Cancels an in-flight operation."""
        ...

    @abstractmethod
    def recover_operation(self, operation_id: str) -> Dict[str, Any]:
        """Performs runtime-level recovery of an interrupted operation."""
        ...

    @abstractmethod
    def spawn_agent(self, agent_config: Dict[str, Any]) -> Dict[str, Any]:
        """Spawns a child agent session within bounded concurrency."""
        ...

    @abstractmethod
    def inspect_session(self, session_id: str) -> Dict[str, Any]:
        """Inspects runtime session tree state."""
        ...

    @abstractmethod
    def subscribe_events(self, callback: Callable[[RuntimeEvent], None]) -> str:
        """Subscribes an observer to normalized runtime events."""
        ...

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Evaluates health of the execution harness."""
        ...


class StepCodeHarness(RuntimeHarness):
    """
    Concrete implementation of RuntimeHarness for Step-Code.
    Extracts and adapts Step-Code's durable operation state, effect lifecycle,
    and command permission analysis while strictly subordinating to S-Class assurance.
    """

    def __init__(self, workspace_dir: str, fail_closed: bool = True):
        self.workspace_dir = os.path.abspath(workspace_dir)
        self.fail_closed = fail_closed
        self._operations: Dict[str, DurableOperation] = {}
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._subscribers: Dict[str, Callable[[RuntimeEvent], None]] = {}
        self._sequence: int = 0
        self._is_healthy: bool = True

    @property
    def runtime_name(self) -> str:
        return "step-code"

    def set_healthy(self, healthy: bool) -> None:
        self._is_healthy = healthy

    def start_operation(self, intent: Dict[str, Any]) -> DurableOperation:
        """Initializes a durable operation in PLANNED state."""
        op_id = intent.get("operation_id") or f"op_{uuid.uuid4().hex[:12]}"
        action = intent.get("action", "")
        target = intent.get("target", "")
        parameters = intent.get("parameters", {})
        replay_class = intent.get("replay_class") or classify_replay_safety(action, target, parameters)

        intent_hash = hashlib.sha256(json.dumps(intent, sort_keys=True).encode("utf-8")).hexdigest()
        action_hash = compute_action_hash(
            intent.get("capability", action),
            action,
            target,
            parameters,
        )

        metadata = OperationMetadata(
            operation_id=op_id,
            parent_operation_id=intent.get("parent_operation_id"),
            session_id=intent.get("session_id", "default_session"),
            task_id=intent.get("task_id", "default_task"),
            agent_id=intent.get("agent_id", "default_agent"),
            action_id=intent.get("action_id", f"act_{uuid.uuid4().hex[:8]}"),
            workspace_id=intent.get("workspace_id", self.workspace_dir),
            replay_class=replay_class,
            intent_hash=intent_hash,
            action_hash=action_hash,
        )

        op = DurableOperation(metadata=metadata, state=OperationState.PLANNED)
        self._operations[op_id] = op
        self._emit_event(op, "operation_planned", {"intent": intent})
        return op

    def submit_action(
        self,
        action: ActionRequest,
        authorization: AuthorizationDecision,
        operation: Optional[DurableOperation] = None,
    ) -> Dict[str, Any]:
        """
        Executes action through the dual-layer gate:
        1. S-Class Authorization (Law L3)
        2. Step-Code Runtime Permissions (Section 10)
        3. Parameter Tampering Protection (Action hash check)
        """
        if not self._is_healthy and self.fail_closed:
            raise SecurityViolationError("Step-Code harness is currently unhealthy or unavailable. Failing closed.")

        # Resolve or create operation
        op = operation or self.start_operation({
            "action": action.action,
            "target": action.target,
            "parameters": action.parameters,
            "session_id": action.session,
            "workspace_id": action.workspace or self.workspace_dir,
            "agent_id": action.actor,
        })

        # Check 1: S-Class Authorization Decision
        if not authorization.is_allowed:
            op.transition_to(OperationState.FAILED, {"reason": f"S-Class authorization denied: {authorization.reason}"})
            self._emit_event(op, "action_blocked_sclass", {"reason": authorization.reason})
            raise SecurityViolationError(f"S-Class Authorization DENIED: {authorization.reason}")

        # Check 2: Action Hash Integrity (Protection against parameter modification after auth)
        current_hash = compute_action_hash(action.capability, action.action, action.target, action.parameters)
        auth_action_hash = authorization.metadata.get("action_hash") if authorization.metadata else None
        if auth_action_hash and auth_action_hash != current_hash:
            op.transition_to(OperationState.FAILED, {"reason": "Action parameters modified after authorization"})
            self._emit_event(op, "action_tampered", {"expected_hash": auth_action_hash, "current_hash": current_hash})
            raise SecurityViolationError(
                f"ACTION TAMPERING DETECTED: Action parameters were modified after S-Class authorization. "
                f"Expected hash {auth_action_hash}, computed {current_hash}. Re-authorization required."
            )

        # Check 3: Step-Code Runtime Permission Analysis
        cmd_str = action.parameters.get("command") or action.parameters.get("command_line") or action.target or ""
        perm_analysis = StepCodeCommandAnalyzer.analyze_command(cmd_str, self.workspace_dir)
        if not perm_analysis["allowed"]:
            op.transition_to(OperationState.FAILED, {"reason": f"Step-Code permission denied: {perm_analysis['reason']}"})
            self._emit_event(op, "action_blocked_runtime", {"analysis": perm_analysis})
            raise SecurityViolationError(f"Step-Code Runtime Permission DENIED: {perm_analysis['reason']}")

        # Transition to AUTHORIZED
        op.authorization_id = authorization.decision_id
        op.transition_to(OperationState.AUTHORIZED, {"decision": authorization.to_dict()})
        self._emit_event(op, "action_authorized", {"decision_id": authorization.decision_id})

        # Transition to EFFECT_PENDING
        op.transition_to(OperationState.EFFECT_PENDING, {"action": action.to_dict()})
        self._emit_event(op, "effect_pending", {"action": action.action, "target": action.target})

        # Execute effect in lower runtime layer
        try:
            effect_result = self._execute_runtime_effect(action)
            op.transition_to(OperationState.EFFECT_EXECUTED, effect_result)
            self._emit_event(op, "effect_executed", effect_result)

            # Runtime settlement
            settlement = {
                "settled_at": datetime.now(timezone.utc).isoformat(),
                "exit_code": effect_result.get("exit_code", 0),
                "status": "SETTLED",
                "output_bytes": len(str(effect_result.get("output", ""))),
            }
            op.transition_to(OperationState.SETTLED, settlement)
            self._emit_event(op, "settlement", settlement)

            return {
                "operation_id": op.operation_id,
                "status": "SETTLED",
                "executed": True,
                "result": effect_result,
                "settlement": settlement,
                "untrusted_candidate": True, # Reminder: execution results are evidence candidates, not truth!
            }
        except Exception as e:
            op.transition_to(OperationState.FAILED, {"reason": str(e)})
            self._emit_event(op, "effect_failed", {"error": str(e)})
            raise

    def _execute_runtime_effect(self, action: ActionRequest) -> Dict[str, Any]:
        """Simulates or executes the low-level runtime effect."""
        clean_action = (action.action or "").strip().lower()
        if clean_action in ("read_file", "view_file"):
            target_path = os.path.join(self.workspace_dir, action.target) if not os.path.isabs(action.target) else action.target
            if os.path.exists(target_path) and os.path.isfile(target_path):
                with open(target_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                return {"exit_code": 0, "output": content, "error": ""}
            return {"exit_code": 1, "output": "", "error": f"File not found: {action.target}"}

        # Generic safe execution simulation for tool / test actions
        return {
            "exit_code": 0,
            "output": f"Step-Code executed {action.action} on {action.target}",
            "error": "",
            "duration_ms": 15.0,
        }

    def observe_operation(self, operation_id: str) -> Dict[str, Any]:
        op = self._operations.get(operation_id)
        if not op:
            raise SecurityViolationError(f"Operation not found: {operation_id}")
        return {
            "operation_id": op.operation_id,
            "state": op.state.value,
            "effect_result": op.effect_result,
            "settlement": op.settlement_record,
            "replay_class": op.replay_class.value,
        }

    def get_execution_state(self, operation_id: str) -> OperationState:
        op = self._operations.get(operation_id)
        if not op:
            raise SecurityViolationError(f"Operation not found: {operation_id}")
        return op.state

    def cancel_operation(self, operation_id: str, reason: str = "") -> bool:
        op = self._operations.get(operation_id)
        if not op:
            return False
        if op.state.is_terminal:
            return False
        op.transition_to(OperationState.CANCELLED, {"reason": reason or "Cancelled by caller"})
        self._emit_event(op, "operation_cancelled", {"reason": reason})
        return True

    def recover_operation(self, operation_id: str) -> Dict[str, Any]:
        """
        Attempts runtime-level recovery of an operation.
        Strictly enforces replay semantics: NEVER operations are rejected.
        """
        op = self._operations.get(operation_id)
        if not op:
            raise SecurityViolationError(f"Unknown operation for recovery: {operation_id}")

        # Enforce replay safety
        op.assert_can_replay()

        op.mark_replayed()
        self._emit_event(op, "operation_replayed", {"replayed": True})
        return {
            "operation_id": op.operation_id,
            "recovered": True,
            "replayed": True,
            "state": op.state.value,
        }

    def spawn_agent(self, agent_config: Dict[str, Any]) -> Dict[str, Any]:
        """Spawns an agent session."""
        session_id = agent_config.get("session_id") or f"sess_{uuid.uuid4().hex[:8]}"
        session = {
            "session_id": session_id,
            "agent_type": agent_config.get("agent_type", "worker"),
            "parent_session": agent_config.get("parent_session"),
            "status": "RUNNING",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._sessions[session_id] = session
        return session

    def inspect_session(self, session_id: str) -> Dict[str, Any]:
        return self._sessions.get(session_id, {"session_id": session_id, "status": "UNKNOWN"})

    def subscribe_events(self, callback: Callable[[RuntimeEvent], None]) -> str:
        sub_id = f"sub_{uuid.uuid4().hex[:8]}"
        self._subscribers[sub_id] = callback
        return sub_id

    def unsubscribe_events(self, sub_id: str) -> bool:
        return self._subscribers.pop(sub_id, None) is not None

    def health_check(self) -> Dict[str, Any]:
        return {
            "runtime": self.runtime_name,
            "status": "HEALTHY" if self._is_healthy else "UNAVAILABLE",
            "active_operations": len([op for op in self._operations.values() if not op.state.is_terminal]),
            "sessions": len(self._sessions),
        }

    def _emit_event(self, op: DurableOperation, event_type: str, payload: Dict[str, Any]) -> RuntimeEvent:
        self._sequence += 1
        event = RuntimeEvent(
            operation_id=op.operation_id,
            parent_operation_id=op.metadata.parent_operation_id,
            session_id=op.metadata.session_id,
            task_id=op.metadata.task_id,
            action_id=op.metadata.action_id,
            agent_id=op.metadata.agent_id,
            workspace_id=op.metadata.workspace_id,
            event_type=event_type,
            sequence=self._sequence,
            intent_hash=op.metadata.intent_hash,
            action_hash=op.metadata.action_hash,
            replay_class=op.metadata.replay_class,
            runtime=self.runtime_name,
            payload=payload,
            source="harness",
        )
        for sub in list(self._subscribers.values()):
            try:
                sub(event)
            except Exception as e:
                logger.warning(f"Error in event subscriber: {e}")
        return event


class NativeHarness(RuntimeHarness):
    """Reference native harness demonstrating multi-runtime neutrality."""

    def __init__(self, workspace_dir: str):
        self.workspace_dir = os.path.abspath(workspace_dir)
        self._operations: Dict[str, DurableOperation] = {}
        self._subscribers: Dict[str, Callable[[RuntimeEvent], None]] = {}
        self._sequence = 0

    @property
    def runtime_name(self) -> str:
        return "native"

    def start_operation(self, intent: Dict[str, Any]) -> DurableOperation:
        op_id = intent.get("operation_id") or f"op_nat_{uuid.uuid4().hex[:12]}"
        action = intent.get("action", "")
        target = intent.get("target", "")
        parameters = intent.get("parameters", {})
        metadata = OperationMetadata(
            operation_id=op_id,
            parent_operation_id=intent.get("parent_operation_id"),
            session_id=intent.get("session_id", "native_session"),
            task_id=intent.get("task_id", "default_task"),
            agent_id=intent.get("agent_id", "native_agent"),
            action_id=intent.get("action_id", f"act_{uuid.uuid4().hex[:8]}"),
            workspace_id=intent.get("workspace_id", self.workspace_dir),
            replay_class=classify_replay_safety(action, target, parameters),
            intent_hash=hashlib.sha256(json.dumps(intent, sort_keys=True).encode("utf-8")).hexdigest(),
            action_hash=compute_action_hash(intent.get("capability", action), action, target, parameters),
        )
        op = DurableOperation(metadata=metadata, state=OperationState.PLANNED)
        self._operations[op_id] = op
        return op

    def submit_action(
        self,
        action: ActionRequest,
        authorization: AuthorizationDecision,
        operation: Optional[DurableOperation] = None,
    ) -> Dict[str, Any]:
        if not authorization.is_allowed:
            raise SecurityViolationError(f"Native harness blocked unauthorized action: {authorization.reason}")
        op = operation or self.start_operation({
            "action": action.action,
            "target": action.target,
            "parameters": action.parameters,
        })
        op.transition_to(OperationState.AUTHORIZED)
        op.transition_to(OperationState.EFFECT_PENDING)
        effect_res = {"exit_code": 0, "output": f"Native executed {action.action}"}
        op.transition_to(OperationState.EFFECT_EXECUTED, effect_res)
        op.transition_to(OperationState.SETTLED, {"status": "SETTLED"})
        return {"operation_id": op.operation_id, "executed": True, "result": effect_res}

    def observe_operation(self, operation_id: str) -> Dict[str, Any]:
        op = self._operations.get(operation_id)
        if not op:
            raise SecurityViolationError("Operation not found")
        return {"operation_id": op.operation_id, "state": op.state.value}

    def get_execution_state(self, operation_id: str) -> OperationState:
        op = self._operations.get(operation_id)
        if not op:
            raise SecurityViolationError("Operation not found")
        return op.state

    def cancel_operation(self, operation_id: str, reason: str = "") -> bool:
        op = self._operations.get(operation_id)
        if op and not op.state.is_terminal:
            op.transition_to(OperationState.CANCELLED)
            return True
        return False

    def recover_operation(self, operation_id: str) -> Dict[str, Any]:
        op = self._operations.get(operation_id)
        if not op:
            raise SecurityViolationError("Operation not found")
        op.assert_can_replay()
        op.mark_replayed()
        return {"operation_id": op.operation_id, "recovered": True}

    def spawn_agent(self, agent_config: Dict[str, Any]) -> Dict[str, Any]:
        return {"session_id": f"sess_nat_{uuid.uuid4().hex[:8]}", "status": "RUNNING"}

    def inspect_session(self, session_id: str) -> Dict[str, Any]:
        return {"session_id": session_id, "status": "RUNNING"}

    def subscribe_events(self, callback: Callable[[RuntimeEvent], None]) -> str:
        sub_id = f"sub_{uuid.uuid4().hex[:8]}"
        self._subscribers[sub_id] = callback
        return sub_id

    def health_check(self) -> Dict[str, Any]:
        return {"runtime": self.runtime_name, "status": "HEALTHY"}
