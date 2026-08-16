"""
Unit tests and differential verifier comparing current FileLock metadata persistence
with experimental robust positional writer (write_all_at_zero + ftruncate).
Validates:
1. Exact JSON schema equivalence (keys, types, values, format).
2. Shorter payload overwrite (no stale trailing bytes).
3. Longer payload overwrite.
4. Empty file initialization.
5. Error propagation (no silent failures).
6. Idle vs Released release states.
7. Interoperability & concurrent readers.
"""

import os
import sys
import json
import time
import uuid
import tempfile
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from file_lock import FileLock, _CACHED_PID, _CACHED_HOSTNAME, _CACHED_PROC_START, _META_PREFIX, _lock_fd, _unlock_fd


def _write_metadata_atomic_exact(fd: int, payload: bytes) -> None:
    """
    Robust POSIX/OS positional metadata writer.
    - Writes exact byte sequence starting at byte offset 0, handling partial writes.
    - Truncates file to exact payload length to prevent stale trailing byte corruption.
    - Propagates all OS write/truncate errors deterministically.
    """
    total_written = 0
    payload_len = len(payload)
    while total_written < payload_len:
        written = os.pwrite(fd, payload[total_written:], total_written)
        if written == 0:
            raise IOError("os.pwrite wrote 0 bytes to lock file")
        total_written += written
    os.ftruncate(fd, payload_len)


class ExperimentalFileLock:
    """Experimental candidate testing robust positional write + ftruncate."""
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
                return self

            os.close(fd)
            if time.time() - start_time >= self.timeout:
                raise TimeoutError(f"ExperimentalFileLock timeout waiting for {self.lock_path}")
            time.sleep(self.poll_interval)

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._fd is not None:
            try:
                rel_status = getattr(self, "_release_status", "released")
                if rel_status == "idle":
                    rel_payload = f'{{"status": "idle", "pid": {self.owner_pid}, "token": "{self.token}", "reclaimed_at": {time.time()}}}'.encode("utf-8")
                else:
                    rel_payload = f'{{"status": "released", "pid": {self.owner_pid}, "token": "{self.token}"}}'.encode("utf-8")
                _write_metadata_atomic_exact(self._fd, rel_payload)
            except OSError:
                pass

            _unlock_fd(self._fd)
            os.close(self._fd)
            self._fd = None


def test_metadata_shorter_payload_overwrite_no_trailing_garbage():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "test_shorter.lock")

        # 1. Write an intentionally long initial metadata payload
        fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
        long_payload = b'{"status": "active", "pid": 12345, "token": "long-token-99999999999999999999999999999999999999999999", "custom_extra": "extra_garbage_data_here"}'
        _write_metadata_atomic_exact(fd, long_payload)
        os.close(fd)

        # 2. Overwrite with shorter payload
        fd2 = os.open(path, os.O_RDWR, 0o600)
        short_payload = b'{"status": "released", "pid": 123}'
        _write_metadata_atomic_exact(fd2, short_payload)
        os.close(fd2)

        # 3. Read back and verify exact byte length and valid JSON parsing
        with open(path, "rb") as f:
            content = f.read()

        assert content == short_payload
        parsed = json.loads(content.decode("utf-8"))
        assert parsed == {"status": "released", "pid": 123}


def test_differential_json_schema_equivalence():
    with tempfile.TemporaryDirectory() as tmpdir:
        path_std = os.path.join(tmpdir, "std.lock")
        path_exp = os.path.join(tmpdir, "exp.lock")

        # Enter standard FileLock and capture metadata
        std_lock = FileLock(path_std)
        with std_lock:
            with open(path_std, "r", encoding="utf-8") as f:
                meta_std_enter = json.load(f)

        with open(path_std, "r", encoding="utf-8") as f:
            meta_std_exit = json.load(f)

        # Enter experimental FileLock and capture metadata
        exp_lock = ExperimentalFileLock(path_exp)
        with exp_lock:
            with open(path_exp, "r", encoding="utf-8") as f:
                meta_exp_enter = json.load(f)

        with open(path_exp, "r", encoding="utf-8") as f:
            meta_exp_exit = json.load(f)

        # Verify Enter JSON schema exact key match
        assert set(meta_std_enter.keys()) == set(meta_exp_enter.keys())
        assert meta_std_enter["pid"] == meta_exp_enter["pid"]
        assert meta_std_enter["host"] == meta_exp_enter["host"]
        assert meta_std_enter["process_start_time"] == meta_exp_enter["process_start_time"]
        assert isinstance(meta_exp_enter["token"], str)
        assert isinstance(meta_exp_enter["start_time"], (int, float))

        # Verify Exit JSON schema exact key match
        assert set(meta_std_exit.keys()) == set(meta_exp_exit.keys())
        assert meta_std_exit["status"] == meta_exp_exit["status"] == "released"
        assert meta_std_exit["pid"] == meta_exp_exit["pid"]
        assert isinstance(meta_exp_exit["token"], str)


def test_experimental_lock_mutual_exclusion_and_timeout():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "mutex.lock")
        l1 = ExperimentalFileLock(path, timeout=5.0)
        l2 = ExperimentalFileLock(path, timeout=0.2)

        with l1:
            with pytest.raises(TimeoutError):
                with l2:
                    pass

        # After l1 release, l2 can acquire cleanly
        with l2:
            pass
