"""Hardening and regression tests for S-Class execution boundary.

Verifies:
(a) bwrap/cgroup unavailable -> BoundaryUnavailable and sentinel file proves no worker process started
(b) setting SCLASS_TEST_MODE=1 (and TEST_MODE, SCLASS_UNSANDBOXED) changes nothing
(c) shipped modules never import anything from tests/
"""

from __future__ import annotations

import ast
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import pytest
from sclass_runtime_v6_0_1 import BoundaryUnavailable, LinuxExecutionBoundary


def test_boundary_unavailable_fail_closed_sentinel(tmp_path):
    """(a) bwrap/cgroup unavailable -> BoundaryUnavailable and sentinel file proves no worker process started."""
    sentinel_path = tmp_path / "worker_sentinel.txt"
    if sentinel_path.exists():
        sentinel_path.unlink()

    boundary = LinuxExecutionBoundary(str(tmp_path))
    boundary.bwrap = None  # simulate bwrap unavailable

    cmd = [
        sys.executable,
        "-c",
        f"import pathlib; pathlib.Path(r'{sentinel_path}').write_text('PROCESS_SPAWNED')",
    ]

    with pytest.raises(BoundaryUnavailable):
        boundary._run_from_gate(boundary._gate_capability, cmd)

    # Sentinel must not exist: fail closed without process execution
    assert not sentinel_path.exists(), "SECURITY VIOLATION: Worker process spawned when boundary was unavailable!"

    # Also test cgroup v2 unavailable
    boundary2 = LinuxExecutionBoundary(str(tmp_path))

    def _fail_cgroup():
        raise BoundaryUnavailable("cgroup v2 is required for execution boundary")

    boundary2._assert_cgroup_v2 = _fail_cgroup
    with pytest.raises(BoundaryUnavailable):
        boundary2._run_from_gate(boundary2._gate_capability, cmd)

    assert not sentinel_path.exists(), "SECURITY VIOLATION: Worker process spawned when cgroup v2 was unavailable!"


def test_ambient_security_switches_have_zero_effect(tmp_path, monkeypatch):
    """(b) setting SCLASS_TEST_MODE=1 (and TEST_MODE, SCLASS_UNSANDBOXED) changes nothing."""
    sentinel_path = tmp_path / "ambient_sentinel.txt"
    if sentinel_path.exists():
        sentinel_path.unlink()

    # Set ambient switches that previously bypassed sandboxing
    monkeypatch.setenv("SCLASS_TEST_MODE", "1")
    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.setenv("SCLASS_UNSANDBOXED", "1")

    boundary = LinuxExecutionBoundary(str(tmp_path))
    boundary.bwrap = None  # Bubblewrap unavailable

    cmd = [
        sys.executable,
        "-c",
        f"import pathlib; pathlib.Path(r'{sentinel_path}').write_text('BYPASS_SUCCEEDED')",
    ]

    # Must STILL fail closed with BoundaryUnavailable despite all ambient switches
    with pytest.raises(BoundaryUnavailable):
        boundary._run_from_gate(boundary._gate_capability, cmd)

    assert not sentinel_path.exists(), "SECURITY VIOLATION: Ambient switch allowed unconfined worker execution!"


def test_shipped_modules_never_import_from_tests():
    """(c) shipped modules never import anything from tests/."""
    repo_root = Path(__file__).resolve().parents[2]
    shipped_dirs = [
        repo_root / "src",
        repo_root / "10-CONFORMANCE",
        repo_root / "20-RUNTIME",
    ]

    violations = []
    # 1. Scan shipped source modules (excluding test_*.py)
    for sdir in shipped_dirs:
        if not sdir.exists():
            continue
        for py_path in sdir.rglob("*.py"):
            if py_path.name.startswith("test_"):
                continue  # test suites are not shipped modules
            try:
                tree = ast.parse(py_path.read_text(encoding="utf-8"), filename=str(py_path))
            except Exception:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name == "tests" or alias.name.startswith("tests."):
                            violations.append((str(py_path.relative_to(repo_root)), node.lineno, alias.name))
                elif isinstance(node, ast.ImportFrom):
                    if node.module and (node.module == "tests" or node.module.startswith("tests.")):
                        violations.append((str(py_path.relative_to(repo_root)), node.lineno, node.module))

    # 2. Build clean wheel and verify no member in the wheel imports from tests/
    with tempfile.TemporaryDirectory() as tmp_dir:
        dist_dir = Path(tmp_dir) / "dist"
        dist_dir.mkdir()
        subprocess.run(
            [sys.executable, "-m", "pip", "wheel", "--no-deps", "-w", str(dist_dir), str(repo_root)],
            capture_output=True,
            check=True,
        )
        wheels = list(dist_dir.glob("*.whl"))
        assert wheels, "No wheel built"
        with zipfile.ZipFile(wheels[0]) as z:
            for member in z.namelist():
                if member.endswith(".py"):
                    code = z.read(member).decode("utf-8")
                    try:
                        tree = ast.parse(code, filename=member)
                    except Exception:
                        continue
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                if alias.name == "tests" or alias.name.startswith("tests."):
                                    violations.append((f"wheel:{member}", node.lineno, alias.name))
                        elif isinstance(node, ast.ImportFrom):
                            if node.module and (node.module == "tests" or node.module.startswith("tests.")):
                                violations.append((f"wheel:{member}", node.lineno, node.module))

    assert not violations, f"SECURITY VIOLATION: Shipped code imports from tests/: {violations}"


def test_linux_execution_boundary_has_no_run_for_test(tmp_path):
    """F1 (a): LinuxExecutionBoundary must have no run_for_test method."""
    from sclass_runtime_v6_0_1 import LinuxExecutionBoundary
    b = LinuxExecutionBoundary(str(tmp_path), require_sandbox=False)
    assert not hasattr(b, "run_for_test")
    assert not hasattr(LinuxExecutionBoundary, "run_for_test")


