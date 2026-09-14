"""
S-Class Observation: Trusted Observation Runtime & Factory.
The SINGLE authoritative gateway for producing ObservedReceipt instances.
Only accepts authentic ProcessExecutionResult from S-Class execution infrastructure.
Enforces Invariant 2 (observation originates only from trusted execution) and Invariant 3.
"""

from __future__ import annotations
import os
import uuid
import json
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple

from sclass.domain.evidence import ObservedReceipt
from sclass.execution.process import ProcessExecutionResult
from sclass.execution.identity import ExecutionIdentity, ExecutionIdentityState
from sclass.observation.fingerprint import compute_workspace_snapshot, compute_workspace_fingerprint
from sclass.observation.receipt import save_receipt
from sclass.trust.ledger import LocalLedger
from sclass.core.errors import ObservationIntegrityError, SecurityViolationError
from sclass.observation.lifecycle import ObservationLifecycleTracker, ObservationLifecycleState
from sclass.observation.record import (
    ObservationRecord,
    ProcessTelemetry,
    GitRevisionState,
    WorkspaceDelta,
    FileMutation,
    redact_observation_secrets,
)
from sclass.observation.git_observer import GitObserver
from sclass.observation.delta import DeltaCalculator
from sclass.telemetry.tracing import get_local_tracer, SPAN_OBSERVATION_RECORD


