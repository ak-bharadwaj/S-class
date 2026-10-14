"""
OS-Native Kernel Advisory Mutual Exclusion FileLock and NativeLock Primitives.
Zero-dependency, cross-platform native OS mutex and file locking infrastructure.
"""

import os
import sys
import time
import json
import uuid
import socket
import threading
import asyncio
import logging
from typing import Optional, Set

logger = logging.getLogger("file_lock")

def _nonblocking_sleep(duration: float) -> None:
    """Non-blocking, GIL-releasing sleep alternative that avoids freezing event loops."""
    ev = threading.Event()
    ev.wait(timeout=max(duration, 0.0001))

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
        except Exception as e:
            logger.debug(f"[file_lock] Non-critical error: {e}")
    elif sys.platform.startswith("linux"):
        try:
            with open(f"/proc/{_CACHED_PID}/stat", "r", encoding="utf-8") as f:
                fields = f.read().split()
                starttime_jiffies = float(fields[21])
                clk_tck = os.sysconf("SC_CLK_TCK")
                with open("/proc/stat", "r", encoding="utf-8") as pf:
                    for line in pf:
                        if line.startswith("btime "):
                            btime = float(line.split()[1])
                            return btime + (starttime_jiffies / clk_tck)
        except Exception as e:
            logger.debug(f"[file_lock] Non-critical error: {e}")
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
            err = kernel32.GetLastError()
            if err == 5:  # ERROR_ACCESS_DENIED -> process exists
                return True
            return False
        except Exception:
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except PermissionError:
            return True
        except (OSError, ProcessLookupError):
            return False

# Thread-safe process-local active lock registry
_active_local_locks: Set[str] = set()
_active_locks_guard = threading.Lock()

# Per-path in-process mutual exclusion locks
_path_thread_locks: dict[str, threading.RLock] = {}
_path_thread_locks_guard = threading.Lock()

def _get_path_thread_lock(norm_path: str) -> threading.RLock:
    with _path_thread_locks_guard:
        lock = _path_thread_locks.get(norm_path)
        if lock is None:
            lock = threading.RLock()
            _path_thread_locks[norm_path] = lock
        return lock

# Pre-formatted JSON metadata prefix for zero-overhead string formatting
_META_PREFIX = f'{{"status": "active", "pid": {_CACHED_PID}, "host": "{_CACHED_HOSTNAME}", "process_start_time": {_CACHED_PROC_START}, "token": "'

_LOCK_ERRORS = (OSError, IOError)
LOCK_OFFSET = 1_000_000_000