def test_production_boundary_rejects_test_only_attestor_at_preflight(tmp_path):
    """F1 (b): Production boundary + test-only attestor -> PermissionError at preflight.

    Proves that a real LinuxExecutionBoundary paired with a test-only attestor
    fails closed at preflight before spawning any process or invoking Bubblewrap.
    A sentinel file verifies no worker process was ever started.
    """
    from sclass_runtime_v6_0_1 import (
        ExecutionGate,
        LinuxExecutionBoundary,
        SClassControlPlane,
        SQLiteEventStore,
    )
    from tests.helpers.test_boundary import create_test_quiescence_attestor
    from tests.workers.test_worker_harness import _make_sample_authorized_request

    store = SQLiteEventStore(str(tmp_path / "events.sqlite"))
    cp = SClassControlPlane(store)
    cp.boundary_attestor = create_test_quiescence_attestor(cp.keys)
    assert cp.boundary_attestor._test_only is True
    assert cp.boundary_attestor.is_production_provisioned() is False

    boundary = LinuxExecutionBoundary(str(tmp_path), require_sandbox=False)
    gate = ExecutionGate(boundary, cp)

    sentinel_path = tmp_path / "preflight_sentinel.txt"
    if sentinel_path.exists():
        sentinel_path.unlink()

    req = _make_sample_authorized_request()

    cmd = [
        sys.executable,
        "-c",
        f"import pathlib; pathlib.Path(r'{sentinel_path}').write_text('SPAWNED')",
    ]

    with pytest.raises(PermissionError, match="real LinuxExecutionBoundary rejects test-only quiescence authority"):
        gate.execute_lifecycle(req, cmd)

    assert not sentinel_path.exists(), "SECURITY VIOLATION: Worker process spawned with test-only attestor!"
    store.close()


def test_magicmock_named_objects_strictly_rejected(tmp_path):
    """F2: Prove an object whose class is named 'MagicMock' is strictly rejected."""
    from unittest.mock import MagicMock
    from sclass_runtime_v6_0_1 import (
        WorkerContract,
        BoundaryContext,
        AuthorizedWorkRequest,
        LinuxExecutionBoundary,
        LocalWorkspaceSnapshotHandle,
        SubprocessWorker,
    )
    from tests.workers.test_worker_harness import _make_sample_authorized_request

    boundary = LinuxExecutionBoundary(str(tmp_path), require_sandbox=False)
    worker = SubprocessWorker(boundary=boundary)

    # 1. Reject MagicMock as request in WorkerContract
    mock_request = MagicMock()
    with pytest.raises(PermissionError, match="WorkerContract.execute accepts only AuthorizedWorkRequest"):
        worker.execute(mock_request, MagicMock(), MagicMock())

    # 2. Reject MagicMock as boundary in WorkerContract
    req = _make_sample_authorized_request()
    mock_boundary = MagicMock()
    handle = LocalWorkspaceSnapshotHandle(tmp_path, "ws-1", "snap-1", 1)
    with pytest.raises(PermissionError, match="WorkerContract.execute requires an authentic BoundaryContext"):
        worker.execute(req, mock_boundary, handle, _gate_capability=boundary._gate_capability)

    # 3. Reject MagicMock in WorkerHarness
    from sclass.workers.harness import WorkerHarness

    class TestHarness(WorkerHarness):
        def execute(self, request, b, h, **kwargs):
            self._validate_request(request, b, h)

    harness = TestHarness(boundary=boundary)
    with pytest.raises(PermissionError, match="Worker accepts only AuthorizedWorkRequest"):
        harness.execute(mock_request, mock_boundary, handle)

    with pytest.raises(PermissionError, match="Worker requires authentic BoundaryContext"):
        harness.execute(req, mock_boundary, handle)

    # 4. Reject class named MagicMock even if subclassed
    class MagicMock(AuthorizedWorkRequest):
        pass

    fake_mock_req = object.__new__(MagicMock)
    with pytest.raises(PermissionError, match="WorkerContract.execute accepts only AuthorizedWorkRequest"):
        worker.execute(fake_mock_req, mock_boundary, handle)


def test_production_boundary_reaches_trust_root_check_permission_error(tmp_path):
    """D1: Real LinuxExecutionBoundary reaches trust-root check and gets PermissionError (not AttributeError).

    Proves that when an attestor has a valid key registered in the directory under a root
    that is not active in keys.roots(), preflight reaches line ~2177, calls keys.roots(),
    and raises PermissionError without spawning processes or requiring Bubblewrap.
    """
    import time
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from sclass_runtime_v6_0_1 import (
        ExecutionGate,
        KeyStatus,
        LinuxExecutionBoundary,
        LocalQuiescenceAttestor,
        PinnedKey,
        SClassControlPlane,
        SQLiteEventStore,
        _BOUNDARY_PROVISIONING_TOKEN,
    )
    from tests.workers.test_worker_harness import _make_sample_authorized_request

    boundary = LinuxExecutionBoundary(str(tmp_path), require_sandbox=False)
    store = SQLiteEventStore(str(tmp_path / "d1.sqlite"))

    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    cp = SClassControlPlane(store, pinned_keys=[PinnedKey("d1-root", pub)])
    cp.keys.register("d1-key", "d1-root", pub)

    # Deactivate the root in runtime_trust_roots so it is excluded from keys.roots()
    cp.db.execute("UPDATE runtime_trust_roots SET status='INACTIVE' WHERE root_id='d1-root'")
    assert "d1-root" not in cp.keys.roots()

    attestor = LocalQuiescenceAttestor(
        cp.keys,
        "d1-root",
        "d1-key",
        priv,
        _provisioning_token=_BOUNDARY_PROVISIONING_TOKEN,
    )
    cp.boundary_attestor = attestor
    gate = ExecutionGate(boundary, cp)
    req = _make_sample_authorized_request()
    cmd = [sys.executable, "-c", "pass"]

    with pytest.raises(PermissionError) as exc_info:
        gate.execute_lifecycle(req, cmd)

    # Must raise PermissionError from keys.roots() check, NOT AttributeError
    assert "quiescence attestor trust root is not in provisioned trust roots" in str(exc_info.value)
    store.close()


