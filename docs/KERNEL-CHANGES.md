# Kernel Changes Declaration: Phase H1a

This document formally declares all modifications made to the S-Class kernel (`20-RUNTIME/sclass_runtime_v6_0_1.py`) for Phase H1a.

## 1. Baseline Kernel Hashes

Per normative specification, `00-SPEC` and `10-CONFORMANCE` remain 100% byte-identical to the canonical baseline (`5420797` / `e60a089`).

| Component | Normalized LF SHA-256 | Status |
|:---|:---|:---|
| `00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md` | `53c02b13085dc3e1dcf75b9e8c306704d83bf37175b73a6be1a4b6ab7823ebb1` | Unchanged (Byte-identical) |
| `10-CONFORMANCE/sclass_semantics_v6_0_1.py` | `ed2faf251863e1411fe2f33f2848f87e8fa9d4904b7bb1e032a472874e839922` | Unchanged (Byte-identical) |
| `10-CONFORMANCE/sclass_kernel_v6_0_1.py` | `d0f8f124dd55aab5cfb68d8c7d644eccf2694f52016c2e4a2132e6d6cef5575c` | Unchanged (Byte-identical) |
| `10-CONFORMANCE/c1-vectors.v6.0.1.json` | `db58744d9829f7cac2ec7715a93d30d20a0d9ba6912d01f563504564e85b2da8` | Unchanged (Byte-identical) |
| `10-CONFORMANCE/state-machines.v6.0.1.json` | `24f159e6f72179ea66365b585f085727f6ef48420a09eae8c6024cb0bb51fdad` | Unchanged (Byte-identical) |
| `20-RUNTIME/sclass_runtime_v6_0_1.py` | `d890cff7e14c2fd7e4e7f7ea513439efc3349ef781b64425654479fcf5de43c1` | Declared H1a Baseline |

BASELINE_20_RUNTIME_SHA256: d890cff7e14c2fd7e4e7f7ea513439efc3349ef781b64425654479fcf5de43c1

---

## 2. Declared Changes to `20-RUNTIME/sclass_runtime_v6_0_1.py`

### Hunk 1: Definition of `BoundaryUnavailable` (lines 1371–1374)
- **Lines**: 1371–1374
- **Reason**: Implement fail-closed boundary exception when required OS isolation primitives (bubblewrap or cgroup v2) are missing or inoperative.
- **Spec Section**: §2.2, §18 (Zero-Bypass Execution Invariant)
- **Change**:
  ```python
  class BoundaryUnavailable(PermissionError):
      """Raised when required OS boundary mechanisms (bubblewrap, cgroup v2) are unavailable."""
      pass
  ```

### Hunk 2: Cgroup v2 Hardening in `_assert_cgroup_v2` (lines 1478–1484)
- **Lines**: 1478–1484
- **Reason**: Require cgroup v2 controllers and hierarchy writability; raise `BoundaryUnavailable` fail-closed instead of generic `PermissionError`.
- **Spec Section**: §18, ERR-004
- **Change**:
  ```python
  def _assert_cgroup_v2(self) -> None:
      root=Path("/sys/fs/cgroup")
      controllers=root/"cgroup.controllers"
      if not controllers.exists():
          raise BoundaryUnavailable("cgroup v2 is required for execution boundary")
      if not os.access(root,os.W_OK):
          raise BoundaryUnavailable("cgroup v2 hierarchy is not writable by execution runtime")
  ```

### Hunk 3: Elimination of `SCLASS_TEST_MODE` in `_command` (lines 1515–1520)
- **Lines**: 1515–1520 (previously line 1511)
- **Reason**: Delete ambient environment switch `SCLASS_TEST_MODE` in `LinuxExecutionBoundary._command`. Enforce that bubblewrap and cgroup v2 are non-negotiable prerequisites. If unavailable, fail closed with `BoundaryUnavailable` before spawning any subprocess.
- **Spec Section**: §2.2, §18
- **Change**:
  ```python
  # Old:
  if not self.bwrap:
      if self.require_sandbox: raise PermissionError("bubblewrap unavailable; OS-enforced execution denied")
      if os.environ.get("SCLASS_TEST_MODE") != "1": raise PermissionError("unsandboxed execution is test-only")
      return normalized, () , ()

  # New:
  if not self.bwrap:
      raise BoundaryUnavailable("bubblewrap unavailable; OS-enforced execution denied")
  self._assert_cgroup_v2()
  ```

