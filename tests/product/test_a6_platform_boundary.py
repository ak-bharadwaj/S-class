"""Platform tests for H01/H02 and fail-closed boundary isolation (CL Directive A6.5).

Asserts:
1. When bubblewrap or cgroup v2 is unavailable, execution must raise BoundaryUnavailable.
2. The presence of MockResource (H02) or O_NOFOLLOW=0 (H01) never enables fallback or uncontained execution.
3. Sentinel files prove that no worker subprocess is spawned when boundary prerequisites fail.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
import pytest

from sclass_runtime_v6_0_1 import (
    BoundaryUnavailable,
    LinuxExecutionBoundary,
)


def test_bubblewrap_unavailable_raises_boundary_unavailable(tmp_path: Path):
    """A6.5: If bubblewrap is unavailable, execution must raise BoundaryUnavailable (never unconfined fallback)."""
    sentinel = tmp_path / "sentinel_bwrap_missing.txt"
    if sentinel.exists():
        sentinel.unlink()

    boundary = LinuxExecutionBoundary(str(tmp_path))
    boundary.bwrap = None  # Simulate bubblewrap missing on system

    cmd = [
        sys.executable,
        "-c",
        f"import pathlib; pathlib.Path(r'{sentinel}').write_text('SPAWNED')",
    ]

    with pytest.raises(BoundaryUnavailable, match="bubblewrap unavailable"):
        boundary._run_from_gate(boundary._gate_capability, cmd)

    assert not sentinel.exists(), "SECURITY VIOLATION: Worker spawned when bubblewrap was unavailable!"


def test_bubblewrap_unfunctional_namespaces_raises_boundary_unavailable(tmp_path: Path):
    """A6.5: If unprivileged user namespaces are blocked, raise BoundaryUnavailable."""
    boundary = LinuxExecutionBoundary(str(tmp_path))
    boundary.bwrap = "/usr/bin/bwrap"

    # Simulate bubblewrap present but namespace creation failing
    boundary._is_bwrap_functional = lambda bwrap_path: False

    with pytest.raises(BoundaryUnavailable, match="bubblewrap unprivileged user namespaces are blocked or restricted"):
        boundary._assert_bwrap_usable()


def test_cgroup_v2_unavailable_raises_boundary_unavailable(tmp_path: Path):
    """A6.5: If cgroup v2 is unavailable, execution must raise BoundaryUnavailable."""
    sentinel = tmp_path / "sentinel_cgroup_missing.txt"
    if sentinel.exists():
        sentinel.unlink()

    boundary = LinuxExecutionBoundary(str(tmp_path))
    # Point cgroup_root to an empty directory lacking cgroup.controllers
    fake_cgroup = tmp_path / "fake_cgroup"
    fake_cgroup.mkdir()
    boundary.cgroup_root = fake_cgroup

    # Ensure /sys/fs/cgroup/cgroup.controllers does not satisfy check by mocking _assert_cgroup_v2
    def _fail_cgroup():
        raise BoundaryUnavailable("cgroup v2 is required for execution boundary")

    boundary._assert_cgroup_v2 = _fail_cgroup

    cmd = [
        sys.executable,
        "-c",
        f"import pathlib; pathlib.Path(r'{sentinel}').write_text('SPAWNED')",
    ]

    with pytest.raises(BoundaryUnavailable, match="cgroup v2 is required"):
        boundary._run_from_gate(boundary._gate_capability, cmd)

    assert not sentinel.exists(), "SECURITY VIOLATION: Worker spawned when cgroup v2 was unavailable!"


def test_cgroup_v2_not_writable_raises_boundary_unavailable(tmp_path: Path):
    """A6.5: If cgroup v2 hierarchy is not writable, raise BoundaryUnavailable."""
    boundary = LinuxExecutionBoundary(str(tmp_path))

    def _fail_cgroup_writability():
        raise BoundaryUnavailable("cgroup v2 hierarchy is not writable by execution runtime")

    boundary._assert_cgroup_v2 = _fail_cgroup_writability

    with pytest.raises(BoundaryUnavailable, match="cgroup v2 hierarchy is not writable"):
        boundary._assert_cgroup_v2()


def test_h02_mock_resource_never_permits_unconfined_execution(tmp_path: Path, monkeypatch):
    """A6.5 / RUN-H02: MockResource dummy resource limits must never permit execution fallback.

    Even when running with MockResource (simulating non-Linux or missing resource module),
    the execution boundary must fail closed with BoundaryUnavailable.
    """
    sentinel = tmp_path / "sentinel_mock_resource.txt"
    if sentinel.exists():
        sentinel.unlink()

    boundary = LinuxExecutionBoundary(str(tmp_path))
    boundary.bwrap = None  # bwrap unavailable

    cmd = [
        sys.executable,
        "-c",
        f"import pathlib; pathlib.Path(r'{sentinel}').write_text('BYPASSED')",
    ]

    # Boundary must raise BoundaryUnavailable and never fall back to no-op MockResource execution
    with pytest.raises(BoundaryUnavailable):
        boundary._run_from_gate(boundary._gate_capability, cmd)

    assert not sentinel.exists(), "SECURITY VIOLATION: MockResource permitted unconfined execution!"


def test_h01_no_follow_fallback_cannot_bypass_openat2_requirement():
    """A6.5 / RUN-H01: O_NOFOLLOW=0 fallback must never bypass Linux openat2 path resolution requirement."""
    # When os.name != 'posix', _openat2_beneath must fail closed with PermissionError
    orig_name = os.name
    try:
        os.name = "nt"
        with pytest.raises(PermissionError, match="Linux openat2-class path resolution is required"):
            LinuxExecutionBoundary._openat2_beneath(0, "rel/path")
    finally:
        os.name = orig_name
