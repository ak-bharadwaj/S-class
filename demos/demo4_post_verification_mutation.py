"""
S-Class Demo 4: Post-Verification Mutation Invalidation
Flow:
1. Command executes under observation -> S-Class records observation in ledger.
2. Initial claim verification succeeds (ACCEPTED).
3. Post-verification workspace file modification occurs.
4. S-Class verification detects workspace fingerprint divergence -> proof is STALE (REJECTED).
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sclass.domain.claim import Claim
from sclass.domain.execution import ExecutionMode
from sclass.observation.observer import observe_command
from sclass.trust.ledger import LocalLedger
from sclass.verification.engine import verify_claim


def run():
    print("=" * 70)
    print("DEMO 4: POST-VERIFICATION MUTATION INVALIDATION")
    print("=" * 70)
    print("Scenario: Code was verified, but workspace files modified prior to commit.")

    with tempfile.TemporaryDirectory() as tmp_dir:
        ledger = LocalLedger(tmp_dir)
        src_file = os.path.join(tmp_dir, "auth.py")
        with open(src_file, "w", encoding="utf-8") as f:
            f.write("def verify_jwt(): return True\n")

        cmd = f'"{sys.executable}" -c "print(\'auth verification\')"'
        receipt = observe_command(
            command=cmd,
            workspace_dir=tmp_dir,
            ledger=ledger,
            mode=ExecutionMode.HOST_ARGV,
        )

        claim = Claim(
            claim_id=receipt.claim_id,
            task_id=receipt.task_id,
            statement="Executed auth verification",
            claim_type="execution",
        )

        print("\n[1] Initial State Verification:")
        print(f"    Receipt ID:          {receipt.receipt_id}")
        print(f"    Fingerprint:         {receipt.workspace_fingerprint[:16]}...")
        verdict1 = verify_claim(claim, receipt, workspace_dir=tmp_dir, ledger=ledger)
        print(f"    Initial Verdict:     {verdict1.status} (Accepted)")
        assert verdict1.is_accepted

        print("\n[2] Agent introduces unobserved modification after verification:")
        with open(src_file, "a", encoding="utf-8") as f:
            f.write("# unauthorized backdoor inserted\ndef bypass(): return True\n")
        print("    Appended unverified changes to auth.py.")

        print("\n[3] S-Class Independent Verification Audit on Mutated Workspace:")
        verdict2 = verify_claim(claim, receipt, workspace_dir=tmp_dir, ledger=ledger)
        print(f"    Audited Verdict:     {verdict2.status}")
        print(f"    Verdict Reason:      {verdict2.reason}")

        assert verdict2.is_rejected, "Expected rejection due to stale workspace fingerprint"
        assert "stale" in verdict2.reason.lower()
        print("\n[SUCCESS] S-Class detected workspace divergence and invalidated stale proof!")
        print("=" * 70 + "\n")


if __name__ == "__main__":
    run()
