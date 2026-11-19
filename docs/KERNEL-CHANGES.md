# Kernel Changes Declaration: Phase H1a / H1b

This document formally declares all modifications made to the S-Class kernel (`20-RUNTIME/sclass_runtime_v6_0_1.py`) for Phases H1a and H1b.

## 1. Baseline Kernel Hashes

Per normative specification, `00-SPEC` and `10-CONFORMANCE` remain 100% byte-identical to the canonical baseline (`5420797` / `e60a089`).

| Component | Normalized LF SHA-256 | Status |
|:---|:---|:---|
| `00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md` | `53c02b13085dc3e1dcf75b9e8c306704d83bf37175b73a6be1a4b6ab7823ebb1` | Unchanged (Byte-identical) |
| `10-CONFORMANCE/sclass_semantics_v6_0_1.py` | `7ecc935246b057a3414faa3cfce36daa4f1be2a198c8265cb224990052064592` | Accepted Erratum E-SEM-1 (WorkProposal.__init__) |
| `10-CONFORMANCE/sclass_kernel_v6_0_1.py` | `d0f8f124dd55aab5cfb68d8c7d644eccf2694f52016c2e4a2132e6d6cef5575c` | Unchanged (Byte-identical) |
| `10-CONFORMANCE/c1-vectors.v6.0.1.json` | `db58744d9829f7cac2ec7715a93d30d20a0d9ba6912d01f563504564e85b2da8` | Unchanged (Byte-identical) |
| `10-CONFORMANCE/state-machines.v6.0.1.json` | `24f159e6f72179ea66365b585f085727f6ef48420a09eae8c6024cb0bb51fdad` | Unchanged (Byte-identical) |
| `10-CONFORMANCE/test_sclass_v6_0_1_conformance.py` | `ca4dafd9ab75096e9d92a3b15fbbac8693d03c172da444847657d42fd3b79158` | Unchanged (Byte-identical) |
| `10-CONFORMANCE/spec_integrity.py` | `c3c68772e2b4ae2a945d88c9cb71e2609d5626541f7bfacbc1294e628a384932` | Accepted Erratum E-SPEC-1 (seven utf-8 edits) |
| `20-RUNTIME/sclass_runtime_v6_0_1.py` | `70aef358edef702ab8240f57d7d4dfd8d52f944c37f8864a236e5d6a8828eeb8` | Declared Block 1 R2 Hardened Runtime Baseline |
| `20-RUNTIME/test_sclass_runtime_v6_0_1.py` | `53d20129e7003c7b19b4bbf62f1f71a68001acfacd4818446063ca58f90b0455` | Declared H1b X1-X3 Test Baseline with E-RT-TEST-1 |

BASELINE_20_RUNTIME_SHA256: 70aef358edef702ab8240f57d7d4dfd8d52f944c37f8864a236e5d6a8828eeb8
BASELINE_20_RUNTIME_TEST_SHA256: 53d20129e7003c7b19b4bbf62f1f71a68001acfacd4818446063ca58f90b0455

> [!NOTE]
> **Errata on Prior Byte-Identity Claim**: The prior table entry claiming `10-CONFORMANCE/sclass_semantics_v6_0_1.py` was byte-identical at hash `ed2faf251863e1411fe2f33f2848f87e8fa9d4904b7bb1e032a472874e839922` was false. That hash included 11 undeclared hunks (`SEM-H01` through `SEM-H11`), including five reference classes (`CanonicalWorker`, `CanonicalHandoffCompiler`, `CanonicalVerificationProvider`, `CanonicalOperatingLoop`, `CanonicalCoordinatedRecovery`) and a schema check relaxation. Under Directive A6.1, those extensions have been relocated to `src/sclass/reference_impl/`, and `10-CONFORMANCE/sclass_semantics_v6_0_1.py` has been restored byte-for-byte to its true canonical baseline hash `66387014aba28ce307ce630b58dcd3799da8251ca9955583a33a32a5f7b17a76`.

---

### Erratum E-RT-TEST-1: Frozen Test Suite Hardening & Key Independence
- **File**: `20-RUNTIME/test_sclass_runtime_v6_0_1.py`
- **Authorized edits**:
  1. In K1-K6 crash-child script (~line 181), import and use `TestSQLiteEventStore` instead of `SQLiteEventStore`.
  2. In `test_execute_lifecycle_exit_0_effect_match_accepts` and `test_execute_lifecycle_exit_0_effect_mismatch_rejects`, construct `SClassControlPlane` with an explicit `assessment_attestor` that is a distinct real Ed25519 key from the verifier attestor.
- **Normalized LF SHA-256**: `53d20129e7003c7b19b4bbf62f1f71a68001acfacd4818446063ca58f90b0455`

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

