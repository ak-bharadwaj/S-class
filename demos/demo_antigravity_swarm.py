"""
S-Class Flagship Demo: Google Antigravity Parallel Multi-Agent Swarm Integrity.

Demonstrates:
1. Concurrency preservation: Multiple parallel subagents execute without artificial locks.
2. Concurrent mutation prevention: Prevents race conditions on shared files.
3. Duplicate work detection: Prevents redundant implementations of identical symbols.
4. Escalation quarantine: Isolates rogue/defective workers without killing the healthy swarm.
5. Epistemic evidence merging: Merges verified partial receipts into durable project truth.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sclass.agent_fleet import (
    FleetIntegrityEngine,
    LeaseType,
    ConflictType,
    AgentStatus,
)
from sclass.domain.project import VerifiedProjectState


def run():
    print("=" * 70)
    print("FLAGSHIP DEMO C: GOOGLE ANTIGRAVITY MULTI-AGENT SWARM INTEGRITY")
    print("=" * 70)
    print("Scenario: Parallel swarm coordination, race prevention, quarantine & merge.")

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
        fleet = FleetIntegrityEngine(workspace_root=tmp_dir)

        # 1. Register 3 concurrent swarm subagents
        print("\n[1] Registering Antigravity Multi-Agent Swarm:")
        a1 = fleet.register_agent("subagent_backend", role="Backend Engineer", base_revision="rev-v1")
        a2 = fleet.register_agent("subagent_frontend", role="Frontend Engineer", base_revision="rev-v1")
        a3 = fleet.register_agent("subagent_security", role="Security Auditor", base_revision="rev-v1")
        print(f"    Registered: {a1.agent_id} ({a1.role})")
        print(f"    Registered: {a2.agent_id} ({a2.role})")
        print(f"    Registered: {a3.agent_id} ({a3.role})")

        # 2. Concurrency Preservation: Parallel non-overlapping leases
        print("\n[2] Parallel Execution Without Artificial Serialization:")
        g1, _ = fleet.acquire_lease("subagent_backend", "src/backend/api.py", LeaseType.EXCLUSIVE_WRITE)
        g2, _ = fleet.acquire_lease("subagent_frontend", "src/frontend/app.tsx", LeaseType.EXCLUSIVE_WRITE)
        print(f"    Lease [src/backend/api.py]     -> {a1.agent_id}: Granted={g1}")
        print(f"    Lease [src/frontend/app.tsx]   -> {a2.agent_id}: Granted={g2}")
        assert g1 is True and g2 is True
        print("    --> Both subagents running concurrently!")

        # 3. Concurrent Mutation Collision Detection
        print("\n[3] Detecting & Preventing Concurrent Mutation Race Condition:")
        print("    subagent_frontend attempts to acquire write lease on src/backend/api.py...")
        g_race, conflict_race = fleet.acquire_lease("subagent_frontend", "src/backend/api.py", LeaseType.EXCLUSIVE_WRITE)
        print(f"    Lease Granted: {g_race} | Conflict Detected: {conflict_race.conflict_type.value}")
        print(f"    Involved Agents: {conflict_race.agents_involved}")
        assert g_race is False
        assert conflict_race.conflict_type == ConflictType.CONCURRENT_MUTATION

        # 4. Duplicate Work Detection
        print("\n[4] Detecting & Preventing Duplicate Work via CKG Symbol Tracking:")
        c1, _ = fleet.claim_symbol_work("subagent_backend", "hash_password", "src/backend/crypto.py")
        print(f"    {a1.agent_id} claimed symbol 'hash_password': Granted={c1}")
        c2, conflict_dup = fleet.claim_symbol_work("subagent_frontend", "hash_password", "src/frontend/util.ts")
        print(f"    {a2.agent_id} attempts to claim 'hash_password': Granted={c2}")
        print(f"    Conflict: {conflict_dup.conflict_type.value} ({conflict_dup.details['message']})")
        assert c2 is False
        assert conflict_dup.conflict_type == ConflictType.DUPLICATE_WORK

        # 5. Targeted Subagent Quarantine
        print("\n[5] Escalation: Isolating Rogue Subagent Without Halting Healthy Swarm:")
        print("    subagent_security attempts unauthorized privilege escalation.")
        quarantined = fleet.quarantine_agent("subagent_security", reason="Attempted unauthorized shell injection")
        print(f"    Subagent Status: {quarantined.status.value} (Reason: {quarantined.quarantine_reason})")
        
        # Quarantined agent cannot act
        g_bad, c_bad = fleet.acquire_lease("subagent_security", "src/secret.py")
        print(f"    Quarantined Agent Action: Granted={g_bad} (Violation: {c_bad.conflict_type.value})")
        assert g_bad is False

        # Healthy agents proceed normally
        g_healthy, _ = fleet.acquire_lease("subagent_backend", "src/backend/db.py", LeaseType.EXCLUSIVE_WRITE)
        print(f"    Healthy Agent ({a1.agent_id}) Action: Granted={g_healthy}")
        assert g_healthy is True

        # 6. Epistemic Evidence Merging into VerifiedProjectState
        print("\n[6] Epistemic Evidence Merging into Verified Project State:")
        state = VerifiedProjectState(repository="antigravity-app", workspace=tmp_dir, current_revision="rev-v1")
        receipts = [
            {
                "receipt_id": "rcpt_backend_ok",
                "claim_id": "claim_be_1",
                "claim_text": "Backend GraphQL endpoints passing",
                "agent": "subagent_backend",
                "base_commit": "rev-v1",
                "exit_code": 0,
                "files_changed": ["src/backend/api.py"],
            },
            {
                "receipt_id": "rcpt_frontend_ok",
                "claim_id": "claim_fe_1",
                "claim_text": "Frontend responsive dashboard passing",
                "agent": "subagent_frontend",
                "base_commit": "rev-v1",
                "exit_code": 0,
                "files_changed": ["src/frontend/app.tsx"],
            },
            {
                "receipt_id": "rcpt_quarantine_reject",
                "claim_id": "claim_sec_1",
                "claim_text": "Security scan completed",
                "agent": "subagent_security",
                "base_commit": "rev-v1",
                "exit_code": 0,
                "files_changed": ["audit.log"],
            },
        ]
        merge_res = fleet.merge_fleet_evidence(state, receipts, current_revision="rev-v1")
        print(f"    Merged Verified Claims:       {len(merge_res.merged_claims)}")
        print(f"    Rejected Quarantined Claims:  {len(merge_res.quarantined_agents)}")
        assert len(merge_res.merged_claims) == 2
        assert "subagent_security" in merge_res.quarantined_agents

        print("\n[SUCCESS] Antigravity Multi-Agent Swarm Integrity Demo Verified!")
        print("=" * 70 + "\n")


if __name__ == "__main__":
    run()