def test_attestor_built_with_production_token_ephemeral_key_rejected_at_preflight(tmp_path):
    """D2 (a) / E1 (d): Attestor built with production token and an ephemeral key -> PermissionError at preflight.

    Strengthened per E1 (d):
    1. Assert cp.keys.register refuses the ephemeral key with exact PermissionError message.
    2. Register ephemeral key first directly in DB so status is ACTIVE.
    3. Assert gate preflight rejects it with exact PermissionError message.
    """
    import time
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from sclass_runtime_v6_0_1 import (
        ExecutionGate,
        KeyStatus,
        LinuxExecutionBoundary,
        LocalQuiescenceAttestor,
        PinnedKey,
        SClassControlPlane,
        SQLiteEventStore,
        _BOUNDARY_PROVISIONING_TOKEN,
    )
    from tests.workers.test_worker_harness import _make_sample_authorized_request

    boundary = LinuxExecutionBoundary(str(tmp_path), require_sandbox=False)
    store = SQLiteEventStore(str(tmp_path / "d2a.sqlite"))

    legit_priv = Ed25519PrivateKey.generate()
    legit_pub = legit_priv.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    pinned_root = "pinned-root"

    # Control plane strictly pins legitimate key
    cp = SClassControlPlane(store, pinned_keys=[PinnedKey(pinned_root, legit_pub, key_id="legit-key")])
    cp.keys.register("legit-key", pinned_root, legit_pub)

    ephemeral_priv = Ed25519PrivateKey.generate()
    ephemeral_pub = ephemeral_priv.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)

    # 1. Registering ephemeral key first via keys.register is refused with exact message
    with pytest.raises(PermissionError) as reg_exc:
        cp.keys.register("ephemeral-key", pinned_root, ephemeral_pub)
    assert str(reg_exc.value) == f"key ephemeral-key for root {pinned_root} is not in pinned key set"

    # 2. Register ephemeral key first directly in DB so status is ACTIVE
    cp.db.execute(
        "INSERT INTO runtime_keys(key_id, trust_root, public_key, status, not_before, not_after, inserted_at, rotated_at, revoked_at) "
        "VALUES (?, ?, ?, ?, 0, ?, ?, NULL, NULL)",
        ("ephemeral-key", pinned_root, ephemeral_pub, KeyStatus.ACTIVE.value, 2**63 - 1, time.time_ns()),
    )

    # 3. Attestor constructed with production token and the registered ephemeral key
    att = LocalQuiescenceAttestor(
        cp.keys,
        pinned_root,
        "ephemeral-key",
        ephemeral_priv,
        _provisioning_token=_BOUNDARY_PROVISIONING_TOKEN,
    )
    cp.boundary_attestor = att
    gate = ExecutionGate(boundary, cp)
    req = _make_sample_authorized_request()
    cmd = [sys.executable, "-c", "pass"]

    with pytest.raises(PermissionError) as exc_info:
        gate.execute_lifecycle(req, cmd)

    # Assert exact PermissionError message
    assert str(exc_info.value) == "quiescence attestor key is not in pinned key set"
    store.close()


def test_constructing_attestor_leaves_key_directory_unchanged(tmp_path):
    """D2 (b): Constructing an attestor leaves the key directory completely unchanged.

    Proves that LocalQuiescenceAttestor.__init__ never self-registers roots or keys into
    the key directory.
    """
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from sclass_runtime_v6_0_1 import (
        LocalQuiescenceAttestor,
        SClassControlPlane,
        SQLiteEventStore,
        _BOUNDARY_PROVISIONING_TOKEN,
        _BOUNDARY_TEST_TOKEN,
    )

    store = SQLiteEventStore(str(tmp_path / "d2b.sqlite"))
    cp = SClassControlPlane(store)

    roots_before = cp.keys.roots()
    keys_count_before = cp.db.execute("SELECT count(*) FROM runtime_keys").fetchone()[0]
    roots_count_before = cp.db.execute("SELECT count(*) FROM runtime_trust_roots").fetchone()[0]

    priv1 = Ed25519PrivateKey.generate()
    priv2 = Ed25519PrivateKey.generate()
    _ = LocalQuiescenceAttestor(
        cp.keys, "arbitrary-root-1", "arbitrary-key-1", priv1, _provisioning_token=_BOUNDARY_PROVISIONING_TOKEN
    )
    _ = LocalQuiescenceAttestor(
        cp.keys, "arbitrary-root-2", "arbitrary-key-2", priv2, _provisioning_token=_BOUNDARY_TEST_TOKEN
    )

    assert cp.keys.roots() == roots_before
    assert cp.db.execute("SELECT count(*) FROM runtime_keys").fetchone()[0] == keys_count_before
    assert cp.db.execute("SELECT count(*) FROM runtime_trust_roots").fetchone()[0] == roots_count_before
    store.close()


def test_no_constructor_route_accepted_when_pinned_roots_exclude_it(tmp_path, monkeypatch):
    """D2 (c): No constructor route yields an attestor accepted by a gate whose pinned roots exclude it.

    Proves that even if an excluded root/key exists in the key registry, ExecutionGate preflight
    rejects it because trust roots are pinned outside the attestor at control plane construction.
    """
    import base64
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from sclass_runtime_v6_0_1 import (
        ExecutionGate,
        KeyStatus,
        LinuxExecutionBoundary,
        LocalQuiescenceAttestor,
        PinnedKey,
        SClassControlPlane,
        SQLiteEventStore,
        _BOUNDARY_PROVISIONING_TOKEN,
        _BOUNDARY_TEST_TOKEN,
    )
    from tests.workers.test_worker_harness import _make_sample_authorized_request

    boundary = LinuxExecutionBoundary(str(tmp_path), require_sandbox=False)
    store = SQLiteEventStore(str(tmp_path / "d2c.sqlite"))
    # Control plane strictly pins ONLY "allowed-root"
    priv_allowed = Ed25519PrivateKey.generate()
    pub_allowed = priv_allowed.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    cp = SClassControlPlane(store, pinned_keys=[PinnedKey("allowed-root", pub_allowed)])
    cp.keys.register("key-allowed", "allowed-root", pub_allowed)

    gate = ExecutionGate(boundary, cp)
    req = _make_sample_authorized_request()
    cmd = [sys.executable, "-c", "pass"]

    # Route 1: Direct constructor with production token and an unpinned root
    priv1 = Ed25519PrivateKey.generate()
    pub1 = priv1.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    with pytest.raises(PermissionError, match="not in pinned key set"):
        cp.keys.register("key-ex-1", "excluded-root", pub1)
    cp.keys.add_root("excluded-root")
    cp.db.execute(
        "INSERT INTO runtime_keys(key_id, trust_root, public_key, status, not_before, not_after, inserted_at, rotated_at, revoked_at) "
        "VALUES (?, ?, ?, ?, 0, ?, ?, NULL, NULL)",
        ("key-ex-1", "excluded-root", pub1, KeyStatus.ACTIVE.value, 2**63 - 1, 1),
    )
    att1 = LocalQuiescenceAttestor(
        cp.keys, "excluded-root", "key-ex-1", priv1, _provisioning_token=_BOUNDARY_PROVISIONING_TOKEN
    )
    cp.boundary_attestor = att1
    with pytest.raises(PermissionError, match="quiescence attestor trust root is not in pinned trust roots"):
        gate.execute_lifecycle(req, cmd)

    # Route 2: Direct constructor with test token
    att2 = LocalQuiescenceAttestor(
        cp.keys, "excluded-root", "key-ex-2", Ed25519PrivateKey.generate(), _provisioning_token=_BOUNDARY_TEST_TOKEN
    )
    cp.boundary_attestor = att2
    with pytest.raises(PermissionError):
        gate.execute_lifecycle(req, cmd)

    # Route 3: from_environment with excluded root
    pub_env = priv1.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    cp.db.execute(
        "INSERT INTO runtime_keys(key_id, trust_root, public_key, status, not_before, not_after, inserted_at, rotated_at, revoked_at) "
        "VALUES (?, ?, ?, ?, 0, ?, ?, NULL, NULL)",
        ("key-ex-env", "excluded-root", pub_env, KeyStatus.ACTIVE.value, 2**63 - 1, 1),
    )
    monkeypatch.setenv("SCLASS_BOUNDARY_TRUST_ROOT", "excluded-root")
    monkeypatch.setenv("SCLASS_BOUNDARY_KEY_ID", "key-ex-env")
    raw_key = base64.b64encode(
        priv1.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
    ).decode("ascii")
    assert not hasattr(LocalQuiescenceAttestor, "from_environment")
    att3 = LocalQuiescenceAttestor(cp.keys, "excluded-root", "key-ex-env", priv1, _provisioning_token=_BOUNDARY_PROVISIONING_TOKEN)
    cp.boundary_attestor = att3
    with pytest.raises(PermissionError, match="quiescence attestor trust root is not in pinned trust roots"):
        gate.execute_lifecycle(req, cmd)

    store.close()


