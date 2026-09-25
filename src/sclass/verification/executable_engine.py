"""
S-Class Verification: ExecutableVerificationEngine.
Translates VerificationPlan into independently observed execution and verification.
"""
from __future__ import annotations
import os
import subprocess
from typing import Any, Optional, Dict
from sclass.domain.evidence import ObservedReceipt
from sclass.domain.verification import VerificationResult
from sclass.observation.git_observer import GitObserver
from sclass.observation.delta import DeltaCalculator
from sclass.observation.fingerprint import compute_workspace_snapshot


class ExecutableVerificationEngine:
    def __init__(self, workspace_dir: str):
        self.workspace_dir = workspace_dir
        self.git_observer = GitObserver()

    def execute_plan(self, plan: Any) -> VerificationResult:
        commands = getattr(plan, "commands", [])
        verifiers = getattr(plan, "verifiers", [])
        task_id = getattr(plan, "task_id", "task_exec")
        plan_id = getattr(plan, "plan_id", "plan_exec")
        claim_ids = getattr(plan, "claim_ids", ["claim_exec"])
        primary_claim = claim_ids[0] if claim_ids else "claim_exec"

        snap_before = compute_workspace_snapshot(self.workspace_dir)

        # Execute commands under independent authenticated OS execution
        from sclass.execution.identity import ExecutionIdentity, ExecutionIdentityState
        from sclass.verification.detector import StandardVerifierDetector, VerifierConfidence
        from sclass.verification.trust_registry import get_trust_registry, VerifierTrustMode

        last_exit = 0
        stdout_acc = []
        stderr_acc = []
        last_ident = None
        last_det_res = None
        trust_reg = get_trust_registry()
        detector = StandardVerifierDetector()

        is_test_runner_verification = any(
            v in ("test", "pytest", "jest", "vitest", "mocha", "playwright", "cargo", "go", "cargo-test", "go-test")
            for v in verifiers
        )

        for cmd in commands:
            cmd_args = list(cmd) if isinstance(cmd, list) else cmd.split()
            if not cmd_args:
                continue

            # 1. Capture authenticated execution identity (DEFECT-10)
            ident = ExecutionIdentity.capture(
                command_argv=cmd_args,
                cwd=self.workspace_dir,
            )
            last_ident = ident

            # 2. Check for missing/unresolvable binary
            if ident.identity_state == ExecutionIdentityState.IDENTITY_UNCERTAIN.value:
                return VerificationResult(
                    status="REJECT",
                    claim_id=primary_claim,
                    reason=f"Command '{cmd_args[0]}' has uncertain or unresolvable execution identity.",
                    observed_exit_code=1,
                    receipt_id=f"rcpt_{plan_id}_rejected",
                    metadata={"identity": ident.to_dict()},
                )

            # 3. Authoritative Trust Registry verification
            trust_mode = trust_reg.classify_binary_trust(execution=ident, workspace_dir=self.workspace_dir)
            if trust_mode == VerifierTrustMode.UNTRUSTED:
                return VerificationResult(
                    status="REJECT",
                    claim_id=primary_claim,
                    reason=f"Verification command '{ident.executable_name}' is UNTRUSTED under trust policy.",
                    observed_exit_code=1,
                    receipt_id=f"rcpt_{plan_id}_rejected",
                    metadata={"identity": ident.to_dict(), "trust_mode": trust_mode.value},
                )

            # 4. StandardVerifierDetector validation
            det_res = detector.detect(ident)
            last_det_res = det_res

            if is_test_runner_verification:
                if det_res.confidence != VerifierConfidence.AUTHORIZED:
                    return VerificationResult(
                        status="REJECT",
                        claim_id=primary_claim,
                        reason=(
                            f"Command '{cmd_args[0]}' is not an authorized test verifier: "
                            f"confidence={det_res.confidence.value}, reason={det_res.evidence.get('reason')}"
                        ),
                        observed_exit_code=1,
                        receipt_id=f"rcpt_{plan_id}_rejected",
                        metadata={"identity": ident.to_dict(), "detection": det_res.to_dict()},
                    )
            else:
                if trust_mode not in (
                    VerifierTrustMode.SYSTEM_TRUSTED,
                    VerifierTrustMode.TRUSTED,
                    VerifierTrustMode.WORKSPACE_TRUSTED,
                ):
                    return VerificationResult(
                        status="REJECT",
                        claim_id=primary_claim,
                        reason=f"Command '{cmd_args[0]}' failed authorization under trust policy (trust_mode={trust_mode.value}).",
                        observed_exit_code=1,
                        receipt_id=f"rcpt_{plan_id}_rejected",
                        metadata={"identity": ident.to_dict(), "trust_mode": trust_mode.value},
                    )

            proc = subprocess.run(
                cmd_args,
                cwd=self.workspace_dir,
                capture_output=True,
                text=True,
            )
            last_exit = proc.returncode
            stdout_acc.append(proc.stdout)
            stderr_acc.append(proc.stderr)
            if proc.returncode != 0:
                break

        snap_after = compute_workspace_snapshot(self.workspace_dir)
        delta = DeltaCalculator.compute_delta(snap_before, snap_after, self.workspace_dir)

        receipt_meta = {
            "verifiers": verifiers,
            "delta": delta.to_dict(),
        }
        if last_ident:
            receipt_meta["execution_identity"] = last_ident.to_dict()
        if last_det_res:
            receipt_meta["detection"] = last_det_res.to_dict()

        receipt = ObservedReceipt(
            receipt_id=f"rcpt_{plan_id}",
            task_id=task_id,
            claim_id=primary_claim,
            agent="verification_engine",
            action="verify_plan",
            workspace=self.workspace_dir,
            command=" ".join([str(c) for c in commands]),
            exit_code=last_exit,
            files_changed=tuple(delta.files_modified + delta.files_added),
            metadata=receipt_meta,
        )

        if last_exit != 0:
            res = VerificationResult(
                status="REJECT",
                claim_id=primary_claim,
                reason=f"Verification plan command exited with error code {last_exit}",
                observed_exit_code=last_exit,
                receipt_id=receipt.receipt_id,
                metadata={"receipt": receipt.to_dict(), "observation_record": receipt}
            )
            setattr(res, "receipt", receipt)
            setattr(res, "observation_record", receipt)
            return res

        res = VerificationResult(
            status="ACCEPT",
            claim_id=primary_claim,
            reason=f"Verification plan executed successfully ({len(commands)} command(s) verified)",
            observed_exit_code=last_exit,
            receipt_id=receipt.receipt_id,
            metadata={"receipt": receipt.to_dict(), "observation_record": receipt}
        )
        setattr(res, "receipt", receipt)
        setattr(res, "observation_record", receipt)
        return res
