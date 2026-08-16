"""
Strict Current-vs-Candidate Contract Differential Harness & Failure Injection Suite.

This module systematically executes identical scenarios against BOTH:
1. Current S-Class FileLock (`FileLock`)
2. Experimental Candidate (`ExperimentalFileLock`)

and directly compares their normalized contract observations.

Dimensions Differentially Verified:
1. Schema & Field Type Parity (Enter, Released, and Idle/Reclaim states).
2. Process-Local Thread Serialization (_active_local_locks parity).
3. Multiprocessing Mutual Exclusion.
4. Abrupt Crash Recovery (os._exit).
5. Stale Metadata Takeover (dead PID lock overwrite).
6. Config GC Safety Integration.
7. Portalocker Bidirectional Interoperability.
8. Error & Failure Injection (partial pwrite, pwrite exception, ftruncate failure, pwrite-to-crash window barrier).
"""

import os
import sys
import json
import time
import uuid
import tempfile
import threading
import subprocess
import pytest
import portalocker
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from file_lock import (
    FileLock,
    _CACHED_PID,
    _CACHED_HOSTNAME,
    _CACHED_PROC_START,
    _META_PREFIX,
    _lock_fd,
    _unlock_fd,
    _active_local_locks,
    _active_locks_guard
)
from config_gc import run_gc


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


class ExperimentalFileLock:
    """
    Experimental candidate testing robust positional write + ftruncate + active_local_locks thread safety.
    """
    def __init__(self, lock_path: str, timeout: float = 10.0, poll_interval: float = 0.05):
        self.lock_path = os.path.abspath(lock_path)
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.token = uuid.uuid4().hex
        self.owner_pid = _CACHED_PID
        self.owner_proc_start = _CACHED_PROC_START
        self._fd = None

    def __enter__(self):
        start_time = time.time()
        owner_payload = f'{_META_PREFIX}{self.token}", "start_time": {start_time}}}'.encode("utf-8")

        while True:
            # 1. Process-local thread serialization
            with _active_locks_guard:
                is_locally_active = self.lock_path in _active_local_locks

            if is_locally_active:
                if time.time() - start_time >= self.timeout:
                    raise TimeoutError(f"ExperimentalFileLock thread timeout waiting for {self.lock_path}")
                time.sleep(self.poll_interval)
                continue

            try:
                fd = os.open(self.lock_path, os.O_RDWR | os.O_CREAT, 0o600)
            except OSError:
                if time.time() - start_time >= self.timeout:
                    raise TimeoutError(f"ExperimentalFileLock timeout opening {self.lock_path}")
                time.sleep(self.poll_interval)
                continue

            if _lock_fd(fd):
                try:
                    _write_metadata_atomic_exact(fd, owner_payload)
                except Exception as err:
                    _unlock_fd(fd)
                    os.close(fd)
                    raise err

                self._fd = fd
                with _active_locks_guard:
                    _active_local_locks.add(self.lock_path)
                return self

            os.close(fd)
            if time.time() - start_time >= self.timeout:
                raise TimeoutError(f"ExperimentalFileLock timeout waiting for live lock: {self.lock_path}")
            time.sleep(self.poll_interval)

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if self._fd is not None:
                rel_status = getattr(self, "_release_status", "released")
                if rel_status == "idle":
                    rel_payload = f'{{"status": "idle", "pid": {self.owner_pid}, "token": "{self.token}", "reclaimed_at": {time.time()}}}'.encode("utf-8")
                else:
                    rel_payload = f'{{"status": "released", "pid": {self.owner_pid}, "token": "{self.token}"}}'.encode("utf-8")

                try:
                    _write_metadata_atomic_exact(self._fd, rel_payload)
                except OSError as err:
                    if exc_type is None:
                        raise err

                _unlock_fd(self._fd)
                os.close(self._fd)
                self._fd = None
        finally:
            with _active_locks_guard:
                _active_local_locks.discard(self.lock_path)


def _read_metadata_safe(lock_obj, path: str) -> dict:
    """Reads metadata safely while lock is held (avoiding Win32 msvcrt locking PermissionError)."""
    if hasattr(lock_obj, "_file") and lock_obj._file is not None and not lock_obj._file.closed:
        lock_obj._file.seek(0)
        return json.loads(lock_obj._file.read().decode("utf-8"))
    elif hasattr(lock_obj, "_fd") and lock_obj._fd is not None:
        pos = os.lseek(lock_obj._fd, 0, os.SEEK_SET)
        data = os.read(lock_obj._fd, 4096)
        os.lseek(lock_obj._fd, pos, os.SEEK_SET)
        return json.loads(data.decode("utf-8"))
    else:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)


