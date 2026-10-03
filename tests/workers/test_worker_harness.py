"""Test suite for Worker Execution Harness (03-RUNTIME / 01-ARCHITECTURE)."""

import os
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

# Add project roots
_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "10-CONFORMANCE"))
sys.path.insert(0, str(_ROOT / "20-RUNTIME"))
sys.path.insert(0, str(_ROOT / "src"))

import pytest
import sclass_semantics_v6_0_1 as S
from sclass_runtime_v6_0_1 import (
    LinuxExecutionBoundary,
    LocalWorkspaceSnapshotHandle,
)

from sclass.workers.harness import (
    PatchAgentWorker,
    SubprocessToolWorker,
    WorkerHarness,
)


def _make_sample_authorized_request(
    request_id: str = "req-1",
    fencing_token: int = 1,
    filesystem_accesses: Sequence[S.FsAccess] = (),
) -> S.AuthorizedWorkRequest:
    zero_dig = S.Digest("sha256:" + "0" * 64)
    z_budget = S.ResourceBudget(0, 0, 0, 30000, 0, 0, 0, 0, 0, 0, 0)
    req_eff = S.RequestedEffect(
        filesystem=tuple(filesystem_accesses),
        subprocess=(),
        network=(),
        environment=S.FrozenMap.from_items(),
        credentials=(),
        external_side_effects=(),
        requested_budget=z_budget,
        delta_digest=None,
    )
    scope = S.EffectScope((), (), (), S.FrozenMap.from_items(), ".", (), (), z_budget)
    proposal = S.WorkProposal("prop-1", "node-1", zero_dig, None, zero_dig, req_eff)
    exe_path = Path(sys.executable)
    exe_dig = LinuxExecutionBoundary._file_digest(exe_path)
    ex_id = S.ExecutionIdentity(
        str(exe_path), str(exe_path), exe_dig, "1.0", "python",
        exe_dig, exe_dig, 1000, ()
    )
    ex_lease = S.ExecutionLease(
        "lease-1", "ws", "node-1", zero_dig, 1, "attempt-1",
        zero_dig, "lineage-1", "res-1", "snap-1", zero_dig,
        "auth-lease-1", "rev-1", "pol-1", "worker-1", ex_id,
        zero_dig, "rev-1", fencing_token, S.UtcInstant(1), S.UtcInstant(1000)
    )
    auth_claims = S.AuthorizationLeaseClaims(
        "auth-lease-1", "dec-1", zero_dig, zero_dig, "pol-1", (),
        "ws", "snap-1", "worker-1", "nonce-1", "issuer-1",
        S.UtcInstant(1), S.UtcInstant(1000)
    )
    sig = S.SignatureBlock("ed25519", "key-1", "root-1", "c1", b"sig")
    auth_lease = S.AuthorizationLease(auth_claims, sig)
    ctx_pkg = S.ContextPackage(
        4000,
        S.ContextItem(
            "rm", S.ContextItemKind.REPO_MAP, "s", None, None, None,
            zero_dig, S.DataClassification.INTERNAL, S.TrustLevel.TRUSTED, 1, 100
        ),
        (), "ob-1", (), (),
        S.TokenUsage(0, 0, 0, 0, 100, 100, 0),
        S.RedactionReport("pol", (), 0, zero_dig), "c1"
    )

    return S.AuthorizedWorkRequest(
        request_id, "node-1", 1, "attempt-1", "lineage-1", "res-1", zero_dig,
        "obl-1", frozenset({"obl-1"}), "action", S.ActionType.CODE_EDIT,
        req_eff, scope, ctx_pkg, (), proposal, auth_lease, ex_lease, zero_dig, zero_dig
    )


def _make_sample_boundary_context(fencing_token: int = 1) -> S.BoundaryContext:
    return S.BoundaryContext("boundary-1", S.IsolationLevel.PROCESS, "handle-1", fencing_token)


def test_worker_harness_fail_closed_checks():
    class DummyWorker(WorkerHarness):
        def execute(self, request, boundary, handle, **kwargs):
            self._validate_request(request, boundary, handle)

    worker = DummyWorker()

    # 1. Prohibit WorkProposal execution
    proposal = S.WorkProposal("prop-1", "node-1")
    with pytest.raises(PermissionError, match="AuthorizedWorkRequest"):
        worker.execute(proposal, None, None)

    # 2. Require BoundaryContext
    req = _make_sample_authorized_request()
    with pytest.raises(PermissionError, match="BoundaryContext"):
        worker.execute(req, None, None)

    # 3. Fencing token mismatch
    bad_ctx = _make_sample_boundary_context(fencing_token=999)
    with tempfile.TemporaryDirectory() as tmp_dir:
        handle = LocalWorkspaceSnapshotHandle(Path(tmp_dir), "w", "s", 1)
        with pytest.raises(PermissionError, match="fencing token"):
            worker.execute(req, bad_ctx, handle)

    # 4. Cancellation check
    good_ctx = _make_sample_boundary_context(fencing_token=req.execution_lease.fencing_token)
    worker.cancel(req.request_id, "test cancellation")
    assert worker.heartbeat(req.request_id) is S.WorkerHealth.EXITED

    with tempfile.TemporaryDirectory() as tmp_dir:
        handle = LocalWorkspaceSnapshotHandle(Path(tmp_dir), "w", "s", 1)
        with pytest.raises(PermissionError, match="cancelled"):
            worker.execute(req, good_ctx, handle)


