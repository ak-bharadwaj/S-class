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

        # Execute commands under independent OS execution
        last_exit = 0
        stdout_acc = []
        stderr_acc = []
        for cmd in commands:
            cmd_args = cmd if isinstance(cmd, list) else cmd.split()
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
            metadata={"verifiers": verifiers, "delta": delta.to_dict()}
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
