#!/usr/bin/env python3
"""Section F7, F6, and F3 Security Probes: Authority & Resolver Verification.

Normative verification that no candidate payload can manufacture authority without
caller-injected dependencies across F7, F6, and F3 evaluators.
"""

from __future__ import annotations
import sys
from pathlib import Path

# Add repo to sys.path
repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root / "src"))

from sclass.product.claim_ledger import evaluate_f7_claim, evaluate_f7_claim_ledger
from sclass.product.traceability import evaluate_f6_traceability
from sclass.product.trust_model import evaluate_claim, GateState


def run_probes() -> None:
    print("================================================================================")
    print("S-CLASS SECURITY PROBES: EXCLUSIVE CALLER-INJECTED AUTHORITY VERIFICATION")
    print("================================================================================")

    # -------------------------------------------------------------------------
    # 1. Section F7 Four CL Probes (No Resolvers Injected)
    # -------------------------------------------------------------------------
    print("\n--- [F7 PROBE 1] Behavioral Claim with Invented Evidence Ref (No Resolver) ---")
    probe1_claim = {
        "claim_id": "CL-PROBE-1",
        "type": "behavioral",
        "subject": "POST /rate-limit",
        "evidence_refs": ["EV-INVENTED-FAKE-999"],
        "kernel_evidence_resolves": True,  # Asserted flag must be disregarded
    }
    res1 = evaluate_f7_claim(probe1_claim)
    print(f"Candidate: {probe1_claim}")
    print(f"Output: {res1}")
    print(f"State: {res1.state}, MUST ID: {res1.must_id}")
    print(f"Detail: {res1.detail}")
    assert res1.state == GateState.MISSING
    assert res1.must_id == "PD-F7-002"

    print("\n--- [F7 PROBE 2] Completion Claim with obligation_closed: true (No Resolver) ---")
    probe2_claim = {
        "claim_id": "CL-PROBE-2",
        "type": "completion",
        "subject": "Close audit obligation",
        "obligation_ref": "OBL-AUDIT-1",
        "obligation_closed": True,  # Asserted flag must never confer closure
        "evidence_refs": ["EV-INVENTED-1"],
    }
    res2 = evaluate_f7_claim(probe2_claim)
    print(f"Candidate: {probe2_claim}")
    print(f"Output: {res2}")
    print(f"State: {res2.state}, MUST ID: {res2.must_id}")
    print(f"Detail: {res2.detail}")
    assert res2.state == GateState.MISSING
    assert res2.must_id == "PD-F7-005"

    print("\n--- [F7 PROBE 3] Package Claim with Matching Payload Digests (No Resolver) ---")
    probe3_claim = {
        "claim_id": "CL-PROBE-3",
        "type": "reference",
        "reference_kind": "package",
        "subject": "untrusted-crypto-pkg",
        "expected_dependency_digest": "sha256:same-hash-12345",
        "canonical_dependency_set_digest": "sha256:same-hash-12345",  # Matching payload digests alone must never satisfy
    }
    res3 = evaluate_f7_claim(probe3_claim)
    print(f"Candidate: {probe3_claim}")
    print(f"Output: {res3}")
    print(f"State: {res3.state}, MUST ID: {res3.must_id}")
    print(f"Detail: {res3.detail}")
    assert res3.state == GateState.MISSING
    assert res3.must_id == "PD-F7-003"

    print("\n--- [F7 PROBE 4] Nonexistent Symbol with No Repository Index ---")
    # Case A: Pre-existing
    probe4_pre = {
        "claim_id": "CL-PROBE-4-PRE",
        "type": "reference",
        "reference_kind": "symbol",
        "subject": "pkg.nonexistent:MissingClass",
        "created_by_delta": False,
        "evaluator_resolution": "RESOLVED",
    }
    res4_pre = evaluate_f7_claim(probe4_pre)
    print(f"Candidate (pre-existing): {probe4_pre}")
    print(f"Output: {res4_pre}")
    print(f"State: {res4_pre.state}, MUST ID: {res4_pre.must_id}")
    print(f"Detail: {res4_pre.detail}")
    assert res4_pre.state == GateState.MISSING
    assert res4_pre.must_id == "PD-F7-004"

    # Case B: Delta-created
    probe4_delta = {
        "claim_id": "CL-PROBE-4-DELTA",
        "type": "reference",
        "reference_kind": "symbol",
        "subject": "pkg.nonexistent:NewClass",
        "created_by_delta": True,
        "evaluator_resolution": "RESOLVED",
    }
    res4_delta = evaluate_f7_claim(probe4_delta)
    print(f"Candidate (delta-created): {probe4_delta}")
    print(f"Output: {res4_delta}")
    print(f"State: {res4_delta.state}, MUST ID: {res4_delta.must_id}")
    print(f"Detail: {res4_delta.detail}")
    assert res4_delta.state == GateState.MISSING
    assert res4_delta.must_id == "PD-F7-006"

    # -------------------------------------------------------------------------
    # 2. Section F6 Security Probe (evaluate_f6_traceability without SourceRefResolver)
    # -------------------------------------------------------------------------
    print("\n--- [F6 PROBE] Traceability without Injected SourceRefResolver ---")
    class EmbeddedCandidateResolver:
        def resolve_ref(self, ref: str) -> bool: return True

    spec_f6 = {
        "nodes": ["REQ-1", "TEST-1"],
        "links": [{"source": "REQ-1", "target": "TEST-1", "type": "verifies"}],
        "resolver": EmbeddedCandidateResolver(),  # Candidate attempts to inject resolver inside dictionary
        "source_refs": ["src/auth.py:10"],
        "agent_claimed_coverage_percent": 100.0,
    }
    res_f6 = evaluate_f6_traceability(spec_f6, resolver=None)
    print(f"Candidate Spec (with embedded resolver): {list(spec_f6.keys())}")
    print(f"Output: {res_f6}")
    print(f"State: {res_f6.state}, MUST ID: {res_f6.must_id}")
    print(f"Detail: {res_f6.detail}")
    assert res_f6.state == GateState.MISSING
    assert res_f6.must_id == "PD-F6-001"

    # -------------------------------------------------------------------------
    # 3. Section F3 Security Probe (evaluate_claim without CheckRecordSource)
    # -------------------------------------------------------------------------
    print("\n--- [F3 PROBE] evaluate_claim without Injected CheckRecordSource ---")
    candidate_f3 = {
        "claim_id": "CL-F3-01",
        "status": "PASS",
        "verified": True,
        "check_records": [
            {
                "producer": "evaluator",
                "status": "PASS",
                "object_digest": "sha256:obj-digest-1",
                "target_digest": "sha256:tgt-digest-1",
            }
        ],
    }
    res_f3 = evaluate_claim(
        candidate_f3,
        check_record_source=None,
        expected_object_digest="sha256:obj-digest-1",
        expected_target_digest="sha256:tgt-digest-1",
    )
    print(f"Candidate Payload (asserting PASS and embedding evaluator records): {candidate_f3}")
    print(f"Output: {res_f3}")
    print(f"State: {res_f3.state}, MUST ID: {res_f3.must_id}")
    print(f"Detail: {res_f3.detail}")
    assert res_f3.state == GateState.MISSING
    assert res_f3.must_id == "PD-F3-002"

    print("\n================================================================================")
    print("ALL SECURITY PROBES PASSED: 100% FAIL-CLOSED AT EVERY TRUST BOUNDARY")
    print("================================================================================")


if __name__ == "__main__":
    run_probes()