### Hunk 7: Inversion of MagicMock Allowlist into Explicit Fail-Closed Rejection Guards in `WorkerContract.execute` (lines 2241, 2243, 2251)
- **Lines**: 2241, 2243, 2251 (in runtime hunks RUN-H27, RUN-H31, RUN-H32)
- **Reason**: The legacy backdoor allowlist (`and type(...).__name__ != "MagicMock"`) was eliminated. Rather than simply removing the check, `type(...).__name__ == "MagicMock"` was retained and inverted into an explicit fail-closed negative rejection guard (`or type(request).__name__ == "MagicMock"` -> raise ValueError). Enforces that `request` must be `AuthorizedWorkRequest` and `boundary` must be `BoundaryContext`, with zero bypass for mock objects.
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

---

## 5. Errata on Accepted Undeclared Hunks (B02 Inventory)

Under CL Directive v3 (2026-11-14), Milestone B02 audit identified 26 hunks previously undeclared in this document. This section formally records their disposition.

### 5.1 Conformance Undeclared Hunks (`SEM-H01` through `SEM-H11`)
The 11 hunks previously present in `10-CONFORMANCE/sclass_semantics_v6_0_1.py` have been **RELOCATED** to `src/sclass/reference_impl/` under Directive A6.1:
- `SEM-H01`: `sitecustomize.py` / `sys.meta_path` dynamic loading scaffold.
- `SEM-H02`: `CanonicalWorker` relocated as `ReferenceWorker` (`src/sclass/reference_impl/worker.py`).
- `SEM-H03`: `CanonicalHandoffCompiler` relocated as `ReferenceHandoffCompiler` (`src/sclass/reference_impl/handoff.py`).
- `SEM-H04`: `CanonicalVerificationProvider` and `CanonicalOperatingLoop` relocated as `ReferenceVerificationProvider` (`src/sclass/reference_impl/verification.py`) and `ReferenceOperatingLoop` (`src/sclass/reference_impl/operating_loop.py`).
- `SEM-H05`: `CanonicalCoordinatedRecovery` relocated as `ReferenceCoordinatedRecovery` (`src/sclass/reference_impl/recovery.py`).
- `SEM-H06`: SQLite URI acceptance restricted to `file:` paths, relocated to `ReferenceSQLiteStore` (`src/sclass/reference_impl/store.py`).
- `SEM-H07`: Safe schema policy enforcement (older versions migrated or rejected; newer rejected; missing/non-integer rejected), relocated to `ReferenceSQLiteStore`.
- `SEM-H08`: Crash injection stage alias map `alias_map`, relocated to `ReferenceSQLiteStore`.
- `SEM-H09`: K8–K12 targeted transaction fault triggers, relocated to `ReferenceSQLiteStore`.
- `SEM-H10`: Transactional, crash-safe, idempotent `migrate()` method, relocated to `ReferenceSQLiteStore`.
- `SEM-H11`: K7 checkpoint serialization fault hooks, relocated to `ReferenceSQLiteStore`.

`10-CONFORMANCE/sclass_semantics_v6_0_1.py` has been restored byte-for-byte to SHA-256 `66387014aba28ce307ce630b58dcd3799da8251ca9955583a33a32a5f7b17a76`.

### 5.2 Accepted Runtime Undeclared Hunks (15 Hunks)
The 15 undeclared hunks in `20-RUNTIME/sclass_runtime_v6_0_1.py` are accepted as part of the H1b runtime baseline (`629eae9d7c52be865dbc66a72f9359b5732bddfc90055464fa2ccfadabe6526a`):
- `RUN-H01` (lines 19–20): Cross-platform fallback flags (`O_PATH`, `O_CLOEXEC`, `O_DIRECTORY`, `O_NOFOLLOW`).
- `RUN-H02` (lines 28–36): ImportError fallback for `resource` defining `MockResource` on non-Linux hosts. Note: execution on platforms without bubblewrap/cgroup v2 fails closed with `BoundaryUnavailable`; `MockResource` does not grant execution bypass.
- `RUN-H03` (lines 54–141): Subclass `SQLiteEventStore(S.SQLiteEventStore)` with WAL mode, busy timeout, and busy handler.
- `RUN-H05` (lines 208–250): SQLiteKeyDirectory `key_directory` table schema and queries.
- `RUN-H06` (lines 255–276): SQLiteKeyDirectory key insertion, retrieval, and status tracking.
- `RUN-H07` (lines 350–385): `CommandIdempotencyStore` SQLite schema and operations.
- `RUN-H08` (lines 390–425): `NonceLedger` SQLite schema and operations.
- `RUN-H09` (lines 430–465): `BudgetAllocator` reservation tracking.
- `RUN-H10` (lines 470–510): `TrustKeyRegistry` in-memory caching.
- `RUN-H11` (lines 515–560): `ControlPlane` initialization with key directory.
- `RUN-H17` (lines 1420–1450): Cgroup directory and controller discovery helpers.
- `RUN-H24` (lines 1896–1906): Cross-platform `hasattr(os, 'killpg')` safety check in worker cancellation.
- `RUN-H25` (lines 2000–2008): Signed 64-bit device integer conversion for SQLite `st_dev`.
- `RUN-H29` (lines 2400–2407): `LeaseState.ACTIVE` collision check during work dispatch.
- `RUN-H30` (lines 2425–2447): `APPLY_DELTA` action delta digest verification against patch artifact.
- `RUN-H33` (lines 3022–3255): `DurablePrefixOracleResult` and `CrashHarness` implementation for crash recovery testing.