### Hunk 4: Cgroup v2 Assertion on Boundary Entry (lines 1735–1740)
- **Lines**: 1735–1740
- **Reason**: Validate both bubblewrap and cgroup v2 availability on `LinuxExecutionBoundary.enter()`, failing closed with `BoundaryUnavailable`.
- **Spec Section**: §2.2, §18
- **Change**:
  ```python
  def enter(self, request: AuthorizedWorkRequest, handle: LocalWorkspaceSnapshotHandle) -> BoundaryContext:
      if not self.bwrap:
          raise BoundaryUnavailable("bubblewrap unavailable; boundary entry denied")
      self._assert_cgroup_v2()
  ```

### Hunk 5: Deletion of `run_for_test` from `LinuxExecutionBoundary` (lines 1762–1768)
- **Lines**: 1762–1768 (deleted)
- **Reason**: Test authority must never equal canonical authority. Completely remove `run_for_test` from the shipped LinuxExecutionBoundary. Test-only boundaries (`TestOnlyUnsandboxedBoundary`) maintain their own test methods under `tests/helpers/`.
- **Spec Section**: §18 (Zero-Bypass Execution Invariant)
- **Change**:
  ```python
  # Deleted from LinuxExecutionBoundary:
  def run_for_test(self, argv: Sequence[str], **kwargs) -> BoundaryRunResult:
      """Test-only adapter entry. Shipped code must use ExecutionGate."""
      return self._run_from_gate(self._gate_capability, argv, **kwargs)
  ```

### Hunk 6: Decoupling of Attestor Authority and Meaningful `is_provisioned` (lines 1867–1908)
- **Lines**: 1867–1908
- **Reason**: Attestor authority must be injected rather than self-registered. Removed self-registration from `LocalQuiescenceAttestor.__init__` so constructing an attestor leaves the key directory unchanged. Implemented meaningful `is_provisioned` property that checks whether the attestor's signing key is registered and active in the key directory, eliminating dead code in `attest()`. `is_production_provisioned()` ensures test attestors (`_test_only=True`) and unprovisioned keys are rejected.
- **Spec Section**: §2.2, §13, §18
- **Change**:
  ```python
  # LocalQuiescenceAttestor.__init__: no keys.add_root or keys.register
  def is_production_provisioned(self) -> bool:
      return not self._test_only and self.is_provisioned

  @property
  def is_provisioned(self) -> bool:
      if not self.trust_root or not self.key_id or self.private is None:
          return False
      if self.keys is None or not hasattr(self.keys, "status"):
          return False
      return self.keys.status(self.key_id, self.trust_root, _now()) is KeyStatus.ACTIVE
  ```

### Hunk 7: Removal of MagicMock Name Checks in `WorkerContract.execute` (lines 1970–1988)
- **Lines**: 1970–1988
- **Reason**: Remove all `type(...).__name__ != "MagicMock"` backdoors from kernel. Enforce that `request` must be `AuthorizedWorkRequest` and `boundary` must be `BoundaryContext`. Explicitly reject any object whose class is named `"MagicMock"`.
- **Spec Section**: §8.6, §18
- **Change**:
  ```python
  # Old:
  if not isinstance(request, AuthorizedWorkRequest) and type(request).__name__ != "MagicMock": ...
  if boundary is None or (not isinstance(boundary, BoundaryContext) and type(boundary).__name__ != "MagicMock"): ...
  if type(boundary).__name__ != "MagicMock" and boundary.fencing_token != request.execution_lease.fencing_token: ...

  # New:
  if not isinstance(request, AuthorizedWorkRequest) or type(request).__name__ == "MagicMock": ...
  if boundary is None or not isinstance(boundary, BoundaryContext) or type(boundary).__name__ == "MagicMock": ...
  if boundary.fencing_token != request.execution_lease.fencing_token: ...
  ```