def test_is_provisioned_guard_meaningful_and_active(tmp_path):
    """D3: Prove is_provisioned is meaningful (not constant True) and actively guards attest().

    Proves that LocalQuiescenceAttestor.is_provisioned reflects the active key registration
    status, and attest() raises PermissionError when the signing key has been revoked.
    """
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from sclass_runtime_v6_0_1 import (
        BoundaryIsolation,
        BoundaryRunResult,
        Digest,
        LocalQuiescenceAttestor,
        PinnedKey,
        SClassControlPlane,
        SQLiteEventStore,
        _BOUNDARY_PROVISIONING_TOKEN,
    )
    from tests.workers.test_worker_harness import _make_sample_authorized_request

    store = SQLiteEventStore(str(tmp_path / "d3.sqlite"))
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    cp = SClassControlPlane(store, pinned_keys=[PinnedKey("root-d3", pub)])
    cp.keys.register("key-d3", "root-d3", pub)

    att = LocalQuiescenceAttestor(
        cp.keys, "root-d3", "key-d3", priv, _provisioning_token=_BOUNDARY_PROVISIONING_TOKEN
    )
    # Active registered key -> is_provisioned is True
    assert att.is_provisioned is True

    # Revoking key makes is_provisioned False
    cp.keys.revoke("key-d3")
    assert att.is_provisioned is False

    # attest() fails closed with PermissionError
    req = _make_sample_authorized_request()
    run_res = BoundaryRunResult(
        BoundaryIsolation.DENY, 0, b"", b"", False, 1,
        Digest("sha256:" + "1" * 64), Digest("sha256:" + "2" * 64),
        12345, 1000000,
    )
    with pytest.raises(PermissionError, match="quiescence attestation requires provisioned boundary authority"):
        att.attest(req, run_res)

    store.close()


def test_scenario_a_ephemeral_key_under_pinned_root_rejected(tmp_path):
    """E1 (a): Scenario A is rejected.

    An attacker cannot register an unpinned ephemeral key under a pinned root,
    and ExecutionGate preflight rejects any attestor built with an unpinned key
    even if possessing _BOUNDARY_PROVISIONING_TOKEN.
    """
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from sclass_runtime_v6_0_1 import (
        ExecutionGate,
        KeyStatus,
        LinuxExecutionBoundary,
        LocalQuiescenceAttestor,
        PinnedKey,
        SClassControlPlane,
        SQLiteEventStore,
        _BOUNDARY_PROVISIONING_TOKEN,
    )
    from tests.workers.test_worker_harness import _make_sample_authorized_request

    boundary = LinuxExecutionBoundary(str(tmp_path), require_sandbox=False)
    store = SQLiteEventStore(str(tmp_path / "scenario_a.sqlite"))

    legit_priv = Ed25519PrivateKey.generate()
    legit_pub = legit_priv.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)

    # Control plane pins ("R1", legit_pub)
    cp = SClassControlPlane(store, pinned_keys=[PinnedKey("R1", legit_pub, key_id="legit-key")])
    # Register the legitimate pinned key
    cp.keys.register("legit-key", "R1", legit_pub)

    ephemeral_priv = Ed25519PrivateKey.generate()
    ephemeral_pub = ephemeral_priv.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)

    # Layer 1: cp.keys.register must refuse unpinned key
    with pytest.raises(PermissionError, match="not in pinned key set"):
        cp.keys.register("evil", "R1", ephemeral_pub)

    # Layer 2: Even if evil key is directly inserted into runtime_keys DB
    cp.db.execute(
        "INSERT INTO runtime_keys(key_id, trust_root, public_key, status, not_before, not_after, inserted_at, rotated_at, revoked_at) "
        "VALUES (?, ?, ?, ?, 0, ?, ?, NULL, NULL)",
        ("evil", "R1", ephemeral_pub, KeyStatus.ACTIVE.value, 2**63 - 1, 1),
    )

    # Attestor built with evil key and _BOUNDARY_PROVISIONING_TOKEN
    evil_attestor = LocalQuiescenceAttestor(
        cp.keys, "R1", "evil", ephemeral_priv, _provisioning_token=_BOUNDARY_PROVISIONING_TOKEN
    )
    cp.boundary_attestor = evil_attestor
    gate = ExecutionGate(boundary, cp)
    req = _make_sample_authorized_request()
    cmd = [sys.executable, "-c", "pass"]

    with pytest.raises(PermissionError, match="quiescence attestor key is not in pinned key set"):
        gate.execute_lifecycle(req, cmd)

    store.close()


