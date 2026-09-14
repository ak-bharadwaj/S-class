"""
S-Class Policy: Real OPA Process Runner and Binary Manager.
Provides lifecycle management for real Open Policy Agent (OPA) binaries and daemon processes.

70-85% OSS Reuse:
- Delegates policy evaluation directly to official CNCF OPA binary (v1.20.2+).
- Reuses official OPA server HTTP REST API and CLI runner.
- S-Class owns process supervision, port binding, and health gating.
"""

from __future__ import annotations
import os
import sys
import time
import socket
import shutil
import platform
import subprocess
import urllib.request
import urllib.error
import logging
import tempfile
from typing import Optional, List, Dict, Any

logger = logging.getLogger("sclass.policy.opa_runner")

OPA_VERSION_DEFAULT = "v1.20.2"


def get_default_cache_dir() -> str:
    cache = os.path.expanduser("~/.sclass/bin")
    os.makedirs(cache, exist_ok=True)
    return cache


def find_free_port() -> int:
    """Finds an available TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def ensure_opa_binary(version: str = OPA_VERSION_DEFAULT, target_dir: Optional[str] = None) -> str:
    """
    Locates or automatically downloads the official Open Policy Agent binary.
    Resolution order:
    1. Environment variable SCLASS_OPA_BIN
    2. System PATH (via shutil.which)
    3. User cache directory (~/.sclass/bin/opa or ~/.sclass/bin/opa.exe)
    4. Automatic download from official GitHub release assets
    """
    # 1. SCLASS_OPA_BIN
    env_bin = os.environ.get("SCLASS_OPA_BIN")
    if env_bin:
        if os.path.isfile(env_bin) and os.access(env_bin, os.X_OK):
            return os.path.abspath(env_bin)
        if sys.platform == "win32" and not env_bin.lower().endswith(".exe"):
            env_bin_exe = env_bin + ".exe"
            if os.path.isfile(env_bin_exe) and os.access(env_bin_exe, os.X_OK):
                return os.path.abspath(env_bin_exe)

    # 2. PATH
    bin_name = "opa.exe" if sys.platform == "win32" else "opa"
    which_bin = shutil.which(bin_name) or shutil.which("opa")
    if which_bin and os.path.isfile(which_bin):
        return os.path.abspath(which_bin)

    # 3. Cache directory
    cache_dir = target_dir or get_default_cache_dir()
    cached_exe = os.path.join(cache_dir, bin_name)
    if os.path.isfile(cached_exe) and os.access(cached_exe, os.X_OK):
        return os.path.abspath(cached_exe)

    # 4. Download from official GitHub releases
    logger.info(f"Downloading official OPA binary ({version}) for {sys.platform}...")
    system = sys.platform
    machine = platform.machine().lower()

    if system == "win32":
        asset = "opa_windows_amd64.exe"
    elif system == "darwin":
        asset = "opa_darwin_arm64" if "arm" in machine or "aarch64" in machine else "opa_darwin_amd64"
    else:
        # Default linux
        asset = "opa_linux_amd64_static" if "static" in os.environ.get("SCLASS_OPA_FLAVOR", "") else "opa_linux_amd64"

    url = f"https://github.com/open-policy-agent/opa/releases/download/{version}/{asset}"
    tmp_dest = cached_exe + ".tmp"

    try:
        urllib.request.urlretrieve(url, tmp_dest)
        if os.path.exists(cached_exe):
            try:
                os.remove(cached_exe)
            except OSError:
                pass
        os.replace(tmp_dest, cached_exe)
        if system != "win32":
            os.chmod(cached_exe, 0o755)
        logger.info(f"OPA binary ready at: {cached_exe}")
        return os.path.abspath(cached_exe)
    except Exception as e:
        if os.path.exists(tmp_dest):
            try:
                os.remove(tmp_dest)
            except OSError:
                pass
        raise RuntimeError(
            f"Failed to obtain real OPA binary from {url}: {e}. "
            f"Please install 'opa' in PATH or set SCLASS_OPA_BIN."
        ) from e


class OPAServerProcess:
    """
    Supervises a real OPA daemon process running 'opa run --server'.
    Enforces clean startup verification via /health and guaranteed process termination.
    """

    def __init__(
        self,
        binary_path: Optional[str] = None,
        port: Optional[int] = None,
        policies: Optional[List[str]] = None,
        bundle_path: Optional[str] = None,
        extra_args: Optional[List[str]] = None,
        timeout: float = 5.0,
    ):
        self.binary_path = binary_path or ensure_opa_binary()
        self.port = port or find_free_port()
        self.policies = list(policies or [])
        self.bundle_path = bundle_path
        self.extra_args = list(extra_args or [])
        self.timeout = timeout
        self.process: Optional[subprocess.Popen] = None
        self._url = f"http://127.0.0.1:{self.port}"
        self._stderr_file: Optional[Any] = None
        self._stderr_path: Optional[str] = None

    @property
    def url(self) -> str:
        return self._url

    @property
    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def start(self) -> OPAServerProcess:
        """Starts the real OPA server and waits until /health responds 200."""
        if self.is_running:
            return self

        cmd = [
            self.binary_path,
            "run",
            "--server",
            "--addr",
            f"127.0.0.1:{self.port}",
            "--log-level",
            "error",
        ]
        if self.bundle_path:
            cmd.extend(["--bundle", self.bundle_path])
        for p in self.policies:
            if os.path.exists(p):
                cmd.append(os.path.abspath(p))
        cmd.extend(self.extra_args)

        try:
            self._stderr_file = tempfile.NamedTemporaryFile(mode="w+", encoding="utf-8", delete=False, suffix="_opa_err.log")
            self._stderr_path = self._stderr_file.name
        except Exception:
            self._stderr_file = None
            self._stderr_path = None

        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=self._stderr_file or subprocess.DEVNULL,
        )

        # Wait for health check
        deadline = time.time() + self.timeout
        health_url = f"{self._url}/health"
        last_err = None

        while time.time() < deadline:
            if self.process.poll() is not None:
                err_detail = ""
                if self._stderr_file:
                    try:
                        self._stderr_file.seek(0)
                        err_detail = self._stderr_file.read().strip()
                    except Exception:
                        pass
                detail_str = f": {err_detail}" if err_detail else ""
                self.stop()
                raise RuntimeError(f"OPA process exited prematurely with code {self.process.returncode}{detail_str}")
            try:
                req = urllib.request.Request(health_url, headers={"User-Agent": "S-Class-OPA"})
                with urllib.request.urlopen(req, timeout=0.5) as resp:
                    if resp.status == 200:
                        return self
            except Exception as ex:
                last_err = ex
            time.sleep(0.05)

        self.stop()
        raise TimeoutError(f"OPA server on {self._url} did not become healthy within {self.timeout}s: {last_err}")

    def stop(self) -> None:
        """Stops the supervised OPA daemon."""
        if self.process is not None:
            try:
                if self.process.poll() is None:
                    self.process.terminate()
                    try:
                        self.process.wait(timeout=2.0)
                    except subprocess.TimeoutExpired:
                        self.process.kill()
                        self.process.wait()
            except Exception:
                pass
            finally:
                self.process = None

        if self._stderr_file is not None:
            try:
                self._stderr_file.close()
            except Exception:
                pass
            self._stderr_file = None

        if self._stderr_path is not None and os.path.exists(self._stderr_path):
            try:
                os.remove(self._stderr_path)
            except Exception:
                pass
            self._stderr_path = None

    def __enter__(self) -> OPAServerProcess:
        return self.start()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()