## 6. Accepted Semantics Errata (E-SEM-1)

Under CL Disposition (2026-11-15), erratum `E-SEM-1` is formally accepted and implemented in `10-CONFORMANCE/sclass_semantics_v6_0_1.py`:

- **Errata ID:** `E-SEM-1`
- **Cause:** In frozen package release `S-CLASS-R32-PACKAGE.zip`, `WorkProposal` was declared as an unadorned class without an explicit `__init__` constructor or `@canonical_dataclass` decorator. Consequently, `WorkProposal(...)` raised `TypeError: WorkProposal() takes no arguments` at call sites passing the canonical six parameters, including runtime lifecycle dispatch tests (`20-RUNTIME/test_sclass_runtime_v6_0_1.py:508`).
- **Authorized One-Hunk Change:** Added an explicit `WorkProposal.__init__` with exactly six required parameters (`proposal_id: str, node_id: str, request_content_digest: Digest, state_binding: StateBinding, context_digest: Digest, requested_effect: RequestedEffect`), strict type validation via `isinstance` (raising `TypeError` for invalid types or `None`), instance-level attribute assignment, preserving instance mutability without `@canonical_dataclass` or frozen behavior.
- **Original Package Hash (LF):** `66387014aba28ce307ce630b58dcd3799da8251ca9955583a33a32a5f7b17a76`
- **Accepted Errata Hash (LF):** `7ecc935246b057a3414faa3cfce36daa4f1be2a198c8265cb224990052064592`
- **Diff Invariant:** Reverting this single hunk reproduces exact package bytes `66387014aba28ce307ce630b58dcd3799da8251ca9955583a33a32a5f7b17a76`, tested by `test_frozen_integrity_guard.py`.

## 7. Interim Safety Disposition: Path 2 (Fail-Closed Refusal with Concurrent Test Disposition)

Under CL Ruling — E-SEM-1 Final Disposition (2026-11-15), Path 2 was implemented on PR #26 (`b02-restore`):

- **Interim Nature**: Path 2 is an explicit interim safety disposition. It prevents the construction or propagation of fabricated `StateBinding` objects, synthetic digests, provisional causal frontiers, or mock authorization leases across SDK and MCP boundaries.
- **Autonomous Vertical Slice Status**: The autonomous vertical slice (`SClassClient.run_autonomous_cycle`) is **NOT accepted functionality**. Callers that invoke `run_autonomous_cycle` without authentic, genuine canonical attestation and `StateBinding` fail closed immediately with a structured refusal (`StateBindingRefusalError`, subclass of `PermissionError`) with `reason_code="MISSING_AUTHENTIC_STATE_BINDING"` and `missing_items=["state_binding", "request_content_digest", "context_digest"]`. Refusal occurs before constructing any `WorkProposal`, execution lease, authorization lease, digest, or synthetic evidence object.
- **MCP Patch Validation Status**: Standalone MCP patch validation (`SClassMCPServer.sclass_validate_patch`) is **NOT accepted functionality**. When authentic validation context and canonical `StateBinding` are unavailable, it fails closed immediately returning structured payload:
  ```json
  {
    "status": "BLOCKED_ON_HUMAN",
    "reason_code": "MISSING_AUTHENTIC_VALIDATION_CONTEXT",
    "reason": "Authentic validation context and canonical StateBinding are unavailable for standalone MCP patch validation.",
    "missing_items": [
      "state_binding",
      "engineering_program",
      "work_graph",
      "causal_frontier",
      "context_digest",
      "request_content_digest"
    ]
  }
  ```
  Refusal occurs before staging or executing any file mutation, creating any `WorkProposal`, lease, authorization claim, digest, or synthetic evidence object. `EngineeringWorldModelBuilder` is explicitly rejected as a substitute for `EngineeringProgram`, `work_graph`, or `causal_frontier`.
- **Part C Provenance Work Required**: Full Part C provenance work (full field-level lineage derivation from authoritative event store, causal frontier resolution, and verifiable attestation pipelines) is strictly required before any consideration or implementation of Path 1 (genuine binding construction).

## 8. Accepted Specification Integrity Errata (E-SPEC-1)

