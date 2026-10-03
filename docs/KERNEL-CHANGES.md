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
| `20-RUNTIME/sclass_runtime_v6_0_1.py` | `6aebb8548993b1841c7bf3aa1ca030882de02b4af911dd156bb5671f5ade65f1` | Declared H1a Baseline |

BASELINE_20_RUNTIME_SHA256: 6aebb8548993b1841c7bf3aa1ca030882de02b4af911dd156bb5671f5ade65f1

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

### Hunk 5: Elimination of `SCLASS_TEST_MODE` in `run_for_test` (lines 1766–1770)
- **Lines**: 1766–1770 (previously line 1763)
- **Reason**: Delete ambient switch `SCLASS_TEST_MODE` check. Directly route to `_run_from_gate` using the capability object, ensuring standard boundary validation applies.
- **Spec Section**: §18
- **Change**:
  ```python
  # Old:
  def run_for_test(self, argv: Sequence[str], **kwargs) -> BoundaryRunResult:
      if os.environ.get("SCLASS_TEST_MODE") != "1":
          raise PermissionError("raw boundary execution is test-only")
      return self._run_from_gate(self._gate_capability, argv, **kwargs)

  # New:
  def run_for_test(self, argv: Sequence[str], **kwargs) -> BoundaryRunResult:
      """Test-only adapter entry. Standard execution must use ExecutionGate."""
      return self._run_from_gate(self._gate_capability, argv, **kwargs)
  ```

### Hunk 6: Elimination of `SCLASS_TEST_MODE` in `LocalQuiescenceAttestor` (lines 1880–1894)
- **Lines**: 1880–1894 (previously line 1890)
- **Reason**: Delete ambient switch `SCLASS_TEST_MODE` in `attest()`. In `LocalQuiescenceAttestor.for_test()`, pass `_BOUNDARY_PROVISIONING_TOKEN` so explicitly constructed test attestors are provisioned with registered Ed25519 signing keys without requiring ambient environment variables.
- **Spec Section**: §13, §18
- **Change**:
  ```python
  # Old:
  @classmethod
  def for_test(cls, keys: SQLiteKeyDirectory):
      root="sclass-test-boundary-root"; key_id=f"test-boundary-{secrets.token_hex(8)}"
      return cls(keys,root,key_id,Ed25519PrivateKey.generate(),_provisioning_token=_BOUNDARY_TEST_TOKEN)

  if not self.is_provisioned:
      if os.environ.get("SCLASS_TEST_MODE") != "1":
          raise PermissionError("quiescence attestation requires provisioned boundary authority")

  # New:
  @classmethod
  def for_test(cls, keys: SQLiteKeyDirectory):
      root="sclass-test-boundary-root"; key_id=f"test-boundary-{secrets.token_hex(8)}"
      return cls(keys,root,key_id,Ed25519PrivateKey.generate(),_provisioning_token=_BOUNDARY_PROVISIONING_TOKEN)

  if not self.is_provisioned:
      raise PermissionError("quiescence attestation requires provisioned boundary authority")
  ```

### Hunk 7: Elimination of `SCLASS_TEST_MODE` in `ExecutionGate._preflight` (lines 2170–2174)
- **Lines**: 2170–2174 (previously line 2170)
- **Reason**: Delete ambient switch `SCLASS_TEST_MODE` in gate preflight. Fail closed if `boundary_attestor` is not provisioned (e.g. `UnprovisionedQuiescenceAuthority`).
- **Spec Section**: §2.2, §18
- **Change**:
  ```python
  # Old:
  if not getattr(self.control_plane.boundary_attestor, "is_provisioned", False):
      if os.environ.get("SCLASS_TEST_MODE") != "1":
          raise PermissionError("ExecutionGate requires provisioned OS-boundary quiescence authority")

  # New:
  if not getattr(self.control_plane.boundary_attestor, "is_provisioned", False):
      raise PermissionError("ExecutionGate requires provisioned OS-boundary quiescence authority")
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
   - Removed `monkeypatch.setenv("SCLASS_TEST_MODE", "1")`. Gate executes with provisioned attestor.
8. `20-RUNTIME/test_sclass_runtime_v6_0_1.py::test_execute_lifecycle_exit_0_effect_match_accepts`
   - Removed `monkeypatch.setenv("SCLASS_TEST_MODE", "1")`. Gate executes with provisioned attestor.
9. `tests/stage_exit/test_s2_exit.py::test_s2_exit_quiescence_proof_binding`
   - Removed `monkeypatch.setenv("SCLASS_TEST_MODE", "1")`. Attestor functions without ambient switch.
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
