# Kernel Changes Declaration: Phase H1a / H1b

This document formally declares all modifications made to the S-Class kernel (`20-RUNTIME/sclass_runtime_v6_0_1.py`) for Phases H1a and H1b.

## 1. Baseline Kernel Hashes

Per normative specification, `00-SPEC` and `10-CONFORMANCE` remain 100% byte-identical to the canonical baseline (`5420797` / `e60a089`).

| Component | Normalized LF SHA-256 | Status |
|:---|:---|:---|
| `00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md` | `53c02b13085dc3e1dcf75b9e8c306704d83bf37175b73a6be1a4b6ab7823ebb1` | Unchanged (Byte-identical) |
| `10-CONFORMANCE/sclass_semantics_v6_0_1.py` | `ed2faf251863e1411fe2f33f2848f87e8fa9d4904b7bb1e032a472874e839922` | Unchanged (Byte-identical) |
| `10-CONFORMANCE/sclass_kernel_v6_0_1.py` | `d0f8f124dd55aab5cfb68d8c7d644eccf2694f52016c2e4a2132e6d6cef5575c` | Unchanged (Byte-identical) |
| `10-CONFORMANCE/c1-vectors.v6.0.1.json` | `db58744d9829f7cac2ec7715a93d30d20a0d9ba6912d01f563504564e85b2da8` | Unchanged (Byte-identical) |
| `10-CONFORMANCE/state-machines.v6.0.1.json` | `24f159e6f72179ea66365b585f085727f6ef48420a09eae8c6024cb0bb51fdad` | Unchanged (Byte-identical) |
| `20-RUNTIME/sclass_runtime_v6_0_1.py` | `b84f7bd79cd164734aa3497af845ab27e4a042e6cfe3b23dd6593718a4a7ff0b` | Declared H1b X1-X3 Baseline |

BASELINE_20_RUNTIME_SHA256: b84f7bd79cd164734aa3497af845ab27e4a042e6cfe3b23dd6593718a4a7ff0b

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