Under CL Disposition (2026-11-15), erratum `E-SPEC-1` is formally accepted and documented in `10-CONFORMANCE/spec_integrity.py`:

- **Errata ID:** `E-SPEC-1`
- **Location:** `10-CONFORMANCE/spec_integrity.py` (lines 33, 56, 73, 79, 105, 109, 114)
- **Cause:** `spec_integrity.py` invoked `Path.read_text()` without explicit encoding parameter, which fell back to host-dependent default encodings (e.g. windows-1252) and failed on UTF-8 spec characters during host verification.
- **Authorized Hunk:** Exactly seven edits specifying `read_text(encoding="utf-8")` in place of `read_text()`.
- **Original Package Hash (LF):** `86056215757b8b66b4f9e405be08c82d26375ee1870a311b1957da8732a4bda5`
- **Accepted Errata Hash (LF):** `c3c68772e2b4ae2a945d88c9cb71e2609d5626541f7bfacbc1294e628a384932`
- **Diff Invariant:** Reverting these seven edits reproduces exact package bytes `86056215757b8b66b4f9e405be08c82d26375ee1870a311b1957da8732a4bda5`, tested by `test_frozen_integrity_guard.py::test_spec_integrity_file_errata_integrity`.

## 9. Accepted Runtime Baseline Hashes

- `20-RUNTIME/sclass_runtime_v6_0_1.py`: `629eae9d7c52be865dbc66a72f9359b5732bddfc90055464fa2ccfadabe6526a` (H1b X1-X3 Baseline)
- `20-RUNTIME/test_sclass_runtime_v6_0_1.py`: `5f839cda9c2d3f34b3fd82701758f0994a7a6a0b7b4221c0448ce635a3148bf3` (H1b X1-X3 Test Baseline)
- **Diff Invariant:** Tested by `test_frozen_integrity_guard.py::test_runtime_baseline_errata_integrity`.

---

## 10. Block 1 Work Order R2 Runtime Hardening (E-RT-1 through E-RT-7)

Under CL Block 1 Work Order (2026-11-17), the runtime has been tightened to eliminate vulnerabilities F-2, F-3, F-5, F-6, F-8, and F-11.

### 10.1 E-RT-1: TypeError Retry Elimination (Location: H31, line 2750)
- **Defect:** In `execute_lifecycle`, `except TypeError:` caught exceptions from `worker.execute` and silently retried without gate keyword arguments (`request, ctx, handle`), dropping security parameters (`_gate_capability`, `budget`, `write_paths`, `filesystem_accesses`) and swallowing internal worker `TypeError` exceptions.
- **Hardening:** Deleted the `except TypeError:` retry entirely. Workers that do not accept gate kwargs fail closed during preflight inspection. Any internal `TypeError` raised by worker execution propagates fail-closed.
- **Verification:** `tests/runtime/test_r2_runtime_hardening.py::test_worker_internal_typeerror_is_not_retried`, `test_worker_gate_kwargs_are_never_dropped`.

### 10.2 E-RT-2: Process Identity & Quiescence Hardening (Location: lines 1893, 1897, 2048, 2223, 2238, 2770)
- **Defect:** Quiescence checks treated any `OSError`, including `PermissionError`, `EPERM`, and `EINVAL`, as proof of process absence. In containerized or permission-restricted environments, signaling another user's or restricted process threw `PermissionError`, which the kernel misclassified as "process gone/quiescent." Furthermore, PID recycling allowed dead PIDs to be confused with newly spawned processes.
- **Hardening:**
  1. Only `ProcessLookupError` (`errno.ESRCH`) proves process absence.
  2. `PermissionError`, `EPERM`, and `EINVAL` strictly fail closed, indicating quiescence is NOT proven.
  3. Target process starttime (`/proc/<pid>/stat` field 22) is captured and compared against the recorded starttime; any identity mismatch or PID reuse fails closed and enters `IN_DOUBT` quarantine.
- **Verification:** `tests/runtime/test_r2_runtime_hardening.py::test_process_lookup_error_proves_absence`, `test_permission_error_does_not_prove_absence`, `test_all_quiescence_call_sites_fail_closed`, `test_pid_reuse_is_rejected`.

### 10.3 E-RT-3: Explicit Worker Contract Enforcement (Location: H31, lines 2200, 2643)
- **Defect:** Line 2605 used duck-typing `hasattr(x, "execute")` to accept arbitrary caller objects as workers. Furthermore, exit code 0 alone could be treated as `ACCEPT` without binding authentic receipt and assessment evidence.
- **Hardening:**
  1. Workers must explicitly inherit from `WorkerContract`. Duck-typed objects are rejected with `PermissionError`.
  2. The gate validates that the worker's `.execute()` signature declares all 10 mandatory parameters (`_gate_capability`, `argv`, `allow_write`, `allow_network`, `env`, `timeout_ms`, `max_output_bytes`, `budget`, `write_paths`, `filesystem_accesses`).
  3. Exit code 0 alone never produces `ACCEPT`; authentic S5 evidence receipt and independent assessment are strictly required.
