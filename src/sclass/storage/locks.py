"""
S-Class Storage: Cross-Process File Locking.
Ensures atomic state transitions and journal writes across concurrent processes.
"""

from __future__ import annotations
import os
import time
from typing import Optional

try:
    import portalocker
    HAS_PORTALOCKER = True
except ImportError:
    HAS_PORTALOCKER = False

from sclass.storage.paths import WorkspacePaths


class WorkspaceLock:
    """Acquires a cross-process file lock within the workspace locks directory."""

    def __init__(self, workspace_dir: str, lock_name: str = "state", timeout: float = 10.0):
        self.paths = WorkspacePaths(workspace_dir)
        self.lock_name = lock_name
        self.timeout = timeout
        self.lock_file = os.path.join(self.paths.locks_dir, f"{lock_name}.lock")
        self._fp = None

    def __enter__(self) -> WorkspaceLock:
        self.paths.ensure_directories()
        start = time.time()
        while True:
            try:
                self._fp = open(self.lock_file, "a+", encoding="utf-8")
                if HAS_PORTALOCKER:
                    portalocker.lock(self._fp, portalocker.LOCK_EX | portalocker.LOCK_NB)
                return self
            except (OSError, IOError):
                if self._fp:
                    try:
                        self._fp.close()
                    except Exception:
                        pass
                    self._fp = None
                if time.time() - start > self.timeout:
                    raise TimeoutError(f"Timed out waiting to acquire S-Class workspace lock: {self.lock_file}")
                time.sleep(0.05)

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._fp:
            try:
                if HAS_PORTALOCKER:
                    portalocker.unlock(self._fp)
                self._fp.close()
            except Exception:
                pass
            finally:
                self._fp = None
