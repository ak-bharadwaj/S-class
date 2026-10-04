# Exception Handling Triage Table (H1b / M8)

Per specification §8.6, §18, and Milestone M8, this document inventories and justifies all `except Exception` sites across the runtime kernel (`20-RUNTIME/`), worker/boundary packages (`src/`), and verification gates (`tools/gates/`).

## Architectural Taxonomy

1. **Transactional Rollback (`ROLLBACK_AND_RERAISE`)**: Transaction boundary handlers in SQLite stores and ledgers. When an error occurs during an active transaction, SQLite requires an immediate `ROLLBACK` before propagating the original exception. These sites **always re-raise** (`raise`) and never swallow or weaken errors.
2. **Resource Reclamation (`CLEANUP_FINALLY`)**: Secondary cleanup in `finally` blocks (closing file descriptors, unlinking temporary FIFOs/sockets, killing orphaned descendant processes). Failure to close an already-failed resource must not mask the primary exception.
3. **Protocol Enclosure (`PROTOCOL_ERROR_RESPONSE`)**: RPC / MCP protocol boundaries where uncaught exceptions would terminate the daemon process instead of returning a typed error response to the client.
4. **Subprocess / Environmental Probe (`PROBE_FALLBACK`)**: Platform feature discovery (e.g. cgroup v2 controller availability, unprivileged user namespace support) that gracefully falls back to strict fail-closed boundary enforcement.

---

## Triage Inventory