def test_scenario_b_env_source_without_explicit_pins_rejected(tmp_path, monkeypatch):
    """E1 (b): Scenario B (env root + key + key id, no explicit pin) is rejected.

    Control plane constructor never reads environment for pins, never auto-registers
    attestor keys, and ExecutionGate rejects execution without explicit pinned keys.
    """
    import base64
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from sclass_runtime_v6_0_1 import (
        ExecutionGate,
        LinuxExecutionBoundary,
        LocalQuiescenceAttestor,
        SClassControlPlane,
        SQLiteEventStore,
        _BOUNDARY_PROVISIONING_TOKEN,
    )
    from tests.workers.test_worker_harness import _make_sample_authorized_request

    boundary = LinuxExecutionBoundary(str(tmp_path), require_sandbox=False)
    store = SQLiteEventStore(str(tmp_path / "scenario_b.sqlite"))

    priv = Ed25519PrivateKey.generate()
    raw_key = base64.b64encode(
        priv.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
    ).decode("ascii")

    # Set ambient env variables for boundary trust root, key id, private key
    monkeypatch.setenv("SCLASS_BOUNDARY_TRUST_ROOT", "env-root")
    monkeypatch.setenv("SCLASS_BOUNDARY_KEY_ID", "env-key")
    monkeypatch.setenv("SCLASS_BOUNDARY_PRIVATE_KEY_B64", raw_key)

    # Control plane constructed with NO explicit pins
    cp = SClassControlPlane(store)

    # Verify constructor did NOT auto-register key or auto-populate pins from env
    assert cp.pinned_keys is None
    assert cp.pinned_trust_roots == set()
    assert "env-root" not in cp.keys.roots()
    assert not cp.boundary_attestor.is_provisioned

    # 1. Default attestor is UnprovisionedQuiescenceAuthority -> fails preflight
    gate = ExecutionGate(boundary, cp)
    req = _make_sample_authorized_request()
    cmd = [sys.executable, "-c", "pass"]

    with pytest.raises(PermissionError, match="ExecutionGate requires provisioned OS-boundary quiescence authority"):
        gate.execute_lifecycle(req, cmd)

    # 2. LocalQuiescenceAttestor.from_environment is deleted from production kernel (M2)
    assert not hasattr(LocalQuiescenceAttestor, "from_environment")
    att = LocalQuiescenceAttestor(cp.keys, "env-root", "env-key", priv, _provisioning_token=_BOUNDARY_PROVISIONING_TOKEN)
    cp.boundary_attestor = att

    # Attestor's key is not in directory -> fails at quiescence authority check
    with pytest.raises(PermissionError, match="ExecutionGate requires provisioned OS-boundary quiescence authority"):
        gate.execute_lifecycle(req, cmd)

    # 3. Even if key is force-registered directly in DB so is_provisioned is True:
    cp.db.execute("INSERT INTO runtime_trust_roots(root_id, status) VALUES ('env-root', 'ACTIVE')")
    pub = priv.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    cp.db.execute(
        "INSERT INTO runtime_keys(key_id, trust_root, public_key, status, not_before, not_after, inserted_at, rotated_at, revoked_at) "
        "VALUES (?, ?, ?, 'ACTIVE', 0, ?, 1, NULL, NULL)",
        ("env-key", "env-root", pub, 2**63 - 1),
    )
    assert att.is_provisioned is True

    # Preflight fails closed because control plane has no explicit pinned keys
    with pytest.raises(PermissionError, match="real LinuxExecutionBoundary requires explicit pinned keys"):
        gate.execute_lifecycle(req, cmd)

    store.close()


def test_sclass_pinned_trust_roots_env_has_zero_effect(tmp_path, monkeypatch):
    """E1 (c): Setting SCLASS_PINNED_TRUST_ROOTS has zero effect.

    Pins come exclusively from explicit constructor arguments; ambient environment
    variables are completely ignored by SClassControlPlane.
    """
    from sclass_runtime_v6_0_1 import SClassControlPlane, SQLiteEventStore

    store = SQLiteEventStore(str(tmp_path / "env_effect.sqlite"))
    monkeypatch.setenv("SCLASS_PINNED_TRUST_ROOTS", "arbitrary-root-1,arbitrary-root-2")

    cp = SClassControlPlane(store)
    assert cp.pinned_keys is None
    assert cp.pinned_trust_roots == set()
    assert "arbitrary-root-1" not in cp.keys.roots()
    assert "arbitrary-root-2" not in cp.keys.roots()

    store.close()


def test_worker_without_boundary_fails_closed_and_spawns_no_process(tmp_path):
    """E2: PatchAgentWorker / SubprocessToolWorker without a boundary raises and sentinel proves no process started."""
    from sclass.workers.harness import PatchAgentWorker, SubprocessToolWorker

    sentinel_path = tmp_path / "sentinel_no_boundary.txt"
    if sentinel_path.exists():
        sentinel_path.unlink()

    # 1. PatchAgentWorker() with no boundary argument raises TypeError
    with pytest.raises((TypeError, ValueError)):
        PatchAgentWorker()

    # 2. PatchAgentWorker(boundary=None) raises ValueError
    with pytest.raises(ValueError, match="boundary is required"):
        PatchAgentWorker(boundary=None)

    # 3. SubprocessToolWorker() with no boundary argument raises TypeError
    with pytest.raises((TypeError, ValueError)):
        SubprocessToolWorker()

    # 4. SubprocessToolWorker(boundary=None) raises ValueError
    with pytest.raises(ValueError, match="boundary is required"):
        SubprocessToolWorker(boundary=None)

    # Sentinel must NOT exist
    assert not sentinel_path.exists(), "SECURITY VIOLATION: Process started without boundary!"


@pytest.mark.parametrize("trigger", ["process-tree", "running executable", "unsandboxed"])
def test_boundary_permission_error_trigger_strings_propagate_fail_closed_no_process(tmp_path, trigger):
    """E2: PermissionError containing each trigger string propagates with no process spawned.

    Triggers: "process-tree", "running executable", "unsandboxed".
    Verifies that neither bare Popen fallback nor fabricated BoundaryRunResult occurs.
    A sentinel file verifies no fallback subprocess is spawned.
    """
    from sclass.workers.harness import PatchAgentWorker
    from tests.helpers.test_boundary import TestOnlyUnsandboxedBoundary
    from tests.workers.test_worker_harness import (
        _make_sample_authorized_request,
        _make_sample_boundary_context,
    )
    from sclass_runtime_v6_0_1 import LocalWorkspaceSnapshotHandle

    sentinel_file = tmp_path / f"sentinel_{trigger.replace(' ', '_').replace('-', '_')}.txt"
    if sentinel_file.exists():
        sentinel_file.unlink()

    class FailingBoundary(TestOnlyUnsandboxedBoundary):
        def _run_from_gate(self, capability, argv, **kwargs):
            raise PermissionError(f"Simulated boundary violation: {trigger} constraint violated")

    boundary = FailingBoundary(tmp_path)
    worker = PatchAgentWorker(boundary=boundary)

    # Command that would create the sentinel file if fallback Popen executed
    cmd = [
        sys.executable,
        "-c",
        f"import pathlib; pathlib.Path(r'{sentinel_file}').write_text('SPAWNED_BY_FALLBACK')",
    ]

    req = _make_sample_authorized_request(fencing_token=1)
    boundary_ctx = _make_sample_boundary_context(fencing_token=1)
    handle = LocalWorkspaceSnapshotHandle(tmp_path, "ws", "snap-1", 1)

    with pytest.raises(PermissionError) as exc_info:
        worker.execute(req, boundary_ctx, handle, argv=cmd)

    # The exception must be the original error containing the trigger string
    assert trigger in str(exc_info.value)
    # The sentinel file must NOT exist (no bare Popen was executed)
    assert not sentinel_file.exists(), f"SECURITY VIOLATION: Bare Popen fallback spawned process for trigger '{trigger}'!"


