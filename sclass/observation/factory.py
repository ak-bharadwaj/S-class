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
from sclass.verification.detector import StandardVerifierDetector, DetectionResult
from sclass.verification.registry import get_verifier_registry
from sclass.verification.result_parser import compute_output_hash, NormalizedTestResult
from sclass.observation.fingerprint import compute_workspace_snapshot, compute_workspace_fingerprint
from sclass.observation.receipt import save_receipt
from sclass.trust.ledger import LocalLedger
from sclass.core.errors import ObservationIntegrityError, SecurityViolationError
from sclass.observation.lifecycle import ObservationLifecycleTracker, ObservationLifecycleState


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
    ) -> ObservedReceipt:
        """
        Transforms an authentic ProcessExecutionResult into an immutable ObservedReceipt.
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
        detector = StandardVerifierDetector()
        det_result = detector.detect(identity)
        authoritative_verifier = det_result.verifier_id
        authoritative_kind = "test_runner" if authoritative_verifier not in ("generic", "none", "") else "generic_command"

        # 2. Output hashing
        stdout_hash = hashlib.sha256(execution_result.stdout.encode("utf-8")).hexdigest()
        stderr_hash = hashlib.sha256(execution_result.stderr.encode("utf-8")).hexdigest()

        # 3. Workspace state after execution
        snapshot_after = compute_workspace_snapshot(ws)
        fingerprint_after = compute_workspace_fingerprint(snapshot_after)
        fp_before = fingerprint_before or fingerprint_after

        # 4. Compute file changes between before and after snapshots
        files_changed = []
        if snapshot_before and snapshot_after:
            files_before = set(snapshot_before.get("files", {}).keys())
            files_after = set(snapshot_after.get("files", {}).keys())
            # Added or removed files
            files_changed.extend(list(files_after.symmetric_difference(files_before)))
            # Modified files
            for fpath in files_after.intersection(files_before):
                if snapshot_after["files"][fpath] != snapshot_before["files"][fpath]:
                    files_changed.append(fpath)
            files_changed = sorted(list(set(files_changed)))

        # 5. Parse structured test results if recognized verifier
        structured_res = None
        registry = get_verifier_registry()
        verifier_plugin = registry.get_verifier(authoritative_verifier)
        if verifier_plugin and hasattr(verifier_plugin, "parse_result"):
            try:
                structured_res = verifier_plugin.parse_result(execution_result)
            except Exception:
                structured_res = None

        receipt_id = f"rcpt_{uuid.uuid4().hex[:12]}"

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
        }

        # 6. Bind authoritative hash across all execution and observation parameters
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

        # 7. Construct receipt
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

        # 8. Atomically anchor into LocalLedger before publishing
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
            "fingerprint_before": fp_before,
            "fingerprint_after": fingerprint_after,
            "command": " ".join(identity.actual_argv),
            "exit_code": execution_result.exit_code,
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

        # 9. Seal receipt to ensure absolute post-issuance immutability
        object.__setattr__(receipt, "_sealed", True)

        return receipt



TrustedObservationRuntime = ObservationFactory
