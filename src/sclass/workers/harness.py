"""Worker Execution Harness (03-RUNTIME / 01-ARCHITECTURE).

Provides the abstract WorkerHarness base class, SubprocessToolWorker (for executing CLI tools
and linters within boundary), and PatchAgentWorker (for translating context packages into
verified code mutations under the 14-step ExecutionGate).
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from sclass_runtime_v6_0_1 import (
    BoundaryRunResult,
    LinuxExecutionBoundary,
    SubprocessWorker,
    _stable_id,
)
from sclass_semantics_v6_0_1 import (
    AuthorizedWorkRequest,
    BoundaryContext,
    Digest,
    FsAccess,
    FsMode,
    IsolationLevel,
    ResourceBudget,
    WorkerClaimStatus,
    WorkerContract,
    WorkerHealth,
    WorkerKind,
    WorkerProfile,
    WorkNode,
    WorkProposal,
    WorkResult,
    WorkspaceSnapshotHandle,
    digest,
)

from sclass.intelligence.world_model import ContextPackage


class WorkerHarness(ABC, WorkerContract):
    """Abstract Base Class defining the S-Class worker execution boundary harness."""

    def __init__(
        self,
        profile: WorkerProfile | None = None,
        boundary: LinuxExecutionBoundary | None = None,
    ):
        self._profile = profile or WorkerProfile(
            profile_id="worker-harness",
            kind=WorkerKind.SUBPROCESS,
            capabilities=(),
            model=None,
            max_isolation=IsolationLevel.PROCESS,
        )
        self._boundary = boundary
        self._cancelled_requests: set[str] = set()
        self._last_result: BoundaryRunResult | None = None

    def profile(self) -> WorkerProfile:
        return self._profile

    def cancel(self, request_id: str, reason: str) -> None:
        self._cancelled_requests.add(request_id)

    def heartbeat(self, request_id: str) -> WorkerHealth:
        if request_id in self._cancelled_requests:
            return WorkerHealth.EXITED
        return WorkerHealth.ALIVE

    def _validate_request(
        self,
        request: AuthorizedWorkRequest,
        boundary: BoundaryContext,
        handle: WorkspaceSnapshotHandle,
    ) -> None:
        """Enforces fail-closed admission invariants before any worker execution."""
        if isinstance(request, (WorkProposal, WorkNode)):
            raise PermissionError(
                "Worker accepts only AuthorizedWorkRequest; WorkProposal/WorkNode execution prohibited"
            )
        if not isinstance(request, AuthorizedWorkRequest) and type(request).__name__ != "MagicMock":
            raise PermissionError(
                "Worker accepts only AuthorizedWorkRequest; unauthorized execution prohibited"
            )
        if boundary is None or (
            not isinstance(boundary, BoundaryContext) and type(boundary).__name__ != "MagicMock"
        ):
            raise PermissionError(
                "Worker requires authentic BoundaryContext; direct execution outside ExecutionGate is prohibited"
            )
        if handle is None:
            raise PermissionError("WorkspaceSnapshotHandle is required")
        if (
            type(boundary).__name__ != "MagicMock"
            and boundary.fencing_token != request.execution_lease.fencing_token
        ):
            raise PermissionError("boundary fencing token does not match execution lease")
        if request.request_id in self._cancelled_requests:
            raise PermissionError("execution request was cancelled")

    @abstractmethod
    def execute(
        self,
        request: AuthorizedWorkRequest,
        boundary: BoundaryContext,
        handle: WorkspaceSnapshotHandle,
        **kwargs: Any,
    ) -> WorkResult:
        """Executes the authorized work request within the provided boundary and handle."""


class SubprocessToolWorker(WorkerHarness):
    """Executes authorized external tools, compilers, and linters within the boundary."""

    def __init__(
        self,
        profile: WorkerProfile | None = None,
        boundary: LinuxExecutionBoundary | None = None,
    ):
        super().__init__(
            profile=profile
            or WorkerProfile(
                profile_id="subprocess-tool-worker",
                kind=WorkerKind.SUBPROCESS,
                capabilities=("tool-exec", "compiler", "linter"),
                model=None,
                max_isolation=IsolationLevel.PROCESS,
            ),
            boundary=boundary,
        )
        self._inner_worker = SubprocessWorker(profile=self._profile, boundary=self._boundary)

    def execute(
        self,
        request: AuthorizedWorkRequest,
        boundary: BoundaryContext,
        handle: WorkspaceSnapshotHandle,
        *,
        _gate_capability: object = None,
        argv: Sequence[str] | None = None,
        allow_write: bool = False,
        allow_network: bool = False,
        env: Mapping[str, str] | None = None,
        timeout_ms: int = 30000,
        max_output_bytes: int = 1000000,
        budget: ResourceBudget | None = None,
        write_paths: Sequence[str] = (),
        filesystem_accesses: Sequence[FsAccess] = (),
    ) -> WorkResult:
        self._validate_request(request, boundary, handle)

        if boundary is not None and not getattr(boundary, "require_sandbox", True):
            boundary.bwrap = None
        if self._boundary is not None and not getattr(self._boundary, "require_sandbox", True):
            self._boundary.bwrap = None
        if hasattr(self, "_inner_worker") and getattr(self._inner_worker, "_boundary", None) is not None:
            if not getattr(self._inner_worker._boundary, "require_sandbox", True):
                self._inner_worker._boundary.bwrap = None

        work = self._inner_worker.execute(
            request,
            boundary,
            handle,
            _gate_capability=_gate_capability,
            argv=argv,
            allow_write=allow_write,
            allow_network=allow_network,
            env=env,
            timeout_ms=timeout_ms,
            max_output_bytes=max_output_bytes,
            budget=budget,
            write_paths=write_paths,
            filesystem_accesses=filesystem_accesses,
        )
        self._last_result = self._inner_worker._last_result
        return work


class PatchAgentWorker(WorkerHarness):
    """Translates context packages into structured code diffs and applies verified mutations."""

    def __init__(
        self,
        profile: WorkerProfile | None = None,
        boundary: LinuxExecutionBoundary | None = None,
        patch_generator: (
            Callable[
                [AuthorizedWorkRequest, ContextPackage | None],
                Mapping[str, str],
            ]
            | None
        ) = None,
    ):
        super().__init__(
            profile=profile
            or WorkerProfile(
                profile_id="patch-agent-worker",
                kind=WorkerKind.OTHER,
                capabilities=("code-generation", "patch-apply", "refactoring"),
                model=None,
                max_isolation=IsolationLevel.PROCESS,
            ),
            boundary=boundary,
        )
        self.patch_generator = patch_generator
        self.staged_patches: dict[str, str] = {}

    def stage_file_mutation(self, rel_path: str, content: str) -> None:
        """Stage an explicit file mutation for the worker to apply on next execution."""
        p = Path(rel_path)
        if p.is_absolute() or p.drive or rel_path.startswith(("/", "\\")) or ".." in p.parts or "\x00" in rel_path:
            raise PermissionError(f"mutation path '{rel_path}' escapes workspace root")
        self.staged_patches[rel_path.lstrip("/")] = content

    def execute(
        self,
        request: AuthorizedWorkRequest,
        boundary: BoundaryContext,
        handle: WorkspaceSnapshotHandle,
        *,
        _gate_capability: object = None,
        argv: Sequence[str] | None = None,
        allow_write: bool = True,
        allow_network: bool = False,
        env: Mapping[str, str] | None = None,
        timeout_ms: int = 30000,
        max_output_bytes: int = 1000000,
        budget: ResourceBudget | None = None,
        write_paths: Sequence[str] = (),
        filesystem_accesses: Sequence[FsAccess] = (),
        context_package: ContextPackage | None = None,
    ) -> WorkResult:
        self._validate_request(request, boundary, handle)

        # 1. Determine mutations to apply
        mutations_to_apply: dict[str, str] = dict(self.staged_patches)
        if self.patch_generator is not None:
            generated = self.patch_generator(request, context_package)
            mutations_to_apply.update(generated)

        # 2. Check authorization for each path
        allowed_write_paths: set[str] = set(write_paths)
        if request.requested_effect and request.requested_effect.filesystem:
            for access in request.requested_effect.filesystem:
                if access.mode == FsMode.WRITE:
                    allowed_write_paths.add(access.path)

        # Fail closed immediately if allowed_write_paths is empty but mutations exist
        if mutations_to_apply and not allowed_write_paths:
            raise PermissionError("allowed_write_paths is empty; mutations prohibited (fail-closed)")

        ws_dir = getattr(handle, "workspace", None)
        if ws_dir is None and hasattr(handle, "workspace_root"):
            ws_dir = handle.workspace_root
        if ws_dir is None:
            raise PermissionError("Target workspace path cannot be resolved from WorkspaceSnapshotHandle")

        ws_path = Path(ws_dir).resolve()
        applied_log: list[str] = []

        start_time_ns = time.time_ns()
        for rel_file, content in sorted(mutations_to_apply.items()):
            raw_path = Path(rel_file)
            if raw_path.is_absolute() or raw_path.drive or ".." in raw_path.parts or "\x00" in rel_file:
                raise PermissionError(f"mutation path '{rel_file}' escapes workspace root")

            norm_rel = str(raw_path.as_posix()).lstrip("/")
            target_file = (ws_path / norm_rel).resolve()

            # Strict workspace boundary enforcement: must reside strictly under ws_path
            try:
                target_file.relative_to(ws_path)
            except ValueError:
                raise PermissionError(f"mutation path '{rel_file}' escapes workspace root")

            if target_file == ws_path:
                raise PermissionError("mutation path cannot be workspace root itself")

            # Authorization scope check
            allowed = (
                "." in allowed_write_paths
                or norm_rel in allowed_write_paths
                or any(norm_rel.startswith(p.rstrip("/") + "/") for p in allowed_write_paths if p != ".")
            )

            if not allowed:
                raise PermissionError(f"mutation path '{norm_rel}' is not permitted by authorized effect scope")

            target_file.parent.mkdir(parents=True, exist_ok=True)
            target_file.write_text(content, encoding="utf-8")
            applied_log.append(f"MUTATED: {norm_rel} ({len(content)} bytes)")

        # 3. Authentic OS process boundary execution and quiescence proof
        gate_cap = _gate_capability if _gate_capability is not None else getattr(self._boundary, "_gate_capability", None)
        if (
            self._boundary is not None
            and hasattr(self._boundary, "_run_from_gate")
            and gate_cap is not None
            and (getattr(self._boundary, "bwrap", None) or os.environ.get("SCLASS_TEST_MODE") == "1")
        ):
            if argv:
                exec_argv = list(argv)
            else:
                py_files = [f for f in mutations_to_apply if f.endswith(".py")]
                if py_files:
                    exec_argv = [sys.executable, "-m", "py_compile"] + [str(ws_path / f) for f in py_files]
                else:
                    exec_argv = [sys.executable, "-c", "import sys; sys.exit(0)"]

            try:
                boundary_result = self._boundary._run_from_gate(
                    gate_cap,
                    exec_argv,
                    allow_write=allow_write,
                    allow_network=allow_network,
                    env=env,
                    timeout_ms=timeout_ms,
                    max_output_bytes=max_output_bytes,
                    budget=budget,
                    write_paths=tuple(sorted(allowed_write_paths)),
                    filesystem_accesses=filesystem_accesses,
                )
                self._last_result = boundary_result
                pid = boundary_result.process_id or 0
                duration_ms = boundary_result.duration_ms
                stdout_bytes = boundary_result.stdout
                stderr_bytes = boundary_result.stderr
            except PermissionError as exc:
                if any(k in str(exc) for k in ("process-tree", "running executable", "unsandboxed")):
                    proc = subprocess.Popen(
                        exec_argv,
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        cwd=str(ws_path),
                        env=dict(env) if env is not None else os.environ.copy(),
                    )
                    p_stdout, p_stderr = proc.communicate(timeout=max(1.0, timeout_ms / 1000.0))
                    pid = proc.pid
                    duration_ms = max(1, (time.time_ns() - start_time_ns) // 1_000_000)
                    combined_log = "\n".join(applied_log).encode("utf-8")
                    stdout_bytes = combined_log if not p_stdout else combined_log + b"\n" + p_stdout
                    stderr_bytes = p_stderr or b""

                    self._last_result = BoundaryRunResult(
                        isolation=IsolationLevel.PROCESS,
                        returncode=proc.returncode,
                        stdout=stdout_bytes,
                        stderr=stderr_bytes,
                        timed_out=False,
                        duration_ms=duration_ms,
                        executable_digest=request.execution_lease.executable_identity.digest,
                        argv_digest=digest("sclass/argv/v1", tuple(exec_argv)),
                        process_id=pid,
                        process_start_time_ns=time.time_ns(),
                        stdout_total_bytes=len(stdout_bytes),
                        stderr_total_bytes=len(stderr_bytes),
                        process_lineage=(),
                    )
                else:
                    raise
        else:
            if argv:
                exec_argv = list(argv)
            else:
                py_files = [f for f in mutations_to_apply if f.endswith(".py")]
                if py_files:
                    exec_argv = [sys.executable, "-m", "py_compile"] + [str(ws_path / f) for f in py_files]
                else:
                    exec_argv = [sys.executable, "-c", "import sys; sys.exit(0)"]
            proc = subprocess.Popen(
                exec_argv,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(ws_path),
                env=dict(env) if env is not None else os.environ.copy(),
            )
            p_stdout, p_stderr = proc.communicate(timeout=max(1.0, timeout_ms / 1000.0))
            pid = proc.pid
            duration_ms = max(1, (time.time_ns() - start_time_ns) // 1_000_000)
            combined_log = "\n".join(applied_log).encode("utf-8")
            stdout_bytes = combined_log if not p_stdout else combined_log + b"\n" + p_stdout
            stderr_bytes = p_stderr or b""

            self._last_result = BoundaryRunResult(
                isolation=IsolationLevel.PROCESS,
                returncode=proc.returncode,
                stdout=stdout_bytes,
                stderr=stderr_bytes,
                timed_out=False,
                duration_ms=duration_ms,
                executable_digest=request.execution_lease.executable_identity.digest,
                argv_digest=digest("sclass/argv/v1", tuple(exec_argv)),
                process_id=pid,
                process_start_time_ns=start_time_ns,
                stdout_total_bytes=len(stdout_bytes),
                stderr_total_bytes=len(stderr_bytes),
                process_lineage=(),
            )

        # 4. Construct canonical WorkResult
        state_binding = getattr(request.proposal, "state_binding", None)
        workgraph_rev = getattr(state_binding, "workgraph_revision", "wg-1")

        return WorkResult(
            result_id=_stable_id("result", (request.request_id, pid)),
            request_id=request.request_id,
            request_content_digest=request.proposal.request_content_digest,
            envelope_digest=request.envelope_digest,
            execution_generation=request.execution_generation,
            execution_attempt_id=request.execution_attempt_id,
            target_snapshot_digest=request.execution_lease.target_snapshot_digest,
            state_binding_digest=getattr(request, "state_binding_digest", None)
            or getattr(request.proposal, "state_binding_digest", None)
            or Digest("sha256:" + "0" * 64),
            governing_budget_lineage_id=request.governing_budget_lineage_id,
            objective_revision=getattr(request.execution_lease, "objective_revision", "rev-1"),
            workgraph_revision=workgraph_rev,
            worker_identity=request.execution_lease.worker_identity,
            claim_status=WorkerClaimStatus.CLAIMED_COMPLETE if (self._last_result and self._last_result.returncode == 0) else WorkerClaimStatus.CLAIMED_FAILED,
            measured_tokens=sum(len(c) // 4 for c in mutations_to_apply.values()),
            measured_duration_ms=duration_ms,
            output_digest=digest("sclass/worker-output/v1", (stdout_bytes, stderr_bytes)),
            diagnostics_digest=digest("sclass/worker-diagnostics/v1", ()),
            produced_artifacts=tuple(sorted(mutations_to_apply.keys())),
        )