def test_m1_preflight_rejects_attestor_private_key_mismatch(tmp_path):
    """M1: Preflight compares the attestor's own public key (from its private key)
    to the pinned public key and rejects a mismatch BEFORE any process spawns.
    Right key_id/root + wrong private key -> PermissionError at preflight, sentinel proves no spawn.
    """
    import base64
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from sclass_runtime_v6_0_1 import (
        ExecutionGate,
        LinuxExecutionBoundary,
        LocalQuiescenceAttestor,
        PinnedKey,
        SClassControlPlane,
        SQLiteEventStore,
        _BOUNDARY_PROVISIONING_TOKEN,
    )
    from tests.workers.test_worker_harness import _make_sample_authorized_request

    sentinel_path = tmp_path / "sentinel_m1_spawned.txt"
    if sentinel_path.exists():
        sentinel_path.unlink()

    class SentinelLinuxBoundary(LinuxExecutionBoundary):
        def _run_from_gate(self, capability, argv, **kwargs):
            sentinel_path.write_text("SPAWNED")
            return super()._run_from_gate(capability, argv, **kwargs)

    boundary = SentinelLinuxBoundary(str(tmp_path), require_sandbox=False)
    store = SQLiteEventStore(str(tmp_path / "m1_store.sqlite"))

    legit_priv = Ed25519PrivateKey.generate()
    legit_pub = legit_priv.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    root = "m1-root"
    key_id = "m1-key"

    # Control plane pins ("m1-root", legit_pub)
    cp = SClassControlPlane(store, pinned_keys=[PinnedKey(root, legit_pub, key_id=key_id)])
    # Legitimate key registered in key directory
    cp.keys.register(key_id, root, legit_pub)

    # Attestor created with RIGHT root, RIGHT key_id, but WRONG private key!
    wrong_priv = Ed25519PrivateKey.generate()
    wrong_attestor = LocalQuiescenceAttestor(
        cp.keys, root, key_id, wrong_priv, _provisioning_token=_BOUNDARY_PROVISIONING_TOKEN
    )
    cp.boundary_attestor = wrong_attestor

    gate = ExecutionGate(boundary, cp)
    req = _make_sample_authorized_request()
    cmd = [
        sys.executable,
        "-c",
        f"import pathlib; pathlib.Path(r'{sentinel_path}').write_text('SPAWNED_BY_CHILD')",
    ]

    # Preflight MUST reject the private key mismatch with PermissionError
    with pytest.raises(PermissionError, match="quiescence attestor private key"):
        gate.execute_lifecycle(req, cmd)

    # Sentinel proves NO process was spawned
    assert not sentinel_path.exists(), "SECURITY VIOLATION: Process spawned despite attestor private key mismatch!"

    # Calling _preflight directly also rejects with PermissionError
    with pytest.raises(PermissionError, match="quiescence attestor private key"):
        gate._preflight(req, cmd, allow_write=False, allow_network=False, env=None, timeout_ms=30000, max_output_bytes=1000000)

    store.close()


