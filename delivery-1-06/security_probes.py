#!/usr/bin/env python3
"""Section F6, F7, and F3 Security Probes: Authority & Resolver Verification.

Authoritative verification that candidate payloads cannot manufacture authority
without caller-injected dependencies across F6, F7, and F3 evaluators.
"""

from __future__ import annotations
import sys
from pathlib import Path

# Add repo to sys.path
repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root / "src"))

from sclass.product.traceability import (
    evaluate_f6_traceability,
    InMemorySourceRefResolver,
)
from sclass.product.claim_ledger import evaluate_f7_claim
from sclass.product.trust_model import evaluate_claim, GateState


def run_probes() -> None:
    print("================================================================================")
    print("S-CLASS SECURITY PROBES: EXCLUSIVE CALLER-INJECTED AUTHORITY VERIFICATION")
    print("================================================================================")

    # -------------------------------------------------------------------------
    # 1. Section F6 Freshness Probes (Caller-Injected Authority Enforcement)
    # -------------------------------------------------------------------------
    nodes = ["REQ-1", "AC-1", "VS-1", "TEST-1", "EV-1", "OBL-1"]
    resolver = InMemorySourceRefResolver({
        nid: {"id": nid, "kind": nid.split("-")[0]} for nid in nodes
    })
    base_5link_spec = {
        "nodes": list(nodes),
        "links": [
            {"type": "REQUIREMENT_TO_ACCEPTANCE", "source": "REQ-1", "destination": "AC-1"},
            {"type": "ACCEPTANCE_TO_VERIFICATION", "source": "AC-1", "destination": "VS-1"},
            {"type": "VERIFICATION_TO_TEST", "source": "VS-1", "destination": "TEST-1"},
            {"type": "TEST_TO_EVIDENCE", "source": "TEST-1", "destination": "EV-1"},
            {"type": "EVIDENCE_TO_OBLIGATION", "source": "EV-1", "destination": "OBL-1"},
        ],
        "source_refs": list(nodes),
        "source_refs_resolve": True,
        "mode": "realized",
    }

    print("\n--- [F6 PROBE 1] 5-Link Chain with No Freshness Info and No Predicate ---")
    p1 = evaluate_f6_traceability(base_5link_spec, resolver=resolver, freshness_predicate=None)
    print(f"Output: {p1}")
    print(f"State: {p1.state}, MUST ID: {p1.must_id}, Detail: {p1.detail}")
    assert p1.state == GateState.MISSING
    assert p1.must_id == "PD-F6-005"
    assert "caller-injected" in p1.detail.lower()

    print("\n--- [F6 PROBE 2] 5-Link Chain with All-True Payload freshness_map (No Predicate) ---")
    spec_p2 = dict(base_5link_spec)
    spec_p2["freshness_map"] = {nid: True for nid in nodes}
    p2 = evaluate_f6_traceability(spec_p2, resolver=resolver, freshness_predicate=None)
    print(f"Output: {p2}")
    print(f"State: {p2.state}, MUST ID: {p2.must_id}, Detail: {p2.detail}")
    assert p2.state == GateState.MISSING
    assert p2.must_id == "PD-F6-005"
    assert "caller-injected" in p2.detail.lower()

    print("\n--- [F6 PROBE 3] 5-Link Chain with source_fresh/destination_fresh=True (No Predicate) ---")
    spec_p3 = dict(base_5link_spec)
    spec_p3["source_fresh"] = True
    spec_p3["destination_fresh"] = True
    p3 = evaluate_f6_traceability(spec_p3, resolver=resolver, freshness_predicate=None)
    print(f"Output: {p3}")
    print(f"State: {p3.state}, MUST ID: {p3.must_id}, Detail: {p3.detail}")
    assert p3.state == GateState.MISSING
    assert p3.must_id == "PD-F6-005"
    assert "caller-injected" in p3.detail.lower()

    print("\n--- [F6 PROBE 4] Candidate-Embedded freshness_predicate in Spec Mapping ---")
    spec_p4 = dict(base_5link_spec)
    spec_p4["freshness_predicate"] = lambda nid: True
    p4 = evaluate_f6_traceability(spec_p4, resolver=resolver, freshness_predicate=None)
    print(f"Output: {p4}")
    print(f"State: {p4.state}, MUST ID: {p4.must_id}, Detail: {p4.detail}")
    assert p4.state == GateState.MISSING
    assert p4.must_id == "PD-F6-005"
    assert "caller-injected" in p4.detail.lower()

    print("\n--- [F6 PROBE 5] Injected Predicate Reports Endpoint EV-1 Stale ---")
    p5 = evaluate_f6_traceability(
        base_5link_spec,
        resolver=resolver,
        freshness_predicate=lambda nid: nid != "EV-1",
    )
    print(f"Output: {p5}")
    print(f"State: {p5.state}, MUST ID: {p5.must_id}, Detail: {p5.detail}")
    assert p5.state == GateState.MISSING
    assert p5.must_id == "PD-F6-005"
    assert "EV-1" in p5.detail

    print("\n--- [F6 PROBE 6] Injected Predicate Raises Authority Exception ---")
    def raising_pred(nid: str) -> bool:
        raise RuntimeError(f"Authority fault checking {nid}")
    p6 = evaluate_f6_traceability(
        base_5link_spec,
        resolver=resolver,
        freshness_predicate=raising_pred,
    )
    print(f"Output: {p6}")
    print(f"State: {p6.state}, MUST ID: {p6.must_id}, Detail: {p6.detail}")
    assert p6.state == GateState.MISSING
    assert p6.must_id == "PD-F6-005"
    assert "exception" in p6.detail.lower()

    print("\n--- [F6 PROBE 7] Injected Predicate Returns Truthy Integer 1 (Non-Boolean) ---")
    p7 = evaluate_f6_traceability(
        base_5link_spec,
        resolver=resolver,
        freshness_predicate=lambda nid: 1,  # type: ignore
    )
    print(f"Output: {p7}")
    print(f"State: {p7.state}, MUST ID: {p7.must_id}, Detail: {p7.detail}")
    assert p7.state == GateState.MISSING
    assert p7.must_id == "PD-F6-005"

    print("\n--- [F6 PROBE 8] Payload Claims All Fresh while Injected Predicate Reports Stale ---")
    spec_p8 = dict(base_5link_spec)
    spec_p8["freshness_map"] = {nid: True for nid in nodes}
    spec_p8["source_fresh"] = True
    spec_p8["destination_fresh"] = True
    p8 = evaluate_f6_traceability(
        spec_p8,
        resolver=resolver,
        freshness_predicate=lambda nid: nid != "TEST-1",
    )
    print(f"Output: {p8}")
    print(f"State: {p8.state}, MUST ID: {p8.must_id}, Detail: {p8.detail}")
    assert p8.state == GateState.MISSING
    assert p8.must_id == "PD-F6-005"
    assert "TEST-1" in p8.detail

    print("\n--- [F6 PROBE 9] Payload Claims Stale while Injected Predicate Reports Fresh ---")
    spec_p9 = dict(base_5link_spec)
    spec_p9["freshness_map"] = {"VS-1": False}
    p9 = evaluate_f6_traceability(
        spec_p9,
        resolver=resolver,
        freshness_predicate=lambda nid: True,
    )
    print(f"Output: {p9}")
    print(f"State: {p9.state}, MUST ID: {p9.must_id}, Detail: {p9.detail}")
    assert p9.state == GateState.MISSING
    assert p9.must_id == "PD-F6-005"
    assert "VS-1" in p9.detail

    print("\n--- [F6 POSITIVE CONTROL] Valid 5-Link Chain with Injected Predicate ---")
    p_pos = evaluate_f6_traceability(
        base_5link_spec,
        resolver=resolver,
        freshness_predicate=lambda nid: True,
    )
    print(f"Output: {p_pos}")
    print(f"State: {p_pos.state}, MUST ID: {p_pos.must_id}, Detail: {p_pos.detail}")
    assert p_pos.state == GateState.SATISFIED
    assert p_pos.must_id == "PD-F6-001"

    # -------------------------------------------------------------------------
    # 2. Section F7 Regression Checks (Caller-Injected Authority Intact)
    # -------------------------------------------------------------------------
    print("\n--- [F7 REGRESSION 1] Behavioral Claim with Fake Evidence Ref (No Resolver) ---")
    f7_p1 = evaluate_f7_claim({
        "claim_id": "CL-PROBE-1",
        "type": "behavioral",
        "subject": "POST /rate-limit",
        "evidence_refs": ["EV-INVENTED-FAKE-999"],
    })
    assert f7_p1.state == GateState.MISSING
    assert f7_p1.must_id == "PD-F7-002"
    print(f"State: {f7_p1.state}, MUST ID: {f7_p1.must_id}")

    print("\n--- [F7 REGRESSION 2] Completion Claim with obligation_closed: true (No Resolver) ---")
    f7_p2 = evaluate_f7_claim({
        "claim_id": "CL-PROBE-2",
        "type": "completion",
        "subject": "Close audit obligation",
        "obligation_ref": "OBL-AUDIT-1",
        "obligation_closed": True,
        "evidence_refs": ["EV-INVENTED-1"],
    })
    assert f7_p2.state == GateState.MISSING
    assert f7_p2.must_id == "PD-F7-005"
    print(f"State: {f7_p2.state}, MUST ID: {f7_p2.must_id}")

    print("\n--- [F7 REGRESSION 3] Package Claim with Matching Payload Digests (No Resolver) ---")
    f7_p3 = evaluate_f7_claim({
        "claim_id": "CL-PROBE-3",
        "type": "reference",
        "reference_kind": "package",
        "subject": "untrusted-crypto-pkg",
        "expected_dependency_digest": "sha256:same-hash-12345",
        "canonical_dependency_set_digest": "sha256:same-hash-12345",
    })
    assert f7_p3.state == GateState.MISSING
    assert f7_p3.must_id == "PD-F7-003"
    print(f"State: {f7_p3.state}, MUST ID: {f7_p3.must_id}")

    print("\n--- [F7 REGRESSION 4] Nonexistent Symbol with No Repository Index ---")
    f7_p4 = evaluate_f7_claim({
        "claim_id": "CL-PROBE-4",
        "type": "reference",
        "reference_kind": "symbol",
        "subject": "pkg.nonexistent:MissingClass",
        "created_by_delta": False,
    })
    assert f7_p4.state == GateState.MISSING
    assert f7_p4.must_id == "PD-F7-004"
    print(f"State: {f7_p4.state}, MUST ID: {f7_p4.must_id}")

    # -------------------------------------------------------------------------
    # 3. Section F3 Regression Check
    # -------------------------------------------------------------------------
    print("\n--- [F3 REGRESSION] Empty Claim Evaluation Fails Closed ---")
    f3_res = evaluate_claim({})
    assert f3_res.state == GateState.MISSING
    print(f"State: {f3_res.state}, MUST ID: {f3_res.must_id}")

    print("\n================================================================================")
    print("ALL SECURITY PROBES PASSED: 10/10 F6 PROBES, 4/4 F7 PROBES, 1/1 F3 PROBES")
    print("Zero candidate-supplied evaluator authority across F6, F7, and F3.")
    print("================================================================================")


if __name__ == "__main__":
    run_probes()