### Hunk 8: Fail-Closed Real LinuxExecutionBoundary Preflight Attestor and Pinned Root Verification (lines 2185–2201)
- **Lines**: 2185–2201
- **Reason**: When `ExecutionGate` runs with a concrete `LinuxExecutionBoundary`, verify that `boundary_attestor` is canonically provisioned (`is_production_provisioned() == True`), its trust root is in `self.control_plane.keys.roots()`, its trust root is in `self.control_plane.pinned_trust_roots`, and its signing key is active. Reject any test-only attestor or unpinned root with `PermissionError` at preflight before any subprocess spawn.
- **Spec Section**: §2.2, §8.6, §18
- **Change**:
  ```python
  if isinstance(self.boundary, LinuxExecutionBoundary):
      attestor = self.control_plane.boundary_attestor
      is_prod = getattr(attestor, "is_production_provisioned", None)
      if callable(is_prod):
          is_prod = is_prod()
      if not is_prod or getattr(attestor, "_test_only", False):
          raise PermissionError("real LinuxExecutionBoundary rejects test-only quiescence authority")
      if not attestor or not getattr(attestor, "trust_root", None):
          raise PermissionError("quiescence attestor has no provisioned trust root")
      if attestor.trust_root not in self.control_plane.keys.roots():
          raise PermissionError("quiescence attestor trust root is not in provisioned trust roots")
      if attestor.trust_root not in self.control_plane.pinned_trust_roots:
          raise PermissionError("quiescence attestor trust root is not in pinned trust roots")
      if self.control_plane.keys.status(attestor.key_id, attestor.trust_root, _now()) is not KeyStatus.ACTIVE:
          raise PermissionError("quiescence attestor key is not active in provisioned trust root")
  ```

### Hunk 9: Implementation of `SQLiteKeyDirectory.roots()` (lines 502–505)
- **Lines**: 502–505
- **Reason**: Implement `roots()` method on `SQLiteKeyDirectory` returning active trust root IDs from `runtime_trust_roots`. Prevents `AttributeError` when `ExecutionGate._preflight` checks active trust roots.
- **Spec Section**: §2.2, §18
- **Change**:
  ```python
  def roots(self) -> set[str]:
      rows = self.db.execute("SELECT root_id FROM runtime_trust_roots WHERE status='ACTIVE'").fetchall()
      return {r[0] for r in rows}
  ```

### Hunk 10: Injected Pinned Trust Roots in `SClassControlPlane.__init__` (lines 917–948)
- **Lines**: 917–948
- **Reason**: Pin trust roots outside the attestor at control plane construction time via `pinned_trust_roots`. Eliminates circular self-provisioning.
- **Spec Section**: §2.2, §18
- **Change**:
  ```python
  def __init__(self, store: SQLiteEventStore, pinned_trust_roots: Optional[Iterable[str]] = None):
      ...
      self.pinned_trust_roots: set[str] = pinned
      for root in self.pinned_trust_roots:
          self.keys.add_root(root)
  ```

---

## 3. List of Migrated Tests (Task 3)

The following tests previously depended on ambient `os.environ["SCLASS_TEST_MODE"] = "1"` or required sandbox execution. All tests have been migrated to use explicit dependency injection (`TestOnlyUnsandboxedBoundary` under `tests/helpers/test_boundary.py` or provisioned attestors), with their assertions 100% UNCHANGED:

1. `20-RUNTIME/test_sclass_runtime_v6_0_1.py::test_fail_closed_os_boundary_without_sandbox`
   - Removed `monkeypatch.setenv("SCLASS_TEST_MODE", "1")`. Validates bubblewrap fail-closed behavior directly.
2. `20-RUNTIME/test_sclass_runtime_v6_0_1.py::test_raw_os_execution_cannot_bypass_execution_gate`
   - Removed `monkeypatch.setenv("SCLASS_TEST_MODE", "1")`. Tests raw boundary bypass denial.
3. `20-RUNTIME/test_sclass_runtime_v6_0_1.py::test_execution_boundary_checks_authorized_executable_digest`
   - Injected `TestOnlyUnsandboxedBoundary(tmp_path)`. Removed `monkeypatch.setenv("SCLASS_TEST_MODE", "1")`.
4. `20-RUNTIME/test_sclass_runtime_v6_0_1.py::test_quiescence_attestation_is_bound_to_exact_process_identity`
   - Removed `monkeypatch.setenv("SCLASS_TEST_MODE", "1")`. Attestor constructed via `LocalQuiescenceAttestor.for_test(cp.keys)` works without ambient switches.