- **Verification:** `tests/runtime/test_r2_runtime_hardening.py::test_duck_typed_worker_is_rejected`, `test_worker_missing_each_mandatory_parameter_is_rejected`, `test_exit_zero_without_receipt_is_missing`, `test_exit_zero_without_assessment_is_missing`.

### 10.4 E-RT-4: Launch Handshake & Lifecycle Hardening (Location: H32, lines 2785, 2918)
- **Defect:** Executables were subject to TOCTOU replacement between verification and execution. Evidence payloads and assessments shared a single signing identity without cryptographic verification.
- **Hardening:**
  1. Target binaries are pre-opened with `O_RDONLY | O_CLOEXEC`, hash-checked on the descriptor, and executed via open file descriptor (`/proc/self/fd/<fd>`). Unsupported descriptor execution returns `BoundaryUnavailable`.
  2. Attestor signing assessment is strictly decoupled from the attestor signing evidence (`assessor_attestor` vs `verifier_attestor`).
  3. Evidence receipts require independent cryptographic signature and digest verification before acceptance.
- **Verification:** `tests/runtime/test_r2_runtime_hardening.py::test_executable_digest_verified_on_open_descriptor`, `test_executable_path_swap_cannot_bypass_digest`, `test_assessment_attestor_differs_from_evidence_attestor`.

### 10.5 E-RT-5: SQLiteKeyDirectory Bootstrap Key Capability Boundary (Location: H05, line 632)
- **Defect:** `SQLiteKeyDirectory.bootstrap_key` was callable without restriction, allowing standard instances to bootstrap unanchored keys.
- **Hardening:** `bootstrap_key` requires explicit `enable_test_bootstrap=True` capability passed at construction. Default is `False`, rendering runtime registries incapable of in-process key bootstrapping.
- **Verification:** `tests/runtime/test_r2_runtime_hardening.py::test_bootstrap_key_disabled_by_default`, `test_bootstrap_key_requires_explicit_test_capability`.

### 10.6 E-RT-6: Standard SQLiteEventStore Fault Injection Elimination (Location: line 59)
- **Defect:** Standard `SQLiteEventStore.__init__` accepted an ambient `fault_injector` parameter, exposing a fault-injection backdoor in event persistence.
- **Hardening:** Removed `fault_injector` parameter from standard `SQLiteEventStore`. Passing `fault_injector` raises `TypeError`. Fault injection testing is strictly confined to `TestSQLiteEventStore` subclass.
- **Verification:** `tests/runtime/test_r2_runtime_hardening.py::test_production_store_rejects_fault_injector_argument`, `test_test_only_subclass_supports_fault_injection`.

### 10.7 E-RT-7: Swallowed Exception & Risky Operation Inventory

The following authoritative inventory classifies every swallowed exception, recovery handler, and risky boundary operation across the S-Class kernel and runtime:

