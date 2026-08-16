#!/usr/bin/env python3
"""
S-Class EOS V11.2 - Canonical Hardware & OS Mutual Exclusion FileLock Engine (Layer 0)

Architecture & Contract:
1. Authoritative Mutual Exclusion:
   - The OS kernel advisory lock (msvcrt.locking on Windows, fcntl.flock on POSIX) is the
     SOLE authoritative gate for mutual exclusion across processes.
   - When a process exits, terminates, or crashes, the OS automatically closes file descriptors
     and releases the kernel lock, guaranteeing crash resilience without unsafe secondary authorities.

2. Diagnostic & Audit Metadata:
   - On lock acquisition, owner metadata (PID, UUID token, hostname, timestamp) is written atomically
     to the lock file while holding the kernel lock.
   - This metadata is strictly for diagnostics, audit trails, and tooling (e.g. doctor, monitoring),
     never as a secondary ownership authority.

3. Process-Local Thread Safety:
   - Process-local thread tracking (_active_local_locks) ensures concurrent threads within the same
     Python runtime serialize access deterministically.
"""

import os
import sys
import json
import uuid
import time
import socket
import logging
import threading
from typing import Optional, Set

logger = logging.getLogger("file_lock")

_active_local_locks: Set[str] = set()
_active_locks_guard = threading.Lock()


def _process_exists(pid: int) -> bool:
    """Verifies whether an OS process with the given PID is actively running (diagnostic utility)."""
    if pid <= 0:
        return False
    if sys.platform == "win32":
        try:
            import ctypes
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if handle:
                exit_code = ctypes.c_ulong()
                if kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                    is_active = (exit_code.value == 259)  # 259 = STILL_ACTIVE
                    kernel32.CloseHandle(handle)
                    return is_active
                kernel32.CloseHandle(handle)
                return True
            err = kernel32.GetLastError()
            if err == 5:  # Access Denied -> system/privileged process exists
                return True
            return False
        except Exception:
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def _get_process_start_time(pid: int) -> Optional[float]:
    """Retrieves process creation timestamp (epoch seconds) for diagnostic audit trails."""
    if pid <= 0:
        return None
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes
            class FILETIME(ctypes.Structure):
                _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if handle:
                create_time = FILETIME()
                exit_time = FILETIME()
                kernel_time = FILETIME()
                user_time = FILETIME()
                res = kernel32.GetProcessTimes(
                    handle,
                    ctypes.byref(create_time),
                    ctypes.byref(exit_time),
                    ctypes.byref(kernel_time),
                    ctypes.byref(user_time)
                )
                kernel32.CloseHandle(handle)
                if res:
                    ft64 = (create_time.dwHighDateTime << 32) + create_time.dwLowDateTime
                    return (ft64 - 116444736000000000) / 10000000.0
        except Exception:
            return None
    else:
        try:
            proc_path = f"/proc/{pid}"
            if os.path.exists(proc_path):
                return os.path.getmtime(proc_path)
        except Exception:
            return None
    return None