def _normalize_metadata(meta_dict: dict) -> dict:
    """Normalizes metadata observation for comparative schema validation."""
    return {
        "keys": sorted(list(meta_dict.keys())),
        "pid_type": type(meta_dict.get("pid")).__name__,
        "pid_matches_cached": meta_dict.get("pid") == _CACHED_PID,
        "token_is_str": isinstance(meta_dict.get("token"), str),
        "token_len": len(meta_dict.get("token", "")),
        "has_host": "host" in meta_dict,
        "has_process_start_time": "process_start_time" in meta_dict,
        "has_start_time": "start_time" in meta_dict,
        "status": meta_dict.get("status"),
        "has_reclaimed_at": "reclaimed_at" in meta_dict
    }


# ============================================================================
# 1. Differential Schema Normalization: Enter, Released, Idle/Reclaim
# ============================================================================
def test_differential_schema_normalization_enter_released_idle():
    with tempfile.TemporaryDirectory() as tmpdir:
        path_cur = os.path.join(tmpdir, "cur.lock")
        path_exp = os.path.join(tmpdir, "exp.lock")

        # --- Current FileLock ---
        fl_cur = FileLock(path_cur)
        fl_cur.__enter__()
        meta_cur_enter = _read_metadata_safe(fl_cur, path_cur)

        fl_cur._release_status = "idle"
        fl_cur.__exit__(None, None, None)
        meta_cur_idle = _read_metadata_safe(None, path_cur)

        fl_cur2 = FileLock(path_cur)
        fl_cur2.__enter__()
        fl_cur2._release_status = "released"
        fl_cur2.__exit__(None, None, None)
        meta_cur_rel = _read_metadata_safe(None, path_cur)

        # --- Experimental Candidate ---
        fl_exp = ExperimentalFileLock(path_exp)
        fl_exp.__enter__()
        meta_exp_enter = _read_metadata_safe(fl_exp, path_exp)

        fl_exp._release_status = "idle"
        fl_exp.__exit__(None, None, None)
        meta_exp_idle = _read_metadata_safe(None, path_exp)

        fl_exp2 = ExperimentalFileLock(path_exp)
        fl_exp2.__enter__()
        fl_exp2._release_status = "released"
        fl_exp2.__exit__(None, None, None)
        meta_exp_rel = _read_metadata_safe(None, path_exp)

        # Direct Normalized Contract Comparison
        norm_cur_enter = _normalize_metadata(meta_cur_enter)
        norm_exp_enter = _normalize_metadata(meta_exp_enter)
        assert norm_cur_enter == norm_exp_enter, f"Enter metadata schema mismatch!\nCurrent: {norm_cur_enter}\nCandidate: {norm_exp_enter}"

        norm_cur_rel = _normalize_metadata(meta_cur_rel)
        norm_exp_rel = _normalize_metadata(meta_exp_rel)
        assert norm_cur_rel == norm_exp_rel, f"Released metadata schema mismatch!\nCurrent: {norm_cur_rel}\nCandidate: {norm_exp_rel}"

        norm_cur_idle = _normalize_metadata(meta_cur_idle)
        norm_exp_idle = _normalize_metadata(meta_exp_idle)
        assert norm_cur_idle == norm_exp_idle, f"Idle metadata schema mismatch!\nCurrent: {norm_cur_idle}\nCandidate: {norm_exp_idle}"


# ============================================================================
# 2. Differential Thread Serialization (Current vs Candidate)
# ============================================================================
def test_differential_thread_serialization():
    def run_thread_test(lock_cls, lock_path):
        counter = [0]
        def worker():
            for _ in range(50):
                with lock_cls(lock_path, timeout=10.0):
                    c = counter[0]
                    time.sleep(0.0001)
                    counter[0] = c + 1
        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        return counter[0]

    with tempfile.TemporaryDirectory() as tmpdir:
        cur_count = run_thread_test(FileLock, os.path.join(tmpdir, "cur_threads.lock"))
        exp_count = run_thread_test(ExperimentalFileLock, os.path.join(tmpdir, "exp_threads.lock"))

        assert cur_count == 200
        assert exp_count == 200
        assert cur_count == exp_count