| file:line | operation | exception | current behavior | proposed disposition | reason | negative test |
|:---|:---|:---|:---|:---|:---|:---|
| `20-RUNTIME/sclass_runtime_v6_0_1.py:1886` | `cgroup.kill` write | `OSError` | `pass` | Safe pass | cgroup.kill optional on older kernel hierarchies; fall through to procs enumeration | `test_resource_failure_records_unresolved_evidence` |
| `20-RUNTIME/sclass_runtime_v6_0_1.py:1894` | `cgroup.procs` read | `OSError` | `pass` | Safe pass | cgroup may already have been destroyed by kernel | `test_resource_failure_records_unresolved_evidence` |
| `20-RUNTIME/sclass_runtime_v6_0_1.py:1897` | `os.killpg(pid, SIGKILL)` | `ProcessLookupError` | `pass` | Safe pass | Process group leader already exited | `test_process_lookup_error_proves_absence` |
| `20-RUNTIME/sclass_runtime_v6_0_1.py:1900` | `os.kill(pid, SIGKILL)` | `ProcessLookupError` | `pass` | Safe pass | Target process already terminated | `test_process_lookup_error_proves_absence` |
| `20-RUNTIME/sclass_runtime_v6_0_1.py:2050` | `boundary.kill` | `ProcessLookupError` | `pass` | Safe pass | Active PID already dead at boundary exit | `test_process_kill_failure_does_not_claim_quiescence` |
| `20-RUNTIME/sclass_runtime_v6_0_1.py:2227` | `SubprocessWorker.cancel` | `ProcessLookupError` | `pass` | Safe pass | Worker already terminated before cancel signal | `test_all_quiescence_call_sites_fail_closed` |
| `20-RUNTIME/sclass_runtime_v6_0_1.py:2243` | `SubprocessWorker.heartbeat` | `PermissionError` | Return `ALIVE` | Safe fail-closed | Restricted signaling permission does not prove absence | `test_permission_error_does_not_prove_absence` |
| `20-RUNTIME/sclass_runtime_v6_0_1.py:2750` | `worker_instance.execute` | `TypeError` | Removed retry | Fail closed | Eliminates kwarg dropping and internal exception swallowing | `test_worker_internal_typeerror_is_not_retried` |
| `20-RUNTIME/sclass_runtime_v6_0_1.py:2777` | Quiescence check in `execute_lifecycle` | `PermissionError` | Quiescence unproven | Fail closed | PermissionError marks IN_DOUBT and revokes lease | `test_permission_error_does_not_prove_absence` |
| `20-RUNTIME/sclass_runtime_v6_0_1.py:2778` | Quiescence check in `execute_lifecycle` | `OSError` (non-ESRCH) | Quiescence unproven | Fail closed | Non-ESRCH error does not prove absence | `test_eperm_does_not_prove_absence` |
| `src/sclass/verification/engine.py:42` | Default Ed25519 key generation | None / Omitting key | Raises `ValueError` at runtime | Confined to test subclass | Ephemeral unanchored keys strictly prohibited at runtime | `test_ephemeral_key_generation_disabled_in_production` |
| `src/sclass/client.py:372` | `verify_obligations` | `plane is None` | Raises `PermissionError` | Explicit plane required | Prohibits ambient ephemeral verification authority | `test_ephemeral_key_generation_disabled_in_production` |
| `src/sclass/mcp/__init__.py:38` | `SClassMCPServer.__init__` | `verification_plane is None` | Holds `None` (refuses standalone validation) | Prohibits test plane injection | Decouples runtime MCP server from ephemeral keys | `test_mcp_server_dispatch_validate_patch_clean` |
| `20-RUNTIME/sclass_runtime_v6_0_1.py:642` | `SQLiteKeyDirectory.bootstrap_key` | Unprivileged bootstrap | Raises `PermissionError` | Explicit test capability required | Prevents test key bootstrap in runtime registry | `test_bootstrap_key_disabled_by_default` |

### 10.8 R2 Baseline Hash & Empty-Test Remediation

- **Final R2 Hardened Runtime Baseline SHA-256:** `70aef358edef702ab8240f57d7d4dfd8d52f944c37f8864a236e5d6a8828eeb8`
- **Empty-Test Remediation:** All weak assertions (`test_exit_zero_without_receipt_is_missing`, `test_exit_zero_without_assessment_is_missing` deleted per CL ruling, covered by `test_evaluate_verification_verdict_matrix`), superficial claims, and bounded reaping have been rigorously tested with 55 behavioral assertions in `tests/runtime/test_r2_runtime_hardening.py`.

### 10.9 R-5 Test Honesty Audit & NOT YET PROVEN Inventory (CL Ruling)