class FileLock:
    """
    Canonical OS-native kernel advisory mutual exclusion file lock (msvcrt.locking / fcntl.flock)
    with diagnostic owner metadata and thread-safe local activation tracking.
    """
    def __init__(self, lock_path: str, timeout: float = 10.0):
        self.lock_path = os.path.abspath(lock_path)
        self.timeout = timeout
        self.token = str(uuid.uuid4())
        self.owner_pid = os.getpid()
        self.owner_proc_start = _get_process_start_time(self.owner_pid)
        self._fd: Optional[int] = None

    def _lock_handle(self, fd: int) -> bool:
        """Acquires OS-native non-blocking kernel advisory lock."""
        try:
            if sys.platform == "win32":
                import msvcrt
                # Lock byte offset 0x7FFFFFFF (2GB) so byte range 0-1MB remains completely free for unhindered ftruncate and metadata writing
                os.lseek(fd, 0x7FFFFFFF, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                os.lseek(fd, 0, os.SEEK_SET)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except (OSError, IOError):
            return False

    def _unlock_handle(self, fd: int) -> None:
        """Releases OS-native kernel advisory lock."""
        try:
            if sys.platform == "win32":
                import msvcrt
                os.lseek(fd, 0x7FFFFFFF, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                os.lseek(fd, 0, os.SEEK_SET)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_UN)
        except (OSError, IOError):
            pass

    def __enter__(self):
        start_time = time.time()
        owner_payload = json.dumps({
            "pid": self.owner_pid,
            "token": self.token,
            "host": socket.gethostname(),
            "start_time": start_time,
            "process_start_time": self.owner_proc_start
        }).encode("utf-8")

        dir_path = os.path.dirname(self.lock_path)
        os.makedirs(dir_path, mode=0o700, exist_ok=True)
        try:
            os.chmod(dir_path, 0o700)
        except OSError:
            pass

        while True:
            # Enforce local thread-safe activation tracking within same process
            with _active_locks_guard:
                is_locally_active = self.lock_path in _active_local_locks

            if is_locally_active:
                if time.time() - start_time >= self.timeout:
                    raise TimeoutError(f"Local thread lock timeout after {self.timeout}s waiting for {self.lock_path}")
                time.sleep(0.05)
                continue

            try:
                # Open or create persistent lock file with owner-only permissions (0o600)
                fd = os.open(self.lock_path, os.O_CREAT | os.O_RDWR, 0o600)
                try:
                    os.chmod(self.lock_path, 0o600)
                except OSError:
                    pass
            except OSError:
                if time.time() - start_time >= self.timeout:
                    raise TimeoutError(f"FileLock timeout opening persistent lock file: {self.lock_path}")
                time.sleep(0.05)
                continue

            # Attempt OS-native non-blocking kernel advisory lock on persistent file descriptor
            if not self._lock_handle(fd):
                try:
                    os.close(fd)
                except OSError:
                    pass
                if time.time() - start_time >= self.timeout:
                    raise TimeoutError(f"FileLock timeout after {self.timeout}s waiting for live kernel lock owner: {self.lock_path}")
                time.sleep(0.05)
                continue

            # KERNEL ADVISORY LOCK GRANTED!
            # Verify that the locked descriptor still matches the file on disk (guards against unlinks/recreations)
            try:
                stat_fd = os.fstat(fd)
                stat_path = os.stat(self.lock_path)
                if stat_fd.st_ino != 0 and (stat_fd.st_ino != stat_path.st_ino or stat_fd.st_dev != stat_path.st_dev):
                    # Stale inode detected - file was unlinked/recreated before acquisition
                    self._unlock_handle(fd)
                    try:
                        os.close(fd)
                    except OSError:
                        pass
                    continue
            except OSError:
                # File was unlinked between open and lock
                self._unlock_handle(fd)
                try:
                    os.close(fd)
                except OSError:
                    pass
                continue

            try:
                os.ftruncate(fd, 0)
                os.lseek(fd, 0, os.SEEK_SET)
                os.write(fd, owner_payload)
                os.fsync(fd)
            except OSError as err:
                self._unlock_handle(fd)
                try:
                    os.close(fd)
                except OSError:
                    pass
                raise err

            self._fd = fd
            with _active_locks_guard:
                _active_local_locks.add(self.lock_path)
            return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if self._fd is not None:
                # 1. Update metadata payload to "released" state while STILL HOLDING kernel lock
                try:
                    rel_payload = json.dumps({"status": "released", "pid": self.owner_pid, "token": self.token}).encode("utf-8")
                    os.ftruncate(self._fd, 0)
                    os.lseek(self._fd, 0, os.SEEK_SET)
                    os.write(self._fd, rel_payload)
                    os.fsync(self._fd)
                except OSError:
                    pass

                # 2. Release OS-native kernel advisory lock
                self._unlock_handle(self._fd)

                # 3. Close persistent file descriptor
                try:
                    os.close(self._fd)
                except OSError:
                    pass
        finally:
            with _active_locks_guard:
                _active_local_locks.discard(self.lock_path)