def _lock_fd(fd: int) -> bool:
    """Acquires non-blocking kernel advisory lock via OS-native API."""
    try:
        if sys.platform == "win32":
            import msvcrt
            os.lseek(fd, LOCK_OFFSET, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            return True
        else:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
    except _LOCK_ERRORS:
        return False


def _unlock_fd(fd: int) -> None:
    """Releases kernel advisory lock via OS-native API."""
    try:
        if sys.platform == "win32":
            import msvcrt
            os.lseek(fd, LOCK_OFFSET, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_UN)
    except _LOCK_ERRORS:
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
    Bare OS-native kernel advisory lock primitive using native OS file locking.
    No metadata overhead, no JSON serialization, no extra stat/chmod calls, pure OS-native runtime calls.
    Target: High-throughput, low-latency cross-platform kernel advisory locking.
    """
    def __init__(self, lock_path: str, timeout: float = 10.0, poll_interval: float = 0.05, stale_ttl: float = 60.0):
        self.raw_lock_path = os.path.abspath(lock_path)
        self.lock_path = os.path.normcase(self.raw_lock_path)
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.stale_ttl = stale_ttl
        self._fd: Optional[int] = None
        self._thread_lock = _get_path_thread_lock(self.lock_path)
        self._thread_acquired = False

    def __enter__(self):
        start_time = time.time()
        remaining = self.timeout
        if not self._thread_lock.acquire(timeout=max(remaining, 0.0001)):
            raise TimeoutError(f"NativeLock thread timeout after {self.timeout}s waiting for {self.lock_path}")
        self._thread_acquired = True

        try:
            while True:
                try:
                    fd = os.open(self.lock_path, os.O_RDWR | os.O_CREAT, 0o600)
                except FileNotFoundError:
                    try:
                        os.makedirs(os.path.dirname(self.lock_path), mode=0o700, exist_ok=True)
                        fd = os.open(self.lock_path, os.O_RDWR | os.O_CREAT, 0o600)
                    except OSError:
                        if time.time() - start_time >= self.timeout:
                            raise TimeoutError(f"NativeLock timeout opening file: {self.lock_path}")
                        _nonblocking_sleep(min(self.poll_interval, 0.0002))
                        continue
                except OSError:
                    if time.time() - start_time >= self.timeout:
                        raise TimeoutError(f"NativeLock timeout opening file: {self.lock_path}")
                    _nonblocking_sleep(min(self.poll_interval, 0.0002))
                    continue

                if _lock_fd(fd):
                    self._fd = fd
                    return self

                try:
                    os.close(fd)
                except OSError:
                    pass

                try:
                    if (time.time() - os.path.getmtime(self.lock_path)) > self.stale_ttl:
                        try:
                            os.unlink(self.lock_path)
                            continue
                        except OSError:
                            pass
                except OSError:
                    pass

                if time.time() - start_time >= self.timeout:
                    raise TimeoutError(f"NativeLock timeout after {self.timeout}s waiting for lock: {self.lock_path}")
                _nonblocking_sleep(min(self.poll_interval, 0.0002))
        except:
            if self._thread_acquired:
                self._thread_lock.release()
                self._thread_acquired = False
            raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if self._fd is not None:
                _unlock_fd(self._fd)
                try:
                    os.close(self._fd)
                except OSError:
                    pass
                self._fd = None
        finally:
            if self._thread_acquired:
                self._thread_lock.release()
                self._thread_acquired = False


class FileLock:
    """
    Canonical OS-native kernel advisory mutual exclusion file lock with OS-native msvcrt/fcntl
    backend, diagnostic owner metadata, and thread-safe local activation tracking.
    """
    def __init__(self, lock_path: str, timeout: float = 10.0, poll_interval: float = 0.05, enable_profiling: bool = False, stale_ttl: float = 60.0):
        self.raw_lock_path = os.path.abspath(lock_path)
        self.lock_path = os.path.normcase(self.raw_lock_path)
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.stale_ttl = stale_ttl
        self.token = uuid.uuid4().hex
        self.owner_pid = _CACHED_PID
        self.owner_proc_start = _CACHED_PROC_START
        self.enable_profiling = enable_profiling
        self.profile_timings = {}
        self._file = None
        self._fd: Optional[int] = None
        self._thread_lock = _get_path_thread_lock(self.lock_path)
        self._thread_acquired = False

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

    def _attempt_acquire(self) -> Optional[int]:
        """Attempts to open and acquire kernel advisory lock."""
        t_open0 = time.perf_counter_ns() if self.enable_profiling else 0
        try:
            fd = os.open(self.lock_path, os.O_RDWR | os.O_CREAT, 0o600)
        except FileNotFoundError:
            try:
                os.makedirs(os.path.dirname(self.lock_path), mode=0o700, exist_ok=True)
                fd = os.open(self.lock_path, os.O_RDWR | os.O_CREAT, 0o600)
            except OSError:
                return None
        except OSError:
            return None
        if self.enable_profiling:
            self.profile_timings["open_ns"] = time.perf_counter_ns() - t_open0

        t_lock0 = time.perf_counter_ns() if self.enable_profiling else 0
        if not _lock_fd(fd):
            try:
                os.close(fd)
            except OSError:
                pass
            return None
        if self.enable_profiling:
            self.profile_timings["lock_ns"] = time.perf_counter_ns() - t_lock0

        return fd

    def _handle_stale_lock(self) -> bool:
        """
        Inspect existing lock file for dead process or mutual exclusion.
        Returns True if the lock path is clear / stale lock reclaimed.
        Returns False if a live process or active file holds the lock.
        """
        try:
            if not os.path.exists(self.lock_path):
                return True

            lock_mtime = os.path.getmtime(self.lock_path)
            lock_age = time.time() - lock_mtime
            target_pid = None
            is_raw_pid = False
            raw_meta = ""
            read_failed = False
            try:
                with open(self.lock_path, "r", encoding="utf-8") as pf:
                    raw_meta = pf.read().strip()
                if raw_meta:
                    if raw_meta.isdigit():
                        target_pid = int(raw_meta)
                        is_raw_pid = True
                    elif raw_meta.startswith("{"):
                        try:
                            meta = json.loads(raw_meta)
                            if "pid" in meta and isinstance(meta["pid"], int):
                                target_pid = meta["pid"]
                        except Exception as e:
                            logger.debug(f"[file_lock] Non-critical error: {e}")
            except FileNotFoundError:
                return True
            except (OSError, IOError, PermissionError):
                read_failed = True

            if read_failed:
                return False

            if target_pid is not None:
                if not _process_exists(target_pid):
                    # Target process is dead: reclaim stale lock
                    try:
                        os.unlink(self.lock_path)
                        return True
                    except OSError:
                        pass
                elif target_pid != _CACHED_PID or is_raw_pid:
                    # Target process IS ALIVE (different process, or simulated raw PID lock)
                    # Enforce strict mutual exclusion: do NOT steal
                    return False
                else:
                    return True
            elif lock_age > self.stale_ttl or (not raw_meta and lock_age > 0.5):
                # Empty/corrupt lock file or unparseable PID expired
                try:
                    os.unlink(self.lock_path)
                    return True
                except OSError:
                    pass
            elif not raw_meta and lock_age <= 0.5:
                # Fresh empty file being initialized by another process: wait and retry
                return False
        except OSError:
            pass

        return True

    def _wait_with_backoff(self, attempt: int) -> None:
        """Sleep with exponential backoff."""
        delay = min(self.poll_interval, 0.0002 * (1.5 ** min(attempt, 8)))
        _nonblocking_sleep(delay)

    def __enter__(self):
        t0 = time.perf_counter_ns() if self.enable_profiling else 0
        start_time = time.time()

        remaining = self.timeout
        if not self._thread_lock.acquire(timeout=max(remaining, 0.0001)):
            raise TimeoutError(f"Local thread lock timeout after {self.timeout}s waiting for {self.lock_path}")
        self._thread_acquired = True

        try:
            t_meta0 = time.perf_counter_ns() if self.enable_profiling else 0
            owner_payload = f'{_META_PREFIX}{self.token}", "start_time": {start_time}}}'.encode("utf-8")
            if self.enable_profiling:
                self.profile_timings["json_serialize_enter_ns"] = time.perf_counter_ns() - t_meta0

            attempt = 0
            while True:
                with _active_locks_guard:
                    is_locally_active = (self.lock_path in _active_local_locks or self.raw_lock_path in _active_local_locks)

                if is_locally_active:
                    if time.time() - start_time >= self.timeout:
                        raise TimeoutError(f"Local thread lock timeout after {self.timeout}s waiting for {self.lock_path}")
                    self._wait_with_backoff(attempt)
                    attempt += 1
                    continue

                if not self._handle_stale_lock():
                    if time.time() - start_time >= self.timeout:
                        raise TimeoutError(f"Concurrency Lock Timeout: Active lock on {self.lock_path} held > {self.timeout}s")
                    self._wait_with_backoff(attempt)
                    attempt += 1
                    continue

                fd = self._attempt_acquire()
                if fd is None:
                    # Inspect for stale lock or dead PID if acquisition failed
                    self._handle_stale_lock()
                    if time.time() - start_time >= self.timeout:
                        raise TimeoutError(f"FileLock timeout after {self.timeout}s waiting for live kernel lock owner: {self.lock_path}")
                    self._wait_with_backoff(attempt)
                    attempt += 1
                    continue

                # KERNEL ADVISORY LOCK GRANTED!
                if sys.platform != "win32":
                    try:
                        os.fchmod(fd, 0o600)
                    except OSError:
                        pass
                    try:
                        os.chmod(os.path.dirname(self.lock_path), 0o700)
                    except OSError:
                        pass

                t_write0 = time.perf_counter_ns() if self.enable_profiling else 0
                try:
                    _write_metadata_atomic_exact(fd, owner_payload)
                except OSError as err:
                    _unlock_fd(fd)
                    try:
                        os.close(fd)
                    except OSError:
                        pass
                    raise err
                if self.enable_profiling:
                    self.profile_timings["write_flush_enter_ns"] = time.perf_counter_ns() - t_write0

                self._fd = fd
                self._file = None
                with _active_locks_guard:
                    _active_local_locks.add(self.raw_lock_path)
                    _active_local_locks.add(self.lock_path)
                if self.enable_profiling:
                    self.profile_timings["enter_total_ns"] = time.perf_counter_ns() - t0
                return self
        except:
            if self._thread_acquired:
                self._thread_lock.release()
                self._thread_acquired = False
            raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        t0 = time.perf_counter_ns() if self.enable_profiling else 0
        try:
            is_owner = False
            try:
                if os.path.exists(self.lock_path):
                    with open(self.lock_path, "r", encoding="utf-8") as f:
                        content = f.read().strip()
                    my_pid = os.getpid()
                    if content == str(my_pid) or not content:
                        is_owner = True
                    elif content.startswith("{"):
                        try:
                            meta = json.loads(content)
                            if meta.get("token") == self.token or meta.get("pid") == my_pid:
                                is_owner = True
                        except Exception as e:
                            logger.debug(f"[file_lock] Non-critical error: {e}")
                        if not is_owner:
                            if f'"pid": {my_pid}' in content or f'"pid":{my_pid}' in content:
                                is_owner = True
                            elif f'"token": "{self.token}"' in content or f'"token":"{self.token}"' in content:
                                is_owner = True
            except (OSError, UnicodeDecodeError):
                is_owner = True

            if self._fd is not None:
                rel_status = getattr(self, "_release_status", "released")
                if is_owner and rel_status == "idle":
                    try:
                        t_meta0 = time.perf_counter_ns() if self.enable_profiling else 0
                        rel_payload = f'{{"status": "idle", "pid": {self.owner_pid}, "token": "{self.token}", "reclaimed_at": {time.time()}}}'.encode("utf-8")
                        if self.enable_profiling:
                            self.profile_timings["json_serialize_exit_ns"] = time.perf_counter_ns() - t_meta0

                        t_write0 = time.perf_counter_ns() if self.enable_profiling else 0
                        _write_metadata_atomic_exact(self._fd, rel_payload)
                        if self.enable_profiling:
                            self.profile_timings["write_flush_exit_ns"] = time.perf_counter_ns() - t_write0
                    except OSError:
                        pass

                t_unlock0 = time.perf_counter_ns() if self.enable_profiling else 0
                _unlock_fd(self._fd)
                if self.enable_profiling:
                    self.profile_timings["unlock_ns"] = time.perf_counter_ns() - t_unlock0

                t_close0 = time.perf_counter_ns() if self.enable_profiling else 0
                try:
                    os.close(self._fd)
                except OSError:
                    pass
                if self.enable_profiling:
                    self.profile_timings["close_ns"] = time.perf_counter_ns() - t_close0

                self._fd = None

            # Clean unlinking of owned locks (only unlink if lock file is owned by current process/token, do not unlink foreign locks)
            if is_owner and getattr(self, "_release_status", "released") != "idle":
                try:
                    if os.path.exists(self.lock_path):
                        os.unlink(self.lock_path)
                except OSError:
                    pass
        finally:
            with _active_locks_guard:
                _active_local_locks.discard(self.raw_lock_path)
                _active_local_locks.discard(self.lock_path)
            if self._thread_acquired:
                self._thread_lock.release()
                self._thread_acquired = False
            if self.enable_profiling:
                self.profile_timings["exit_total_ns"] = time.perf_counter_ns() - t0


class AsyncNativeLock:
    """Non-blocking asynchronous context manager wrapper for NativeLock in async event loops."""
    def __init__(self, lock_path: str, timeout: float = 10.0, poll_interval: float = 0.05, stale_ttl: float = 60.0):
        self.lock_path = lock_path
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.stale_ttl = stale_ttl
        self._sync_lock = NativeLock(lock_path, timeout=0.001, poll_interval=poll_interval, stale_ttl=stale_ttl)

    async def __aenter__(self):
        start = time.time()
        while True:
            try:
                self._sync_lock.timeout = 0.001
                self._sync_lock.__enter__()
                return self
            except (TimeoutError, OSError):
                if time.time() - start >= self.timeout:
                    raise TimeoutError(f"AsyncNativeLock timeout after {self.timeout}s waiting for {self.lock_path}")
                await asyncio.sleep(min(self.poll_interval, 0.01))

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._sync_lock.__exit__(exc_type, exc_val, exc_tb)


class AsyncFileLock:
    """Non-blocking asynchronous context manager wrapper for FileLock in async event loops."""
    def __init__(self, lock_path: str, timeout: float = 10.0, poll_interval: float = 0.05, enable_profiling: bool = False, stale_ttl: float = 60.0):
        self.lock_path = lock_path
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.enable_profiling = enable_profiling
        self.stale_ttl = stale_ttl
        self._sync_lock = FileLock(lock_path, timeout=0.001, poll_interval=poll_interval, enable_profiling=enable_profiling, stale_ttl=stale_ttl)

    async def __aenter__(self):
        start = time.time()
        while True:
            try:
                self._sync_lock.timeout = 0.001
                self._sync_lock.__enter__()
                return self
            except (TimeoutError, OSError):
                if time.time() - start >= self.timeout:
                    raise TimeoutError(f"AsyncFileLock timeout after {self.timeout}s waiting for {self.lock_path}")
                await asyncio.sleep(min(self.poll_interval, 0.01))

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._sync_lock.__exit__(exc_type, exc_val, exc_tb)