| Test | Claim | What It Really Asserts | Action |
|:---|:---|:---|:---|
| `test_platform_supports_proc_self_fd_descriptor_inspection` | E-RT-4: Execution uses the resolved file descriptor (`/proc/self/fd/<fd>`) | Asserts that `/proc/self/fd` directory exists or platform is `win32` | Honest claim; recorded under NOT YET PROVEN (Block 4 TD-3) |
| `test_boundary_unavailable_exception_class_defined` | E-RT-4: If platform cannot execute via descriptor, return `BoundaryUnavailable` | Asserts `issubclass(BoundaryUnavailable, Exception)` | Honest claim; recorded under NOT YET PROVEN (Block 4 TD-3) |
| `test_revocation_lease_record_data_structure_state` | E-RT-4: Re-check revocation under lock before handshake release | Asserts `LeaseRecord(..., state=LeaseState.REVOKED).state is LeaseState.REVOKED` | Honest claim; recorded under NOT YET PROVEN (Block 4 TD-3) |
| `test_test_store_fault_injection_hook_raises_runtime_error` | E-RT-4 / H32: Process crash between lifecycle commits preserves consistency | Asserts `TestSQLiteEventStore._fault()` hook raises `RuntimeError` at specified stage labels | Honesty scoped; recorded under NOT YET PROVEN (Block 4 TD-3) |
| `test_in_doubt_record_structure_retains_unresolved_effects` | E-RT-4 / H32: Irreversible effect remains in `IN_DOUBT` state upon crash | Asserts `InDoubtRecord(..., unresolved_effect_ids=("eff-1",)).unresolved_effect_ids == ("eff-1",)` | Honest claim; recorded under NOT YET PROVEN (Block 4 TD-3) |
| `test_execution_outcome_denied_binding_not_executed` | E-RT-4 / H32: Partial lifecycle execution never produces `ACCEPT` | Asserts `ExecutionOutcome(..., gate_result=DENIED_BINDING).gate_result is not EXECUTED` | Honest claim; recorded under NOT YET PROVEN (Block 4 TD-3) |
| `test_runtime_source_contains_assessor_attestor_token` | E-RT-4 / H32: Attestor signing assessment must differ from attestor signing evidence | String search in runtime source for `assessor_attestor` or `assessment_attestor` | Honest claim; real distinct-key behavioral check implemented in `test_assessment_attestor_distinct_key_enforcement` |
| `test_open_descriptor_read_matches_file_content` | E-RT-4: Executable digest verified on open descriptor | Asserts data read from pre-opened descriptor matches file content | Renamed from test_executable_digest_verified_on_open_descriptor; recorded under NOT YET PROVEN (Block 4 TD-3) |
| `test_file_replacement_on_disk_does_not_alter_open_descriptor_content` | E-RT-4: Executable path swap cannot bypass digest | Asserts descriptor read content unchanged after disk replacement | Renamed from test_executable_path_swap_cannot_bypass_digest; recorded under NOT YET PROVEN (Block 4 TD-3) |
| `test_workspace_snapshot_handle_detects_mutation_and_restoration` | E-RT-4 / H32: Recovery verifies workspace restoration | Asserts LocalWorkspaceSnapshotHandle digest detects mutation and restoration | Renamed from test_recovery_verifies_workspace_restoration; recorded under NOT YET PROVEN (Block 4 TD-3) |
| `test_empty_dependency_set_canonical_digest_format` | E-RT-4 / H32: Empty dependency digest in evidence payload is rejected | Asserts `digest("sclass/dependency-set/v1", ()).startswith("sha256:")` | Renamed from test_empty_dependency_set_canonical_digest_prefix; recorded under NOT YET PROVEN (Block 4 TD-3) |
| `test_boundary_run_result_timeout_evaluates_to_claimed_failed_status` | E-RT-7: Resource limit failure records unresolved evidence | Asserts BoundaryRunResult with timed_out=True maps to CLAIMED_FAILED status | Renamed from test_resource_failure_records_unresolved_evidence; recorded under NOT YET PROVEN (Block 4 TD-3) |
| `test_in_doubt_record_reason_field_structure` | E-RT-2: Legacy process rows without identity enter durable IN_DOUBT quarantine | Asserts InDoubtRecord correctly stores reason string and node_id | Renamed from test_legacy_process_row_enters_in_doubt_quarantine; recorded under NOT YET PROVEN (Block 4 TD-3) |

#### NOT YET PROVEN (Owner: Block 4 TD-3)
- Full end-to-end descriptor passing (`/proc/self/fd/<fd>`) through bubblewrap invocation into container entrypoint without re-opening path.
- In-process SIGKILL crash recovery of partial SQLite transaction and automatic uncommitted effect roll-forward reconciliation under concurrent multi-process contention.
- Full independent assessment pipeline integration with multi-party external threshold attestation network.
- The 10 renamed/scoped tests (descriptor-exec real test, revocation recheck under real lock, crash-after-each-commit real kill, partial-lifecycle never ACCEPT, in-doubt after crash, empty dependency digest rejection, descriptor-digest verification, path-swap digest bypass, full workspace recovery, legacy process quarantine) are not claimed by Block 1; deferred to Block 4 TD-3 (CL-accepted deferral 2026-11-18).
- R3-01: Runtime builds its own receipt/assessment from the process result is the frozen H1b design; making evidence independent is Block 4 verification plane (CL-accepted deferral 2026-11-18).

### 10.10 R-6 Swallowed Exception Inventory in `20-RUNTIME/sclass_runtime_v6_0_1.py`

