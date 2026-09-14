"""
S-Class Flagship Demo: OpenAI Codex Autonomous Long-Horizon Execution.

Demonstrates:
1. S-Class synthesizes a non-invasive ControlPolicy for Codex (suppressing micro-prompts).
2. Codex executes uninterrupted across long autonomous task steps.
3. At the task boundary, S-Class performs rigorous cryptographic verification.
4. Fail-closed protection triggers if unobserved or unauthorized actions occur.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sclass.platform.archetypes.codex import get_codex_profile, get_codex_compensation_policy
from sclass.platform.engine import PlatformOptimizationEngine
from sclass.domain.action import ActionRequest, DecisionOutcome
from sclass.control.authorization import authorize
from sclass.domain.project import VerifiedProjectState


def run():
    print("=" * 70)
    print("FLAGSHIP DEMO A: OPENAI CODEX AUTONOMOUS LONG-HORIZON GOVERNANCE")
    print("=" * 70)
    print("Scenario: Autonomous multi-step coding with silent observation & final gate.")

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
        profile = get_codex_profile()
        policy = get_codex_compensation_policy()

        # 1. Synthesize Codex-tailored Control Policy
        print("\n[1] Synthesizing S-Class Control Policy for Codex:")
        control = PlatformOptimizationEngine.reconcile(
            profile=profile,
            compensation_policy=policy,
            task={"type": "autonomous_feature_implementation"},
            risk="normal",
        )
        print(f"    Observation Mode:        {control.observation_mode}")
        print(f"    Interruption Policy:     {control.interruption_policy}")
        print(f"    Preserved Capabilities:  {', '.join(control.preserved_capabilities[:3])}...")
        print(f"    Suppressed Interventions:{', '.join(control.suppressed_interventions[:3])}...")
        assert control.is_intervention_suppressed("unnecessary_interruptions")

        # 2. Codex executes autonomous loop without interruptions
        print("\n[2] Codex Executes Autonomous Coding Horizon (5 Iterations):")
        steps = [
            ("edit_file", "src/pool.py", "Initialize connection pool queue"),
            ("edit_file", "src/pool.py", "Implement acquire() with backoff"),
            ("edit_file", "src/pool.py", "Implement release() and heartbeat"),
            ("write_file", "tests/test_pool.py", "Write 12 pool stress tests"),
            ("execute_command", "pytest tests/test_pool.py", "Run test suite"),
        ]
        for idx, (action, target, desc) in enumerate(steps, 1):
            req = ActionRequest(
                agent="codex_agent",
                action=action,
                tool="bash" if action == "execute_command" else "file_editor",
                target=target,
                parameters={"command": desc} if action == "execute_command" else {"content": desc},
                workspace=tmp_dir,
            )
            decision = authorize(req, workspace_dir=tmp_dir)
            print(f"    Step {idx}: [{action:15}] -> {target:18} | Decision: {decision.outcome.value}")
            assert decision.outcome == DecisionOutcome.ALLOW

        # 3. Final Boundary Verification Gate
        print("\n[3] Task Boundary Reached -> S-Class Final Cryptographic Verification:")
        state = VerifiedProjectState(
            repository="db-pool-service",
            workspace=tmp_dir,
            current_revision="rev-codex-final-hash",
        )
        state.record_verified_claim(
            claim={"claim_id": "c_pool_1", "statement": "Connection pool implemented with backoff"},
            receipt={"receipt_id": "rcpt_pool_001", "exit_code": 0, "base_commit": "rev-codex-final-hash"},
        )
        print(f"    Cryptographically Verified Claims: {len(state.verified_claims)}")
        print("    Status: APPROVED & SEALED TO DURABLE TRUTH LAYER")

        # 4. Dangerous Action Fails Closed
        print("\n[4] Adversarial Check: Codex attempts destructive command:")
        cmd = "rm -rf /"
        evil_req = ActionRequest(
            agent="codex_agent",
            action="run_command",
            tool="terminal",
            target=cmd,
            parameters={"command": cmd},
            workspace=tmp_dir,
        )
        evil_decision = authorize(evil_req, workspace_dir=tmp_dir)
        print(f"    Action: {cmd} -> Decision: {evil_decision.outcome.value} ({evil_decision.reason})")
        assert evil_decision.outcome == DecisionOutcome.DENY

        print("\n[SUCCESS] Codex Autonomous Long-Horizon Demo Verified!")
        print("=" * 70 + "\n")


if __name__ == "__main__":
    run()
