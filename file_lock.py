"""
OS-Native Kernel Advisory Mutual Exclusion FileLock and NativeLock Primitives.
Zero-dependency, zero-portalocker-runtime cross-platform locking infrastructure.
"""

import os
import sys
import time
import json
import uuid
import socket
import threading
from typing import Optional, Set

# Process-level static caching for metadata building
_CACHED_PID = os.getpid()
_CACHED_HOSTNAME = socket.gethostname()

def _get_process_start_time() -> float:
    """Best-effort process creation timestamp for stale lock validation."""
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes
            kernel32 = ctypes.windll.kernel32
            h_proc = kernel32.GetCurrentProcess()
            ft_create = wintypes.FILETIME()
            ft_exit = wintypes.FILETIME()
            ft_kernel = wintypes.FILETIME()
            ft_user = wintypes.FILETIME()
            if kernel32.GetProcessTimes(h_proc, ctypes.byref(ft_create), ctypes.byref(ft_exit), ctypes.byref(ft_kernel), ctypes.byref(ft_user)):
                intervals = (ft_create.dwHighDateTime << 32) + ft_create.dwLowDateTime
                return (intervals - 116444736000000000) / 10000000.0
        except Exception:
            pass
    elif sys.platform.startswith("linux"):
        try:
            with open(f"/proc/{_CACHED_PID}/stat", "r") as f:
                fields = f.read().split()
                starttime_jiffies = float(fields[21])
                clk_tck = os.sysconf("SC_CLK_TCK")
                with open("/proc/stat", "r") as pf:
                    for line in pf:
                        if line.startswith("btime "):
                            btime = float(line.split()[1])
                            return btime + (starttime_jiffies / clk_tck)
        except Exception:
            pass
    return time.time()

_CACHED_PROC_START = _get_process_start_time()

def _process_exists(pid: int) -> bool:
    """Checks if a process with the given PID is currently running."""
    if pid <= 0:
        return False
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            h_proc = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if h_proc:
                exit_code = ctypes.c_ulong()
                kernel32.GetExitCodeProcess(h_proc, ctypes.byref(exit_code))
                kernel32.CloseHandle(h_proc)
                return exit_code.value == 259  # STILL_ACTIVE = 259
            return False
        except Exception:
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False

# Thread-safe process-local active lock registry
_active_local_locks: Set[str] = set()
_active_locks_guard = threading.Lock()

# Pre-formatted JSON metadata prefix for zero-overhead string formatting
_META_PREFIX = f'{{"status": "active", "pid": {_CACHED_PID}, "host": "{_CACHED_HOSTNAME}", "process_start_time": {_CACHED_PROC_START}, "token": "'

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


def _write_metadata_atomic_exact(fd: int, payload: bytes) -> None:
    """
    Robust POSIX/OS positional metadata writer.
    - Writes exact byte sequence starting at byte offset 0, handling partial writes.
    - Truncates file to exact payload length to prevent stale trailing byte corruption.
    - Propagates all OS write/truncate errors deterministically.
    """
    total_written = 0
    payload_len = len(payload)
    if hasattr(os, "pwrite"):
        while total_written < payload_len:
            written = os.pwrite(fd, payload[total_written:], total_written)
            if written == 0:
                raise IOError("os.pwrite wrote 0 bytes to lock file")
            total_written += written
    else:
        os.lseek(fd, 0, os.SEEK_SET)
        while total_written < payload_len:
            written = os.write(fd, payload[total_written:])
            if written == 0:
                raise IOError("os.write wrote 0 bytes to lock file")
            total_written += written
    os.ftruncate(fd, payload_len)


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
                fd = os.open(self.lock_path, os.O_RDWR | os.O_CREAT, 0o600)
                file_obj = os.fdopen(fd, "r+b")
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
        self.token = uuid.uuid4().hex
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
                os.makedirs(os.path.dirname(self.lock_path), mode=0o700, exist_ok=True)
            except OSError:
                pass

            try:
                fd = os.open(self.lock_path, os.O_RDWR | os.O_CREAT, 0o600)
                file_obj = os.fdopen(fd, "r+b")
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
            t_write0 = time.perf_counter_ns() if self.enable_profiling else 0
            try:
                _write_metadata_atomic_exact(fd, owner_payload)
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
                    t_meta0 = time.perf_counter_ns() if self.enable_profiling else 0
                    if rel_status == "idle":
                        rel_payload = f'{{"status": "idle", "pid": {self.owner_pid}, "token": "{self.token}", "reclaimed_at": {time.time()}}}'.encode("utf-8")
                    else:
                        rel_payload = f'{{"status": "released", "pid": {self.owner_pid}, "token": "{self.token}"}}'.encode("utf-8")
                    if self.enable_profiling:
                        self.profile_timings["json_serialize_exit_ns"] = time.perf_counter_ns() - t_meta0

                    t_write0 = time.perf_counter_ns() if self.enable_profiling else 0
                    if self._fd is not None:
                        _write_metadata_atomic_exact(self._fd, rel_payload)
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
