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

    harness = TestHarness()
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
        SClassControlPlane,
        SQLiteEventStore,
        _BOUNDARY_PROVISIONING_TOKEN,
    )
    from tests.workers.test_worker_harness import _make_sample_authorized_request

    boundary = LinuxExecutionBoundary(str(tmp_path), require_sandbox=False)
    store = SQLiteEventStore(str(tmp_path / "d1.sqlite"))
    cp = SClassControlPlane(store, pinned_trust_roots={"d1-root"})

    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    # Register key in runtime_keys so status is ACTIVE, but deactivate the root in runtime_trust_roots
    cp.db.execute(
        "INSERT INTO runtime_keys(key_id, trust_root, public_key, status, not_before, not_after, inserted_at, rotated_at, revoked_at) "
        "VALUES (?, ?, ?, ?, 0, ?, ?, NULL, NULL)",
        ("d1-key", "d1-root", pub, KeyStatus.ACTIVE.value, 2**63 - 1, time.time_ns()),
    )
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
    """D2 (a): Attestor built with production token and an ephemeral key -> PermissionError at preflight.

    Proves that possessing the private module-level _BOUNDARY_PROVISIONING_TOKEN does not
    confer provisioning authority: an ephemeral key not provisioned into the control plane
    fails closed at preflight on a real LinuxExecutionBoundary before any process is started.
    """
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
    store = SQLiteEventStore(str(tmp_path / "d2a.sqlite"))
    cp = SClassControlPlane(store, pinned_trust_roots={"pinned-root"})

    ephemeral_priv = Ed25519PrivateKey.generate()
    # Attestor constructed with production token and an ephemeral unprovisioned key
    att = LocalQuiescenceAttestor(
        cp.keys,
        "pinned-root",
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

    # Ephemeral key is not provisioned in key directory
    assert "quiescence" in str(exc_info.value)
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
        LinuxExecutionBoundary,
        LocalQuiescenceAttestor,
        SClassControlPlane,
        SQLiteEventStore,
        _BOUNDARY_PROVISIONING_TOKEN,
        _BOUNDARY_TEST_TOKEN,
    )
    from tests.workers.test_worker_harness import _make_sample_authorized_request

    boundary = LinuxExecutionBoundary(str(tmp_path), require_sandbox=False)
    store = SQLiteEventStore(str(tmp_path / "d2c.sqlite"))
    # Control plane strictly pins ONLY "allowed-root"
    cp = SClassControlPlane(store, pinned_trust_roots={"allowed-root"})
    gate = ExecutionGate(boundary, cp)
    req = _make_sample_authorized_request()
    cmd = [sys.executable, "-c", "pass"]

    # Route 1: Direct constructor with production token and an unpinned root (even if registered in DB)
    priv1 = Ed25519PrivateKey.generate()
    pub1 = priv1.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    cp.keys.add_root("excluded-root")
    cp.keys.register("key-ex-1", "excluded-root", pub1)
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
    cp.keys.register("key-ex-env", "excluded-root", pub_env)
    monkeypatch.setenv("SCLASS_BOUNDARY_TRUST_ROOT", "excluded-root")
    monkeypatch.setenv("SCLASS_BOUNDARY_KEY_ID", "key-ex-env")
    raw_key = base64.b64encode(
        priv1.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
    ).decode("ascii")
    monkeypatch.setenv("SCLASS_BOUNDARY_PRIVATE_KEY_B64", raw_key)
    att3 = LocalQuiescenceAttestor.from_environment(cp.keys)
    assert att3 is not None
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
        SClassControlPlane,
        SQLiteEventStore,
        _BOUNDARY_PROVISIONING_TOKEN,
    )
    from tests.workers.test_worker_harness import _make_sample_authorized_request

    store = SQLiteEventStore(str(tmp_path / "d3.sqlite"))
    cp = SClassControlPlane(store, pinned_trust_roots={"root-d3"})

    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
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

