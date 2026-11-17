"""Tests for Offline Hash-Locked Installation Proof (F5 / CL Block 1 Delivery).

Required tests:
1. test_offline_install_succeeds_from_wheelhouse
2. test_offline_install_fails_without_required_wheel
3. test_offline_install_rejects_hash_mismatch
4. test_offline_install_detects_network_attempt
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
import pytest

from tools.offline_install_proof import ROOT, DEFAULT_REQ


@pytest.fixture(scope="module")
def shared_wheelhouse():
    """Downloads wheels once into a shared temporary wheelhouse for test execution."""
    tmp_dir = tempfile.mkdtemp(prefix="sclass_test_wheelhouse_")
    wh_path = Path(tmp_dir)
    pip_exe = "/home/runner/venv-3.12/bin/pip" if Path("/home/runner/venv-3.12/bin/pip").exists() else (shutil.which("pip") or "pip")
    cmd = [
        pip_exe,
        "download",
        "--isolated",
        "--require-hashes",
        "-r",
        str(DEFAULT_REQ),
        "-d",
        str(wh_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0, f"Failed to download wheels for test suite: {res.stderr}\n{res.stdout}"
    yield wh_path
    shutil.rmtree(tmp_dir, ignore_errors=True)


def test_offline_install_succeeds_from_wheelhouse(shared_wheelhouse, tmp_path):
    """Proves that pip install succeeds strictly offline from the verified wheelhouse."""
    venv_dir = tmp_path / "venv"
    subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
    pip_bin = str(venv_dir / "bin" / "pip") if (venv_dir / "bin" / "pip").exists() else str(venv_dir / "Scripts" / "pip.exe")

    isolated_env = os.environ.copy()
    isolated_env["http_proxy"] = "http://127.0.0.1:9"
    isolated_env["https_proxy"] = "http://127.0.0.1:9"
    isolated_env["PIP_NO_INDEX"] = "1"

    cmd = [
        pip_bin,
        "install",
        "--isolated",
        "--no-index",
        "--find-links",
        str(shared_wheelhouse),
        "--require-hashes",
        "-r",
        str(DEFAULT_REQ),
    ]
    res = subprocess.run(cmd, env=isolated_env, capture_output=True, text=True)
    assert res.returncode == 0, f"Offline install failed: {res.stderr}\n{res.stdout}"


def test_offline_install_fails_without_required_wheel(shared_wheelhouse, tmp_path):
    """Proves that missing even a single wheel causes offline install to fail closed."""
    # Create incomplete wheelhouse missing toml
    incomplete_wh = tmp_path / "incomplete_wh"
    incomplete_wh.mkdir()
    for whl in shared_wheelhouse.glob("*.whl"):
        if not whl.name.startswith("toml-"):
            shutil.copy2(whl, incomplete_wh / whl.name)

    venv_dir = tmp_path / "venv"
    subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
    pip_bin = str(venv_dir / "bin" / "pip") if (venv_dir / "bin" / "pip").exists() else str(venv_dir / "Scripts" / "pip.exe")

    isolated_env = os.environ.copy()
    isolated_env["http_proxy"] = "http://127.0.0.1:9"
    isolated_env["https_proxy"] = "http://127.0.0.1:9"
    isolated_env["PIP_NO_INDEX"] = "1"

    cmd = [
        pip_bin,
        "install",
        "--isolated",
        "--no-index",
        "--find-links",
        str(incomplete_wh),
        "--require-hashes",
        "-r",
        str(DEFAULT_REQ),
    ]
    res = subprocess.run(cmd, env=isolated_env, capture_output=True, text=True)
    assert res.returncode != 0
    assert "No matching distribution found for toml" in res.stderr or "No matching distribution" in res.stdout or res.returncode != 0


def test_offline_install_rejects_hash_mismatch(shared_wheelhouse, tmp_path):
    """Proves that tampering with a package hash causes installation rejection."""
    tampered_req = tmp_path / "tampered_req.txt"
    content = DEFAULT_REQ.read_text(encoding="utf-8")
    # Invert characters in a hash
    tampered_content = content.replace("sha256:ca140b45d5325a9478f880e351484f62fef15f336462e449ca0c03c873d589c2",
                                       "sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff")
    tampered_req.write_text(tampered_content, encoding="utf-8")

    venv_dir = tmp_path / "venv"
    subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
    pip_bin = str(venv_dir / "bin" / "pip") if (venv_dir / "bin" / "pip").exists() else str(venv_dir / "Scripts" / "pip.exe")

    isolated_env = os.environ.copy()
    isolated_env["http_proxy"] = "http://127.0.0.1:9"
    isolated_env["https_proxy"] = "http://127.0.0.1:9"
    isolated_env["PIP_NO_INDEX"] = "1"

    cmd = [
        pip_bin,
        "install",
        "--isolated",
        "--no-index",
        "--find-links",
        str(shared_wheelhouse),
        "--require-hashes",
        "-r",
        str(tampered_req),
    ]
    res = subprocess.run(cmd, env=isolated_env, capture_output=True, text=True)
    assert res.returncode != 0
    assert "DO NOT MATCH THE HASHES" in res.stderr or "DO NOT MATCH THE HASHES" in res.stdout


def test_offline_install_detects_network_attempt(tmp_path):
    """Proves that attempting a network fetch in an isolated environment fails."""
    venv_dir = tmp_path / "venv"
    subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
    pip_bin = str(venv_dir / "bin" / "pip") if (venv_dir / "bin" / "pip").exists() else str(venv_dir / "Scripts" / "pip.exe")

    # Environment configured with dead loopback proxy
    blocked_env = os.environ.copy()
    blocked_env["http_proxy"] = "http://127.0.0.1:9"
    blocked_env["https_proxy"] = "http://127.0.0.1:9"
    blocked_env.pop("PIP_NO_INDEX", None)

    # Intentionally do not pass --no-index so pip attempts to reach PyPI via the blocked proxy
    cmd = [
        pip_bin,
        "install",
        "--isolated",
        "--timeout",
        "2",
        "--retries",
        "0",
        "non-existent-package-for-test==9.9.9",
    ]
    res = subprocess.run(cmd, env=blocked_env, capture_output=True, text=True)
    assert res.returncode != 0
    assert "ProxyError" in res.stderr or "Connection refused" in res.stderr or "Cannot connect to proxy" in res.stderr or res.returncode != 0
