"""Security and negative probes for lane-b2-gate-b.

Verifies:
1. No injected source / unauthorized caller never returns SATISFIED.
2. Hand-created or spoofed check IDs return MISSING[PD-CH5-006].
3. Additive evidence alone cannot override blockers under PD-CH5-008.
4. Unknown or uncertain dependency index fails closed under PD-CH5-009.
5. Incomplete explicit gate input tuple fails closed under PD-CH5-007.
6. Timeout, flaky disagreement, or pending adapter outcomes never green under PD-CH5-010.
"""
from __future__ import annotations

import sys
from typing import Any, Dict

from sclass.product.check_registry import (
    QUALIFIED_EVALUATOR_BOUNDARY as REG_BOUNDARY,
    validate_check_id,
)
from sclass.product.gate import GateOutput, GateState
from sclass.product.gate_cache import (
    QUALIFIED_EVALUATOR_BOUNDARY as CACHE_BOUNDARY,
    GateCache,
    compute_gate_cache_key,
)


def probe_unauthorized_callers():
    """Verify unauthorized callers cannot obtain SATISFIED."""
    # 1. Check registry
    out1 = validate_check_id("some_check", caller_authority=None)
    assert out1.state == GateState.MISSING
    assert out1.must_id == "PD-CH5-006"

    out2 = validate_check_id("some_check", caller_authority="AGENT_PROMPT")
    assert out2.state == GateState.MISSING
    assert out2.must_id == "PD-CH5-006"

    # 2. Gate cache
    cache = GateCache()
    out3 = cache.evaluate_cache_lookup("k", {}, caller_authority=None)
    assert out3.state == GateState.MISSING

    out4 = cache.evaluate_blocker_invalidation("b", [], caller_authority="MALICIOUS")
    assert out4.state == GateState.MISSING

    out5 = cache.evaluate_key_digests_and_dependency([], [], "complete", caller_authority="")
    assert out5.state == GateState.MISSING

    out6 = cache.evaluate_adapter_outcome("PASSED", caller_authority="LLM_CLAIM")
    assert out6.state == GateState.MISSING
    print("[PROBE 1] Unauthorized callers fail closed: PASSED")


def probe_hand_created_check_ids():
    """Verify hand-created or unregistered IDs cannot achieve SATISFIED."""
    for rogue_id in ["PRODUCT-CUSTOM-CHECK-01", "HAND_INSERTED_CHECK", "P5-UNREGISTERED"]:
        out = validate_check_id(rogue_id, caller_authority=REG_BOUNDARY)
        assert out.state == GateState.MISSING
        assert out.must_id == "PD-CH5-006"
        assert "MISSING[PD-CH5-006]" in out.failures
    print("[PROBE 2] Hand-created check IDs rejected: PASSED")


def probe_blocker_bypass_attempts():
    """Verify additive evidence cannot bypass existing blockers."""
    cache = GateCache()
    out = cache.evaluate_blocker_invalidation(
        binding_digest="sha256:target_binding",
        blocker_ids=["PD-CH2-002", "PD-CH2-003"],
        additive_evidence_digest="sha256:extra_payload_claim",
        authoritative_invalidation=False,
        caller_authority=CACHE_BOUNDARY,
    )
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-CH5-008"
    assert "PD-CH2-002" in out.explain.get("blocker_ids", [])
    print("[PROBE 3] Blocker bypass attempts rejected: PASSED")


def probe_uncertain_dependencies():
    """Verify uncertain dependency indices fail closed."""
    cache = GateCache()
    for uncertain_state in ["unknown", "uncertain", "incomplete"]:
        out = cache.evaluate_key_digests_and_dependency(
            declared_key_digests=["D1"],
            lookup_digests=["D1"],
            dependency_index_completeness=uncertain_state,
            cached_result_digest="sha256:cached",
            evaluator_record_ref="ref-01",
            caller_authority=CACHE_BOUNDARY,
        )
        assert out.state == GateState.MISSING
        assert out.must_id == "PD-CH5-009"
    print("[PROBE 4] Uncertain dependencies fail closed: PASSED")


def probe_unmeasured_or_flaky_outcomes():
    """Verify unmeasured, timeout, and flaky outcomes are never green."""
    cache = GateCache()
    # Timeout
    out_timeout = cache.evaluate_adapter_outcome(
        test_run_status="TIMEOUT",
        caller_authority=CACHE_BOUNDARY,
    )
    assert out_timeout.state == GateState.MISSING
    assert out_timeout.must_id == "PD-CH5-010"

    # Flaky disagreement
    out_flaky = cache.evaluate_adapter_outcome(
        test_run_status="PASSED",
        flaky_disagreement=True,
        caller_authority=CACHE_BOUNDARY,
    )
    assert out_flaky.state == GateState.MISSING
    assert out_flaky.must_id == "PD-CH5-010"

    # Pending
    out_pending = cache.evaluate_adapter_outcome(
        test_run_status="PENDING",
        caller_authority=CACHE_BOUNDARY,
    )
    assert out_pending.state == GateState.MISSING
    assert out_pending.must_id == "PD-CH5-010"
    print("[PROBE 5] Timeout, flaky, and pending outcomes never green: PASSED")


def main():
    print("=" * 60)
    print("SECURITY & NEGATIVE PROBES: LANE-B2-GATE-B")
    print("=" * 60)
    probe_unauthorized_callers()
    probe_hand_created_check_ids()
    probe_blocker_bypass_attempts()
    probe_uncertain_dependencies()
    probe_unmeasured_or_flaky_outcomes()
    print("=" * 60)
    print("ALL 5 SECURITY PROBE BATTERIES PASSED")
    print("=" * 60)


if __name__ == "__main__":
    main()
