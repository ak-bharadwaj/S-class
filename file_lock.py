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


# Process-cached static metadata to avoid Win32 Ctypes & socket calls per lock instance
_CACHED_PID = os.getpid()
_CACHED_HOSTNAME = socket.gethostname()
_CACHED_PROC_START = _get_process_start_time(_CACHED_PID)
_META_PREFIX = f'{{"pid": {_CACHED_PID}, "host": "{_CACHED_HOSTNAME}", "process_start_time": {_CACHED_PROC_START}, "token": "'


try:
    import portalocker
    HAS_PORTALOCKER = True
except ImportError:
    HAS_PORTALOCKER = False


def _lock_fd(fd: int) -> bool:
    """Acquires non-blocking kernel advisory lock via OS-native kernel primitive."""
    try:
        if sys.platform == "win32":
            import msvcrt
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except (OSError, IOError):
        return False


def _unlock_fd(fd: int) -> None:
    """Releases kernel advisory lock via OS-native kernel primitive."""
    try:
        if sys.platform == "win32":
            import msvcrt
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_UN)
    except (OSError, IOError):
        pass


class NativeLock:
    """
    Bare OS-native kernel advisory lock primitive matching reference portalocker interface.
    No metadata overhead, no JSON serialization, no extra stat/chmod calls, zero portalocker runtime calls.
    Target: <= 0.5% latency difference from reference portalocker.
    """
    def __init__(self, lock_path: str, timeout: float = 10.0, poll_interval: float = 0.05):
        self.lock_path = os.path.abspath(lock_path)
        self.timeout = timeout
        self.poll_interval = poll_interval
        self._file = None
        self._fd: Optional[int] = None

    def __enter__(self):
        start_time = time.time()
        while True:
            try:
                file_obj = open(self.lock_path, "a+b")
                fd = file_obj.fileno()
            except FileNotFoundError:
                os.makedirs(os.path.dirname(self.lock_path), mode=0o700, exist_ok=True)
                file_obj = open(self.lock_path, "a+b")
                fd = file_obj.fileno()
            except OSError:
                if time.time() - start_time >= self.timeout:
                    raise TimeoutError(f"NativeLock timeout opening file: {self.lock_path}")
                time.sleep(self.poll_interval)
                continue

            if _lock_fd(fd):
                self._file = file_obj
                self._fd = fd
                return self

            try:
                file_obj.close()
            except OSError:
                pass

            if time.time() - start_time >= self.timeout:
                raise TimeoutError(f"NativeLock timeout after {self.timeout}s waiting for lock: {self.lock_path}")
            time.sleep(self.poll_interval)

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._file is not None:
            if self._fd is not None:
                _unlock_fd(self._fd)
            try:
                self._file.close()
            except OSError:
                pass
            self._file = None
            self._fd = None


