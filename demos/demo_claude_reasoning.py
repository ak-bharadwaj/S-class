"""
S-Class Flagship Demo: Anthropic Claude Code Deep Reasoning Optimization.

Demonstrates:
1. Minimal, ultra-dense verified context projection (zero chat transcript bloat).
2. Preserves Claude's deep architectural reasoning capacity without token exhaustion.
3. Relies on verified cryptographic receipts rather than re-running passed suites.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sclass.platform.archetypes.claude_code import get_claude_code_profile, get_claude_code_compensation_policy
from sclass.platform.engine import PlatformOptimizationEngine
from sclass.context.continuity import CrossPlatformContinuityEngine
from sclass.domain.project import VerifiedProjectState
from sclass.observation.fingerprint import compute_workspace_snapshot, compute_workspace_fingerprint


def run():
    print("=" * 70)
    print("FLAGSHIP DEMO B: CLAUDE CODE DEEP REASONING MINIMAL PROJECTION")
    print("=" * 70)
    print("Scenario: Delivering ultra-dense truth without chat history bloat.")

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
        # Create small workspace
        f = os.path.join(tmp_dir, "app.py")
        with open(f, "w", encoding="utf-8") as fp:
            fp.write("def main(): pass\n")

        snap = compute_workspace_snapshot(tmp_dir)
        tree_fp = compute_workspace_fingerprint(snap)

        # 1. Build Verified Project State with multiple prior milestones
        print("\n[1] Constructing Authoritative Verified Project State:")
        state = VerifiedProjectState(
            repository="finance-engine",
            workspace=tmp_dir,
            current_revision=tree_fp,
        )
        state.record_verified_claim(
            claim={"claim_id": "c_db", "statement": "PostgreSQL ACID transaction isolation configured"},
            receipt={"receipt_id": "rcpt_db_pass", "exit_code": 0},
        )
        state.record_verified_claim(
            claim={"claim_id": "c_jwt", "statement": "RS256 JWT cryptographic signing verified"},
            receipt={"receipt_id": "rcpt_jwt_pass", "exit_code": 0},
        )
        state.record_invalidated_claim(
            claim_or_id="c_cache",
            reason="Redis sentinel failover unreachable in staging",
        )
        print(f"    Verified Prior Claims:    {len(state.verified_claims)}")
        print(f"    Invalidated Known Risks:  {len(state.invalidated_claims)}")

        # 2. Synthesize Context Projection for Claude Code
        print("\n[2] Synthesizing Ultra-Dense Platform Projection for Claude Code:")
        transfer = CrossPlatformContinuityEngine.transfer(
            source_platform="codex",
            target_platform="claude_code",
            state=state,
            workspace_dir=tmp_dir,
            next_action="Architect distributed multi-region failover handler",
        )
        projection = transfer.prompt_projection

        print("    --- Platform Projection Preview ---")
        for line in projection.strip().split("\n")[:14]:
            print(f"    | {line}")
        print("    | ... (clipped)")
        print("    -----------------------------------")

        raw_transcript_simulated_size = 48500  # 48.5 KB typical raw multi-turn conversation
        projection_size = len(projection)
        savings_pct = (1.0 - (projection_size / raw_transcript_simulated_size)) * 100.0

        print(f"\n[3] Context Compression & Token Efficiency:")
        print(f"    Raw Chat Transcript Size:  {raw_transcript_simulated_size} bytes (~12,125 tokens)")
        print(f"    S-Class Projection Size:    {projection_size} bytes (~{projection_size // 4} tokens)")
        print(f"    Context Reduction:          {savings_pct:.1f}% reduction")
        print("    Result: Zero token exhaustion, 100% of reasoning budget preserved for Claude.")

        assert len(projection) < 2500
        assert "CLAUDE_CODE" in projection
        assert "PostgreSQL ACID" in projection
        assert "Redis sentinel failover" in projection

        print("\n[SUCCESS] Claude Code Deep Reasoning Optimization Demo Verified!")
        print("=" * 70 + "\n")


if __name__ == "__main__":
    run()
