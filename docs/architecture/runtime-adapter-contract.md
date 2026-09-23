# Architecture: Runtime Adapter Contract (`RuntimeHarness`)

## 1. Universal Contract & Multi-Runtime Neutrality

The `RuntimeHarness` abstract base class defines the formal interface between the S-Class assurance plane and pluggable lower-tier execution engines.

S-Class assurance logic is **100% neutral** to which runtime harness executes actions. Whether an action is executed by `StepCodeRpcHarness`, `ClaudeCodeHarness`, `CodexHarness`, or `NativeHarness`:
- Authorization policies evaluate identically with zero runtime bias.
- Action hashes and capability policies enforce cryptographically.
- Replay safety contracts enforce identically (`SAFE`, `IDEMPOTENT`, `NEVER`).
- Event streams normalize into canonical `RuntimeEvent` dataclasses.
- Project truth promotes only via S-Class independent observation and verification.

```python
class RuntimeHarness(ABC):
    @property
    @abstractmethod
    def runtime_name(self) -> str:
        """Identifier of the underlying execution runtime."""
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
        Fails closed on tamper or authorization denial.
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
        """Cancels an in-flight operation in the runtime engine."""
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
        """Returns health and readiness status of the runtime substrate."""
        ...
```

---

## 2. Standard Harness Implementations

1. **`StepCodeRpcHarness`**:
   - Manages a real external Step-Code child process via stdio RPC (`step --mode rpc` / `tools/step_rpc_server.js`).
   - Implements strict LF framing (`b'\n'`, `0x0A`) buffering to prevent line-splitting on Unicode separators (`\u2028`, `\u2029`).
   - Translates tool requests, enforces Dual-Layer Authorization, and maps runtime events into canonical `RuntimeEvent` records.
   - Dual-persists operations to `.sclass/trust/cross_runtime_operations.jsonl` and SQLite `project.db`.
2. **`NativeHarness`**:
   - Standalone reference harness executing tool actions directly within the workspace.
   - Demonstrates that S-Class assurance mechanisms function identically without external dependencies.
3. **`StepCodeHarness` (alias `ReferenceMockHarness`)**:
   - High-speed in-process mock implementation used for fast deterministic unit tests and isolated property testing.

---

## 3. Cross-Runtime Operation Schema & Migration 006

All operations dispatched across external runtimes are standardized into `CrossRuntimeOperation` and persisted via `CanonicalOperationStore`:

```sql
-- Migration 006: cross_runtime_operations
CREATE TABLE IF NOT EXISTS cross_runtime_operations (
    operation_id TEXT PRIMARY KEY,
    parent_operation_id TEXT,
    session_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    action_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    state TEXT NOT NULL,
    replay_class TEXT NOT NULL,
    intent_hash TEXT NOT NULL,
    action_hash TEXT NOT NULL,
    authorization_id TEXT,
    runtime_name TEXT NOT NULL,
    runtime_operation_id TEXT,
    adapter_version TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    effect_result TEXT,
    settlement_record TEXT
);

CREATE INDEX IF NOT EXISTS idx_cro_session ON cross_runtime_operations(session_id);
CREATE INDEX IF NOT EXISTS idx_cro_task ON cross_runtime_operations(task_id);
CREATE INDEX IF NOT EXISTS idx_cro_runtime ON cross_runtime_operations(runtime_name);
CREATE INDEX IF NOT EXISTS idx_cro_state ON cross_runtime_operations(state);
```

---

## 4. Invariants & Epistemic Boundaries

1. **Candidate Demotion Invariant**:
   Any execution output returned by `submit_action()` or `observe_operation()` carries `untrusted_candidate = True`. It provides evidence signals only, never verified facts.
2. **Fail-Closed Runtime Invariant**:
   If an external runtime process crashes or exits unexpectedly, the harness marks health as `UNAVAILABLE`. Any subsequent operation attempts raise `SecurityViolationError`.
3. **Replay Safety Invariant**:
   Operations classified with `ReplayClass.NEVER` (destructive commands, non-idempotent mutations) cannot be replayed during crash recovery.

---

## 5. MIT Attribution Notice

```text
Portions of the runtime harness contract and operation lifecycle are derived from Step-Code:
Copyright (c) Step-Code Contributors.
Licensed under the MIT License (MIT).
```