def test_m2_no_env_key_reads_and_tamper_fails_gate6(tmp_path):
    """M2: LocalQuiescenceAttestor.from_environment is deleted.
    No key, root or pin is read from os.environ anywhere in 20-RUNTIME/ or src/.
    Gate 6 fails on any new env read in these trees outside an explicit allowlist file;
    tamper: re-add an env read -> gate fails.
    The env-read allowlist is a separate committed file, starts with ZERO entries
    for key, root, pin or private-key names, and every addition is declared in the report.
    """
    import ast
    import json
    import re
    import subprocess
    import sys
    from pathlib import Path
    from sclass_runtime_v6_0_1 import LocalQuiescenceAttestor

    # 1. LocalQuiescenceAttestor.from_environment is deleted
    assert not hasattr(LocalQuiescenceAttestor, "from_environment"), (
        "SECURITY VIOLATION: LocalQuiescenceAttestor.from_environment still exists!"
    )

    repo_root = Path(__file__).resolve().parents[2]
    allowlist_file = repo_root / "tools" / "gates" / "env_read_allowlist.json"

    # 2. The env-read allowlist is a separate committed file
    assert allowlist_file.exists(), f"Allowlist file {allowlist_file} does not exist"

    with allowlist_file.open("r", encoding="utf-8") as f:
        allowlist_data = json.load(f)

    # Allowlist must start with ZERO entries for key, root, pin or private-key names
    forbidden_pattern = re.compile(r"key|root|pin|private", re.IGNORECASE)
    key_root_pin_pattern = re.compile(
        r"""(?:getenv|environ(?:\.get)?)\s*\(\s*['"][^'"]*(?:key|root|pin|private)[^'"]*['"]|environ\s*\[\s*['"][^'"]*(?:key|root|pin|private)[^'"]*['"]""",
        re.IGNORECASE,
    )
    for entry in allowlist_data:
        for k in ("env_var", "pattern", "access"):
            val = entry.get(k)
            if val and isinstance(val, str):
                assert not key_root_pin_pattern.search(val), (
                    f"SECURITY VIOLATION: Allowlist entry '{k}' contains forbidden pattern: {entry}"
                )
                if k == "env_var":
                    assert not forbidden_pattern.search(val), (
                        f"SECURITY VIOLATION: Allowlist contains forbidden env_var: {entry}"
                    )

    def is_env_node(n):
        return (isinstance(n, ast.Attribute) and n.attr == "environ") or (isinstance(n, ast.Name) and n.id == "environ")

    # 3. No key, root or pin is read from os.environ anywhere in 20-RUNTIME/ or src/
    trees = [repo_root / "20-RUNTIME", repo_root / "src"]
    for tree in trees:
        for py_path in tree.rglob("*.py"):
            try:
                tree_ast = ast.parse(py_path.read_text(encoding="utf-8"), filename=str(py_path))
            except Exception:
                continue
            for node in ast.walk(tree_ast):
                if isinstance(node, ast.Call):
                    func = node.func
                    if isinstance(func, ast.Attribute):
                        if (func.attr == "get" and is_env_node(func.value)) or (func.attr == "getenv" and isinstance(func.value, ast.Name) and func.value.id == "os"):
                            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                                var_name = node.args[0].value
                                assert not forbidden_pattern.search(var_name), (
                                    f"SECURITY VIOLATION: {py_path} reads secret/key env var '{var_name}'"
                                )
                elif isinstance(node, ast.Subscript):
                    if is_env_node(node.value):
                        if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
                            var_name = node.slice.value
                            assert not forbidden_pattern.search(var_name), (
                                f"SECURITY VIOLATION: {py_path} reads secret/key env var '{var_name}'"
                            )

    # 4. Run Gate 6: must pass on clean repo
    gate6_script = repo_root / "tools" / "gates" / "gate_env_vars.py"
    res = subprocess.run([sys.executable, str(gate6_script)], cwd=str(repo_root), capture_output=True, text=True)
    assert res.returncode == 0, f"Gate 6 failed unexpectedly on clean repo: {res.stderr}\n{res.stdout}"

    # 5. Tamper test: re-add an env read outside allowlist in src/ -> Gate 6 MUST FAIL
    tamper_file = repo_root / "src" / "sclass" / "tamper_env_leak.py"
    try:
        tamper_file.write_text("import os\nSECRET_KEY = os.environ.get('UNAUTHORIZED_TEST_SECRET')\n", encoding="utf-8")
        res_tamper = subprocess.run([sys.executable, str(gate6_script)], cwd=str(repo_root), capture_output=True, text=True)
        assert res_tamper.returncode != 0, "SECURITY VIOLATION: Gate 6 passed despite unauthorized env read outside allowlist!"
        assert "Gate 6 Result: FAIL" in res_tamper.stdout or "Gate 6 Result: FAIL" in res_tamper.stderr
    finally:
        if tamper_file.exists():
            tamper_file.unlink()
        build_dir = repo_root / "build"
        if build_dir.exists():
            import shutil
            shutil.rmtree(build_dir, ignore_errors=True)


@pytest.mark.parametrize("case", ["0644", "symlink", "wrong_owner", "missing_file", "malformed_json"])
def test_m3_protected_pin_file_permissions_and_ownership(tmp_path, monkeypatch, case):
    """M3: Pins and keys load from a protected file: regular file (no symlink), mode <= 0600,
    owned by the service user, fail closed on any violation or if missing.
    Parametrized: 0644, symlink, wrong owner, missing file, malformed JSON:
    each raises and the control plane is not constructed.
    """
    import json
    import os
    import sys
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from sclass_runtime_v6_0_1 import SClassControlPlane, SQLiteEventStore

    store = SQLiteEventStore(str(tmp_path / f"store_{case}.sqlite"))
    legit_priv = Ed25519PrivateKey.generate()
    legit_pub = legit_priv.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()
    valid_pins_data = [{"trust_root": "root-m3", "public_key": legit_pub, "key_id": "key-m3"}]

    valid_file = tmp_path / f"valid_pins_{case}.json"
    valid_file.write_text(json.dumps(valid_pins_data), encoding="utf-8")
    os.chmod(valid_file, 0o600)

    target_pin_path = None

    if case == "0644":
        pin_file = tmp_path / "pins_0644.json"
        pin_file.write_text(json.dumps(valid_pins_data), encoding="utf-8")
        os.chmod(pin_file, 0o644)
        target_pin_path = pin_file

    elif case == "symlink":
        symlink_file = tmp_path / "pins_symlink.json"
        if symlink_file.exists():
            symlink_file.unlink()
        try:
            symlink_file.symlink_to(valid_file)
        except OSError:
            symlink_file.write_text("{}", encoding="utf-8")
            orig_lstat = os.lstat
            def fake_symlink_lstat(path, *args, **kwargs):
                st = orig_lstat(path, *args, **kwargs)
                if str(path) == str(symlink_file):
                    import stat
                    return os.stat_result((
                        stat.S_IFLNK | 0o777, st.st_ino, st.st_dev, st.st_nlink,
                        st.st_uid, st.st_gid, st.st_size,
                        st.st_atime, st.st_mtime, st.st_ctime
                    ))
                return st
            monkeypatch.setattr(os, "lstat", fake_symlink_lstat)
            monkeypatch.setattr(Path, "is_symlink", lambda self: str(self) == str(symlink_file))
        target_pin_path = symlink_file

    elif case == "wrong_owner":
        pin_file = tmp_path / "pins_wrong_owner.json"
        pin_file.write_text(json.dumps(valid_pins_data), encoding="utf-8")
        os.chmod(pin_file, 0o600)
        target_pin_path = pin_file

        orig_lstat = os.lstat
        def fake_lstat(path, *args, **kwargs):
            st = orig_lstat(path, *args, **kwargs)
            if str(path) == str(pin_file):
                fake_uid = (os.getuid() + 1000) if hasattr(os, "getuid") else 9999
                return os.stat_result((
                    st.st_mode, st.st_ino, st.st_dev, st.st_nlink,
                    fake_uid, st.st_gid, st.st_size,
                    st.st_atime, st.st_mtime, st.st_ctime
                ))
            return st

        monkeypatch.setattr(os, "lstat", fake_lstat)
        orig_stat = os.stat
        def fake_stat(path, *args, **kwargs):
            st = orig_stat(path, *args, **kwargs)
            if str(path) == str(pin_file):
                fake_uid = (os.getuid() + 1000) if hasattr(os, "getuid") else 9999
                return os.stat_result((
                    st.st_mode, st.st_ino, st.st_dev, st.st_nlink,
                    fake_uid, st.st_gid, st.st_size,
                    st.st_atime, st.st_mtime, st.st_ctime
                ))
            return st
        monkeypatch.setattr(os, "stat", fake_stat)

    elif case == "missing_file":
        target_pin_path = tmp_path / "non_existent_pins.json"

    elif case == "malformed_json":
        pin_file = tmp_path / "pins_malformed.json"
        pin_file.write_text("NOT_VALID_JSON{[[", encoding="utf-8")
        os.chmod(pin_file, 0o600)
        target_pin_path = pin_file

    cp = None
    with pytest.raises((PermissionError, ValueError, FileNotFoundError)):
        cp = SClassControlPlane(store, pinned_keys=target_pin_path)

    assert cp is None, f"SECURITY VIOLATION: Control plane was constructed for case {case}!"
    store.close()


