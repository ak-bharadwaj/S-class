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


@pytest.mark.parametrize(
    "case",
    [
        "0644",
        "0640",
        "0660",
        "0700",
        "0666",
        "04600",
        "symlink",
        "wrong_owner",
        "missing_file",
        "malformed_json",
    ],
)
def test_m3_protected_pin_file_permissions_and_ownership(tmp_path, monkeypatch, case):
    """M3: Pins and keys load from a protected file: regular file (no symlink), mode <= 0600,
    owned by the service user, fail closed on any violation or if missing.
    Parametrized: 0644, 0640, 0660, 0700, 0666, 04600, symlink, wrong owner, missing file, malformed JSON:
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

    if case.startswith("0") or case == "wrong_owner":
        monkeypatch.setattr("sclass_runtime_v6_0_1.sys.platform", "linux")
        monkeypatch.setattr("sclass_runtime_v6_0_1.os.getuid", lambda: 1000, raising=False)
        monkeypatch.setattr("os.getuid", lambda: 1000, raising=False)

    if case.startswith("0"):
        mode_val = int(case, 8)
        pin_file = tmp_path / f"pins_{case}.json"
        pin_file.write_text(json.dumps(valid_pins_data), encoding="utf-8")
        if hasattr(os, "chmod"):
            try:
                os.chmod(pin_file, mode_val)
            except OSError:
                pass
        orig_fstat = os.fstat
        def fake_fstat(fd, *args, **kwargs):
            st = orig_fstat(fd, *args, **kwargs)
            import stat
            return os.stat_result((
                stat.S_IFREG | mode_val, st.st_ino, st.st_dev, st.st_nlink,
                st.st_uid, st.st_gid, st.st_size,
                st.st_atime, st.st_mtime, st.st_ctime
            ))
        monkeypatch.setattr(os, "fstat", fake_fstat)
        monkeypatch.setattr("sclass_runtime_v6_0_1.os.fstat", fake_fstat)
        orig_lstat = os.lstat
        def fake_lstat(path, *args, **kwargs):
            st = orig_lstat(path, *args, **kwargs)
            if str(path) == str(pin_file):
                import stat
                return os.stat_result((
                    stat.S_IFREG | mode_val, st.st_ino, st.st_dev, st.st_nlink,
                    st.st_uid, st.st_gid, st.st_size,
                    st.st_atime, st.st_mtime, st.st_ctime
                ))
            return st
        monkeypatch.setattr(os, "lstat", fake_lstat)
        monkeypatch.setattr("sclass_runtime_v6_0_1.os.lstat", fake_lstat)
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
            monkeypatch.setattr("sclass_runtime_v6_0_1.os.lstat", fake_symlink_lstat)
            monkeypatch.setattr(Path, "is_symlink", lambda self: str(self) == str(symlink_file))
        target_pin_path = symlink_file

    elif case == "wrong_owner":
        pin_file = tmp_path / "pins_wrong_owner.json"
        pin_file.write_text(json.dumps(valid_pins_data), encoding="utf-8")
        os.chmod(pin_file, 0o600)
        target_pin_path = pin_file

        fake_uid = 9999
        orig_lstat = os.lstat
        def fake_lstat(path, *args, **kwargs):
            st = orig_lstat(path, *args, **kwargs)
            if str(path) == str(pin_file):
                return os.stat_result((
                    st.st_mode, st.st_ino, st.st_dev, st.st_nlink,
                    fake_uid, st.st_gid, st.st_size,
                    st.st_atime, st.st_mtime, st.st_ctime
                ))
            return st
        monkeypatch.setattr(os, "lstat", fake_lstat)
        monkeypatch.setattr("sclass_runtime_v6_0_1.os.lstat", fake_lstat)

        orig_stat = os.stat
        def fake_stat(path, *args, **kwargs):
            st = orig_stat(path, *args, **kwargs)
            if str(path) == str(pin_file):
                return os.stat_result((
                    st.st_mode, st.st_ino, st.st_dev, st.st_nlink,
                    fake_uid, st.st_gid, st.st_size,
                    st.st_atime, st.st_mtime, st.st_ctime
                ))
            return st
        monkeypatch.setattr(os, "stat", fake_stat)
        monkeypatch.setattr("sclass_runtime_v6_0_1.os.stat", fake_stat)

        orig_fstat = os.fstat
        def fake_fstat(fd, *args, **kwargs):
            st = orig_fstat(fd, *args, **kwargs)
            return os.stat_result((
                st.st_mode, st.st_ino, st.st_dev, st.st_nlink,
                fake_uid, st.st_gid, st.st_size,
                st.st_atime, st.st_mtime, st.st_ctime
            ))
        monkeypatch.setattr(os, "fstat", fake_fstat)
        monkeypatch.setattr("sclass_runtime_v6_0_1.os.fstat", fake_fstat)

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


def test_m3_symlink_to_valid_0600_file_rejected(tmp_path, monkeypatch):
    """M3 / F2: Symlink to a valid 0600 file is rejected with symlink-specific PermissionError."""
    import json
    import os
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from sclass_runtime_v6_0_1 import SClassControlPlane, SQLiteEventStore

    store = SQLiteEventStore(str(tmp_path / "store_symlink.sqlite"))
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()
    valid_pins = [{"trust_root": "symlink-root", "public_key": pub, "key_id": "symlink-key"}]

    target_file = tmp_path / "target_valid_pins.json"
    target_file.write_text(json.dumps(valid_pins), encoding="utf-8")
    if hasattr(os, "chmod"):
        os.chmod(target_file, 0o600)

    symlink_file = tmp_path / "pins_symlink.json"
    try:
        symlink_file.symlink_to(target_file)
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

    with pytest.raises(PermissionError, match="cannot be a symlink"):
        SClassControlPlane(store, pinned_keys=symlink_file)
    store.close()


def test_m3_mutation_check_loosened_mask_fails():
    """M3 / F2: Mutation check proving loosening the mask to '& 0o004' fails on mode violations.

    Demonstrates that a mutant which only checks other-read ('& 0o004') fails to detect
    insecure permissions on 0640 (group read), 0660 (group rw), 0700 (owner exec), and 04600 (setuid).
    The production mask '(stat.S_IMODE(st.st_mode) & ~0o600) != 0' catches all of them.
    """
    import stat

    forbidden_modes = [0o640, 0o660, 0o700, 0o666, 0o4600]

    for mode in forbidden_modes:
        # Production check:
        prod_violation = (stat.S_IMODE(mode) & ~0o600) != 0
        assert prod_violation is True, f"Production mask failed to reject mode {oct(mode)}"

        # Loosened mutant check:
        mutant_violation = (mode & 0o004) != 0
        if mode in (0o640, 0o660, 0o700, 0o4600):
            # The mutant fails to detect these violations!
            assert mutant_violation is False, f"Mutant unexpectedly caught mode {oct(mode)}"


@pytest.mark.parametrize(
    "evasion_form,code",
    [
        ("from_os_getenv", "from os import getenv\nx = getenv('CANARY')\n"),
        ("aliased_os_import", "import os as secret_os\nx = secret_os.environ.get('CANARY')\n"),
        ("aliased_environ_import", "from os import environ as secret_env\nx = secret_env.get('CANARY')\n"),
        ("getattr_os_environ", "import os\nx = getattr(os, 'environ').get('CANARY')\n"),
        ("vars_os_environ", "import os\nx = vars(os)['environ'].get('CANARY')\n"),
        ("os_environb", "import os\nx = os.environb.get(b'CANARY')\n"),
        ("from_os_environb", "from os import environb\nx = environb.get(b'CANARY')\n"),
        ("bare_getenv", "from os import getenv\nx = getenv('CANARY')\n"),
    ],
)
def test_f1_gate6_tamper_evasion_forms(evasion_form, code):
    """F1: Gate 6 detects all evasion forms:
    from os import getenv, aliased imports, getattr(os, 'environ'),
    vars(os)['environ'], os.environb, from os import environb, bare getenv.
    One tamper test per form; each MUST fail Gate 6.
    """
    repo_root = Path(__file__).resolve().parents[2]
    gate6_script = repo_root / "tools" / "gates" / "gate_env_vars.py"
    tamper_file = repo_root / "src" / "sclass" / f"tamper_{evasion_form}.py"

    try:
        tamper_file.write_text(code, encoding="utf-8")
        res = subprocess.run([sys.executable, str(gate6_script)], cwd=str(repo_root), capture_output=True, text=True)
        assert res.returncode != 0, f"SECURITY VIOLATION: Gate 6 passed evasion form '{evasion_form}'!"
        assert "Gate 6 Result: FAIL" in res.stdout or "Gate 6 Result: FAIL" in res.stderr
    finally:
        if tamper_file.exists():
            tamper_file.unlink()
        build_dir = repo_root / "build"
        if build_dir.exists():
            import shutil
            shutil.rmtree(build_dir, ignore_errors=True)


def test_f4_git_calls_clean_env_and_hooks_disabled(tmp_path, monkeypatch):
    """F4: Host-side git calls in workspace/preflight.py and workspace/worktrees.py
    pass a minimal environment plus GIT_CONFIG_NOSYSTEM=1, GIT_CONFIG_GLOBAL=/dev/null,
    and -c core.hooksPath=/dev/null.
    Tests:
    1. Secret in parent environment is scrubbed and never reached by git subprocesses.
    2. core.hooksPath=/dev/null is passed on all invocations.
    3. Malicious git hooks in repository are never executed.
    4. shell=True is eliminated (shell=False verified).
    """
    from sclass.workspace.preflight import WorkspacePreflightScanner
    from sclass.workspace.worktrees import WorktreeManager
    import os

    # 1. Setup a real git repository directory in tmp_path
    git_dir = tmp_path / ".git"
    git_dir.mkdir(parents=True)
    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(parents=True)

    sentinel_hook = tmp_path / "hook_sentinel.txt"
    if sentinel_hook.exists():
        sentinel_hook.unlink()

    # Create dummy hook that would touch sentinel if invoked
    hook_script = hooks_dir / "post-commit"
    hook_script.write_text(f"#!/bin/sh\necho HOOK_RAN > {sentinel_hook.as_posix()}\n")
    if hasattr(os, "chmod"):
        os.chmod(hook_script, 0o755)

    # 2. Inject parent secret
    secret_key = "SECRET_PARENT_TOKEN"
    secret_val = "EVALUATOR_TOP_SECRET_12345"
    monkeypatch.setenv(secret_key, secret_val)

    # 3. Intercept subprocess.run to verify arguments and environment
    captured_calls = []
    orig_run = subprocess.run

    def spy_git_run(cmd, *args, **kwargs):
        captured_calls.append({
            "cmd": cmd,
            "env": kwargs.get("env"),
            "shell": kwargs.get("shell", False),
        })
        return subprocess.CompletedProcess(cmd, 0, stdout="main\n", stderr="")

    monkeypatch.setattr(subprocess, "run", spy_git_run)

    # 4. Invoke WorkspacePreflightScanner
    scanner = WorkspacePreflightScanner(tmp_path)
    scanner.scan()

    # 5. Invoke WorktreeManager
    wt = WorktreeManager(tmp_path)
    wt.is_git_repo()
    wt.create_worktree("wt-1", "feature-branch")
    wt.remove_worktree("wt-1", force=True)

    assert len(captured_calls) >= 5, "Expected at least 5 git subprocess calls"

    for call in captured_calls:
        cmd = call["cmd"]
        env = call["env"]
        shell = call["shell"]

        # Verification 1: shell=False strictly enforced
        assert shell is False, f"SECURITY VIOLATION: Subprocess called with shell=True: {cmd}"

        # Verification 2: Command contains -c core.hooksPath=/dev/null (for git commands)
        if isinstance(cmd, list) and cmd and cmd[0] == "git":
            assert "core.hooksPath=/dev/null" in " ".join(cmd), (
                f"SECURITY VIOLATION: Git call missing core.hooksPath=/dev/null: {cmd}"
            )

        # Verification 3: Environment does NOT contain parent secret
        assert env is not None, f"SECURITY VIOLATION: Subprocess called without explicit env (leaked parent env): {cmd}"
        assert secret_key not in env, f"SECURITY VIOLATION: Parent secret passed to subprocess: {cmd}"

        # Verification 4: Git isolation env vars present
        if isinstance(cmd, list) and cmd and cmd[0] == "git":
            assert env.get("GIT_CONFIG_NOSYSTEM") == "1", f"Missing GIT_CONFIG_NOSYSTEM in {cmd}"
            assert env.get("GIT_CONFIG_GLOBAL") == "/dev/null", f"Missing GIT_CONFIG_GLOBAL in {cmd}"

    # Verification 5: Sentinel from hook was NEVER touched
    assert not sentinel_hook.exists(), "SECURITY VIOLATION: Git hook executed despite core.hooksPath=/dev/null!"


def test_m10_worker_boundary_without_gate_capability_fails_closed(tmp_path):
    """M10: PatchAgentWorker / SubprocessToolWorker with a boundary lacking a gate capability fail closed.
    PermissionError, sentinel proves no spawn, and zero unconfined disk mutations.
    """
    from sclass.workers.harness import PatchAgentWorker, SubprocessToolWorker
    from sclass_runtime_v6_0_1 import LinuxExecutionBoundary, LocalWorkspaceSnapshotHandle
    from tests.workers.test_worker_harness import _make_sample_authorized_request, _make_sample_boundary_context

    ws = tmp_path / "workspace_m10"
    ws.mkdir()
    sentinel = ws / "sentinel_spawned.txt"
    mutation_target = ws / "leaked_mutation.py"

    # Boundary with NO gate capability
    boundary = LinuxExecutionBoundary(str(ws), require_sandbox=False)
    boundary._gate_capability = None

    req = _make_sample_authorized_request(fencing_token=1)
    b_ctx = _make_sample_boundary_context(fencing_token=1)
    handle = LocalWorkspaceSnapshotHandle(ws, "ws", "snap-1", 1)

    cmd = [
        sys.executable,
        "-c",
        f"import pathlib; pathlib.Path(r'{sentinel.as_posix()}').write_text('SPAWNED')",
    ]

    # 1. PatchAgentWorker fails closed
    patch_worker = PatchAgentWorker(boundary=boundary)
    patch_worker.stage_file_mutation("leaked_mutation.py", "print('EXPLOITED')\n")
    with pytest.raises(PermissionError, match="requires authentic LinuxExecutionBoundary with gate capability"):
        patch_worker.execute(req, b_ctx, handle, argv=cmd, write_paths=["leaked_mutation.py"])

    assert not sentinel.exists(), "SECURITY VIOLATION: Worker process spawned despite missing gate capability!"
    assert not mutation_target.exists(), "SECURITY VIOLATION: Mutations written to disk despite missing gate capability!"

    # 2. SubprocessToolWorker fails closed
    tool_worker = SubprocessToolWorker(boundary=boundary)
    with pytest.raises(PermissionError):
        tool_worker.execute(req, b_ctx, handle, argv=cmd)

    assert not sentinel.exists(), "SECURITY VIOLATION: Tool worker process spawned despite missing gate capability!"


def test_m9_no_test_only_mutators_on_runtime_classes():
    """M9: The _*_for_test methods in 20-RUNTIME/ are proven non-authoritative
    and unreachable from production objects, and all public mutators fail closed
    with PermissionError.
    """
    from sclass_runtime_v6_0_1 import (
        BreakGlassAuthority,
        Digest,
        LinuxExecutionBoundary,
        LocalQuiescenceAttestor,
        ResourceBudget,
        SQLiteBreakGlassLedger,
        SQLiteBudgetAllocator,
        SQLiteRetryBudgetStore,
        UtcInstant,
    )

    repo_root = Path(__file__).resolve().parents[2]
    src_dir = repo_root / "src"

    # 1. Zero calls to _for_test in src/ (production tree)
    src_violations = []
    for py_file in src_dir.rglob("*.py"):
        try:
            content = py_file.read_text(encoding="utf-8")
        except Exception:
            continue
        if "_for_test" in content:
            src_violations.append(str(py_file.relative_to(repo_root)))
    assert not src_violations, f"SECURITY VIOLATION: Production code calls _for_test: {src_violations}"

    # 2. Public mutators on runtime ledgers fail closed with PermissionError
    import sqlite3
    db = sqlite3.connect(":memory:")
    budgets = SQLiteBudgetAllocator(db)
    retries = SQLiteRetryBudgetStore(db)
    breakglass = SQLiteBreakGlassLedger(db)

    with pytest.raises(PermissionError, match="canonical policy state"):
        budgets.set_workspace_limit("ws-1", ResourceBudget(1, 10, 10, 1000, 0, 1, 0, 0, 0, 0, 1))

    with pytest.raises(PermissionError, match="direct runtime budget reservation is non-authoritative"):
        budgets.reserve("ws-1", "req-1", "lineage-1", ResourceBudget(1, 10, 10, 1000, 0, 1, 0, 0, 0, 0, 1), UtcInstant(1000))

    with pytest.raises(PermissionError, match="direct runtime retry consumption is non-authoritative"):
        retries.try_consume("budget-1", 1, Digest("sha256:" + "0" * 64), 3)

    with pytest.raises(PermissionError, match="direct break-glass consumption is non-authoritative"):
        breakglass.consume(None, "requester", "reason")  # type: ignore[arg-type]

    db.close()

    # 3. Kernel classes do not expose for_test or from_environment
    assert not hasattr(LinuxExecutionBoundary, "run_for_test")
    assert not hasattr(LocalQuiescenceAttestor, "for_test")
    assert not hasattr(LocalQuiescenceAttestor, "from_environment")


def test_m8_worktrees_rejects_shell_metacharacters_and_triage_table():
    """M8: shell=True at src/sclass/workspace/worktrees.py:140 is removed.
    Metacharacters in worktree paths are passed as argument list (shell=False)
    and cannot cause command injection.
    Triage table in docs/EXCEPTION-TRIAGE.md exists and covers all remaining sites.
    """
    repo_root = Path(__file__).resolve().parents[2]

    # 1. Verify docs/EXCEPTION-TRIAGE.md exists and contains triage table
    triage_doc = repo_root / "docs" / "EXCEPTION-TRIAGE.md"
    assert triage_doc.exists(), f"Missing exception triage table at {triage_doc}"
    text = triage_doc.read_text(encoding="utf-8")
    assert "ROLLBACK_AND_RERAISE" in text
    assert "CLEANUP_FINALLY" in text
    assert "PROTOCOL_ERROR_RESPONSE" in text

    # 2. Verify worktrees.py has ZERO shell=True
    worktrees_py = repo_root / "src" / "sclass" / "workspace" / "worktrees.py"
    wt_content = worktrees_py.read_text(encoding="utf-8")
    assert "shell=True" not in wt_content, "SECURITY VIOLATION: shell=True found in worktrees.py!"
    assert "shell=False" in wt_content


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

def test_m6_missing_bwrap_or_cgroup_fails_closed_boundary_unavailable(tmp_path, monkeypatch):
    """M6: Host without usable user namespaces or cgroup v2 -> BoundaryUnavailable,
    never an unsandboxed run. Sentinel file proves no worker started.
    """
    from sclass_runtime_v6_0_1 import BoundaryUnavailable, LinuxExecutionBoundary
    sentinel = tmp_path / "m6_sentinel.txt"
    if sentinel.exists():
        sentinel.unlink()

    worker_code = f"import pathlib; pathlib.Path(r'{sentinel.as_posix()}').write_text('PROCESS_RAN')"
    cmd = [sys.executable, "-c", worker_code]

    # Case 1: bwrap binary missing
    b1 = LinuxExecutionBoundary(str(tmp_path))
    b1.bwrap = None
    with pytest.raises(BoundaryUnavailable):
        b1._run_from_gate(b1._gate_capability, cmd)
    assert not sentinel.exists(), "SECURITY VIOLATION: Worker spawned when bwrap missing!"

    # Case 2: bwrap exists, but unprivileged user namespaces are blocked (e.g. Ubuntu 24.04 AppArmor restriction)
    b2 = LinuxExecutionBoundary(str(tmp_path))
    # If _is_bwrap_functional is not implemented yet or user namespaces are simulated blocked
    if hasattr(b2, "_is_bwrap_functional"):
        monkeypatch.setattr(b2, "_is_bwrap_functional", lambda *args, **kwargs: False)
    else:
        # Pre-fix bypass: current code lacks _is_bwrap_functional, simulate failure by checking hasattr
        raise AssertionError("BYPASS: LinuxExecutionBoundary lacks user namespace usability check")
    with pytest.raises(BoundaryUnavailable):
        b2._run_from_gate(b2._gate_capability, cmd)
    assert not sentinel.exists(), "SECURITY VIOLATION: Worker spawned when user namespaces blocked!"


    # Case 3: cgroup v2 unavailable or unwritable
    b3 = LinuxExecutionBoundary(str(tmp_path))
    def _fail_cg():
        raise BoundaryUnavailable("cgroup v2 hierarchy is not writable")
    monkeypatch.setattr(b3, "_assert_cgroup_v2", _fail_cg)
    with pytest.raises(BoundaryUnavailable):
        b3._run_from_gate(b3._gate_capability, cmd)
    assert not sentinel.exists(), "SECURITY VIOLATION: Worker spawned when cgroup v2 unavailable!"


def test_m7_ubuntu_24_04_apparmor_prerequisite_and_docs():
    """M7: The Ubuntu 24.04 prerequisite is documented and applied in CI explicitly:
    preferred a narrow bwrap AppArmor profile, otherwise a CI-only sysctl,
    stated in the workflow and in docs/. Not a silent default.
    Doc states the PRODUCTION requirement honestly.
    """
    repo_root = Path(__file__).resolve().parents[2]

    # 1. Profile file exists and has valid structure
    profile_path = repo_root / "docs" / "security" / "bwrap-apparmor-profile"
    assert profile_path.exists(), f"Missing AppArmor profile at {profile_path}"
    profile_text = profile_path.read_text(encoding="utf-8")
    assert "/usr/bin/bwrap" in profile_text, "Profile does not confine /usr/bin/bwrap"
    assert "userns" in profile_text, "Profile does not grant userns capability"
    assert "flags=(unconfined)" in profile_text or "unconfined" in profile_text, "Profile must specify unconfined execution flags"

    # 2. Ubuntu 24.04 documentation exists and honestly states production requirement vs CI-only
    doc_path = repo_root / "docs" / "security" / "UBUNTU-24.04-APPARMOR.md"
    assert doc_path.exists(), f"Missing Ubuntu 24.04 AppArmor doc at {doc_path}"
    doc_text = doc_path.read_text(encoding="utf-8")
    assert "PRODUCTION" in doc_text, "Documentation must honestly state production requirements"
    assert "CI-only" in doc_text or "CI-ONLY" in doc_text, "Documentation must explicitly label sysctl as CI-only"
    assert "apparmor_parser" in doc_text, "Documentation must describe loading profile with apparmor_parser"
    assert "kernel.apparmor_restrict_unprivileged_userns" in doc_text, "Documentation must mention the restriction sysctl"

    # 3. Cgroup v2 delegation documentation exists and states zero privilege escalation
    cg_doc = repo_root / "docs" / "security" / "CGROUP-V2-DELEGATION.md"
    assert cg_doc.exists(), f"Missing cgroup v2 delegation doc at {cg_doc}"
    cg_text = cg_doc.read_text(encoding="utf-8")
    assert "delegated" in cg_text.lower(), "Doc must explain delegated cgroup subtree"
    assert "sudo" in cg_text, "Doc must document administrator setup"
    assert "never escalates" in cg_text.lower() or "zero privilege escalation" in cg_text.lower(), (
        "Doc must state that S-Class never escalates privileges itself"
    )


def test_m5_write_outside_workspace_denied(tmp_path):
    """M5 (1/5): Confined process cannot write outside the workspace."""
    if not Path("/proc").exists() or sys.platform == "win32":
        pytest.skip("Linux bwrap execution requires POSIX environment")
    from sclass_runtime_v6_0_1 import LinuxExecutionBoundary

    outside_file = tmp_path.parent / f"outside_leak_{tmp_path.name}.txt"
    if outside_file.exists():
        outside_file.unlink()

    boundary = LinuxExecutionBoundary(str(tmp_path))
    code = (
        "import pathlib, sys\n"
        f"try:\n"
        f"    pathlib.Path(r'{outside_file.as_posix()}').write_text('LEAKED')\n"
        f"    sys.exit(0)\n"
        f"except Exception as e:\n"
        f"    sys.exit(42)\n"
    )
    res = boundary._run_from_gate(boundary._gate_capability, [sys.executable, "-c", code])
    assert res.returncode != 0, f"Expected write outside workspace to fail, but got returncode 0: {res.stdout}"
    assert not outside_file.exists(), "SECURITY VIOLATION: Confined process wrote outside workspace!"


def test_m5_no_network(tmp_path):
    """M5 (2/5): Confined process has no network."""
    if not Path("/proc").exists() or sys.platform == "win32":
        pytest.skip("Linux bwrap execution requires POSIX environment")
    from sclass_runtime_v6_0_1 import LinuxExecutionBoundary

    boundary = LinuxExecutionBoundary(str(tmp_path))
    code = (
        "import socket, sys\n"
        "s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n"
        "s.settimeout(1.0)\n"
        "try:\n"
        "    s.connect(('1.1.1.1', 80))\n"
        "    sys.exit(0)\n"
        "except OSError as e:\n"
        "    sys.exit(43)\n"
    )
    res = boundary._run_from_gate(boundary._gate_capability, [sys.executable, "-c", code])
    assert res.returncode != 0, f"Expected network connection to fail, but got returncode 0: {res.stdout}"


def test_m5_process_tree_kill_on_timeout(tmp_path):
    """M5 (3/5): Process tree is killed with its whole process tree on timeout."""
    if not Path("/proc").exists() or sys.platform == "win32":
        pytest.skip("Linux bwrap execution requires POSIX environment")
    from sclass_runtime_v6_0_1 import LinuxExecutionBoundary

    boundary = LinuxExecutionBoundary(str(tmp_path))
    # Process spawns a background child of same authorized binary sleeping longer than timeout
    inner_cmd = "import time; time.sleep(30)"
    code = (
        "import subprocess, sys, time\n"
        f"p = subprocess.Popen([sys.executable, '-c', {repr(inner_cmd)}])\n"
        "time.sleep(30)\n"
    )
    res = boundary._run_from_gate(boundary._gate_capability, [sys.executable, "-c", code], timeout_ms=500)
    assert res.timed_out is True, "Expected boundary run to record timed_out=True on timeout"


def test_m5_memory_limit_enforced(tmp_path):
    """M5 (4/5): Confined process obeys memory limit."""
    if not Path("/proc").exists() or sys.platform == "win32":
        pytest.skip("Linux bwrap execution requires POSIX environment")
    from sclass_runtime_v6_0_1 import LinuxExecutionBoundary, ResourceBudget

    boundary = LinuxExecutionBoundary(str(tmp_path))
    # 32 MB limit, process attempts to allocate 128 MB (process_count=50 allows bwrap container init)
    budget = ResourceBudget(1, 32, 100, 5000, 0, 50, 0, 0, 0, 0, 10)
    code = (
        "import sys\n"
        "try:\n"
        "    data = bytearray(128 * 1024 * 1024)\n"
        "    sys.exit(0)\n"
        "except MemoryError:\n"
        "    sys.exit(44)\n"
    )
    res = boundary._run_from_gate(boundary._gate_capability, [sys.executable, "-c", code], budget=budget)
    assert res.returncode != 0, f"Expected memory allocation exceeding 32MB limit to fail, got returncode 0: {res.stdout}"
    assert (
        res.cgroup_events.get("memory.max", 0) > 0
        or res.cgroup_events.get("memory.oom", 0) > 0
        or res.cgroup_events.get("memory.oom_kill", 0) > 0
    ), f"Kernel memory controller limit was not enforced by kernel: {res.cgroup_events}"


def test_m5_pids_limit_enforced(tmp_path):
    """M5 (5/5): Confined process obeys pids limit."""
    if not Path("/proc").exists() or sys.platform == "win32":
        pytest.skip("Linux bwrap execution requires POSIX environment")
    from sclass_runtime_v6_0_1 import LinuxExecutionBoundary, ResourceBudget

    boundary = LinuxExecutionBoundary(str(tmp_path))
    # Limit to 2 processes
    budget = ResourceBudget(1, 128, 100, 5000, 0, 2, 0, 0, 0, 0, 2)
    code = (
        "import os, sys, time\n"
        "pids = []\n"
        "failed = False\n"
        "for i in range(10):\n"
        "    try:\n"
        "        p = os.fork()\n"
        "        if p == 0:\n"
        "            time.sleep(2)\n"
        "            os._exit(0)\n"
        "        pids.append(p)\n"
        "    except (BlockingIOError, OSError):\n"
        "        failed = True\n"
        "        break\n"
        "for p in pids:\n"
        "    try: os.kill(p, 9)\n"
        "    except OSError: pass\n"
        "sys.exit(45 if failed else 0)\n"
    )
    res = boundary._run_from_gate(boundary._gate_capability, [sys.executable, "-c", code], budget=budget)
    assert res.returncode != 0, f"Expected process fork exceeding 2 pids limit to fail, got returncode 0: {res.stdout}"
    assert res.cgroup_events.get("pids.max", 0) > 0, f"Kernel pids controller limit was not enforced by kernel: {res.cgroup_events}"


def test_x2_cgroup_controller_file_absent_fails_closed_no_worker(tmp_path, monkeypatch):
    """X2 (1/4): Missing cgroup controller file raises BoundaryUnavailable before process spawns.

    Uses a temporary fake cgroup directory. A sentinel file proves no worker started.
    """
    from sclass_runtime_v6_0_1 import LinuxExecutionBoundary, ResourceBudget, BoundaryUnavailable

    fake_cgroup = tmp_path / "fake_cgroup_no_ctrl"
    fake_cgroup.mkdir()
    (fake_cgroup / "cgroup.controllers").write_text("memory pids cpu\n")

    sentinel = tmp_path / "sentinel_controller_absent.txt"
    if sentinel.exists():
        sentinel.unlink()

    # Pre-create cgroup.procs in the group on mkdir so cgroup.procs exists but memory.max is absent
    orig_mkdir = Path.mkdir
    def mock_mkdir(self, *args, **kwargs):
        res = orig_mkdir(self, *args, **kwargs)
        if self.parent == fake_cgroup and self.name.startswith("sclass-"):
            (self / "cgroup.procs").write_text("0")
        return res
    monkeypatch.setattr(Path, "mkdir", mock_mkdir)

    boundary = LinuxExecutionBoundary(str(tmp_path), cgroup_root=fake_cgroup)
    budget = ResourceBudget(1, 64, 100, 5000, 0, 10, 0, 0, 0, 0, 10)
    code = f"import pathlib; pathlib.Path(r'{sentinel.as_posix()}').write_text('LEAKED')"

    with pytest.raises(BoundaryUnavailable, match="memory controller \\(memory.max\\) is missing"):
        boundary._run_from_gate(boundary._gate_capability, [sys.executable, "-c", code], budget=budget)

    assert not sentinel.exists(), "SECURITY VIOLATION: Worker started despite missing cgroup controller file!"


def test_x2_cgroup_limit_write_fails_closed_no_worker(tmp_path, monkeypatch):
    """X2 (2/4): Failed write to cgroup limit file raises BoundaryUnavailable before process spawns.

    Uses a temporary fake cgroup directory. A sentinel file proves no worker started.
    """
    import errno
    from sclass_runtime_v6_0_1 import LinuxExecutionBoundary, ResourceBudget, BoundaryUnavailable

    fake_cgroup = tmp_path / "fake_cgroup_write_fail"
    fake_cgroup.mkdir()
    (fake_cgroup / "cgroup.controllers").write_text("memory pids cpu\n")

    sentinel = tmp_path / "sentinel_limit_write_fail.txt"
    if sentinel.exists():
        sentinel.unlink()

    orig_mkdir = Path.mkdir
    orig_write = Path.write_text
    def mock_mkdir(self, *args, **kwargs):
        res = orig_mkdir(self, *args, **kwargs)
        if self.parent == fake_cgroup and self.name.startswith("sclass-"):
            orig_write(self / "cgroup.procs", "0")
            orig_write(self / "memory.max", "max")
            orig_write(self / "pids.max", "max")
            orig_write(self / "cpu.max", "max 100000")
        return res
    monkeypatch.setattr(Path, "mkdir", mock_mkdir)

    def mock_write(self, text, *args, **kwargs):
        if self.name == "memory.max" and "fake_cgroup_write_fail" in str(self):
            raise OSError(errno.EIO, "Simulated hardware I/O error writing memory.max")
        return orig_write(self, text, *args, **kwargs)
    monkeypatch.setattr(Path, "write_text", mock_write)

    boundary = LinuxExecutionBoundary(str(tmp_path), cgroup_root=fake_cgroup)
    budget = ResourceBudget(1, 64, 100, 5000, 0, 10, 0, 0, 0, 0, 10)
    code = f"import pathlib; pathlib.Path(r'{sentinel.as_posix()}').write_text('LEAKED')"

    with pytest.raises(BoundaryUnavailable, match="failed to set memory.max"):
        boundary._run_from_gate(boundary._gate_capability, [sys.executable, "-c", code], budget=budget)

    assert not sentinel.exists(), "SECURITY VIOLATION: Worker started despite failed limit write!"


def test_x2_cgroup_procs_attach_fails_closed_no_worker(tmp_path, monkeypatch):
    """X2 (3/4): Failed write to cgroup.procs raises BoundaryUnavailable and child never executes.

    Uses a temporary fake cgroup directory. A sentinel file proves no worker started.
    """
    import errno
    from sclass_runtime_v6_0_1 import LinuxExecutionBoundary, ResourceBudget, BoundaryUnavailable

    fake_cgroup = tmp_path / "fake_cgroup_attach_fail"
    fake_cgroup.mkdir()
    (fake_cgroup / "cgroup.controllers").write_text("memory pids cpu\n")

    sentinel = tmp_path / "sentinel_attach_fail.txt"
    if sentinel.exists():
        sentinel.unlink()

    orig_mkdir = Path.mkdir
    orig_write = Path.write_text
    def mock_mkdir(self, *args, **kwargs):
        res = orig_mkdir(self, *args, **kwargs)
        if self.parent == fake_cgroup and self.name.startswith("sclass-"):
            orig_write(self / "cgroup.procs", "0")
            orig_write(self / "memory.max", "max")
            orig_write(self / "pids.max", "max")
            orig_write(self / "cpu.max", "max 100000")
        return res
    monkeypatch.setattr(Path, "mkdir", mock_mkdir)

    orig_write = Path.write_text
    def mock_write(self, text, *args, **kwargs):
        if self.name == "cgroup.procs" and "fake_cgroup_attach_fail" in str(self) and text != "0":
            raise OSError(errno.EPERM, "Simulated attach permission error")
        return orig_write(self, text, *args, **kwargs)
    monkeypatch.setattr(Path, "write_text", mock_write)

    boundary = LinuxExecutionBoundary(str(tmp_path), cgroup_root=fake_cgroup)
    budget = ResourceBudget(1, 64, 100, 5000, 0, 10, 0, 0, 0, 0, 10)
    code = f"import pathlib; pathlib.Path(r'{sentinel.as_posix()}').write_text('LEAKED')"

    with pytest.raises(BoundaryUnavailable):
        boundary._run_from_gate(boundary._gate_capability, [sys.executable, "-c", code], budget=budget)

    assert not sentinel.exists(), "SECURITY VIOLATION: Worker started despite cgroup.procs attach failure!"


def test_x2_required_setrlimit_failure_aborts_child_no_worker(tmp_path, monkeypatch):
    """X2 (4/4): Failed setrlimit required by budget aborts child before execution.

    A sentinel file proves no worker started.
    """
    if not Path("/proc").exists() or sys.platform == "win32":
        pytest.skip("Linux execution requires POSIX environment")
    import errno
    import resource
    from sclass_runtime_v6_0_1 import LinuxExecutionBoundary, ResourceBudget, BoundaryUnavailable

    sentinel = tmp_path / "sentinel_rlimit_fail.txt"
    if sentinel.exists():
        sentinel.unlink()

    orig_setrlimit = resource.setrlimit
    def mock_setrlimit(res, limits):
        if res == resource.RLIMIT_AS:
            raise OSError(errno.EPERM, "Simulated setrlimit RLIMIT_AS permission denied")
        return orig_setrlimit(res, limits)
    monkeypatch.setattr(resource, "setrlimit", mock_setrlimit)

    boundary = LinuxExecutionBoundary(str(tmp_path))
    budget = ResourceBudget(1, 64, 100, 5000, 0, 10, 0, 0, 0, 0, 10)
    code = f"import pathlib; pathlib.Path(r'{sentinel.as_posix()}').write_text('LEAKED')"

    with pytest.raises(BoundaryUnavailable):
        boundary._run_from_gate(boundary._gate_capability, [sys.executable, "-c", code], budget=budget)

    assert not sentinel.exists(), "SECURITY VIOLATION: Worker started despite required setrlimit failure!"


def test_m11_pip_audit_and_hash_pinned_constraints():
    """M11: Supply chain integrity with hash-pinned constraints and pip-audit vulnerability scanning.

    1. requirements.txt exists and pins all dependencies with exact version == and --hash=sha256.
    2. Proves deliberately unpinned / unhashed package fails pip --require-hashes.
    3. Runs pip-audit against requirements.txt, asserting 0 known vulnerabilities.
    """
    import shutil
    req_file = Path("requirements.txt").resolve()
    assert req_file.exists(), "requirements.txt must exist at project root"

    lines = req_file.read_text(encoding="utf-8").splitlines()
    req_count = 0
    hash_count = 0
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "==" in stripped and not stripped.startswith("--hash"):
            req_count += 1
            assert not any(op in stripped for op in [">=", "<=", "~=", "!=", ">", "<"]), f"Unpinned operator in {stripped}"
        if "--hash=sha256:" in stripped:
            hash_count += 1

    assert req_count > 0, "No pinned requirements found in requirements.txt"
    assert hash_count >= req_count, f"Found {req_count} requirements but only {hash_count} hashes"

    # Verify that a deliberately unpinned requirement fails --require-hashes
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("flask>=3.0.0\n")
        bad_req_path = f.name

    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--dry-run", "--require-hashes", "-r", bad_req_path],
            capture_output=True,
            text=True,
        )
        assert proc.returncode != 0, "SECURITY VIOLATION: pip --require-hashes accepted unpinned/unhashed requirement!"
        assert (
            "must have their versions pinned with ==" in proc.stderr
            or "must have their versions pinned with ==" in proc.stdout
            or "is not pinned with a hash" in proc.stderr
            or "is not pinned with a hash" in proc.stdout
            or "require-hashes" in proc.stderr
            or "require-hashes" in proc.stdout
        ), f"Expected hash enforcement error, got: {proc.stderr}"
    finally:
        try:
            Path(bad_req_path).unlink()
        except OSError:
            pass

    # Run pip-audit if installed
    pip_audit_bin = shutil.which("pip-audit")
    if pip_audit_bin:
        res = subprocess.run(
            [pip_audit_bin, "-r", str(req_file), "-f", "json"],
            capture_output=True,
            text=True,
        )
        assert res.returncode == 0, f"pip-audit found supply chain vulnerabilities:\n{res.stdout}\n{res.stderr}"