class FileLock:
    """
    Canonical OS-native kernel advisory mutual exclusion file lock with OS-native msvcrt/fcntl
    backend, diagnostic owner metadata, and thread-safe local activation tracking.
    """
    def __init__(self, lock_path: str, timeout: float = 10.0, poll_interval: float = 0.05, enable_profiling: bool = False):
        self.lock_path = os.path.abspath(lock_path)
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.token = str(uuid.uuid4())
        self.owner_pid = _CACHED_PID
        self.owner_proc_start = _CACHED_PROC_START
        self.enable_profiling = enable_profiling
        self.profile_timings = {}
        self._file = None
        self._fd: Optional[int] = None

    def _lock_handle(self, file_obj) -> bool:
        """Acquires non-blocking kernel advisory lock via native OS."""
        fd = file_obj.fileno() if hasattr(file_obj, "fileno") else file_obj
        return _lock_fd(fd)

    def _unlock_handle(self, file_obj) -> None:
        """Releases kernel advisory lock via native OS."""
        if file_obj is None:
            return
        fd = file_obj.fileno() if hasattr(file_obj, "fileno") else file_obj
        _unlock_fd(fd)

    def __enter__(self):
        t0 = time.perf_counter_ns() if self.enable_profiling else 0
        start_time = time.time()
        
        t_meta0 = time.perf_counter_ns() if self.enable_profiling else 0
        owner_payload = f'{_META_PREFIX}{self.token}", "start_time": {start_time}}}'.encode("utf-8")
        if self.enable_profiling:
            self.profile_timings["json_serialize_enter_ns"] = time.perf_counter_ns() - t_meta0

        while True:
            with _active_locks_guard:
                is_locally_active = self.lock_path in _active_local_locks

            if is_locally_active:
                if time.time() - start_time >= self.timeout:
                    raise TimeoutError(f"Local thread lock timeout after {self.timeout}s waiting for {self.lock_path}")
                time.sleep(self.poll_interval)
                continue

            t_open0 = time.perf_counter_ns() if self.enable_profiling else 0
            try:
                file_obj = open(self.lock_path, "a+b")
                fd = file_obj.fileno()
            except FileNotFoundError:
                os.makedirs(os.path.dirname(self.lock_path), mode=0o700, exist_ok=True)
                file_obj = open(self.lock_path, "a+b")
                fd = file_obj.fileno()
            except OSError:
                if time.time() - start_time >= self.timeout:
                    raise TimeoutError(f"FileLock timeout opening persistent lock file: {self.lock_path}")
                time.sleep(self.poll_interval)
                continue
            if self.enable_profiling:
                self.profile_timings["open_ns"] = time.perf_counter_ns() - t_open0

            t_lock0 = time.perf_counter_ns() if self.enable_profiling else 0
            if not self._lock_handle(file_obj):
                try:
                    file_obj.close()
                except OSError:
                    pass
                if time.time() - start_time >= self.timeout:
                    raise TimeoutError(f"FileLock timeout after {self.timeout}s waiting for live kernel lock owner: {self.lock_path}")
                time.sleep(self.poll_interval)
                continue
            if self.enable_profiling:
                self.profile_timings["lock_ns"] = time.perf_counter_ns() - t_lock0

            # KERNEL ADVISORY LOCK GRANTED!
            try:
                stat_fd = os.fstat(fd)
                stat_path = os.stat(self.lock_path)
                if stat_fd.st_ino != 0 and (stat_fd.st_ino != stat_path.st_ino or stat_fd.st_dev != stat_path.st_dev):
                    self._unlock_handle(file_obj)
                    try:
                        file_obj.close()
                    except OSError:
                        pass
                    continue
            except OSError:
                self._unlock_handle(file_obj)
                try:
                    file_obj.close()
                except OSError:
                    pass
                continue

            t_write0 = time.perf_counter_ns() if self.enable_profiling else 0
            try:
                file_obj.seek(0)
                file_obj.truncate(0)
                file_obj.write(owner_payload)
                file_obj.flush()
            except OSError as err:
                self._unlock_handle(file_obj)
                try:
                    file_obj.close()
                except OSError:
                    pass
                raise err
            if self.enable_profiling:
                self.profile_timings["write_flush_enter_ns"] = time.perf_counter_ns() - t_write0

            self._file = file_obj
            self._fd = fd
            with _active_locks_guard:
                _active_local_locks.add(self.lock_path)
            if self.enable_profiling:
                self.profile_timings["enter_total_ns"] = time.perf_counter_ns() - t0
            return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        t0 = time.perf_counter_ns() if self.enable_profiling else 0
        try:
            if self._file is not None:
                try:
                    rel_status = getattr(self, "_release_status", "released")
                    rel_dict = {"status": rel_status, "pid": self.owner_pid, "token": self.token}
                    if rel_status == "idle":
                        rel_dict["reclaimed_at"] = time.time()
                    
                    t_meta0 = time.perf_counter_ns() if self.enable_profiling else 0
                    rel_payload = json.dumps(rel_dict).encode("utf-8")
                    if self.enable_profiling:
                        self.profile_timings["json_serialize_exit_ns"] = time.perf_counter_ns() - t_meta0

                    t_write0 = time.perf_counter_ns() if self.enable_profiling else 0
                    self._file.seek(0)
                    self._file.truncate(0)
                    self._file.write(rel_payload)
                    self._file.flush()
                    if self.enable_profiling:
                        self.profile_timings["write_flush_exit_ns"] = time.perf_counter_ns() - t_write0
                except OSError:
                    pass

                t_unlock0 = time.perf_counter_ns() if self.enable_profiling else 0
                self._unlock_handle(self._file)
                if self.enable_profiling:
                    self.profile_timings["unlock_ns"] = time.perf_counter_ns() - t_unlock0

                t_close0 = time.perf_counter_ns() if self.enable_profiling else 0
                try:
                    self._file.close()
                except OSError:
                    pass
                if self.enable_profiling:
                    self.profile_timings["close_ns"] = time.perf_counter_ns() - t_close0

                self._file = None
                self._fd = None
        finally:
            with _active_locks_guard:
                _active_local_locks.discard(self.lock_path)
            if self.enable_profiling:
                self.profile_timings["exit_total_ns"] = time.perf_counter_ns() - t0