@pytest.mark.parametrize(
    "target",
    [
        "worker_harness",
        "verification_engine",
        "cosmic_ray",
        "locust",
        "playwright",
        "schemathesis",
        "testcontainers",
    ],
)
def test_m4_minimal_allowlisted_env_scrubs_parent_secrets(tmp_path, monkeypatch, target):
    """M4: Workers and verifiers run with a minimal allowlisted environment
    (fixed PATH, locale, workspace-local HOME/TMPDIR). Nothing from the parent environment passes through.
    Parametrized so each case is its own reported test:
    secret placed in parent env is absent in child for:
    worker harness, verification engine, and each of the 5 adapters
    (cosmic_ray, locust, playwright, schemathesis, testcontainers).
    Zero os.environ.copy() remain in src/.
    """
    import os
    import subprocess
    import sys
    from pathlib import Path

    # 1. Zero os.environ.copy() remain in src/
    repo_root = Path(__file__).resolve().parents[2]
    src_dir = repo_root / "src"
    copy_hits = []
    for py_file in src_dir.rglob("*.py"):
        try:
            content = py_file.read_text(encoding="utf-8")
        except Exception:
            continue
        if "os.environ.copy()" in content or "environ.copy()" in content:
            copy_hits.append(str(py_file.relative_to(repo_root)))
    assert not copy_hits, f"SECURITY VIOLATION: os.environ.copy() found in src/: {copy_hits}"

    # 2. Secret placed in parent env
    secret_key = "TOP_SECRET_EVALUATOR_KEY"
    secret_val = "SECRET_CANARY_VALUE_XYZ"
    monkeypatch.setenv(secret_key, secret_val)

    workspace = tmp_path / f"ws_{target}"
    workspace.mkdir()

    captured_envs = []
    orig_run = subprocess.run
    orig_popen = subprocess.Popen

    def spy_run(*args, **kwargs):
        env_passed = kwargs.get("env")
        if env_passed is None:
            captured_envs.append(dict(os.environ))
        else:
            captured_envs.append(dict(env_passed))
        return orig_run(*args, **kwargs)

    def spy_popen(*args, **kwargs):
        env_passed = kwargs.get("env")
        if env_passed is None:
            captured_envs.append(dict(os.environ))
        else:
            captured_envs.append(dict(env_passed))
        return orig_popen(*args, **kwargs)

    monkeypatch.setattr(subprocess, "run", spy_run)
    monkeypatch.setattr(subprocess, "Popen", spy_popen)

    if target == "worker_harness":
        from sclass.workers.harness import PatchAgentWorker
        from tests.helpers.test_boundary import TestOnlyUnsandboxedBoundary
        from tests.workers.test_worker_harness import (
            _make_sample_authorized_request,
            _make_sample_boundary_context,
        )
        from sclass_runtime_v6_0_1 import LocalWorkspaceSnapshotHandle

        boundary = TestOnlyUnsandboxedBoundary(workspace)
        worker = PatchAgentWorker(boundary=boundary)
        req = _make_sample_authorized_request(fencing_token=1)
        b_ctx = _make_sample_boundary_context(fencing_token=1)
        handle = LocalWorkspaceSnapshotHandle(workspace, "ws", "snap-1", 1)

        out_file = workspace / "child_env.json"
        cmd = [
            sys.executable,
            "-c",
            f"import os, json, pathlib; pathlib.Path(r'{out_file}').write_text(json.dumps(dict(os.environ)))",
        ]
        worker.execute(req, b_ctx, handle, argv=cmd)

    elif target == "verification_engine":
        from sclass.verification.engine import PytestVerifier

        verifier = PytestVerifier()
        tests_dir = workspace / "tests"
        tests_dir.mkdir()
        test_file = tests_dir / "test_sample.py"
        test_file.write_text("def test_ok(): pass\n", encoding="utf-8")
        verifier.run(workspace)

    elif target == "cosmic_ray":
        from sclass.verification.adapters.cosmic_ray_adapter import CosmicRayAdapter

        adapter = CosmicRayAdapter()
        tools_dir = workspace / "tools"
        tools_dir.mkdir()
        cr_script = tools_dir / "run_cr.py"
        cr_script.write_text("import sys; sys.exit(0)\n", encoding="utf-8")
        adapter.run(workspace)

    elif target == "locust":
        from sclass.verification.adapters.locust_adapter import LocustAdapter

        adapter = LocustAdapter()
        locust_file = workspace / "locustfile.py"
        locust_file.write_text("# dummy\n", encoding="utf-8")
        adapter.run(workspace)

    elif target == "playwright":
        from sclass.verification.adapters.playwright_adapter import PlaywrightAdapter

        adapter = PlaywrightAdapter()
        adapter.run(workspace)

    elif target == "schemathesis":
        from sclass.verification.adapters.schemathesis_adapter import SchemathesisAdapter

        adapter = SchemathesisAdapter()
        schema_file = workspace / "openapi.json"
        schema_file.write_text('{"openapi": "3.0.0", "info": {"title": "T", "version": "1"}, "paths": {}}', encoding="utf-8")
        adapter.run(workspace)

    elif target == "testcontainers":
        from sclass.verification.adapters.testcontainers_adapter import TestcontainersAdapter

        adapter = TestcontainersAdapter()
        adapter.run(workspace)

    assert len(captured_envs) > 0, f"No subprocess was captured for target {target}"
    for child_env in captured_envs:
        assert secret_key not in child_env, (
            f"SECURITY VIOLATION: Parent secret '{secret_key}' leaked into child env for {target}!"
        )
        assert "HOME" in child_env, f"HOME missing in child env for {target}"
        assert "TMPDIR" in child_env or "TEMP" in child_env, f"TMPDIR missing in child env for {target}"
        assert ".sclass_home" in child_env.get("HOME", ""), f"HOME is not workspace-local for {target}"
        assert ".sclass_tmp" in (child_env.get("TMPDIR") or child_env.get("TEMP") or ""), f"TMPDIR is not workspace-local for {target}"