def test_patch_agent_worker_mutation_and_authorization():
    with tempfile.TemporaryDirectory() as tmp_dir:
        ws_path = Path(tmp_dir)
        boundary = LinuxExecutionBoundary(ws_path, require_sandbox=False)
        worker = PatchAgentWorker(boundary=boundary)

        # Stage mutations
        worker.stage_file_mutation("src/math.py", "def add(a, b): return a + b\n")

        # Authorized request allowing write to src/math.py
        fs_access = (S.FsAccess(path="src/math.py", mode=S.FsMode.WRITE),)
        req = _make_sample_authorized_request(fencing_token=42, filesystem_accesses=fs_access)
        boundary_ctx = _make_sample_boundary_context(fencing_token=42)
        handle = LocalWorkspaceSnapshotHandle(ws_path, "ws", "snap-1", 42)

        # Execute
        result = worker.execute(req, boundary_ctx, handle, write_paths=("src/math.py",))

        assert result.claim_status is S.WorkerClaimStatus.CLAIMED_COMPLETE
        assert "src/math.py" in result.produced_artifacts

        written_file = ws_path / "src" / "math.py"
        assert written_file.exists()
        assert "def add(a, b):" in written_file.read_text(encoding="utf-8")

        # Test unauthorized path rejection
        worker.stage_file_mutation("unauthorized.py", "secret = 1\n")
        with pytest.raises(PermissionError, match="not permitted"):
            worker.execute(req, boundary_ctx, handle, write_paths=("src/math.py",))


def test_subprocess_tool_worker_execution():
    from tests.helpers.test_boundary import TestOnlyUnsandboxedBoundary
    with tempfile.TemporaryDirectory() as tmp_dir:
        ws_path = Path(tmp_dir)
        boundary = TestOnlyUnsandboxedBoundary(ws_path)
        worker = SubprocessToolWorker(boundary=boundary)

        req = _make_sample_authorized_request(fencing_token=10)
        boundary_ctx = _make_sample_boundary_context(fencing_token=10)
        handle = LocalWorkspaceSnapshotHandle(ws_path, "ws", "snap-1", 10)

        result = worker.execute(
            req,
            boundary_ctx,
            handle,
            _gate_capability=boundary._gate_capability,
            argv=[sys.executable, "-c", "print('tool output')"],
        )

        assert result.claim_status is S.WorkerClaimStatus.CLAIMED_COMPLETE
        assert worker._last_result is not None
        assert b"tool output" in worker._last_result.stdout


def test_patch_agent_worker_traversal_and_fail_closed():
    """Verify PatchAgentWorker blocks traversal and fails closed on empty allowed write paths."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        ws_path = Path(tmp_dir)
        boundary = LinuxExecutionBoundary(ws_path, require_sandbox=False)
        worker = PatchAgentWorker(boundary=boundary)

        req_empty = _make_sample_authorized_request(fencing_token=50, filesystem_accesses=())
        boundary_ctx = _make_sample_boundary_context(fencing_token=50)
        handle = LocalWorkspaceSnapshotHandle(ws_path, "ws", "snap-1", 50)

        # 1. Fail closed if allowed_write_paths is empty
        worker.stage_file_mutation("valid.py", "x = 1\n")
        with pytest.raises(PermissionError, match="allowed_write_paths is empty"):
            worker.execute(req_empty, boundary_ctx, handle, write_paths=())

        # 2. Block path traversal via ../../ in stage_file_mutation
        worker = PatchAgentWorker(boundary=boundary)
        with pytest.raises(PermissionError, match="escapes workspace"):
            worker.stage_file_mutation("../../escape.py", "x = 1\n")

        # 3. Block path traversal via absolute path in stage_file_mutation
        worker = PatchAgentWorker(boundary=boundary)
        with pytest.raises(PermissionError, match="escapes workspace"):
            worker.stage_file_mutation("/etc/shadow", "root:x\n")

        # 4. Block path traversal via patch_generator returning escaping path
        generator_escaping = lambda req, ctx: {"../../escape_gen.py": "x = 1\n"}
        worker_gen = PatchAgentWorker(boundary=boundary, patch_generator=generator_escaping)
        with pytest.raises(PermissionError, match="escapes workspace"):
            worker_gen.execute(req_empty, boundary_ctx, handle, write_paths=("escape_gen.py",))

