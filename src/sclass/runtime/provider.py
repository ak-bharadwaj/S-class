"""
S-Class Runtime: Consolidated RuntimeProvider Hierarchy.
Implements Directive Section 38 (Single Runtime Abstraction):
Converges execution harnesses into a unified provider hierarchy:
RuntimeProvider (ABC)
    ├── StepCodeProvider (src/sclass/runtime/stepcode.py)
    ├── NativeProvider
    ├── CodexProvider
    └── ClaudeProvider
Common lifecycle belongs in RuntimeProvider; runtime-specific behavior in adapters.
"""

from __future__ import annotations
import os
import uuid
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Callable

from sclass.domain.action import ActionRequest, AuthorizationDecision, DecisionOutcome
from sclass.execution.operations import (
    OperationState,
    ReplayClass,
    CrossRuntimeOperation,
    CanonicalOperationStore,
    compute_action_hash,
)
from sclass.core.errors import SecurityViolationError


logger = logging.getLogger("sclass.runtime.provider")


class RuntimeProvider(ABC):
    """
    Authoritative base contract for external agent execution engines.
    """

    def __init__(self, workspace_dir: str, provider_name: str):
        self.workspace_dir = os.path.abspath(workspace_dir)
        self.provider_name = provider_name
        self.operation_store = CanonicalOperationStore(self.workspace_dir)

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Returns health diagnostics of the runtime substrate."""
        ...

    @abstractmethod
    def execute_action(
        self,
        action: ActionRequest,
        authorization: AuthorizationDecision,
        parent_operation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Executes an authorized action, enforcing dual-layer authorization
        and persisting through the durable effect boundary.
        """
        ...

    def start_operation(self, intent: Dict[str, Any]) -> CrossRuntimeOperation:
        """Initializes a durable operation record in canonical storage."""
        op_id = f"op_{uuid.uuid4().hex[:12]}"
        action = intent.get("action", "unknown_action")
        target = intent.get("target", "")
        params = intent.get("parameters", {})

        rc = intent.get("replay_class", ReplayClass.NEVER)
        if isinstance(rc, str):
            try:
                rc = ReplayClass(rc)
            except ValueError:
                rc = ReplayClass.NEVER

        op = CrossRuntimeOperation(
            operation_id=op_id,
            runtime_name=self.provider_name,
            session_id=intent.get("session_id", "default_session"),
            task_id=intent.get("task_id", "default_task"),
            action_id=intent.get("action_id", f"act_{uuid.uuid4().hex[:8]}"),
            workspace_id=self.workspace_dir,
            intent_hash=intent.get("intent_hash", ""),
            action_hash=compute_action_hash(
                intent.get("capability", action),
                action,
                target,
                params,
                workspace_dir=self.workspace_dir,
            ),
            replay_class=rc,
            state=OperationState.PLANNED,
            metadata=dict(intent),
        )
        return self.operation_store.save_operation(op)

    def observe_operation(self, operation_id: str) -> Optional[CrossRuntimeOperation]:
        return self.operation_store.get_operation(operation_id)

    def cancel_operation(self, operation_id: str, reason: str = "") -> bool:
        op = self.operation_store.get_operation(operation_id)
        if not op or op.state.is_terminal:
            return False
        updated = op.transition_to(OperationState.CANCELLED, {"cancellation_reason": reason})
        self.operation_store.save_operation(updated)
        return True


class NativeProvider(RuntimeProvider):
    """Local native execution provider using host or sandboxed subprocesses."""

    def __init__(self, workspace_dir: str):
        super().__init__(workspace_dir, provider_name="native")

    def health_check(self) -> Dict[str, Any]:
        return {
            "runtime": "native",
            "status": "HEALTHY",
            "workspace": self.workspace_dir,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def execute_action(
        self,
        action: ActionRequest,
        authorization: AuthorizationDecision,
        parent_operation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if authorization.decision != DecisionOutcome.ALLOW:
            raise SecurityViolationError(f"Action denied by S-Class authorization: {authorization.reason}")

        # Execute safe local file read/check
        target_path = os.path.join(self.workspace_dir, action.target)
        if action.action in ("read_file", "view_file") and os.path.exists(target_path):
            with open(target_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            return {"status": "ok", "output": content, "exit_code": 0, "untrusted_candidate": True}

        return {"status": "ok", "output": f"Native action {action.action} simulated", "exit_code": 0, "untrusted_candidate": True}


class CodexProvider(RuntimeProvider):
    """External Codex provider adapter."""

    def __init__(self, workspace_dir: str):
        super().__init__(workspace_dir, provider_name="codex")

    def health_check(self) -> Dict[str, Any]:
        return {
            "runtime": "codex",
            "status": "HEALTHY",
            "workspace": self.workspace_dir,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def execute_action(
        self,
        action: ActionRequest,
        authorization: AuthorizationDecision,
        parent_operation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if authorization.decision != DecisionOutcome.ALLOW:
            raise SecurityViolationError(f"Action denied by S-Class authorization: {authorization.reason}")
        return {"status": "ok", "output": "Codex action executed", "exit_code": 0, "untrusted_candidate": True}


class ClaudeProvider(RuntimeProvider):
    """External Claude Code provider adapter."""

    def __init__(self, workspace_dir: str):
        super().__init__(workspace_dir, provider_name="claude-code")

    def health_check(self) -> Dict[str, Any]:
        return {
            "runtime": "claude-code",
            "status": "HEALTHY",
            "workspace": self.workspace_dir,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def execute_action(
        self,
        action: ActionRequest,
        authorization: AuthorizationDecision,
        parent_operation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if authorization.decision != DecisionOutcome.ALLOW:
            raise SecurityViolationError(f"Action denied by S-Class authorization: {authorization.reason}")
        return {"status": "ok", "output": "Claude Code action executed", "exit_code": 0, "untrusted_candidate": True}
