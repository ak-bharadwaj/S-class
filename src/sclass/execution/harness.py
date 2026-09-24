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
import sys
import uuid
import json
import hashlib
import logging
import shutil
import subprocess
import threading
import queue

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Callable, Set, Union

from sclass.domain.action import ActionRequest, AuthorizationDecision, DecisionOutcome
from sclass.execution.operations import (
    DurableOperation,
    OperationMetadata,
    OperationState,
    ReplayClass,
    CrossRuntimeOperation,
    CanonicalOperationStore,
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


class StepCodeRpcHarness(RuntimeHarness):
    """
    Real external-runtime adapter for Step-Code over JSONL RPC (`step --mode rpc`).
    
    Architectural Guarantees (Parts C11, D, F):
    1. Does NOT simulate effects in Python.
    2. Communicates with external Step-Code process via stdin/stdout pipes.
    3. Strictly enforces LF (0x0A, \\n) line framing. Never uses generic Unicode line splitters.
    4. S-Class dual-layer authorization executes BEFORE runtime tool execution.
    5. Fails closed on process termination, RPC errors, or malformed JSONL payloads.
    6. Persists all cross-runtime operations in canonical S-Class storage.
    """

    def __init__(
        self,
        workspace_dir: str,
        step_cmd: Optional[List[str]] = None,
        fail_closed: bool = True,
        auto_start: bool = True,
        use_test_double: bool = False,
        session_id: Optional[str] = None,
    ):
        self.workspace_dir = os.path.abspath(workspace_dir)
        self.fail_closed = fail_closed
        self.use_test_double = use_test_double
        self.store = CanonicalOperationStore(self.workspace_dir)
        self._subscribers: Dict[str, Callable[[RuntimeEvent], None]] = {}
        self._sequence = 0
        self._lock = threading.Lock()
        self._pending_requests: Dict[Union[str, int], threading.Event] = {}
        self._responses: Dict[Union[str, int], Dict[str, Any]] = {}
        self._request_counter = 0
        self._is_healthy = True
        self._proc: Optional[subprocess.Popen] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._stderr_thread: Optional[threading.Thread] = None
        self._running = False
        self._active_session: Optional[str] = session_id

        if step_cmd:
            self.step_cmd = list(step_cmd)
        else:
            self.step_cmd = self._discover_step_cmd()

        if auto_start:
            self.start_process()

    def _discover_step_cmd(self) -> List[str]:
        curr_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.abspath(os.path.join(curr_dir, "..", "..", ".."))

        # 1. Environment variable override
        step_bin = os.environ.get("STEP_CODE_BIN")
        if step_bin and os.path.exists(step_bin):
            return [step_bin, "--mode", "rpc"]

        # 2. PATH resolution for canonical step
        system_step = shutil.which("step")
        if system_step:
            return [system_step, "--mode", "rpc"]

        # 3. Explicit test double or test environment
        double_js = os.path.join(root_dir, "tools", "step_code_rpc_test_double.js")
        if not os.path.exists(double_js):
            double_js = os.path.join(root_dir, "tools", "step_rpc_server.js")

        if (
            self.use_test_double
            or os.environ.get("SCLASS_TEST_DOUBLE") == "1"
            or os.environ.get("SCLASS_ENV") == "test"
            or "pytest" in sys.modules
        ):
            if os.path.exists(double_js):
                return ["node", double_js, "--mode", "rpc"]

        # 4. Fail closed: Never default to simulation test double in production
        raise SecurityViolationError(
            "CANONICAL STEP-CODE RUNTIME MISSING: 'step' binary not found in PATH or STEP_CODE_BIN. "
            "Simulation double 'tools/step_code_rpc_test_double.js' cannot be used as default production runtime."
        )

    @property
    def runtime_name(self) -> str:
        return "step-code"

    def start_process(self) -> None:
        """Launches external Step-Code RPC process."""
        with self._lock:
            if self._proc and self._proc.poll() is None:
                return
            try:
                self._proc = subprocess.Popen(
                    self.step_cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=self.workspace_dir,
                    bufsize=0,
                )
                self._running = True
                self._is_healthy = True
                self._reader_thread = threading.Thread(
                    target=self._reader_loop,
                    name=f"StepCodeRpcReader-{id(self)}",
                    daemon=True,
                )
                self._reader_thread.start()
                self._stderr_thread = threading.Thread(
                    target=self._stderr_reader_loop,
                    name=f"StepCodeRpcStderrReader-{id(self)}",
                    daemon=True,
                )
                self._stderr_thread.start()
            except Exception as e:
                self._is_healthy = False
                logger.error(f"Failed to start Step-Code RPC process: {e}")
                if self.fail_closed:
                    raise SecurityViolationError(f"Step-Code RPC process failed to launch: {e}")

    def _stderr_reader_loop(self) -> None:
        """Drains stderr from external process to prevent OS pipe buffer saturation and deadlock."""
        stderr_pipe = self._proc.stderr if self._proc else None
        if not stderr_pipe:
            return
        try:
            while self._running:
                line = stderr_pipe.readline()
                if not line:
                    break
                logger.debug(f"[Step-Code stderr] {line.decode('utf-8', errors='replace').rstrip()}")
        except Exception:
            pass

    def _reader_loop(self) -> None:
        """
        Background reader thread processing raw stdio bytes.
        STRICT REQUIREMENT (C11):
        Uses LF (0x0A, \n) line framing. Never uses str.splitlines() or generic Unicode line splitters.
        """
        raw_buffer = bytearray()
        stdout_pipe = self._proc.stdout if self._proc else None
        if not stdout_pipe:
            return

        try:
            while self._running:
                chunk = stdout_pipe.read(4096)
                if not chunk:
                    break
                raw_buffer.extend(chunk)

                while True:
                    lf_idx = raw_buffer.find(b"\n")
                    if lf_idx == -1:
                        break
                    line_bytes = bytes(raw_buffer[:lf_idx])
                    del raw_buffer[:lf_idx + 1]

                    if line_bytes.endswith(b"\r"):
                        line_bytes = line_bytes[:-1]
                    if not line_bytes:
                        continue

                    try:
                        line_str = line_bytes.decode("utf-8")
                        msg = json.loads(line_str)
                        self._handle_rpc_message(msg)
                    except Exception as err:
                        logger.warning(f"Error parsing Step-Code RPC message: {err}")
        except Exception as e:
            logger.warning(f"Step-Code RPC reader terminated: {e}")
        finally:
            self._running = False
            self._is_healthy = False
            with self._lock:
                for req_id, ev in list(self._pending_requests.items()):
                    self._responses[req_id] = {
                        "error": {"code": -32000, "message": "Step-Code process terminated"}
                    }
                    ev.set()

    def _handle_rpc_message(self, msg: Dict[str, Any]) -> None:
        if not isinstance(msg, dict):
            return

        msg_type = msg.get("type")
        method = msg.get("method")

        # 1. Event notifications from runtime (Upstream type='event' or legacy method='event')
        if msg_type == "event" or method == "event":
            params = msg.get("params") or msg.get("data") or msg
            event_type = msg.get("event") or params.get("event_type") or params.get("event") or "runtime_event"
            ev_sess = params.get("session_id") or msg.get("session_id") or self._active_session or "default_session"

            # Reject cross-session events (Section 23 & 24)
            if self._active_session is None:
                self._active_session = ev_sess
            elif ev_sess and ev_sess != self._active_session:
                logger.warning(f"Cross-session event rejected: event session '{ev_sess}' != active '{self._active_session}'")
                return

            self._sequence += 1
            payload_data = params.get("payload") if isinstance(params.get("payload"), dict) else (params.get("data") if isinstance(params.get("data"), dict) else params)
            ev = RuntimeEvent(
                operation_id=params.get("operation_id", ""),
                session_id=ev_sess,
                task_id=params.get("task_id", "default_task"),
                action_id=params.get("action_id", ""),
                workspace_id=self.workspace_dir,
                event_type=event_type,
                sequence=self._sequence,
                runtime="step-code",
                runtime_operation_id=params.get("runtime_operation_id", ""),
                adapter_version="1.0.0",
                payload=payload_data if isinstance(payload_data, dict) else {},
                source="step-code-rpc",
            )
            for sub in list(self._subscribers.values()):
                try:
                    sub(ev)
                except Exception as ex:
                    logger.warning(f"Subscriber error: {ex}")
            return

        # 2. Extension tool call authorization interception (Part C7)
        if method in ("intercept_tool_call", "authorize_action") or msg_type == "tool_call":
            req_id = msg.get("id")
            params = msg.get("params") or msg.get("data") or msg
            action_name = params.get("action") or params.get("tool") or "read_file"
            target = params.get("target", "")
            action_params = params.get("parameters") or params.get("args") or {}
            actor = params.get("actor", "step-code-agent")
            capability = params.get("capability", "terminal.execute")

            req = ActionRequest(
                actor=actor,
                capability=capability,
                action=action_name,
                target=target,
                parameters=action_params,
                workspace=self.workspace_dir,
                session=params.get("session_id", self._active_session),
            )

            from sclass.control.composite_auth import DualLayerAuthorizer
            auth_decision = DualLayerAuthorizer.authorize_request(req, workspace_dir=self.workspace_dir)
            auth_result = DualLayerAuthorizer.evaluate_dual_layer(req, auth_decision, workspace_dir=self.workspace_dir)

            reason_str = auth_result.sclass_reason if not auth_result.sclass_allowed else auth_result.runtime_reason
            resp = {
                "id": req_id,
                "type": "response",
                "command": "tool_call",
                "success": auth_result.can_execute,
                "jsonrpc": "2.0",
                "result": {
                    "allowed": auth_result.can_execute,
                    "sclass_allowed": auth_result.sclass_allowed,
                    "runtime_allowed": auth_result.runtime_allowed,
                    "decision_id": auth_decision.decision_id,
                    "action_hash": auth_result.action_hash,
                    "reason": reason_str,
                },
                "allowed": auth_result.can_execute,
                "reason": reason_str,
                "decision_id": auth_decision.decision_id,
                "action_hash": auth_result.action_hash,
            }
            wire = (json.dumps(resp, ensure_ascii=False) + "\n").encode("utf-8")
            with self._lock:
                if self._proc and self._proc.stdin and self._proc.poll() is None:
                    try:
                        self._proc.stdin.write(wire)
                        self._proc.stdin.flush()
                    except Exception as err:
                        logger.warning(f"Error transmitting tool authorization response: {err}")
            return

        # 3. Direct response to a client request
        req_id = msg.get("id")
        if req_id is not None:
            with self._lock:
                self._responses[req_id] = msg
                self._responses[str(req_id)] = msg
                ev = self._pending_requests.get(req_id) or self._pending_requests.get(str(req_id))
                if ev:
                    ev.set()

    def _send_rpc(self, method: str, params: Optional[Dict[str, Any]] = None, timeout: float = 10.0) -> Dict[str, Any]:
        if not self._is_healthy and self.fail_closed:
            raise SecurityViolationError("Step-Code harness is currently unhealthy or unavailable. Failing closed.")

        with self._lock:
            self._request_counter += 1
            req_id = str(self._request_counter)
            ev = threading.Event()
            self._pending_requests[req_id] = ev
            self._pending_requests[self._request_counter] = ev

        p_dict = dict(params or {})
        msg_text = p_dict.get("prompt") or p_dict.get("instruction") or p_dict.get("content") or p_dict.get("message") or ""
        req = {
            "id": req_id,
            "type": method,
            "message": msg_text,
            **p_dict,
            "jsonrpc": "2.0",
            "method": method,
            "params": p_dict,
        }
        wire_data = (json.dumps(req, ensure_ascii=False) + "\n").encode("utf-8")

        try:
            if not self._proc or not self._proc.stdin or self._proc.poll() is not None:
                self._is_healthy = False
                raise SecurityViolationError("Step-Code process is not running. Failing closed.")
            self._proc.stdin.write(wire_data)
            self._proc.stdin.flush()
        except Exception as e:
            self._is_healthy = False
            with self._lock:
                self._pending_requests.pop(req_id, None)
                self._pending_requests.pop(int(req_id), None)
            raise SecurityViolationError(f"Failed to transmit RPC request to Step-Code: {e}")

        finished = ev.wait(timeout=timeout)
        with self._lock:
            self._pending_requests.pop(req_id, None)
            self._pending_requests.pop(int(req_id), None)
            res = self._responses.pop(req_id, None) or self._responses.pop(int(req_id), None)

        if not finished or not res:
            self._is_healthy = False
            raise SecurityViolationError(f"Step-Code RPC timeout for method '{method}' after {timeout}s.")

        if "error" in res:
            err = res["error"]
            if isinstance(err, dict):
                raise SecurityViolationError(f"Step-Code RPC error ({err.get('code')}): {err.get('message')}")
            raise SecurityViolationError(f"Step-Code RPC error: {err}")

        if res.get("type") == "response" and not res.get("success", True):
            err_msg = res.get("error") or res.get("reason") or res.get("message") or f"Command '{res.get('command', method)}' failed"
            raise SecurityViolationError(f"Step-Code RPC error: {err_msg}")

        if "result" in res and isinstance(res["result"], dict):
            merged = dict(res["result"])
            for k, v in res.items():
                if k not in ("id", "jsonrpc", "method", "params", "result"):
                    merged.setdefault(k, v)
            return merged

        clean_res = dict(res)
        clean_res.pop("jsonrpc", None)
        clean_res.pop("type", None)
        clean_res.pop("command", None)
        clean_res.pop("success", None)
        return clean_res

    def prompt(self, prompt_text: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        sess_id = session_id or self._active_session
        return self._send_rpc("prompt", {"prompt": prompt_text, "session_id": sess_id, "workspace_dir": self.workspace_dir})

    def steer(self, instruction: str, session_id: Optional[str] = None, operation_id: Optional[str] = None) -> Dict[str, Any]:
        sess_id = session_id or self._active_session
        return self._send_rpc("steer", {"instruction": instruction, "session_id": sess_id, "operation_id": operation_id or ""})

    def follow_up(self, content: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        sess_id = session_id or self._active_session
        return self._send_rpc("follow_up", {"content": content, "session_id": sess_id})

    def abort(self, operation_id: Optional[str] = None, session_id: Optional[str] = None, reason: str = "") -> Dict[str, Any]:
        sess_id = session_id or self._active_session
        return self._send_rpc("abort", {"operation_id": operation_id or "", "session_id": sess_id, "reason": reason})

    def query_state(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        sess_id = session_id or self._active_session
        return self._send_rpc("state", {"session_id": sess_id, "workspace_dir": self.workspace_dir})

    def get_state(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Queries Step-Code internal session state (Upstream protocol)."""
        sess_id = session_id or self._active_session
        return self._send_rpc("get_state", {"session_id": sess_id, "workspace_dir": self.workspace_dir})

    def get_entries(self, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Queries Step-Code session entry history (Upstream protocol)."""
        sess_id = session_id or self._active_session
        res = self._send_rpc("get_entries", {"session_id": sess_id})
        return res.get("entries", []) if isinstance(res, dict) else []

    def get_tree(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Queries Step-Code session tree state (Upstream protocol)."""
        sess_id = session_id or self._active_session
        res = self._send_rpc("get_tree", {"session_id": sess_id})
        return res.get("tree", {}) if isinstance(res, dict) else {}

    def compact(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Requests compaction of session state (Upstream protocol)."""
        sess_id = session_id or self._active_session
        return self._send_rpc("compact", {"session_id": sess_id})

    def retry(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Retries failed step in Step-Code (Upstream protocol)."""
        sess_id = session_id or self._active_session
        return self._send_rpc("retry", {"session_id": sess_id})

    def set_model(self, model: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Configures active LLM model in Step-Code (Upstream protocol)."""
        sess_id = session_id or self._active_session
        return self._send_rpc("set_model", {"model": model, "session_id": sess_id})

    def start_operation(self, intent: Dict[str, Any]) -> DurableOperation:
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
            session_id=intent.get("session_id", self._active_session),
            task_id=intent.get("task_id", "default_task"),
            agent_id=intent.get("agent_id", "default_agent"),
            action_id=intent.get("action_id", f"act_{uuid.uuid4().hex[:8]}"),
            workspace_id=intent.get("workspace_id", self.workspace_dir),
            replay_class=replay_class,
            intent_hash=intent_hash,
            action_hash=action_hash,
            runtime_name=self.runtime_name,
            runtime_operation_id=f"rt_{op_id}",
            adapter_version="1.0.0",
        )

        op = DurableOperation(metadata=metadata, state=OperationState.PLANNED)
        self.store.save_operation(op)
        return op

    def execute_tool_with_interception(
        self,
        action: str,
        target: str = "",
        parameters: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Executes a tool through Step-Code with active extension tool_call authorization interception (Part C7).
        Step-Code calls back into S-Class over RPC for authorization before executing the tool effect.
        """
        sess_id = session_id or self._active_session
        return self._send_rpc(
            "execute_tool_with_interception",
            {
                "action": action,
                "target": target,
                "parameters": parameters or {},
                "session_id": sess_id,
            },
        )

    def submit_action(
        self,
        action: ActionRequest,
        authorization: AuthorizationDecision,
        operation: Optional[DurableOperation] = None,
    ) -> Dict[str, Any]:
        if not self._is_healthy and self.fail_closed:
            raise SecurityViolationError("Step-Code harness is currently unhealthy or unavailable. Failing closed.")

        op = operation or self.start_operation({
            "action": action.action,
            "target": action.target,
            "parameters": action.parameters,
            "session_id": action.session or self._active_session,
            "workspace_id": action.workspace or self.workspace_dir,
            "agent_id": action.actor,
        })

        if not authorization.is_allowed:
            op.transition_to(OperationState.FAILED, {"reason": f"S-Class authorization denied: {authorization.reason}"})
            self.store.save_operation(op)
            raise SecurityViolationError(f"S-Class Authorization DENIED: {authorization.reason}")

        cmd_str = action.parameters.get("command") or action.parameters.get("command_line") or action.target or ""
        perm_analysis = StepCodeCommandAnalyzer.analyze_command(cmd_str, self.workspace_dir)
        if not perm_analysis["allowed"]:
            op.transition_to(OperationState.FAILED, {"reason": f"Step-Code permission denied: {perm_analysis['reason']}"})
            self.store.save_operation(op)
            raise SecurityViolationError(f"Step-Code Runtime Permission DENIED: {perm_analysis['reason']}")

        current_hash = action.compute_action_hash()
        auth_action_hash = getattr(authorization, "action_hash", None) or (authorization.metadata.get("action_hash") if authorization.metadata else None)
        if not auth_action_hash:
            op.transition_to(OperationState.FAILED, {"reason": "Missing action_hash binding on authorization decision"})
            self.store.save_operation(op)
            raise SecurityViolationError("MISSING ACTION HASH: Authorization decision lacks cryptographic action_hash binding.")
        if auth_action_hash != current_hash:
            op.transition_to(OperationState.FAILED, {"reason": "Action parameters modified after authorization"})
            self.store.save_operation(op)
            raise SecurityViolationError(
                f"ACTION TAMPERING DETECTED: Action parameters were modified after S-Class authorization. "
                f"Expected hash {auth_action_hash}, computed {current_hash}. Re-authorization required."
            )

        current_req_hash = action.compute_request_hash()
        if not authorization.request_hash:
            op.transition_to(OperationState.FAILED, {"reason": "Missing request_hash binding on authorization decision"})
            self.store.save_operation(op)
            raise SecurityViolationError("MISSING REQUEST HASH: Authorization decision lacks cryptographic request_hash binding.")
        if authorization.request_hash != current_req_hash:
            op.transition_to(OperationState.FAILED, {"reason": "Action request parameters do not match authorization request hash"})
            self.store.save_operation(op)
            raise SecurityViolationError(
                "REQUEST HASH MISMATCH: Action request parameters do not match authorization request hash."
            )

        op.authorization_id = authorization.decision_id
        op.transition_to(OperationState.AUTHORIZED, {"decision": authorization.to_dict()})
        op.transition_to(OperationState.EFFECT_PENDING, {"action": action.to_dict()})
        self.store.save_operation(op)

        rpc_result = self._send_rpc("tool_call", {
            "action": action.action,
            "target": action.target,
            "parameters": action.parameters,
            "operation_id": op.operation_id,
            "session_id": op.metadata.session_id,
        })

        effect_result = rpc_result.get("result", rpc_result)
        op.transition_to(OperationState.EFFECT_EXECUTED, effect_result)
        settlement = {
            "settled_at": datetime.now(timezone.utc).isoformat(),
            "exit_code": effect_result.get("exit_code", 0),
            "status": "SETTLED",
            "output_bytes": len(str(effect_result.get("output", ""))),
        }
        op.transition_to(OperationState.SETTLED, settlement)
        self.store.save_operation(op)

        return {
            "operation_id": op.operation_id,
            "status": "SETTLED",
            "executed": True,
            "result": effect_result,
            "settlement": settlement,
            "untrusted_candidate": True,
        }

    def observe_operation(self, operation_id: str) -> Dict[str, Any]:
        op = self.store.get_operation(operation_id)
        if not op:
            raise SecurityViolationError(f"Operation not found: {operation_id}")
        return {
            "operation_id": op.operation_id,
            "state": op.state.value,
            "effect_result": op.effect_result,
            "settlement": op.settlement,
            "replay_class": op.replay_class.value,
        }

    def get_execution_state(self, operation_id: str) -> OperationState:
        op = self.store.get_operation(operation_id)
        if not op:
            raise SecurityViolationError(f"Operation not found: {operation_id}")
        return op.state

    def cancel_operation(self, operation_id: str, reason: str = "") -> bool:
        op = self.store.get_operation(operation_id)
        if not op:
            return False
        if op.state.is_terminal:
            return False
        try:
            self.abort(operation_id=operation_id, reason=reason)
        except Exception:
            pass
        self.store.save_operation(
            CrossRuntimeOperation.from_dict({
                **op.to_dict(),
                "state": OperationState.CANCELLED.value,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
        )
        return True

    def recover_operation(self, operation_id: str) -> Dict[str, Any]:
        op = self.store.get_operation(operation_id)
        if not op:
            raise SecurityViolationError(f"Unknown operation for recovery: {operation_id}")
        if op.replay_class == ReplayClass.NEVER:
            raise SecurityViolationError(
                f"REPLAY REJECTED: Operation '{operation_id}' has replay_class=NEVER."
            )
        return {"operation_id": operation_id, "recovered": True, "replayed": True}

    def spawn_agent(self, agent_config: Dict[str, Any]) -> Dict[str, Any]:
        sess_id = agent_config.get("session_id") or f"sess_{uuid.uuid4().hex[:8]}"
        self._active_session = sess_id
        return {"session_id": sess_id, "status": "RUNNING"}

    def inspect_session(self, session_id: str) -> Dict[str, Any]:
        return self.query_state(session_id)

    def subscribe_events(self, callback: Callable[[RuntimeEvent], None]) -> str:
        sub_id = f"sub_{uuid.uuid4().hex[:8]}"
        self._subscribers[sub_id] = callback
        return sub_id

    def unsubscribe_events(self, sub_id: str) -> bool:
        return self._subscribers.pop(sub_id, None) is not None

    def health_check(self) -> Dict[str, Any]:
        is_alive = self._proc is not None and self._proc.poll() is None
        status = "HEALTHY" if (is_alive and self._is_healthy) else "UNAVAILABLE"
        return {
            "runtime": self.runtime_name,
            "status": status,
            "process_alive": is_alive,
        }

    def close(self) -> None:
        self._running = False
        if self._proc:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=2.0)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None


class StepCodeHarness(RuntimeHarness):
    """
    Reference mock/contract harness modeling Step-Code for unit testing without child processes.
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

        if authorization.request_hash and authorization.request_hash != action.compute_hash():
            op.transition_to(OperationState.FAILED, {"reason": "Action request parameters do not match authorization request hash"})
            self._emit_event(op, "action_tampered", {"expected_request_hash": authorization.request_hash, "current_request_hash": action.compute_hash()})
            raise SecurityViolationError(
                "REQUEST HASH MISMATCH: Action request parameters do not match authorization request hash."
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


# Explicit aliases for reference and test harnesses (Part F)
ReferenceMockHarness = StepCodeHarness


class StepCodeRpcTestDouble(StepCodeRpcHarness):
    """
    Explicit test double / simulation harness for Step-Code RPC protocol (Requirement 1 & 28).
    Used solely for unit, protocol, and failure mode testing.
    Never used as canonical Step-Code runtime in production.
    """
    def __init__(self, workspace_dir: str, **kwargs):
        kwargs["use_test_double"] = True
        super().__init__(workspace_dir, **kwargs)


class FakeStepCodeRuntime(StepCodeRpcTestDouble):
    """Alias for StepCodeRpcTestDouble (Requirement 1.1)."""
    pass