5. `20-RUNTIME/test_sclass_runtime_v6_0_1.py::test_process_tree_monitor_rejects_unauthorized_descendant`
   - Injected `TestOnlyUnsandboxedBoundary(tmp_path)`. Removed `monkeypatch.setenv("SCLASS_TEST_MODE", "1")`.
6. `20-RUNTIME/test_sclass_runtime_v6_0_1.py::test_process_tree_monitor_records_authorized_same_binary_child`
   - Injected `TestOnlyUnsandboxedBoundary(tmp_path)`. Removed `monkeypatch.setenv("SCLASS_TEST_MODE", "1")`.
7. `20-RUNTIME/test_sclass_runtime_v6_0_1.py::test_execute_lifecycle_exit_0_effect_mismatch_rejects`
   - Migrated from `MagicMock` to authentic `AuthorizedWorkRequest`, `TestOnlyUnsandboxedBoundary`, and `create_test_quiescence_attestor(cp.keys)`. Assertions 100% unchanged.
8. `20-RUNTIME/test_sclass_runtime_v6_0_1.py::test_execute_lifecycle_exit_0_effect_match_accepts`
   - Migrated from `MagicMock` to authentic `AuthorizedWorkRequest`, `TestOnlyUnsandboxedBoundary`, and `create_test_quiescence_attestor(cp.keys)`. Assertions 100% unchanged.
9. `tests/stage_exit/test_s2_exit.py::test_s2_exit_quiescence_proof_binding`
   - Uses `create_test_quiescence_attestor(cp.keys)` under `tests/helpers/test_boundary.py`. Assertions unchanged.
10. `tests/workers/test_worker_harness.py::test_subprocess_tool_worker_execution`
    - Injected `TestOnlyUnsandboxedBoundary(ws_path)`. Removed `os.environ["SCLASS_TEST_MODE"] = "1"`.
11. `tests/workers/test_worker_harness.py::test_patch_agent_worker_mutation_and_authorization`
    - Injected `TestOnlyUnsandboxedBoundary(ws_path)`. Assertions unchanged.
12. `tests/workers/test_worker_harness.py::test_patch_agent_worker_traversal_and_fail_closed`
    - Injected `TestOnlyUnsandboxedBoundary(ws_path)`. Assertions unchanged.
13. `tests/interfaces/test_mcp_server.py::test_mcp_server_dispatch_validate_patch_clean`
    - Injected `TestOnlyUnsandboxedBoundary(ws_dir)`. Assertions unchanged.
14. `tests/interfaces/test_mcp_server.py::test_mcp_server_dispatch_validate_patch_syntax_error`
    - Injected `TestOnlyUnsandboxedBoundary(ws_dir)`. Assertions unchanged.
15. `tests/e2e/test_golden_vertical_slice.py::test_golden_vertical_slice_end_to_end`
    - Injected `TestOnlyUnsandboxedBoundary(tmp_path)`. Assertions unchanged.
16. `tests/e2e/test_golden_vertical_slice.py::test_golden_vertical_slice_arbitrary_component`
    - Injected `TestOnlyUnsandboxedBoundary(tmp_path)`. Assertions unchanged.
17. `tests/security/test_boundary_hardening.py::test_production_boundary_reaches_trust_root_check_permission_error`
    - Evaluates D1: real LinuxExecutionBoundary reaches trust-root check and raises PermissionError (not AttributeError).
18. `tests/security/test_boundary_hardening.py::test_attestor_built_with_production_token_ephemeral_key_rejected_at_preflight`
    - Evaluates D2 (a): attestor built with token and ephemeral key raises PermissionError at preflight.
19. `tests/security/test_boundary_hardening.py::test_constructing_attestor_leaves_key_directory_unchanged`
    - Evaluates D2 (b): constructing an attestor leaves the key directory unchanged.
20. `tests/security/test_boundary_hardening.py::test_no_constructor_route_accepted_when_pinned_roots_exclude_it`
    - Evaluates D2 (c): no constructor route yields an attestor accepted when pinned roots exclude it.
21. `tests/security/test_boundary_hardening.py::test_is_provisioned_guard_meaningful_and_active`
    - Evaluates D3: proves is_provisioned is meaningful and actively guards attest().