def compute_authoritative_receipt_hash(fields: Dict[str, Any]) -> str:
    """
    Computes canonical SHA-256 digest binding execution identity, requested vs actual argv,
    binary hashes, timestamps, exit code, output hashes, workspace fingerprints, and verifier.
    """
    canonical_json = json.dumps(fields, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


class ObservationFactory:
    """Authoritative factory for creating and anchoring ObservedReceipt instances."""

    @classmethod
    def create_observation(
        cls,
        execution_result: ProcessExecutionResult,
        workspace_dir: str,
        task_id: str = "task_default",
        claim_id: str = "claim_default",
        agent: str = "agent",
        action: str = "run_command",
        fingerprint_before: Optional[str] = None,
        snapshot_before: Optional[Dict[str, Any]] = None,
        ledger: Optional[LocalLedger] = None,
        requested_verifier: Optional[str] = None,
        revision_before: Optional[str] = None,
    ) -> ObservedReceipt:
        """
        Transforms an authentic ProcessExecutionResult into an immutable ObservedReceipt
        bound to an independent ObservationRecord (RC.3 / Layer E).
        Atomically commits the observation to LocalLedger.
        """
        if not isinstance(execution_result, ProcessExecutionResult):
            raise ObservationIntegrityError(
                "ObservationFactory only creates receipts from authentic ProcessExecutionResult instances."
            )

        ws = os.path.abspath(workspace_dir)
        identity = execution_result.identity

        # Observation State Machine
        tracker = ObservationLifecycleTracker(ObservationLifecycleState.REQUESTED)
        tracker.transition_to(ObservationLifecycleState.SPAWNED, "Subprocess successfully spawned")

        if identity.identity_state == ExecutionIdentityState.IDENTITY_UNCERTAIN.value:
            tracker.transition_to(ObservationLifecycleState.IDENTITY_UNCERTAIN, "Process binary or identity uncertain")
        else:
            tracker.transition_to(ObservationLifecycleState.IDENTIFIED, f"Process identified: {identity.executable_name}")
            tracker.transition_to(ObservationLifecycleState.OBSERVED, "Process completed and outputs captured")

        # 1. Authoritative verifier detection (Invariant 3: derived from process identity, never supplied)
        from sclass.verification.detector import StandardVerifierDetector
        from sclass.verification.registry import get_verifier_registry

        detector = StandardVerifierDetector()
        det_result = detector.detect(identity)
        authoritative_verifier = det_result.verifier_id
        authoritative_kind = "test_runner" if authoritative_verifier not in ("generic", "none", "") else "generic_command"

        # 2. Output hashing and byte measurements
        stdout_bytes_raw = execution_result.stdout.encode("utf-8")
        stderr_bytes_raw = execution_result.stderr.encode("utf-8")
        stdout_hash = hashlib.sha256(stdout_bytes_raw).hexdigest()
        stderr_hash = hashlib.sha256(stderr_bytes_raw).hexdigest()
        stdout_bytes = len(stdout_bytes_raw)
        stderr_bytes = len(stderr_bytes_raw)

        # 3. Workspace state after execution
        snapshot_after = compute_workspace_snapshot(ws)
        fingerprint_after = compute_workspace_fingerprint(snapshot_after)
        fp_before = fingerprint_before or fingerprint_after

        # 4. Compute fine-grained WorkspaceDelta
        workspace_delta = DeltaCalculator.compute_delta(
            snapshot_before=snapshot_before,
            snapshot_after=snapshot_after,
            workspace_dir=ws,
            fingerprint_before=fp_before,
            fingerprint_after=fingerprint_after,
        )
        files_changed = sorted(list(set(workspace_delta.files_added + workspace_delta.files_modified + workspace_delta.files_deleted)))

        # 5. Git observation
        git_state = GitObserver.capture_state(ws, revision_before=revision_before)

        # 6. Real OS process telemetry
        exe_hash = identity.executable_hash
        if not exe_hash or len(exe_hash) != 64 or exe_hash == "0" * 64:
            if identity.executable_path and os.path.isfile(identity.executable_path):
                from sclass.observation.fingerprint import compute_file_hash
                h = compute_file_hash(identity.executable_path)
                if h:
                    exe_hash = h
            if not exe_hash or len(exe_hash) != 64:
                exe_hash = hashlib.sha256((identity.executable_path or "process_binary").encode("utf-8")).hexdigest()

        proc_telemetry = ProcessTelemetry(
            pid=identity.pid,
            executable_path=identity.executable_path,
            executable_hash=exe_hash,
            requested_argv=identity.requested_argv,
            actual_argv=identity.actual_argv,
            process_start_time=identity.process_start_time or execution_result.started_at,
            process_end_time=execution_result.finished_at,
            duration_ms=execution_result.duration_ms,
            cpu_user_ms=getattr(identity, "cpu_user_ms", None),
            cpu_kernel_ms=getattr(identity, "cpu_kernel_ms", None),
        )

        # 7. Parse structured test results if recognized verifier
        structured_res = None
        registry = get_verifier_registry()
        verifier_plugin = registry.get_verifier(authoritative_verifier)
        if verifier_plugin and hasattr(verifier_plugin, "parse_result"):
            try:
                structured_res = verifier_plugin.parse_result(execution_result)
            except Exception:
                structured_res = None

        receipt_id = f"rcpt_{uuid.uuid4().hex[:12]}"

        # 8. OpenTelemetry semantic spans with secret redaction
        cmd_str = " ".join(identity.actual_argv) if identity.actual_argv else ""
        cmd_redacted = redact_observation_secrets(cmd_str)
        span_attrs = {
            "sclass.action.id": redact_observation_secrets(action),
            "sclass.evidence.id": receipt_id,
            "process.pid": identity.pid,
            "process.executable.hash": exe_hash,
            "process.executable.path": redact_observation_secrets(identity.executable_path),
            "process.exit_code": execution_result.exit_code,
            "process.command": cmd_redacted,
            "scm.git.revision": git_state.revision_after or git_state.revision_before or "",
            "scm.git.is_repository": git_state.is_git_repository,
            "workspace.fingerprint.before": fp_before,
            "workspace.fingerprint.after": fingerprint_after,
            "workspace.fingerprint.delta": workspace_delta.tree_fingerprint_after != workspace_delta.tree_fingerprint_before,
        }
        if git_state.branch:
            span_attrs["scm.git.branch"] = git_state.branch

        tracer = get_local_tracer(ws)
        span_trace_id = uuid.uuid4().hex
        span_parent_id = None
        if tracer.current_span:
            span_trace_id = tracer.current_span.trace_id
            span_parent_id = tracer.current_span.span_id
            tracer.current_span.set_attributes(span_attrs)

        semantic_span = {
            "name": SPAN_OBSERVATION_RECORD,
            "trace_id": span_trace_id,
            "span_id": uuid.uuid4().hex[:16],
            "parent_span_id": span_parent_id,
            "attributes": span_attrs,
            "start_time": execution_result.started_at,
            "end_time": execution_result.finished_at,
            "duration_ms": execution_result.duration_ms,
            "status": "OK" if execution_result.exit_code == 0 else "ERROR",
        }

        # 9. Construct authoritative independent ObservationRecord
        obs_record = ObservationRecord(
            record_id=f"obsrec_{uuid.uuid4().hex[:12]}",
            task_id=task_id,
            claim_id=claim_id,
            command=cmd_redacted,
            exit_code=execution_result.exit_code,
            stdout_hash=stdout_hash,
            stderr_hash=stderr_hash,
            stdout_bytes=stdout_bytes,
            stderr_bytes=stderr_bytes,
            process=proc_telemetry,
            workspace=workspace_delta,
            git=git_state,
            semantic_spans=(semantic_span,),
            created_at=datetime.now(timezone.utc).isoformat(),
            raw_stdout=execution_result.stdout,
            raw_stderr=execution_result.stderr,
        )

        meta = {
            "execution_identity": identity.to_dict(),
            "requested_verifier": requested_verifier,
            "detected_verifier": authoritative_verifier,
            "verifier_detection": det_result.to_dict(),
            "workspace_snapshot": snapshot_after,
            "workspace_fingerprint": fingerprint_after,
            "workspace_fingerprint_before": fp_before,
            "structured_result": structured_res.to_dict() if structured_res else None,
            "duration_ms": execution_result.duration_ms,
            "lifecycle_state": tracker.current_state.value,
            "lifecycle_history": tracker.to_dict()["history"],
            "stdout": execution_result.stdout,
            "stderr": execution_result.stderr,
            "observation_record_id": obs_record.record_id,
            "observation_record_hash": obs_record.compute_hash(),
            "git_revision": git_state.revision_after or "",
            "observation_record": obs_record.to_dict(),
            "workspace_delta": workspace_delta.to_dict(),
            "git_state": git_state.to_dict(),
            "process_telemetry": proc_telemetry.to_dict(),
            "semantic_spans": [semantic_span],
        }

        # 10. Bind authoritative hash across all execution and observation parameters
        hash_payload = {
            "receipt_id": receipt_id,
            "task_id": task_id,
            "claim_id": claim_id,
            "agent": agent,
            "action": action,
            "workspace": ws,
            "command": " ".join(identity.actual_argv),
            "requested_argv": list(identity.requested_argv),
            "actual_argv": list(identity.actual_argv),
            "executable_hash": identity.executable_hash,
            "execution_mode": identity.execution_mode,
            "process_start_time": identity.process_start_time,
            "exit_code": execution_result.exit_code,
            "started_at": execution_result.started_at,
            "finished_at": execution_result.finished_at,
            "stdout_hash": stdout_hash,
            "stderr_hash": stderr_hash,
            "files_changed": sorted(files_changed),
            "execution_kind": authoritative_kind,
            "verifier": authoritative_verifier,
            "workspace_fingerprint_before": fp_before,
            "workspace_fingerprint": fingerprint_after,
            "structured_result": structured_res.to_dict() if structured_res else None,
        }
        receipt_hash = compute_authoritative_receipt_hash(hash_payload)

        # 11. Construct receipt with cryptographic provenance bindings
        receipt = ObservedReceipt(
            receipt_id=receipt_id,
            task_id=task_id,
            claim_id=claim_id,
            agent=agent,
            action=action,
            workspace=ws,
            command=" ".join(identity.actual_argv),
            exit_code=execution_result.exit_code,
            started_at=execution_result.started_at,
            finished_at=execution_result.finished_at,
            stdout_hash=stdout_hash,
            stderr_hash=stderr_hash,
            files_changed=files_changed,
            metadata=meta,
            execution_kind=authoritative_kind,
            verifier=authoritative_verifier,
            workspace_fingerprint=fingerprint_after,
            verified=False,
        )
        object.__setattr__(receipt, "receipt_hash", receipt_hash)
        object.__setattr__(receipt, "observation_record_id", obs_record.record_id)
        object.__setattr__(receipt, "observation_record_hash", obs_record.compute_hash())
        object.__setattr__(receipt, "git_revision", git_state.revision_after or "")
        object.__setattr__(receipt, "observation_record", obs_record)
        object.__setattr__(receipt, "workspace_delta", workspace_delta)
        object.__setattr__(receipt, "git_state", git_state)
        object.__setattr__(receipt, "process_telemetry", proc_telemetry)

        # 12. Atomically anchor into LocalLedger before publishing
        if tracker.is_failed:
            # Failure states are never silently converted into trusted evidence!
            save_receipt(receipt, ws)
            object.__setattr__(receipt, "_sealed", True)
            return receipt

        if ledger is None:
            ledger = LocalLedger(workspace_dir=ws)

        try:
            tracker.transition_to(ObservationLifecycleState.ANCHORED, "Committing observation to LocalLedger")
        except Exception:
            pass

        def write_receipt_hook(entry: Dict[str, Any]) -> None:
            save_receipt(receipt, ws)

        ledger_payload = {
            "receipt_id": receipt.receipt_id,
            "receipt_hash": receipt_hash,
            "observation_record_id": obs_record.record_id,
            "observation_record_hash": obs_record.compute_hash(),
            "pid": obs_record.process.pid,
            "executable_hash": obs_record.process.executable_hash,
            "exit_code": obs_record.exit_code,
            "fingerprint_before": obs_record.workspace.tree_fingerprint_before,
            "fingerprint_after": obs_record.workspace.tree_fingerprint_after,
            "git_revision": obs_record.git.revision_after or "",
            "command": " ".join(identity.actual_argv),
            "execution_kind": authoritative_kind,
            "verifier": authoritative_verifier,
            "execution_identity": identity.to_dict(),
            "timestamp": execution_result.finished_at,
            "lifecycle_state": tracker.current_state.value,
        }

        try:
            ledger.append_atomic("OBSERVATION", ledger_payload, commit_hook=write_receipt_hook)
            try:
                tracker.transition_to(ObservationLifecycleState.PUBLISHED, "Observation atomically anchored and published")
                meta["lifecycle_state"] = tracker.current_state.value
            except Exception:
                pass
        except Exception as err:
            try:
                tracker.transition_to(ObservationLifecycleState.ANCHOR_FAILED, str(err))
            except Exception:
                pass
            raise ObservationIntegrityError(
                f"Atomic commit of observation failed. Observation not published: {err}"
            ) from err

        # 13. Seal receipt to ensure absolute post-issuance immutability
        object.__setattr__(receipt, "_sealed", True)

        return receipt

    @classmethod
    def create_observation_record(
        cls,
        execution_result: ProcessExecutionResult,
        workspace_dir: str,
        task_id: str = "task_default",
        claim_id: str = "claim_default",
        action: str = "run_command",
        fingerprint_before: Optional[str] = None,
        snapshot_before: Optional[Dict[str, Any]] = None,
        revision_before: Optional[str] = None,
    ) -> ObservationRecord:
        """
        Constructs and returns an authoritative ObservationRecord directly from OS execution reality.
        """
        ws = os.path.abspath(workspace_dir)
        identity = execution_result.identity
        stdout_bytes_raw = execution_result.stdout.encode("utf-8")
        stderr_bytes_raw = execution_result.stderr.encode("utf-8")
        stdout_hash = hashlib.sha256(stdout_bytes_raw).hexdigest()
        stderr_hash = hashlib.sha256(stderr_bytes_raw).hexdigest()
        stdout_bytes = len(stdout_bytes_raw)
        stderr_bytes = len(stderr_bytes_raw)

        snapshot_after = compute_workspace_snapshot(ws)
        fingerprint_after = compute_workspace_fingerprint(snapshot_after)
        fp_before = fingerprint_before or fingerprint_after

        workspace_delta = DeltaCalculator.compute_delta(
            snapshot_before=snapshot_before,
            snapshot_after=snapshot_after,
            workspace_dir=ws,
            fingerprint_before=fp_before,
            fingerprint_after=fingerprint_after,
        )

        git_state = GitObserver.capture_state(ws, revision_before=revision_before)

        exe_hash = identity.executable_hash
        if not exe_hash or len(exe_hash) != 64 or exe_hash == "0" * 64:
            if identity.executable_path and os.path.isfile(identity.executable_path):
                from sclass.observation.fingerprint import compute_file_hash
                h = compute_file_hash(identity.executable_path)
                if h:
                    exe_hash = h
            if not exe_hash or len(exe_hash) != 64:
                exe_hash = hashlib.sha256((identity.executable_path or "process_binary").encode("utf-8")).hexdigest()

        proc_telemetry = ProcessTelemetry(
            pid=identity.pid,
            executable_path=identity.executable_path,
            executable_hash=exe_hash,
            requested_argv=identity.requested_argv,
            actual_argv=identity.actual_argv,
            process_start_time=identity.process_start_time or execution_result.started_at,
            process_end_time=execution_result.finished_at,
            duration_ms=execution_result.duration_ms,
            cpu_user_ms=getattr(identity, "cpu_user_ms", None),
            cpu_kernel_ms=getattr(identity, "cpu_kernel_ms", None),
        )

        cmd_str = " ".join(identity.actual_argv) if identity.actual_argv else ""
        cmd_redacted = redact_observation_secrets(cmd_str)
        span_attrs = {
            "sclass.action.id": redact_observation_secrets(action),
            "process.pid": identity.pid,
            "process.executable.hash": exe_hash,
            "process.executable.path": redact_observation_secrets(identity.executable_path),
            "process.exit_code": execution_result.exit_code,
            "process.command": cmd_redacted,
            "scm.git.revision": git_state.revision_after or git_state.revision_before or "",
            "scm.git.is_repository": git_state.is_git_repository,
            "workspace.fingerprint.before": fp_before,
            "workspace.fingerprint.after": fingerprint_after,
            "workspace.fingerprint.delta": workspace_delta.tree_fingerprint_after != workspace_delta.tree_fingerprint_before,
        }
        if git_state.branch:
            span_attrs["scm.git.branch"] = git_state.branch

        semantic_span = {
            "name": SPAN_OBSERVATION_RECORD,
            "trace_id": uuid.uuid4().hex,
            "span_id": uuid.uuid4().hex[:16],
            "attributes": span_attrs,
            "start_time": execution_result.started_at,
            "end_time": execution_result.finished_at,
            "duration_ms": execution_result.duration_ms,
            "status": "OK" if execution_result.exit_code == 0 else "ERROR",
        }

        return ObservationRecord(
            record_id=f"obsrec_{uuid.uuid4().hex[:12]}",
            task_id=task_id,
            claim_id=claim_id,
            command=cmd_redacted,
            exit_code=execution_result.exit_code,
            stdout_hash=stdout_hash,
            stderr_hash=stderr_hash,
            stdout_bytes=stdout_bytes,
            stderr_bytes=stderr_bytes,
            process=proc_telemetry,
            workspace=workspace_delta,
            git=git_state,
            semantic_spans=(semantic_span,),
            created_at=datetime.now(timezone.utc).isoformat(),
            raw_stdout=execution_result.stdout,
            raw_stderr=execution_result.stderr,
        )




TrustedObservationRuntime = ObservationFactory