# ============================================================================
# 3. Differential Multiprocessing Exclusion (Current vs Candidate)
# ============================================================================
def _mp_generic_worker(lock_cls_name, lock_path, count_file, increments):
    if lock_cls_name == "FileLock":
        cls = FileLock
    else:
        cls = ExperimentalFileLock

    for _ in range(increments):
        with cls(lock_path, timeout=10.0):
            with open(count_file, "r+", encoding="utf-8") as f:
                val = int(f.read().strip())
                f.seek(0)
                f.truncate(0)
                f.write(str(val + 1))


def test_differential_multiprocessing_exclusion():
    def run_mp_test(lock_cls_name, tmpdir):
        lock_path = os.path.join(tmpdir, f"{lock_cls_name}.lock")
        count_path = os.path.join(tmpdir, f"{lock_cls_name}_count.txt")
        with open(count_path, "w", encoding="utf-8") as f:
            f.write("0")

        cmd = [
            sys.executable, "-c",
            f"from tests.test_experimental_metadata_writer import _mp_generic_worker; "
            f"_mp_generic_worker('{lock_cls_name}', r'{lock_path}', r'{count_path}', 25)"
        ]
        procs = [subprocess.Popen(cmd) for _ in range(4)]
        for p in procs:
            p.wait(timeout=10.0)

        with open(count_path, "r", encoding="utf-8") as f:
            return int(f.read().strip())

    with tempfile.TemporaryDirectory() as tmpdir:
        cur_result = run_mp_test("FileLock", tmpdir)
        exp_result = run_mp_test("ExperimentalFileLock", tmpdir)

        assert cur_result == 100
        assert exp_result == 100
        assert cur_result == exp_result


# ============================================================================
# 4. Differential Crash Recovery (Current vs Candidate)
# ============================================================================
def test_differential_crash_recovery():
    def run_crash_test(lock_cls_name, tmpdir):
        lock_path = os.path.join(tmpdir, f"{lock_cls_name}_crash.lock")
        ready_file = os.path.join(tmpdir, f"{lock_cls_name}_ready.marker")

        cmd = [
            sys.executable, "-c",
            f"import os, time; from tests.test_experimental_metadata_writer import FileLock, ExperimentalFileLock; "
            f"cls = FileLock if '{lock_cls_name}' == 'FileLock' else ExperimentalFileLock; "
            f"fl = cls(r'{lock_path}'); fl.__enter__(); "
            f"open(r'{ready_file}', 'w').write('OK'); time.sleep(0.1); os._exit(0)"
        ]
        proc = subprocess.Popen(cmd)
        while not os.path.exists(ready_file):
            time.sleep(0.01)
        proc.wait(timeout=5.0)

        cls = FileLock if lock_cls_name == "FileLock" else ExperimentalFileLock
        t0 = time.perf_counter()
        with cls(lock_path, timeout=2.0):
            t1 = time.perf_counter()

        return (t1 - t0)

    with tempfile.TemporaryDirectory() as tmpdir:
        cur_reclaim_time = run_crash_test("FileLock", tmpdir)
        exp_reclaim_time = run_crash_test("ExperimentalFileLock", tmpdir)

        assert cur_reclaim_time < 0.2
        assert exp_reclaim_time < 0.2


# ============================================================================
# 5. Differential Stale Metadata Takeover (Current vs Candidate)
# ============================================================================
def test_differential_stale_metadata_takeover():
    def run_stale_test(lock_cls, tmpdir, prefix):
        lock_path = os.path.join(tmpdir, f"{prefix}_stale.lock")
        stale_meta = json.dumps({"status": "active", "pid": 99999999, "token": "stale-token", "start_time": 100.0})
        with open(lock_path, "w", encoding="utf-8") as f:
            f.write(stale_meta)

        with lock_cls(lock_path, timeout=2.0) as fl:
            new_meta = _read_metadata_safe(fl, lock_path)

        return _normalize_metadata(new_meta)

    with tempfile.TemporaryDirectory() as tmpdir:
        cur_takeover = run_stale_test(FileLock, tmpdir, "cur")
        exp_takeover = run_stale_test(ExperimentalFileLock, tmpdir, "exp")

        assert cur_takeover == exp_takeover
        assert cur_takeover["pid_matches_cached"] is True


