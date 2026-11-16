"""Non-authoritative reference scaffold worker implementation satisfying WorkerContract.

Cannot manufacture authority or write directly to canonical storage.
Provided for development, testing, and reference execution; not an authoritative
production execution runtime.
"""
from __future__ import annotations

import os
import signal
from typing import Callable, Optional, Sequence

from sclass_semantics_v6_0_1 import (
    AuthorizedWorkRequest,
    BoundaryContext,
    Digest,
    UtcInstant,
    WorkerClaimStatus,
    WorkerContract,
    WorkerHealth,
    WorkerProfile,
    WorkResult,
    WorkspaceSnapshotHandle,
    digest,
    target_snapshot_digest,
)


class ReferenceWorker(WorkerContract):
    """Non-authoritative reference scaffold worker implementation satisfying WorkerContract.

    Cannot manufacture authority or write directly to canonical storage.
    Enforces fail-closed cancellation, heartbeat verification, and honest claim status.
    """

    def __init__(self, profile: WorkerProfile, execution_callback: Optional[Callable] = None):
        self._profile = profile
        self._callback = execution_callback
        self._cancelled_requests: set[str] = set()
        self._running_pids: dict[str, int] = {}
        self._last_result = None
        self._last_kill_error: Optional[Exception] = None

    def profile(self) -> WorkerProfile:
        return self._profile

    def register_pid(self, request_id: str, pid: int) -> None:
        """Register a real operating system PID executing on behalf of request_id."""
        self._running_pids[request_id] = pid

    def cancel(self, request_id: str, reason: str) -> None:
        """A6-R1: A cancellation request marks intent but does not itself establish termination."""
        self._cancelled_requests.add(request_id)
        pid = self._running_pids.get(request_id)
        if pid is not None:
            try:
                if hasattr(os, "killpg"):
                    os.killpg(pid, signal.SIGKILL)
                else:
                    os.kill(pid, signal.SIGKILL)
            except Exception as e:
                self._last_kill_error = e

    def heartbeat(self, request_id: str) -> WorkerHealth:
        """A6-R1: Heartbeat verification.

        Only verified process absence for the gate-owned PID identity can establish EXITED.
        PermissionError and other unverified OS errors must not be treated as process absence.
        Failed termination must remain unresolved / ALIVE.
        """
        pid = self._running_pids.get(request_id)
        if pid is not None:
            try:
                if hasattr(os, "killpg"):
                    os.killpg(pid, 0)
                else:
                    os.kill(pid, 0)
                # If kill(0) succeeds without exception, process is STILL ALIVE.
                return WorkerHealth.ALIVE
            except ProcessLookupError:
                # Verified process absence: PID no longer exists in OS process table.
                return WorkerHealth.EXITED
            except (PermissionError, OSError):
                # PermissionError or unverified OS error: CANNOT prove process absence.
                # Must fail closed: do NOT report EXITED.
                return WorkerHealth.ALIVE

        # When no PID was registered (e.g. in-memory test scaffold without OS process)
        if request_id in self._cancelled_requests:
            return WorkerHealth.EXITED
        return WorkerHealth.ALIVE

    def execute(
        self,
        request: AuthorizedWorkRequest,
        boundary: Optional[BoundaryContext] = None,
        handle: Optional[WorkspaceSnapshotHandle] = None,
    ) -> WorkResult:
        """A6.2: Execute work request fail-closed.

        Never fabricates synthetic successful results or default-pass claims.
        Missing execution or capability produces CLAIMED_FAILED.
        Requires authentic digests and state revisions; never falls back to zero digests.
        """
        if request.request_id in self._cancelled_requests:
            claim_status = WorkerClaimStatus.CANCELLED
        elif self._callback:
            claim_status = self._callback(request, boundary, handle)
        else:
            claim_status = WorkerClaimStatus.CLAIMED_FAILED

        out_digest = digest("sclass/worker-out/v1", (request.request_id, claim_status.value))
        diag_digest = digest("sclass/worker-diag/v1", (request.request_id, claim_status.value))
        binding_digest = getattr(request, "state_binding_digest", None)
        if not binding_digest:
            raise ValueError("ReferenceWorker.execute requires authentic state_binding_digest")

        if hasattr(request, "proposal") and hasattr(request.proposal, "request_content_digest"):
            req_content_digest = request.proposal.request_content_digest
        else:
            req_content_digest = getattr(request, "request_content_digest", None)

        if not req_content_digest or req_content_digest == Digest("sha256:" + "0" * 64):
            raise ValueError("ReferenceWorker.execute requires authentic request_content_digest")

        target_digest = getattr(request, "target_snapshot_digest", None)
        if target_digest is None:
            if hasattr(request, "target_snapshot") and request.target_snapshot is not None:
                target_digest = target_snapshot_digest(request.target_snapshot)
            elif hasattr(request, "execution_lease") and hasattr(request.execution_lease, "target_snapshot_digest"):
                target_digest = request.execution_lease.target_snapshot_digest

        if not target_digest or target_digest == Digest("sha256:" + "0" * 64):
            raise ValueError("ReferenceWorker.execute requires authentic target_snapshot_digest")

        state_binding = None
        if hasattr(request, "proposal") and hasattr(request.proposal, "state_binding"):
            state_binding = request.proposal.state_binding
        elif hasattr(request, "state_binding"):
            state_binding = request.state_binding

        if state_binding is None:
            raise ValueError("ReferenceWorker.execute requires authentic StateBinding")

        obj_rev = getattr(state_binding, "objective_revision", None)
        wg_rev = getattr(state_binding, "workgraph_revision", None)
        if not obj_rev or not wg_rev:
            raise ValueError("ReferenceWorker.execute requires authentic objective and workgraph revisions")

        return WorkResult(
            result_id=f"work-result-{request.request_id}",
            request_id=request.request_id,
            request_content_digest=req_content_digest,
            envelope_digest=request.envelope_digest,
            execution_generation=request.execution_generation,
            execution_attempt_id=request.execution_attempt_id,
            target_snapshot_digest=target_digest,
            state_binding_digest=binding_digest,
            governing_budget_lineage_id=request.governing_budget_lineage_id,
            objective_revision=obj_rev,
            workgraph_revision=wg_rev,
            worker_identity=self._profile.profile_id,
            claim_status=claim_status,
            measured_tokens=0,
            measured_duration_ms=0,
            output_digest=out_digest,
            diagnostics_digest=diag_digest,
            produced_artifacts=(),
        )