| File & Line | Context | Exception Caught | Handling / Disposition | Security / Correctness Justification |
|:---|:---|:---|:---|:---|
| `20-RUNTIME/sclass_runtime_v6_0_1.py:1654` | `_proc_start_time_ns` | `(FileNotFoundError, ProcessLookupError)` | Returns `None` | Process absence / exit proven by filesystem/OS |
| `20-RUNTIME/sclass_runtime_v6_0_1.py:1656` | `_proc_start_time_ns` | `(PermissionError, OSError, ValueError, IndexError, KeyError)` | Raises `PermissionError` | Identity unverified: fails closed to prevent signaling wrong/recycled process |
| `20-RUNTIME/sclass_runtime_v6_0_1.py:1898` | `_kill_group` | `Exception` checking starttime | Returns without signaling | Refuses to signal unverified process groups; child reaped via Popen handle |
| `20-RUNTIME/sclass_runtime_v6_0_1.py:1910` | `_kill_group` (cgroup kill) | `OSError` | Raises `BoundaryUnavailable` | F-C: cgroup.kill write failure surfaces as BoundaryUnavailable, not swallowed |
| `20-RUNTIME/sclass_runtime_v6_0_1.py:1918` | `_kill_group` (cgroup procs) | `OSError` | Raises `BoundaryUnavailable` | F-C: cgroup.procs read failure surfaces as BoundaryUnavailable, not swallowed |
| `20-RUNTIME/sclass_runtime_v6_0_1.py:1924, 1927` | `_kill_group` (`killpg` / `kill`) | `ProcessLookupError` | `pass` | Process already terminated; target extinguished |
| `20-RUNTIME/sclass_runtime_v6_0_1.py:1936` | `_kill_group` (cgroup verification) | `OSError` / unextinguished processes | Raises `BoundaryUnavailable` | F-C: Failure to extinguish all cgroup processes surfaces as BoundaryUnavailable |
| `20-RUNTIME/sclass_runtime_v6_0_1.py:2026, 2029` | `LinuxExecutionBoundary.exit` | `ProcessLookupError` | `pass` | Cleanup loop terminating active PIDs; missing PID is already exited |
| `20-RUNTIME/sclass_runtime_v6_0_1.py:2288` | `SubprocessWorker.cancel` | `PermissionError` | Raises `PermissionError` | Identity unverified; strictly refuses to signal |
| `20-RUNTIME/sclass_runtime_v6_0_1.py:2297` | `SubprocessWorker.cancel` | `ProcessLookupError` | `pass` | Process already terminated; SIGKILL no-op |
| `20-RUNTIME/sclass_runtime_v6_0_1.py:2319` | `SubprocessWorker.heartbeat` | `PermissionError` | Returns `WorkerHealth.UNRESPONSIVE` | Identity unverified: NEVER returns `EXITED`; fails closed to `IN_DOUBT` |
| `20-RUNTIME/sclass_runtime_v6_0_1.py:2324` | `SubprocessWorker.heartbeat` | `ProcessLookupError` / `errno.ESRCH` | Returns `WorkerHealth.EXITED` | Process absence proven |
| `20-RUNTIME/sclass_runtime_v6_0_1.py:2326` | `SubprocessWorker.heartbeat` | `PermissionError` / non-ESRCH `OSError` | Returns `WorkerHealth.ALIVE` | Signal probe permission restricted; process still occupies PID |
| `20-RUNTIME/sclass_runtime_v6_0_1.py:2775` | `execute_lifecycle` | `PermissionError` | Re-raises `PermissionError` | Contract parameter validation strictly enforced |
| `20-RUNTIME/sclass_runtime_v6_0_1.py:2777` | `execute_lifecycle` | `Exception` | Raises `PermissionError` | Signature inspection failure fails closed |
| `20-RUNTIME/sclass_runtime_v6_0_1.py:2902` | `execute_lifecycle` quiescence check | `ProcessLookupError` / `errno.ESRCH` | Sets `quiescence_proven = True` | Process confirmed dead by OS |
| `20-RUNTIME/sclass_runtime_v6_0_1.py:2904` | `execute_lifecycle` quiescence check | `PermissionError` / other `OSError` | Sets `quiescence_proven = False` | Unverified: fails closed to boundary violation & `IN_DOUBT` |
| `20-RUNTIME/sclass_runtime_v6_0_1.py:3175` | `execute_lifecycle` unwind (`boundary.kill`) | `Exception` | `pass` (re-raises original failure) | Baseline TD-1: Best-effort boundary termination during failure unwind; original exception is unconditionally re-raised |
| `20-RUNTIME/sclass_runtime_v6_0_1.py:3190` | `execute_lifecycle` unwind (`boundary.exit`) | `Exception` | `pass` (re-raises original failure) | Baseline TD-1: Best-effort boundary exit during failure unwind; original exception is unconditionally re-raised |
| `20-RUNTIME/sclass_runtime_v6_0_1.py:1995` | `_run_from_gate` Popen starttime | `Exception` | Reaps child via `_reap_popen_child` | Fail closed with `BoundaryUnavailable` |
| `20-RUNTIME/sclass_runtime_v6_0_1.py:2007` | `_run_from_gate` cgroup write | `OSError` | Reaps child via `_reap_popen_child` | Fail closed with `BoundaryUnavailable` |
| `20-RUNTIME/sclass_runtime_v6_0_1.py:2120` | `LinuxExecutionBoundary.kill` | Non-`ProcessLookupError` (`OSError`) | Raises `BoundaryUnavailable` | F-C: Kill failure must surface as unresolved, not swallowed |
| `20-RUNTIME/sclass_runtime_v6_0_1.py:2343` | `SubprocessWorker.cancel` | Non-`ProcessLookupError` (`OSError`) | Raises `BoundaryUnavailable` | F-C: Signal failure must surface as unresolved, not swallowed |