# ============================================================================
# 6. Differential GC Safety Integration (Current vs Candidate)
# ============================================================================
def test_differential_gc_safety():
    def run_gc_test(lock_cls, tmpdir, prefix):
        active_lock = os.path.join(tmpdir, f"{prefix}_active.lock")
        fl = lock_cls(active_lock)
        fl.__enter__()

        # Run GC on workspace
        report = run_gc(tmpdir)
        is_active_preserved = os.path.exists(active_lock)

        fl.__exit__(None, None, None)
        return is_active_preserved, report.stale_locks_reclaimed

    with tempfile.TemporaryDirectory() as tmpdir:
        cur_preserved, cur_reclaimed = run_gc_test(FileLock, tmpdir, "cur")
        exp_preserved, exp_reclaimed = run_gc_test(ExperimentalFileLock, tmpdir, "exp")

        assert cur_preserved is True
        assert exp_preserved is True
        assert cur_preserved == exp_preserved


# ============================================================================
# 7. Differential Portalocker Interoperability (Current vs Candidate)
# ============================================================================
def test_differential_portalocker_interoperability():
    def run_interop_test(lock_cls, tmpdir, prefix):
        lock_path = os.path.join(tmpdir, f"{prefix}_interop.lock")

        # 1. Implementation holds -> Portalocker contender blocks
        with lock_cls(lock_path, timeout=5.0):
            with pytest.raises(portalocker.exceptions.LockException):
                portalocker.Lock(lock_path, mode="a+b", timeout=0.2).acquire()

        # 2. Portalocker holds -> Implementation contender blocks
        with portalocker.Lock(lock_path, mode="a+b", timeout=5.0):
            with pytest.raises(TimeoutError):
                with lock_cls(lock_path, timeout=0.2):
                    pass

        return True

    with tempfile.TemporaryDirectory() as tmpdir:
        assert run_interop_test(FileLock, tmpdir, "cur") is True
        assert run_interop_test(ExperimentalFileLock, tmpdir, "exp") is True


# ============================================================================
# 8. Failure Injection & Crash Consistency Suite
# ============================================================================
def test_failure_injection_partial_pwrite_loop():
    """Simulates pwrite/write returning 1 byte per call to verify write_metadata_atomic_exact loop correctness."""
    written_chunks = []

    if hasattr(os, "pwrite"):
        orig_pwrite = os.pwrite
        def mock_pwrite_1byte(fd, buf, offset):
            chunk = buf[:1]
            written = orig_pwrite(fd, chunk, offset)
            written_chunks.append(written)
            return written

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "partial.lock")
            fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
            try:
                payload = b'{"status": "active", "pid": 1234, "token": "test-partial-write-token-12345"}'
                with patch("os.pwrite", side_effect=mock_pwrite_1byte):
                    _write_metadata_atomic_exact(fd, payload)

                with open(path, "rb") as f:
                    content = f.read()
                assert content == payload, f"File content mismatch! Expected {payload}, got {content}"
                assert len(written_chunks) == len(payload), f"Expected {len(payload)} 1-byte writes, got {len(written_chunks)}"
            finally:
                os.close(fd)
    else:
        orig_write = os.write
        def mock_write_1byte(fd, buf):
            chunk = buf[:1]
            written = orig_write(fd, chunk)
            written_chunks.append(written)
            return written

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "partial.lock")
            fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
            try:
                payload = b'{"status": "active", "pid": 1234, "token": "test-partial-write-token-12345"}'
                with patch("os.write", side_effect=mock_write_1byte):
                    _write_metadata_atomic_exact(fd, payload)

                with open(path, "rb") as f:
                    content = f.read()
                assert content == payload
                assert len(written_chunks) == len(payload)
            finally:
                os.close(fd)


