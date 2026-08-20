"""D8 Autonomous Planning Substrate - Planning Lease Protocol (§3.6, §8.1).

Kernel-level Compare-And-Swap (CAS) lease protocol using atomic lockfiles,
fsync barrier guarantees, and strictly monotonic fencing tokens.
"""

from __future__ import annotations
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from domain.models import _validate_iso8601
from domain.types import TASK_ID_PATTERN
from planner.models import PlanningLease


class LeaseAcquisitionError(RuntimeError):
    """Raised when lease acquisition fails due to active ownership by another worker."""
    pass


class LeaseValidationError(RuntimeError):
    """Raised when lease renewal or release fails due to expired or lost ownership."""
    pass


class PlanningLeaseManager:
    """Manages cross-worker planning leases with kernel-enforced mutual exclusion."""

    def __init__(self, lease_dir: str = ".leases", base_fencing_token: int = 0):
        self._lease_dir = os.path.abspath(lease_dir)
        self._base_fencing_token = base_fencing_token
        os.makedirs(self._lease_dir, exist_ok=True)

    def _lock_path(self, task_id: str) -> str:
        return os.path.join(self._lease_dir, f"{task_id}.lock")

    def _lease_path(self, task_id: str) -> str:
        return os.path.join(self._lease_dir, f"{task_id}.json")

    def _sync_dir(self):
        """Synchronizes directory metadata to persistent storage."""
        if hasattr(os, "O_DIRECTORY") and sys.platform != "win32":
            try:
                dir_fd = os.open(self._lease_dir, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
            except OSError:
                pass

    def _acquire_lock(self, task_id: str, timeout_seconds: float = 5.0) -> int:
        """Acquires exclusive kernel-level lockfile via O_CREAT | O_EXCL."""
        lock_file = self._lock_path(task_id)
        start_time = time.time()
        while True:
            try:
                fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                return fd
            except (FileExistsError, PermissionError):
                # Check for abandoned lock (older than 10 seconds)
                try:
                    mtime = os.path.getmtime(lock_file)
                    if time.time() - mtime > 10.0:
                        try:
                            os.unlink(lock_file)
                            continue
                        except OSError:
                            pass
                except OSError:
                    pass

                if time.time() - start_time >= timeout_seconds:
                    raise LeaseAcquisitionError(
                        f"Timeout acquiring kernel lock for task '{task_id}'."
                    )
                time.sleep(0.02)

    def _release_lock(self, task_id: str, fd: int):
        """Closes and unlinks the kernel lockfile."""
        lock_file = self._lock_path(task_id)
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            if os.path.exists(lock_file):
                os.unlink(lock_file)
        except OSError:
            pass

    def _read_lease_file(self, task_id: str) -> Optional[PlanningLease]:
        """Reads and parses the active lease file if present."""
        path = self._lease_path(task_id)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return PlanningLease(
                task_id=data["task_id"],
                owner_id=data["owner_id"],
                lease_epoch=data["lease_epoch"],
                fencing_token=data["fencing_token"],
                acquired_at=data["acquired_at"],
                expires_at=data["expires_at"],
                is_active=data.get("is_active", True),
            )
        except Exception:
            return None

    def _write_lease_file(self, lease: PlanningLease):
        """Atomically writes lease file with fsync and rename."""
        task_id = lease.task_id
        tmp_path = os.path.join(
            self._lease_dir,
            f"{task_id}.tmp.{os.getpid()}.{uuid.uuid4().hex[:8]}"
        )
        final_path = self._lease_path(task_id)

        data = {
            "task_id": lease.task_id,
            "owner_id": lease.owner_id,
            "lease_epoch": lease.lease_epoch,
            "fencing_token": lease.fencing_token,
            "acquired_at": lease.acquired_at,
            "expires_at": lease.expires_at,
            "is_active": lease.is_active,
        }

        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())

        os.replace(tmp_path, final_path)
        self._sync_dir()

    def acquire_lease(
        self,
        task_id: str,
        owner_id: str,
        ttl_seconds: float = 30.0,
    ) -> PlanningLease:
        """Atomically acquires a planning lease for task_id or raises LeaseAcquisitionError."""
        if not task_id:
            raise ValueError("task_id cannot be empty.")
        if not owner_id:
            raise ValueError("owner_id cannot be empty.")
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be > 0.")

        fd = self._acquire_lock(task_id)
        try:
            current_lease = self._read_lease_file(task_id)
            now = datetime.now(timezone.utc)
            now_iso = now.isoformat()

            # Check if active lease exists
            if current_lease and current_lease.is_active:
                exp = datetime.fromisoformat(current_lease.expires_at.replace("Z", "+00:00"))
                if now < exp:
                    if current_lease.owner_id == owner_id:
                        # Re-entrant acquire is a renewal
                        return self._renew_under_lock(current_lease, ttl_seconds, now)
                    raise LeaseAcquisitionError(
                        f"Task '{task_id}' is already leased to active owner '{current_lease.owner_id}' "
                        f"until {current_lease.expires_at}."
                    )

            # Compute new monotonic fencing token and epoch
            prev_fence = current_lease.fencing_token if current_lease else self._base_fencing_token
            prev_epoch = current_lease.lease_epoch if current_lease else 0
            new_fence = max(prev_fence, self._base_fencing_token) + 1
            new_epoch = prev_epoch + 1

            expires_at = datetime.fromtimestamp(now.timestamp() + ttl_seconds, tz=timezone.utc).isoformat()

            lease = PlanningLease(
                task_id=task_id,
                owner_id=owner_id,
                lease_epoch=new_epoch,
                fencing_token=new_fence,
                acquired_at=now_iso,
                expires_at=expires_at,
                is_active=True,
            )

            self._write_lease_file(lease)
            return lease
        finally:
            self._release_lock(task_id, fd)

    def _renew_under_lock(
        self,
        current_lease: PlanningLease,
        ttl_seconds: float,
        now: datetime,
    ) -> PlanningLease:
        expires_at = datetime.fromtimestamp(now.timestamp() + ttl_seconds, tz=timezone.utc).isoformat()
        renewed = PlanningLease(
            task_id=current_lease.task_id,
            owner_id=current_lease.owner_id,
            lease_epoch=current_lease.lease_epoch,
            fencing_token=current_lease.fencing_token,
            acquired_at=current_lease.acquired_at,
            expires_at=expires_at,
            is_active=True,
        )
        self._write_lease_file(renewed)
        return renewed

    def renew_lease(
        self,
        lease: PlanningLease,
        ttl_seconds: float = 30.0,
    ) -> PlanningLease:
        """Renews an active lease if the caller still holds ownership."""
        if not isinstance(lease, PlanningLease):
            raise TypeError("lease must be a PlanningLease instance.")

        fd = self._acquire_lock(lease.task_id)
        try:
            current_lease = self._read_lease_file(lease.task_id)
            if not current_lease or not current_lease.is_active:
                raise LeaseValidationError("Lease is no longer active.")
            if current_lease.owner_id != lease.owner_id:
                raise LeaseValidationError(
                    f"Lease owner mismatch: current owner is '{current_lease.owner_id}', expected '{lease.owner_id}'."
                )
            if current_lease.lease_epoch != lease.lease_epoch or current_lease.fencing_token != lease.fencing_token:
                raise LeaseValidationError("Lease coordinates are stale or have been superseded.")

            now = datetime.now(timezone.utc)
            return self._renew_under_lock(current_lease, ttl_seconds, now)
        finally:
            self._release_lock(lease.task_id, fd)

    def release_lease(self, lease: PlanningLease) -> bool:
        """Voluntarily releases the planning lease."""
        if not isinstance(lease, PlanningLease):
            return False

        fd = self._acquire_lock(lease.task_id)
        try:
            current_lease = self._read_lease_file(lease.task_id)
            if not current_lease or not current_lease.is_active:
                return True
            if (
                current_lease.owner_id == lease.owner_id
                and current_lease.lease_epoch == lease.lease_epoch
                and current_lease.fencing_token == lease.fencing_token
            ):
                released = PlanningLease(
                    task_id=current_lease.task_id,
                    owner_id=current_lease.owner_id,
                    lease_epoch=current_lease.lease_epoch,
                    fencing_token=current_lease.fencing_token,
                    acquired_at=current_lease.acquired_at,
                    expires_at=current_lease.expires_at,
                    is_active=False,
                )
                self._write_lease_file(released)
                return True
            return False
        finally:
            self._release_lock(lease.task_id, fd)

    def get_active_lease(self, task_id: str) -> Optional[PlanningLease]:
        """Returns the current active lease if not expired."""
        lease = self._read_lease_file(task_id)
        if not lease or not lease.is_active:
            return None
        now = datetime.now(timezone.utc)
        exp = datetime.fromisoformat(lease.expires_at.replace("Z", "+00:00"))
        if now >= exp:
            return None
        return lease

    def is_lease_valid(self, lease: PlanningLease) -> bool:
        """Verifies if the given lease represents the current active unexpired lease."""
        if not isinstance(lease, PlanningLease) or not lease.is_active:
            return False
        active = self.get_active_lease(lease.task_id)
        if not active:
            return False
        return (
            active.owner_id == lease.owner_id
            and active.lease_epoch == lease.lease_epoch
            and active.fencing_token == lease.fencing_token
        )