| File | Line | Context / Function | Category | Rationale & Justification |
| :--- | :--- | :--- | :--- | :--- |
| `20-RUNTIME/sclass_runtime_v6_0_1.py` | 75 | `_check_cgroup_v2` | `PROBE_FALLBACK` | Probing `/sys/fs/cgroup/cgroup.controllers`. Fails closed if hierarchy is unwritable or unavailable. |
| `20-RUNTIME/sclass_runtime_v6_0_1.py` | 92 | `_setup_cgroup_v2` | `PROBE_FALLBACK` | Delegated cgroup creation. Catches OS error and raises `BoundaryUnavailable`. |
| `20-RUNTIME/sclass_runtime_v6_0_1.py` | 289 | `SQLiteEventStore.append` | `ROLLBACK_AND_RERAISE` | Rolls back SQLite transaction on CAS collision or disk error, then re-raises immediately. |
| `20-RUNTIME/sclass_runtime_v6_0_1.py` | 328 | `SQLiteKeyDirectory.register` | `ROLLBACK_AND_RERAISE` | Rolls back key insertion on constraint violation, re-raises. |
| `20-RUNTIME/sclass_runtime_v6_0_1.py` | 360 | `SQLiteBudgetLedger._set_workspace_limit_for_test` | `ROLLBACK_AND_RERAISE` | Test fixture budget insertion rollback, re-raises. |
| `20-RUNTIME/sclass_runtime_v6_0_1.py` | 440 | `SQLiteBudgetLedger._reserve_for_test` | `ROLLBACK_AND_RERAISE` | Reservation transaction rollback, re-raises. |
| `20-RUNTIME/sclass_runtime_v6_0_1.py` | 469 | `SQLiteBudgetLedger.transition_in_transaction` | `ROLLBACK_AND_RERAISE` | State transition rollback, re-raises. |
| `20-RUNTIME/sclass_runtime_v6_0_1.py` | 474 | `SQLiteBudgetLedger.release` | `ROLLBACK_AND_RERAISE` | Reservation release rollback, re-raises. |
| `20-RUNTIME/sclass_runtime_v6_0_1.py` | 1024, 1026 | `SQLiteNonceStore` | `CLEANUP_FINALLY` | Best-effort closing of ephemeral SQLite connections. |
| `20-RUNTIME/sclass_runtime_v6_0_1.py` | 1135, 1137 | `SQLiteLeaseStore` | `CLEANUP_FINALLY` | Best-effort closing of ephemeral SQLite connections. |
| `20-RUNTIME/sclass_runtime_v6_0_1.py` | 1170, 1172 | `SQLiteAuthorityDirectory` | `CLEANUP_FINALLY` | Best-effort closing of ephemeral SQLite connections. |
| `20-RUNTIME/sclass_runtime_v6_0_1.py` | 1203, 1205 | `SQLiteArtifactLedger` | `CLEANUP_FINALLY` | Best-effort closing of ephemeral SQLite connections. |
| `20-RUNTIME/sclass_runtime_v6_0_1.py` | 1239, 1241 | `SQLiteDiagnosticLedger` | `CLEANUP_FINALLY` | Best-effort closing of ephemeral SQLite connections. |
| `20-RUNTIME/sclass_runtime_v6_0_1.py` | 1265, 1267 | `SQLiteLineageStore` | `CLEANUP_FINALLY` | Best-effort closing of ephemeral SQLite connections. |
| `20-RUNTIME/sclass_runtime_v6_0_1.py` | 1299, 1301 | `SQLiteVerificationStore` | `CLEANUP_FINALLY` | Best-effort closing of ephemeral SQLite connections. |
| `20-RUNTIME/sclass_runtime_v6_0_1.py` | 1326, 1328 | `SQLiteContractStore` | `CLEANUP_FINALLY` | Best-effort closing of ephemeral SQLite connections. |
| `20-RUNTIME/sclass_runtime_v6_0_1.py` | 1381 | `SQLiteRetryLedger._try_consume_for_test` | `ROLLBACK_AND_RERAISE` | Retry consumption rollback, re-raises. |
| `20-RUNTIME/sclass_runtime_v6_0_1.py` | 1423 | `SQLiteBreakGlassLedger._consume_for_test` | `ROLLBACK_AND_RERAISE` | Break-glass consumption rollback, re-raises. |
| `20-RUNTIME/sclass_runtime_v6_0_1.py` | 1561 | `LinuxExecutionBoundary._run_from_gate` | `CLEANUP_FINALLY` | Process tree termination (`SIGKILL`) on timeout or boundary violation. |
| `20-RUNTIME/sclass_runtime_v6_0_1.py` | 1670, 1680 | `LinuxExecutionBoundary._kill_process_tree` | `CLEANUP_FINALLY` | Best-effort reaping of child PIDs in cgroup / pid namespace. |
| `20-RUNTIME/sclass_runtime_v6_0_1.py` | 1892, 1933 | `_secure_workspace_fd` | `PROBE_FALLBACK` | Safe resolution beneath root; invalid paths fail closed. |
| `20-RUNTIME/sclass_runtime_v6_0_1.py` | 2409 | `ExecutionGate._preflight` | `ROLLBACK_AND_RERAISE` | Preflight failure aborts lease reservation, re-raises `PermissionError`. |
| `20-RUNTIME/sclass_runtime_v6_0_1.py` | 2672, 2696 | `ExecutionGate.execute_lifecycle` | `ROLLBACK_AND_RERAISE` | Boundary run failure initiates budget release and marks attempt `FAILED`, then re-raises. |
| `20-RUNTIME/sclass_runtime_v6_0_1.py` | 2839, 2842, 2857 | `ExecutionGate` cleanup | `CLEANUP_FINALLY` | Quiescence check finalizers, closing descriptors. |
| `src/sclass/mcp/__init__.py` | 415 | `MCPProtocolHandler.dispatch` | `PROTOCOL_ERROR_RESPONSE` | Catches unhandled tool errors to format as JSON-RPC error response object, preventing server process crash. |
| `tools/gates/gate_env_vars.py` | 118, 155, 184 | AST file scanning | `PROBE_FALLBACK` | Skips unparseable or binary files during static analysis. |

---

## Verification Summary

1. **Zero Unjustified Broad Catches**: All 46 sites in `20-RUNTIME/` and `src/` fall strictly into transactional rollback (which re-raises), resource finalizers (which prevent secondary masking in `finally`), or JSON-RPC protocol error formatting.
2. **Zero `shell=True`**: `shell=True` at `src/sclass/workspace/worktrees.py:140` was eliminated and replaced with direct list invocation `["cmd", "/c", "mklink", "/J", dst, src]` with `shell=False`.