def test_failure_injection_pwrite_and_ftruncate_errors():
    """Verifies that write/ftruncate OS errors propagate deterministically."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "error.lock")
        fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            target_fn = "os.pwrite" if hasattr(os, "pwrite") else "os.write"
            # 1. Write error
            with patch(target_fn, side_effect=OSError(5, "Input/output error")):
                with pytest.raises(OSError):
                    _write_metadata_atomic_exact(fd, b"test")

            # 2. ftruncate error
            with patch("os.ftruncate", side_effect=OSError(28, "No space left on device")):
                with pytest.raises(OSError):
                    _write_metadata_atomic_exact(fd, b"test")
        finally:
            os.close(fd)


def _crash_window_worker(lock_cls_name, lock_path, ready_file):
    """
    Worker process that acquires lock using specified implementation (FileLock or ExperimentalFileLock),
    writes an untruncated long metadata payload without releasing or truncating, signals barrier, and abruptly dies (os._exit).
    """
    long_payload = b'{"status": "active", "pid": 99999999, "token": "crash-window-long-untruncated-payload-999999999999999999999999999999"}'

    if lock_cls_name == "FileLock":
        fl = FileLock(lock_path, timeout=5.0)
        fl.__enter__()
        if hasattr(fl, "_file") and fl._file is not None:
            fl._file.seek(0)
            fl._file.write(long_payload)
            fl._file.flush()
    else:
        fl = ExperimentalFileLock(lock_path, timeout=5.0)
        fl.__enter__()
        if hasattr(os, "pwrite"):
            os.pwrite(fl._fd, long_payload, 0)
        else:
            os.lseek(fl._fd, 0, os.SEEK_SET)
            os.write(fl._fd, long_payload)

    with open(ready_file, "w", encoding="utf-8") as f:
        f.write("WRITE_DONE")

    os._exit(0)


def test_crash_window_between_pwrite_and_ftruncate():
    """
    Comparative Current-vs-Candidate Crash Window Recovery & Exact Byte Content Integrity Test.
    Simulates process crash AFTER write completes but BEFORE truncate/release executes for BOTH FileLock and ExperimentalFileLock:
    1. Current FileLock writer interrupted -> Current FileLock contender recovers.
    2. Candidate ExperimentalFileLock writer interrupted -> Candidate ExperimentalFileLock contender recovers.
    3. Strict Content & Length Assertions:
       - Valid JSON parsing
       - Expected status ('released')
       - Expected PID (os.getpid()) and token presence
       - Exact disk payload match (raw_bytes == json.dumps(parsed).encode('utf-8')) with zero trailing bytes
    4. Normalized Schema Equality between Current and Candidate crash recovery observations.
    """
    def run_recovery(lock_cls_name, lock_cls, tmpdir):
        lock_path = os.path.join(tmpdir, f"{lock_cls_name}_crash_window.lock")
        ready_file = os.path.join(tmpdir, f"{lock_cls_name}_write_done.marker")

        cmd = [
            sys.executable, "-c",
            f"from tests.test_experimental_metadata_writer import _crash_window_worker; "
            f"_crash_window_worker('{lock_cls_name}', r'{lock_path}', r'{ready_file}')"
        ]
        proc = subprocess.Popen(cmd)

        start = time.time()
        while not os.path.exists(ready_file) and time.time() - start < 5.0:
            time.sleep(0.01)
        assert os.path.exists(ready_file), f"Child process failed to signal barrier for {lock_cls_name}"

        proc.wait(timeout=5.0)

        # Contender acquires lock over the untruncated crash file
        with lock_cls(lock_path, timeout=2.0) as fl:
            meta = _read_metadata_safe(fl, lock_path)

        # Read raw disk bytes after release
        with open(lock_path, "rb") as f:
            raw_bytes = f.read()

        # Strict JSON parse & exact content byte match (verifying zero trailing bytes)
        parsed = json.loads(raw_bytes.decode("utf-8"))
        expected_bytes = json.dumps(parsed).encode("utf-8")
        assert raw_bytes == expected_bytes, f"Raw disk bytes do not match expected JSON payload!\nRaw: {raw_bytes!r}\nExpected: {expected_bytes!r}"
        assert parsed["pid"] == os.getpid()
        assert parsed["status"] == "released"

        return _normalize_metadata(meta), _normalize_metadata(parsed)

    with tempfile.TemporaryDirectory() as tmpdir:
        cur_enter_norm, cur_rel_norm = run_recovery("FileLock", FileLock, tmpdir)
        exp_enter_norm, exp_rel_norm = run_recovery("ExperimentalFileLock", ExperimentalFileLock, tmpdir)

        # Direct Comparative Contract Normalization Assertions
        assert cur_enter_norm == exp_enter_norm, f"Crash recovery enter schema mismatch!\nCurrent: {cur_enter_norm}\nCandidate: {exp_enter_norm}"
        assert cur_rel_norm == exp_rel_norm, f"Crash recovery released schema mismatch!\nCurrent: {cur_rel_norm}\nCandidate: {exp_rel_norm}"
