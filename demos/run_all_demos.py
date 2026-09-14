"""
S-Class Product & Platform Demos Runner:
Executes all 8 product and flagship platform demonstrations:
1. False Test Result Claim (Independent Verification & Anti-Cheating)
2. Dangerous Command Execution (Deterministic Boundary Enforcement)
3. Secret Exfiltration Defense (Cryptographic Redaction & Leakage Prevention)
4. Post-Verification Mutation Invalidation (Tamper-Resistant Project State)
5. Cross-Agent Continuity (Claude -> Codex Zero-Drift Handoff)
6. Flagship Demo A: OpenAI Codex Autonomous Long-Horizon Governance
7. Flagship Demo B: Anthropic Claude Code Deep Reasoning Minimal Projection
8. Flagship Demo C: Google Antigravity Parallel Multi-Agent Swarm Integrity
"""

import sys
import demo1_false_test_claim
import demo2_dangerous_command
import demo3_secret_exfiltration
import demo4_post_verification_mutation
import demo5_cross_agent_continuity
import demo_codex_autonomous
import demo_claude_reasoning
import demo_antigravity_swarm


def main():
    print("\n" + "#" * 70)
    print("#  S-CLASS: THE COMPLETE 8-DEMO VERIFICATION & ARCHETYPE SUITE")
    print("#" * 70 + "\n")

    # Baseline Product Demos
    demo1_false_test_claim.run()
    demo2_dangerous_command.run()
    demo3_secret_exfiltration.run()
    demo4_post_verification_mutation.run()
    demo5_cross_agent_continuity.run()

    # Flagship Platform Demos
    demo_codex_autonomous.run()
    demo_claude_reasoning.run()
    demo_antigravity_swarm.run()

    print("#" * 70)
    print("#  ALL 8 PRODUCT & PLATFORM DEMOS COMPLETED 100% SUCCESSFULLY")
    print("#" * 70 + "\n")


if __name__ == "__main__":
    main()
