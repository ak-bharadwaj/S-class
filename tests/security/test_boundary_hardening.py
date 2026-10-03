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