### Hunk 8: Fail-Closed Real LinuxExecutionBoundary Preflight Attestor and Pinned Key Enforcement (lines 2259–2285)
- **Lines**: 2259–2285
- **Reason**: When `ExecutionGate` runs with a concrete `LinuxExecutionBoundary`, enforce that `boundary_attestor` is canonically provisioned (`is_production_provisioned() == True`), explicit `pinned_keys` are configured in the control plane, its trust root is in `self.control_plane.keys.roots()`, its trust root is in `self.control_plane.pinned_trust_roots`, its signing key is active in `self.control_plane.keys`, and the public key of the attestor matches the pinned key set `(attestor.trust_root, attestor_pub) in self.control_plane.pinned_keys`. Reject any test-only attestor, unpinned root, or unpinned key with `PermissionError` at preflight before any subprocess spawn.
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
      if not getattr(self.control_plane, "pinned_keys", None):
          raise PermissionError("real LinuxExecutionBoundary requires explicit pinned keys in control plane")
      if attestor.trust_root not in self.control_plane.keys.roots():
          raise PermissionError("quiescence attestor trust root is not in provisioned trust roots")
      if attestor.trust_root not in self.control_plane.pinned_trust_roots:
          raise PermissionError("quiescence attestor trust root is not in pinned trust roots")
      if self.control_plane.keys.status(attestor.key_id, attestor.trust_root, _now()) is not KeyStatus.ACTIVE:
          raise PermissionError("quiescence attestor key is not active in provisioned trust root")
      pub_row = self.control_plane.keys.db.execute(
          "SELECT public_key FROM runtime_keys WHERE key_id=? AND trust_root=?",
          (attestor.key_id, attestor.trust_root),
      ).fetchone()
      if pub_row is None:
          raise PermissionError("quiescence attestor key is not active in provisioned trust root")
      attestor_pub = bytes(pub_row[0])
      if (attestor.trust_root, attestor_pub) not in self.control_plane.pinned_keys:
          raise PermissionError("quiescence attestor key is not in pinned key set")
  ```

### Hunk 9: Implementation of `SQLiteKeyDirectory.roots()` (lines 582–585)
- **Lines**: 582–585
- **Reason**: Implement `roots()` method on `SQLiteKeyDirectory` returning active trust root IDs from `runtime_trust_roots`. Prevents `AttributeError` when `ExecutionGate._preflight` checks active trust roots.
- **Spec Section**: §2.2, §18
- **Change**:
  ```python
  def roots(self) -> set[str]:
      rows = self.db.execute("SELECT root_id FROM runtime_trust_roots WHERE status='ACTIVE'").fetchall()
      return {r[0] for r in rows}
  ```

### Hunk 10: Removal of Environment Variable Fallbacks in `SClassControlPlane.__init__` (lines 1000–1035)
- **Lines**: 1000–1035
- **Reason**: Remove all `os.environ` reads (`SCLASS_PINNED_TRUST_ROOTS`, `SCLASS_BOUNDARY_TRUST_ROOT`) and eliminate attestor auto-registration from the control-plane constructor. Pins come exclusively from explicit constructor argument `pinned_keys`. Eliminates circular self-provisioning.
- **Spec Section**: §2.2, §18
- **Change**:
  ```python
  # Old:
  if pinned_trust_roots is None:
      env_roots = os.environ.get("SCLASS_PINNED_TRUST_ROOTS")
      if env_roots:
          pinned = {r.strip() for r in env_roots.split(",") if r.strip()}
      else:
          env_root = os.environ.get("SCLASS_BOUNDARY_TRUST_ROOT")
          pinned = {env_root} if env_root else set()
  else:
      pinned = set(pinned_trust_roots)
  self.pinned_trust_roots: set[str] = pinned
  for root in self.pinned_trust_roots:
      self.keys.add_root(root)
  self.boundary_attestor=LocalQuiescenceAttestor.from_environment(self.keys) or UnprovisionedQuiescenceAuthority()
  if isinstance(self.boundary_attestor, LocalQuiescenceAttestor) and self.boundary_attestor.trust_root in self.pinned_trust_roots:
      pub = self.boundary_attestor.private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
      try:
          self.keys.register(self.boundary_attestor.key_id, self.boundary_attestor.trust_root, pub, 0, 2**63 - 1)
      except (sqlite3.IntegrityError, ValueError):
          pass

  # New:
  def __init__(self, store: SQLiteEventStore, pinned_keys: Optional[Iterable[Any]] = None, *, boundary_attestor: Optional[Any] = None, pinned_trust_roots: Optional[Iterable[Any]] = None):
      ...
      if pinned_keys is not None:
          self.pinned_keys = _normalize_pinned_keys(pinned_keys)
      elif pinned_trust_roots is not None:
          self.pinned_keys = _normalize_pinned_keys(pinned_trust_roots)
      else:
          self.pinned_keys = None
      self.pinned_trust_roots: set[str] = {r for r, _ in self.pinned_keys} if self.pinned_keys is not None else set()
      self.keys = SQLiteKeyDirectory(self.db, pinned_keys=self.pinned_keys)
      for root in self.pinned_trust_roots:
          self.keys.add_root(root)
      self.workers=SQLiteWorkerRegistry(self.db)
      self.effects=ExternalEffectReconciler(self.db)
      self.boundary_attestor = boundary_attestor or UnprovisionedQuiescenceAuthority()
  ```

### Hunk 11: PinnedKey Dataclass and Pin Enforcement in `SQLiteKeyDirectory.register` (lines 477–589)
- **Lines**: 477–589
- **Reason**: Implement `PinnedKey` dataclass and `_normalize_pinned_keys` parser. Ensure `SQLiteKeyDirectory.register` strictly refuses any `(trust_root, public_key)` pair not in the pinned set with `PermissionError`. Bare root-id strings are rejected. Supports protected pin file path (mode <= 0600) for H1b compatibility.
- **Spec Section**: §2.2, §18
- **Change**:
  ```python
  @dataclass(frozen=True)
  class PinnedKey:
      trust_root: str
      public_key: bytes
      key_id: Optional[str] = None
      ...

  def register(self, key_id: str, trust_root: str, public_key: bytes, not_before: int=0, not_after: int=2**63-1):
      if len(public_key)!=32 or not key_id or not trust_root or not_before >= not_after: raise ValueError("invalid key registration")
      if self.pinned_keys is not None:
          if (trust_root, bytes(public_key)) not in self.pinned_keys:
              raise PermissionError(f"key {key_id} for root {trust_root} is not in pinned key set")
      ...
  ```

### Hunk 12: Protected Pin File Ownership, Non-Symlink, and Mode Invariants in `_normalize_pinned_keys` (M3, F2, F3)
- **Lines**: 499–550
- **Reason**: Pins and keys must load from a protected file: regular file (reject symlinks via `os.lstat`, `stat.S_ISLNK`, `p.is_symlink()`, and `O_NOFOLLOW`), opened directly with `os.open(p, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)`, stat checked via `os.fstat(fd)` (preventing TOCTOU re-opening races), mode <= 0600 (`(stat.S_IMODE(st.st_mode) & ~0o600) != 0` rejecting special/setuid/execute/group/other bits), owned by the service user (`st_uid == os.getuid()`), content read directly from the descriptor with `os.fdopen(fd)`, failing closed with `PermissionError` on any violation or `FileNotFoundError` if missing.
- **Spec Section**: §2.2, §18
- **Change**:
  ```python
  if isinstance(pinned_keys, (str, Path)):
      p = Path(pinned_keys)
      import stat, errno, json
      try:
          lst = os.lstat(p)
          if stat.S_ISLNK(lst.st_mode) or p.is_symlink():
              raise PermissionError(f"pinned keys file {p} cannot be a symlink")
      except FileNotFoundError as exc:
          raise FileNotFoundError(f"pinned keys path {pinned_keys} does not exist") from exc
      except OSError as exc:
          if getattr(exc, "errno", None) in (errno.ELOOP,):
              raise PermissionError(f"pinned keys file {p} cannot be a symlink") from exc
          raise

      flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
      if hasattr(os, "O_NOFOLLOW"): flags |= os.O_NOFOLLOW
      try:
          fd = os.open(p, flags)
      except FileNotFoundError as exc:
          raise FileNotFoundError(f"pinned keys path {pinned_keys} does not exist") from exc
      except OSError as exc:
          if getattr(exc, "errno", None) in (errno.ELOOP,):
              raise PermissionError(f"pinned keys file {p} cannot be a symlink") from exc
          raise

      try:
          st = os.fstat(fd)
          if stat.S_ISLNK(st.st_mode):
              raise PermissionError(f"pinned keys file {p} cannot be a symlink")
          if not stat.S_ISREG(st.st_mode):
              raise PermissionError(f"pinned keys path {p} must be a regular file")
          if hasattr(os, "fstat") and sys.platform != "win32":
              if (stat.S_IMODE(st.st_mode) & ~0o600) != 0:
                  raise PermissionError(f"pinned keys file {p} has insecure permissions (must be mode <= 0600)")
              if hasattr(os, "getuid") and st.st_uid != os.getuid():
                  raise PermissionError(f"pinned keys file {p} must be owned by the service user (uid {os.getuid()})")
          with os.fdopen(fd, "r", encoding="utf-8") as f:
              fd = None
              content = f.read()
      finally:
          if fd is not None:
              try: os.close(fd)
              except OSError: pass
  ```

### Hunk 13: Removal of `LocalQuiescenceAttestor.from_environment` (M2)
- **Lines**: 1946–1958 (deleted)
- **Reason**: Completely deleted `from_environment` classmethod from `LocalQuiescenceAttestor`. Ambient environment variable reads (`SCLASS_BOUNDARY_TRUST_ROOT`, `SCLASS_BOUNDARY_KEY_ID`, `SCLASS_BOUNDARY_PRIVATE_KEY_B64`) are eliminated; attestor key material must be explicitly injected.
- **Spec Section**: §2.2, §18
- **Change**:
  ```python
  # Deleted from LocalQuiescenceAttestor:
  # @classmethod
  # def from_environment(cls, keys: SQLiteKeyDirectory): ...
  ```

### Hunk 14: Attestor Private Key Validation in `ExecutionGate._preflight` (M1)
- **Lines**: 1968–1972, 2282–2297
- **Reason**: Added `public_key_bytes` property to `LocalQuiescenceAttestor`. In `ExecutionGate._preflight`, derives the attestor's public key directly from its private key (`attestor.private.public_key().public_bytes(...)`), verifies it matches the registered public key, and verifies it is in `pinned_keys`. Fails closed with `PermissionError` before any worker process or container is spawned.
- **Spec Section**: §2.2, §18
- **Change**:
  ```python
  if not hasattr(attestor, "private") or attestor.private is None:
      raise PermissionError("quiescence attestor private key is missing")
  try:
      own_pub = attestor.private.public_key().public_bytes(
          serialization.Encoding.Raw, serialization.PublicFormat.Raw
      )
  except Exception as exc:
      raise PermissionError(f"quiescence attestor private key is invalid: {exc}") from exc
  if own_pub != attestor_pub:
      raise PermissionError("quiescence attestor private key does not match registered public key")
  if (attestor.trust_root, own_pub) not in self.control_plane.pinned_keys:
      raise PermissionError("quiescence attestor private key is not in pinned key set")
  ```

### Hunk 15: Bubblewrap User Namespace Probe and Delegated Cgroup v2 Hardening (M5, M6, M7)
- **Lines**: 1500–1665, 1680–1695, 1753–1756, 1820–1875
- **Reason**:
  1. In `LinuxExecutionBoundary.__init__`, added support for delegated `cgroup_root` argument, automatically probing `/sys/fs/cgroup/sclass` before fallback to `/sys/fs/cgroup`.
  2. Added `_is_bwrap_functional` and `_assert_bwrap_usable` to probe whether unprivileged user namespaces and Bubblewrap mount capabilities are functional on the host (detecting Ubuntu 24.04 AppArmor restrictions), failing closed with `BoundaryUnavailable` before spawning any subprocess.
  3. Added `_create_cgroup` to initialize cgroup v2 leaves before `Popen`, attaching the child process in `preexec_fn` directly to eliminate PID namespace fork races on resource limits (`memory.max`, `memory.swap.max`, `pids.max`, `cpu.max`).
  4. In `_command`, added ro-bind mounts for `/opt` and active Python prefix directories (`sys.prefix` and `sys.base_prefix`), enabling containerized execution across standard system and CI runner toolchains without leaking write privileges.
  5. In `_snapshot_tree` and process tree monitoring, allowed the container supervisor binary (`bwrap`) in addition to the target executable payload, and hardened `_kill_group` with atomic `cgroup.kill` and PID termination.
- **Spec Section**: §8.6, §18
- **Change**:
  ```python
  @classmethod
  def _is_bwrap_functional(cls, bwrap_path: Optional[str]) -> bool:
      if not bwrap_path: return False
      if bwrap_path in cls._bwrap_functional_cache: return cls._bwrap_functional_cache[bwrap_path]
      try:
          res = subprocess.run([bwrap_path, "--unshare-user", "--ro-bind", "/", "/", "true"], capture_output=True, timeout=2.0)
          usable = (res.returncode == 0)
      except Exception: usable = False
      cls._bwrap_functional_cache[bwrap_path] = usable
      return usable

  def _assert_bwrap_usable(self) -> None:
      if not self.bwrap:
          raise BoundaryUnavailable("bubblewrap unavailable; OS-enforced execution denied")
      if not self._is_bwrap_functional(self.bwrap):
          raise BoundaryUnavailable("bubblewrap unprivileged user namespaces are blocked or restricted on this host")
  ```

### Hunk 16: Fail-Closed Cgroup Controller Limits, Attach, and Child RLIMIT Enforcement (X1, X2, X3)
- **Lines**: 41, 1527, 1541, 1648–1705, 1812–1835, 1910–1918, 1973–2005
- **Reason**:
  1. In `_create_cgroup`, strictly require requested controller files (`memory.max`, `pids.max`, `cpu.max`) to exist and write operations to succeed, raising `BoundaryUnavailable` before any process or container is spawned (X1).
  2. Require `cgroup.procs` to exist and be writable in `_create_cgroup`, and raise `BoundaryUnavailable` on any attach failure in `_attach_cgroup`, child `_preexec`, or parent `Popen` (X1, X2).
  3. In child `_preexec`, abort child immediately with `RuntimeError` if any resource limit required by the budget (`RLIMIT_AS` for `memory_mb`, `RLIMIT_NPROC` for `process_count`, `RLIMIT_FSIZE` for `disk_mb`) fails `resource.setrlimit`, preventing unconfined worker execution (X1).
  4. In `BoundaryRunResult` and `LinuxExecutionBoundary`, collect authentic kernel limit enforcement events from `memory.events` (`max`, `oom`, `oom_kill`) and `pids.events` (`max`) before cgroup cleanup, exposing them in `res.cgroup_events` and `boundary.last_cgroup_events` (X3).
- **Spec Section**: §8.6, §18
- **Change**:
  ```python
  if budget.memory_mb > 0:
      mem_file = group / "memory.max"
      if not mem_file.exists():
          raise BoundaryUnavailable(f"cgroup memory controller (memory.max) is missing in {group}")
      try:
          mem_file.write_text(str(budget.memory_mb * 1024 * 1024))
      except OSError as exc:
          raise BoundaryUnavailable(f"failed to set memory.max in {group}: {exc}") from exc
  ```

---

## 3. List of Migrated and Hardened Tests (Task 3)

The following tests execute against the kernel and boundary harnesses, with explicit dependency injection (`TestOnlyUnsandboxedBoundary` under `tests/helpers/test_boundary.py` or provisioned attestors):

1. `20-RUNTIME/test_sclass_runtime_v6_0_1.py::test_fail_closed_os_boundary_without_sandbox`
   - Removed `monkeypatch.setenv("SCLASS_TEST_MODE", "1")`. Tests bubblewrap fail-closed behavior directly.
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
   - Migrated from `MagicMock` to authentic `AuthorizedWorkRequest`, `TestOnlyUnsandboxedBoundary`, and `create_test_quiescence_attestor(cp.keys)`.
8. `20-RUNTIME/test_sclass_runtime_v6_0_1.py::test_execute_lifecycle_exit_0_effect_match_accepts`
   - Migrated from `MagicMock` to authentic `AuthorizedWorkRequest`, `TestOnlyUnsandboxedBoundary`, and `create_test_quiescence_attestor(cp.keys)`.
9. `tests/stage_exit/test_s2_exit.py::test_s2_exit_quiescence_proof_binding`
   - Uses `create_test_quiescence_attestor(cp.keys)` under `tests/helpers/test_boundary.py`.
10. `tests/workers/test_worker_harness.py::test_subprocess_tool_worker_execution`
    - Injected `TestOnlyUnsandboxedBoundary(ws_path)`.
11. `tests/workers/test_worker_harness.py::test_patch_agent_worker_mutation_and_authorization`
    - Injected `TestOnlyUnsandboxedBoundary(ws_path)`.
12. `tests/workers/test_worker_harness.py::test_patch_agent_worker_traversal_and_fail_closed`
    - Injected `TestOnlyUnsandboxedBoundary(ws_path)`.
13. `tests/interfaces/test_mcp_server.py::test_mcp_server_dispatch_validate_patch_clean`
    - Injected `TestOnlyUnsandboxedBoundary(ws_dir)`.
14. `tests/interfaces/test_mcp_server.py::test_mcp_server_dispatch_validate_patch_syntax_error`
    - Injected `TestOnlyUnsandboxedBoundary(ws_dir)`.
15. `tests/e2e/test_golden_vertical_slice.py::test_golden_vertical_slice_end_to_end`
    - Injected `TestOnlyUnsandboxedBoundary(tmp_path)`.
16. `tests/e2e/test_golden_vertical_slice.py::test_golden_vertical_slice_arbitrary_component`
    - Injected `TestOnlyUnsandboxedBoundary(tmp_path)`.
17. `tests/security/test_boundary_hardening.py::test_production_boundary_reaches_trust_root_check_permission_error`
    - Evaluates D1: real LinuxExecutionBoundary reaches trust-root check and raises PermissionError (not AttributeError).
18. `tests/security/test_boundary_hardening.py::test_attestor_built_with_production_token_ephemeral_key_rejected_at_preflight`
    - Evaluates D2 (a) / E1 (d): registers ephemeral key first, asserts exact PermissionError on both registration and preflight.
19. `tests/security/test_boundary_hardening.py::test_constructing_attestor_leaves_key_directory_unchanged`
    - Evaluates D2 (b): constructing an attestor leaves the key directory unchanged.
20. `tests/security/test_boundary_hardening.py::test_no_constructor_route_accepted_when_pinned_roots_exclude_it`
    - Evaluates D2 (c): no constructor route yields an attestor accepted when pinned roots exclude it.
21. `tests/security/test_boundary_hardening.py::test_is_provisioned_guard_meaningful_and_active`
    - Evaluates D3: proves is_provisioned is meaningful and actively guards attest().
22. `tests/security/test_boundary_hardening.py::test_scenario_a_ephemeral_key_under_pinned_root_rejected`
    - Evaluates E1 (a): scenario A rejected (unpinned key under pinned root rejected by register and preflight).
23. `tests/security/test_boundary_hardening.py::test_scenario_b_env_source_without_explicit_pins_rejected`
    - Evaluates E1 (b): scenario B rejected (env variables without explicit constructor pin fail closed).
24. `tests/security/test_boundary_hardening.py::test_sclass_pinned_trust_roots_env_has_zero_effect`
    - Evaluates E1 (c): setting SCLASS_PINNED_TRUST_ROOTS has zero effect.
25. `tests/security/test_boundary_hardening.py::test_worker_without_boundary_fails_closed_and_spawns_no_process`
    - Evaluates E2: PatchAgentWorker/SubprocessToolWorker without boundary raises and sentinel proves no process spawned.
26. `tests/security/test_boundary_hardening.py::test_boundary_permission_error_trigger_strings_propagate_fail_closed_no_process`
    - Evaluates E2: PermissionError containing trigger strings propagates with no process spawned.

---

## 4. Unverified Items

- bwrap/cgroup never executed
- mutation result unreproduced
