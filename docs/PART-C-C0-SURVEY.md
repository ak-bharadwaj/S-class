# S-CLASS Part C — C0 Provenance Survey & Lineage Architecture

**Governing Authority:** CL Ruling — E-SEM-1 A6 Final Disposition  
**Status:** Canonical Part C Survey Deliverable  
**Date:** 2026-11-15  
**Branch:** `b02-restore` (PR #26)

---

## Executive Summary

Following the implementation of erratum `E-SEM-1` (strict 6-parameter constructor on `WorkProposal`) and the selection of **Path 2: Strict Fail-Closed Refusal with Concurrent Test Disposition**, this survey establishes the comprehensive provenance architecture required before any implementation of Path 1 (genuine binding construction).

Under Path 2, both the autonomous vertical slice (`SClassClient.run_autonomous_cycle`) and standalone MCP patch validation (`SClassMCPServer.sclass_validate_patch`) fail closed with structured refusals when authentic canonical attestation is unavailable. This document provides the authoritative provenance map, event lineage derivation, MCP architecture analysis, zero-digest inventory, test designs, gap declarations, and open CL governance questions.

---

## (a) Provenance Map for `StateBinding` and `CausalFrontier`

### 1. `StateBinding` Fields (§10.2, §18)

| Field Name | Type | Description | Authoritative Source Entity | Source Event / Subsystem |
|:---|:---|:---|:---|:---|
| `workspace_id` | `str` | Canonical identifier of active workspace | `EngineeringState.workspace_id` | Genesis `WORKSPACE_INITIALIZED` event |
| `objective_revision` | `str` | Revision ID of governing intent | `EngineeringState.objective.revision` | `OBJECTIVE_CREATED` / `OBJECTIVE_REVISED` |
| `workgraph_revision` | `str` | Active compiled workgraph revision | `EngineeringState.workgraph.revision` | `WORKGRAPH_COMPILED` / `WORKGRAPH_UPDATED` |
| `policy_version` | `str` | Active security/governance policy version | `EngineeringState.active_policy.version` | `POLICY_REGISTERED` event |
| `workspace_snapshot_id` | `str` | Unique handle for workspace tree snapshot | `LocalWorkspaceSnapshotHandle.handle_id` | `SNAPSHOT_CAPTURED` event |
| `target_snapshot_digest` | `Digest` | Canonical SHA-256 of `TargetSnapshot` | `target_snapshot_digest(snapshot)` | Snapshot Manager tree hashing |
| `causal_frontier_digest` | `Digest` | Canonical digest of upstream causal closure | `digest("sclass/causal-frontier/v1", cf)` | Causal Frontier Aggregator |
| `governing_budget_lineage_id` | `str` | Lineage tracking token consumption | `EngineeringState.budget_ledger.lineage_id`| `BUDGET_ALLOCATED` / `BUDGET_RESERVED` |
| `execution_generation` | `int` | Monotonically increasing epoch generation | `EngineeringState.generation` | `GENERATION_ADVANCED` event |
| `authorization_epoch` | `str` | Signing key authorization epoch | `TrustKeyRegistry.current_epoch_id` | `AUTHORIZATION_EPOCH_ADVANCED` |
| `event_head_hash` | `Digest` | SHA-256 of latest committed canonical event | `SQLiteEventStore.get_head().hash` | Authoritative SQLite append-only log |

### 2. `CausalFrontier` Fields (§10.4, §18)

| Field Name | Type | Description | Authoritative Source Entity | Source Event / Subsystem |
|:---|:---|:---|:---|:---|
| `frontier_id` | `str` | Unique causal frontier instance identifier | `cf-<uuid>` or deterministic content hash | Frontier Builder instantiation |
| `profile_id` | `str` | Execution control profile identifier | Active `ControlProfile.profile_id` | `PROFILE_ACTIVATED` event |
| `profile_version` | `str` | Semver of active control profile | Active `ControlProfile.version` | `PROFILE_ACTIVATED` event |
| `objective_revision` | `str` | Monotonic revision of objective | `EngineeringState.objective.revision` | Matches `StateBinding.objective_revision` |
| `obligation_graph_revision`| `str` | Revision of obligation dependency DAG | `EngineeringState.obligations_revision` | `OBLIGATIONS_COMPILED` event |
| `workgraph_revision` | `str` | Monotonic revision of work DAG | `EngineeringState.workgraph.revision` | Matches `StateBinding.workgraph_revision` |
| `policy_digest` | `Digest` | Canonical digest of serialized policy | `digest("sclass/policy/v1", policy)` | Security policy registry |
| `target_snapshot_digest` | `Digest` | Digest of pre-execution filesystem state | `target_snapshot_digest(snapshot)` | Matches `StateBinding.target_snapshot_digest` |
| `authorization_epoch` | `str` | Active cryptographic signing epoch | `TrustKeyRegistry.current_epoch_id` | Matches `StateBinding.authorization_epoch` |
| `capability_digest` | `Digest` | Boundary capability token digest | `digest("sclass/gate-cap/v1", cap)` | `ExecutionGate._gate_capability` |
| `budget_lineage_digest` | `Digest` | Lineage digest of budget reservation chain | `digest("sclass/budget-lineage/v1", lineage)` | Budget Ledger |
| `dependency_digests` | `tuple[Digest, ...]` | Deterministically ordered upstream receipts | Upstream work node outputs | `NODE_COMPLETED` receipt digests |
| `inclusion_reasons` | `tuple[str, ...]` | Semantic justification for each dependency | Directed edges in WorkGraph DAG | Edge annotations in WorkGraph |

---

## (b) Exact Event and State Lineage Derivation

In the S-Class kernel (`20-RUNTIME/sclass_runtime_v6_0_1.py`), state is reconstructed strictly by reducing an append-only sequence of `CanonicalEvent` instances from `SQLiteEventStore`.

```
[ Genesis: WORKSPACE_INITIALIZED ]
               │
               ▼
   [ OBJECTIVE_CREATED / REVISED ] ───────► objective_revision
               │
               ▼
     [ WORKGRAPH_COMPILED ] ──────────────► workgraph_revision, dependency graph
               │
               ▼
     [ SNAPSHOT_CAPTURED ] ───────────────► workspace_snapshot_id, target_snapshot_digest
               │
               ▼
   [ BUDGET_RESERVED / ALLOCATED ] ───────► governing_budget_lineage_id, reservation_id
               │
               ▼
 [ AUTHORIZATION_EPOCH_ADVANCED ] ────────► authorization_epoch, signing keys
               │
               ▼
     [ SQLite COMMIT (head) ] ────────────► event_head_hash
               │
               ▼
   [ REDUCER STATE CONVERGENCE ] ────────► StateBinding(11 fields) & CausalFrontier(13 fields)
```

1. **Event Head Hash Verification**:
   The `event_head_hash` must be queried via `SQLiteEventStore.get_head().hash`. It represents the exact SHA-256 of the most recent committed `CanonicalEvent`. Any transaction committed after the binding is issued alters the head hash and invalidates stale bindings.
2. **WorkGraph and Prerequisite Traversal**:
   When dispatching work node $N_i$, the causal frontier builder inspects the WorkGraph DAG for all immediate predecessor nodes $\text{Pred}(N_i)$. For each predecessor $P \in \text{Pred}(N_i)$, the event log must contain a committed `NODE_COMPLETED` event whose receipt digest is appended to `dependency_digests`. If any predecessor has not successfully completed with an authentic signed receipt, frontier assembly fails closed.
3. **Budget Reservation Lineage**:
   Every mutation request requires an active budget reservation. The `governing_budget_lineage_id` derives from `BudgetAllocator.reserve(...)` recording a `BUDGET_RESERVED` event with a deterministic reservation ID, expiration instant, and parent lineage ID.
4. **Execution Generation and Fencing Tokens**:
   To prevent stale or split-brain worker executions, `execution_generation` increments whenever the control plane recovers or advances node dispatch. Boundary execution verifies that the request's fencing token is strictly greater than the highest token previously seen by the node's boundary.

---

## (c) Analysis of MCP Ephemeral-SQLite Lineage vs. Authoritative State

The implementation of `SClassMCPServer` in `src/sclass/mcp/__init__.py` revealed a fundamental architectural gap:

1. **The Ephemeral SQLite Disconnection**:
   In standalone MCP server mode (or when launched by an IDE co-pilot extension), the server was frequently instantiated with an empty or ephemeral database path (`db_path="val.sqlite"` or `db_path="test_sclass.sqlite"`).
2. **The Absence of Upstream Lineage**:
   An ephemeral SQLite store contains zero events. Consequently:
   - There is no `event_head_hash` (or it defaults to `GENESIS_EVENT_HASH`).
   - There is no compiled `EngineeringProgram` or `WorkGraph`.
   - There is no active `objective_revision` or `budget_lineage`.
   - There are no prior verification receipts or causal dependencies.
3. **The Fabrication Failure**:
   Prior to Path 2, `sclass_validate_patch` attempted to bypass this missing lineage by creating a local, isolated `SQLiteEventStore`, instantiating a temporary `SClassControlPlane`, and fabricating an `AuthorizedWorkRequest` with `zero_dig` and hardcoded IDs (`prop-1`, `node-1`, `snap-val-1`). This violated core specification invariants (§18 Zero-Bypass).
4. **Authoritative Resolution for Path 1**:
   For standalone patch validation to operate under Path 1, the MCP server cannot operate as an unauthenticated authority. It must either:
   - **Mode A (Direct Attached Store)**: Connect directly to the authoritative repository `.sclass/canonical.sqlite` event store, verify read locks, and assemble genuine state from committed history.
   - **Mode B (Delegated Attestation Bundle)**: Receive an explicit, cryptographically signed `ValidationContextBundle` from the user's primary S-Class control plane containing a pre-computed `StateBinding`, `EngineeringProgram`, and `CausalFrontier` signed by the workspace authority.
   Without Mode A or Mode B, standalone MCP patch validation cannot establish genuine provenance and MUST fail closed (`BLOCKED_ON_HUMAN`).

---

## (d) Provenance Map for All 11 Former `zero_dig` Argument Positions

The helper `_make_authorized_work_request` in `src/sclass/client.py` contained 11 arguments stubbed with `zero_dig` (`sha256:000...000`). Each position is mapped below to its field semantics and required genuine source data:

| Pos | Enclosing Class & Field | Exact Line in `client.py` | Field Semantics | Genuine Source Data Required under Path 1 |
|:---|:---|:---|:---|:---|
| 1 | `ExecutionLease.request_content_digest` | Line 86 | SHA-256 of raw work request content | `digest("sclass/request-content/v1", raw_payload)` |
| 2 | `ExecutionLease.state_binding_digest` | Line 87 | Canonical digest of governing `StateBinding` | `state_binding_digest(proposal.state_binding)` |
| 3 | `ExecutionLease.target_snapshot_digest` | Line 87 | Canonical digest of workspace snapshot tree | `target_snapshot_digest(workspace_snapshot)` |
| 4 | `ExecutionLease.execution_environment_digest` | Line 89 | Digest of pinned sandbox environment & interpreter | SHA-256 of Python binary, bwrap profile, env whitelist |
| 5 | `AuthorizationLeaseClaims.request_content_digest` | Line 92 | Duplicate claim pinning authorization to request content | Validated equal to Pos 1 (`request_content_digest`) |
| 6 | `AuthorizationLeaseClaims.state_binding_digest` | Line 92 | Duplicate claim pinning authorization to state binding | Validated equal to Pos 2 (`state_binding_digest`) |
| 7 | `ContextItem.content_digest` | Line 102 | Content digest of individual context package item | SHA-256 of repository map / source file content |
| 8 | `RedactionReport.report_digest` | Line 106 | Canonical digest of data redaction log | SHA-256 of serialized redaction records and policy ID |
| 9 | `AuthorizedWorkRequest.state_binding_digest` | Line 110 | Envelope-level digest of governing `StateBinding` | Validated equal to Pos 2 (`state_binding_digest`) |
| 10 | `AuthorizedWorkRequest.authorization_binding_digest` | Line 112 | Cross-binding digest linking auth lease & execution lease | `digest("sclass/auth-binding/v1", (auth_lease.sig, ex_lease.id))` |
| 11 | `AuthorizedWorkRequest.envelope_digest` | Line 112 | Top-level integrity digest over entire request envelope | Canonical C1 digest over preceding 19 fields |

Under Path 2, `run_autonomous_cycle` refuses execution before any of these positions are constructed, preventing fabricated `zero_dig` propagation.

---

## (e) Tests and Test Designs for Missing/Inconsistent Evidence Fail-Closed

The following tests verify fail-closed enforcement across the affected boundaries:

1. **`test_golden_vertical_slice_end_to_end`** (`tests/e2e/test_golden_vertical_slice.py`):
   Invoking `run_autonomous_cycle` without genuine `StateBinding` raises `StateBindingRefusalError` (subclass of `PermissionError`) with `reason_code="MISSING_AUTHENTIC_STATE_BINDING"` and `missing_items=["state_binding", "request_content_digest", "context_digest"]`. Asserts 0 `WorkProposal`, 0 `ExecutionLease`, 0 `AuthorizationLease` objects created, and workspace filesystem untouched.
2. **`test_golden_vertical_slice_arbitrary_component`** (`tests/e2e/test_golden_vertical_slice.py`):
   Same assertion on arbitrary (non-rate-limiter) intents, ensuring no hardcoded intent bypasses exist.
3. **`test_mcp_server_dispatch_validate_patch_clean`** (`tests/interfaces/test_mcp_server.py`):
   Dispatching `sclass_validate_patch` over JSON-RPC without authentic validation context returns `status="BLOCKED_ON_HUMAN"`, `reason_code="MISSING_AUTHENTIC_VALIDATION_CONTEXT"`, and full missing items list. Asserts 0 proposals/leases created and target file uncreated.
4. **`test_mcp_server_dispatch_validate_patch_syntax_error`** (`tests/interfaces/test_mcp_server.py`):
   Same fail-closed assertion on syntax-invalid patch code; proves refusal occurs before syntax parsing or linting.
5. **Test Design: Inconsistent Event Head Hash Rejection**:
   Provide a `StateBinding` where `event_head_hash` does not match `SQLiteEventStore.get_head().hash`. The control plane must reject dispatch with `ChainIntegrityViolation`.
6. **Test Design: Incomplete Causal Frontier Rejection**:
   Provide a `WorkProposal` whose `causal_frontier` omits a required predecessor node receipt from `work_graph`. Dispatch must fail closed with `IncompleteCausalFrontierError`.

---

## (f) Explicit Declaration of the Known Gap in `EngineeringWorldModelBuilder`

> [!WARNING] **Formal Architectural Gap Declaration**
> `EngineeringWorldModelBuilder.build(workspace_root, workspace_id)` scans workspace directory trees, parses Python ASTs, and yields an `EngineeringWorldModel` containing a `TargetSnapshot` only.
>
> It does **NOT** yield:
> 1. An `EngineeringProgram` (which contains formal objectives, revisions, contracts, and obligations).
> 2. A `WorkGraph` (which defines task node dependencies, topological execution order, and resource budgets).
> 3. A `CausalFrontier` (which establishes cryptographic lineage, prerequisite completion receipts, and policy digests).
> 4. An authoritative event history or SQLite state reduction.
>
> Any attempt to substitute `EngineeringWorldModelBuilder` output for these missing governance structures is categorically invalid and explicitly prohibited by S-Class Specification §18.

---

## (g) The 5 Part C Survey Questions for CL

Before implementing Path 1, the following questions require authoritative resolution by the Change Lead (CL):

1. **MCP Event Store Attachment Topology**:
   Should IDE MCP instances attach directly to the workspace `.sclass/canonical.sqlite` event database with read-write SQLite locks, or must MCP act as an unprivileged client communicating with a persistent background S-Class daemon?
2. **Offline / Detached Validation Protocol**:
   When an IDE user validates a patch in an environment disconnected from the primary control plane, should patch validation remain strictly `BLOCKED_ON_HUMAN`, or should the protocol support an exportable, cryptographic "Validation Delegation Certificate" issued by the primary control plane?
3. **StateBinding Concurrency & Invalidation Thresholds**:
   What event categories invalidate an outstanding `StateBinding`? Specifically, do non-semantic append events (e.g. telemetry observations, read receipts, or worker heartbeat pings) invalidate `event_head_hash`, or is invalidation restricted to causal state mutations (`OBJECTIVE_*`, `WORKGRAPH_*`, `POLICY_*`, `BUDGET_*`)?
4. **Causal Frontier Graph Compaction**:
   In complex, long-running engineering programs with thousands of work nodes, should `CausalFrontier.dependency_digests` retain the complete transitive closure of all ancestor receipts, or should it apply transitive reduction to retain only the immediate boundary cut (frontier horizon)?
5. **Boundary Isolation Primitives across Operating Environments**:
   Under Path 1, where full authorized requests are constructed, how must non-Linux environments (macOS, Windows native) be handled? Should they permanently fail closed with `BoundaryUnavailable` (requiring all work execution to route through Linux/WSL containers), or will a hardened VM/container isolation provider be specified?
