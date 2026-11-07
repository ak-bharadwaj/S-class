"""Unit tests for gate_cache.py.

Tests MUSTs PD-CH5-003, PD-CH5-007, PD-CH5-008, PD-CH5-009, and PD-CH5-010.
"""
import pytest

from sclass.product.gate import GateOutput, GateState
from sclass.product.gate_cache import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    GateCache,
    compute_gate_cache_key,
)


@pytest.fixture
def sample_state_binding():
    return {
        "state_digest": "sha256:state111",
        "policy_version": "2.0.0",
        "evaluator_version": "1.0.0",
        "binding_digest": "sha256:binding111",
        "instant": "2026-11-07T12:00:00Z",
        "target": "target_alpha",
    }


def test_compute_gate_cache_key(sample_state_binding):
    """Test deterministic computation of gate cache key."""
    key1 = compute_gate_cache_key(
        phase="P5",
        canonical_state_binding=sample_state_binding,
        task_ref="task-01",
        spec_anchor_digest="sha256:spec111",
        input_digests=["sha256:in1", "sha256:in2"],
        pinned_guidance_digest="sha256:guide111",
        policy_version="2.0.0",
        evaluator_version="1.0.0",
        evaluation_instant="2026-11-07T12:00:00Z",
    )
    key2 = compute_gate_cache_key(
        phase="P5",
        canonical_state_binding=sample_state_binding,
        task_ref="task-01",
        spec_anchor_digest="sha256:spec111",
        input_digests=["sha256:in1", "sha256:in2"],
        pinned_guidance_digest="sha256:guide111",
        policy_version="2.0.0",
        evaluator_version="1.0.0",
        evaluation_instant="2026-11-07T12:00:00Z",
    )
    assert key1 == key2
    assert len(key1) == 64

    # Policy version mismatch between state binding and tuple must raise ValueError
    with pytest.raises(ValueError, match="Policy version mismatch"):
        compute_gate_cache_key(
            phase="P5",
            canonical_state_binding=sample_state_binding,
            task_ref="task-01",
            spec_anchor_digest="sha256:spec111",
            input_digests=["sha256:in1"],
            pinned_guidance_digest="sha256:guide111",
            policy_version="3.0.0",  # differs from binding's 2.0.0
            evaluator_version="1.0.0",
            evaluation_instant="2026-11-07T12:00:00Z",
        )


def test_pd_ch5_003_guidance_mismatch(sample_state_binding):
    """CH5-T3: guidance mismatch returns MISSING[PD-CH5-003]."""
    cache = GateCache()
    valid_tuple = {
        "phase": "P5",
        "canonical_state_binding": sample_state_binding,
        "pinned_guidance": "G1",
        "policy_version": "2.0.0",
        "evaluator_version": "1.0.0",
        "evaluation_instant": "2026-11-07T12:00:00Z",
    }
    # Put entry in cache so lookup would succeed if guidance wasn't checked
    cache.put(
        cache_key="key123",
        gate_output=GateOutput(state=GateState.SATISFIED),
        replay_record=valid_tuple,
        caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
    )

    # Guidance mismatch: cached G1, current G2
    out = cache.evaluate_cache_lookup(
        cache_key="key123",
        evaluation_tuple=valid_tuple,
        cached_guidance_digest="G1",
        current_guidance_digest="G2",
        caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
    )
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-CH5-003"
    assert "MISSING[PD-CH5-003]" in out.failures


def test_pd_ch5_007_gaming_and_happy(sample_state_binding):
    """CH5-T7: missing elements from input tuple return MISSING[PD-CH5-007].

    CH5-T8: fully populated tuple returns SATISFIED.
    """
    cache = GateCache()
    base_tuple = {
        "phase": "P5",
        "canonical_state_binding": sample_state_binding,
        "pinned_guidance": "G1",
        "policy_version": "2.0.0",
        "evaluator_version": "1.0.0",
        "evaluation_instant": "2026-11-07T12:00:00Z",
    }

    # CH5-T7 A1: omit policy_version
    t1 = dict(base_tuple)
    del t1["policy_version"]
    out1 = cache.evaluate_cache_lookup(
        cache_key="key1",
        evaluation_tuple=t1,
        caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
    )
    assert out1.state == GateState.MISSING
    assert out1.must_id == "PD-CH5-007"
    assert "MISSING[PD-CH5-007]" in out1.failures

    # CH5-T7 A2: omit evaluation_instant
    t2 = dict(base_tuple)
    del t2["evaluation_instant"]
    out2 = cache.evaluate_cache_lookup(
        cache_key="key1",
        evaluation_tuple=t2,
        caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
    )
    assert out2.state == GateState.MISSING
    assert out2.must_id == "PD-CH5-007"

    # CH5-T7 A3: omit evaluator_version
    t3 = dict(base_tuple)
    del t3["evaluator_version"]
    out3 = cache.evaluate_cache_lookup(
        cache_key="key1",
        evaluation_tuple=t3,
        caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
    )
    assert out3.state == GateState.MISSING
    assert out3.must_id == "PD-CH5-007"

    # CH5-T8 happy: put result in cache and retrieve
    sat_output = GateOutput(state=GateState.SATISFIED)
    cache.put(
        cache_key="key_valid",
        gate_output=sat_output,
        replay_record=base_tuple,
        caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
    )
    out_happy = cache.evaluate_cache_lookup(
        cache_key="key_valid",
        evaluation_tuple=base_tuple,
        cached_guidance_digest="G1",
        current_guidance_digest="G1",
        caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
    )
    assert out_happy.state == GateState.SATISFIED
    assert str(out_happy) == "SATISFIED"


def test_pd_ch5_008_blocker_invalidation():
    """CH5-T9: additive evidence cannot bypass existing blockers -> MISSING[PD-CH5-008].

    CH5-T10: no blockers and authorized invalidation -> SATISFIED.
    """
    cache = GateCache()

    # CH5-T9: agent attaches additive evidence to override a blocker
    out_gaming = cache.evaluate_blocker_invalidation(
        binding_digest="sha256:bind1",
        blocker_ids=["BLOCKER-001"],
        additive_evidence_digest="sha256:extra_evidence",
        authoritative_invalidation=True,
        caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
    )
    assert out_gaming.state == GateState.MISSING
    assert out_gaming.must_id == "PD-CH5-008"
    assert "MISSING[PD-CH5-008]" in out_gaming.failures

    # CH5-T10: no open blockers, authorized invalidation
    out_happy = cache.evaluate_blocker_invalidation(
        binding_digest="sha256:bind1",
        blocker_ids=[],
        additive_evidence_digest=None,
        authoritative_invalidation=True,
        caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
    )
    assert out_happy.state == GateState.SATISFIED


def test_pd_ch5_009_key_digests_and_dependency():
    """CH5-T11: key digest mismatch or uncertain dependency -> MISSING[PD-CH5-009].

    CH5-T12: exact equality -> SATISFIED.
    """
    cache = GateCache()

    # CH5-T11 A1: one declared cache_key_digest missing from lookup
    out_a1 = cache.evaluate_key_digests_and_dependency(
        declared_key_digests=["K1", "K2"],
        lookup_digests=["K1"],
        dependency_index_completeness="complete",
        cached_result_digest="sha256:res1",
        evaluator_record_ref="rec-01",
        caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
    )
    assert out_a1.state == GateState.MISSING
    assert out_a1.must_id == "PD-CH5-009"

    # CH5-T11 A2: dependency_index_completeness=unknown
    out_a2 = cache.evaluate_key_digests_and_dependency(
        declared_key_digests=["K1", "K2"],
        lookup_digests=["K1", "K2"],
        dependency_index_completeness="unknown",
        cached_result_digest="sha256:res1",
        evaluator_record_ref="rec-01",
        caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
    )
    assert out_a2.state == GateState.MISSING
    assert out_a2.must_id == "PD-CH5-009"

    # CH5-T11 A3: cached_result_digest missing without evaluator re-derivation
    out_a3 = cache.evaluate_key_digests_and_dependency(
        declared_key_digests=["K1", "K2"],
        lookup_digests=["K1", "K2"],
        dependency_index_completeness="complete",
        cached_result_digest=None,
        evaluator_record_ref="rec-01",
        caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
    )
    assert out_a3.state == GateState.MISSING
    assert out_a3.must_id == "PD-CH5-009"

    # CH5-T12 happy: exact match, complete dependency
    out_happy = cache.evaluate_key_digests_and_dependency(
        declared_key_digests=["K1", "K2"],
        lookup_digests=["K1", "K2"],
        dependency_index_completeness="complete",
        cached_result_digest="sha256:res1",
        evaluator_record_ref="rec-01",
        caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
    )
    assert out_happy.state == GateState.SATISFIED


def test_pd_ch5_010_adapter_outcomes():
    """CH5-T13: timeout, flaky, pending adapter results -> MISSING[PD-CH5-010].

    CH5-T14: valid passed result -> SATISFIED.
    """
    cache = GateCache()

    # CH5-T13 A1: test_run_status=TIMEOUT
    out_a1 = cache.evaluate_adapter_outcome(
        test_run_status="TIMEOUT",
        retry_count=1,
        adapter_result_digest="sha256:ad1",
        elapsed_ms=5000,
        caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
    )
    assert out_a1.state == GateState.MISSING
    assert out_a1.must_id == "PD-CH5-010"
    assert "TIMEOUT counted as pass" in out_a1.explain.get("error", "")

    # CH5-T13 A2: two runs disagree (flaky)
    out_a2 = cache.evaluate_adapter_outcome(
        test_run_status="PASSED",
        retry_count=2,
        adapter_result_digest="sha256:ad1",
        flaky_disagreement=True,
        caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
    )
    assert out_a2.state == GateState.MISSING
    assert out_a2.must_id == "PD-CH5-010"

    # CH5-T13 A3: adapter result pending
    out_a3 = cache.evaluate_adapter_outcome(
        test_run_status="PENDING",
        adapter_result_digest="sha256:ad1",
        caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
    )
    assert out_a3.state == GateState.MISSING
    assert out_a3.must_id == "PD-CH5-010"

    # CH5-T14 happy: clean passed run with adapter digest
    out_happy = cache.evaluate_adapter_outcome(
        test_run_status="PASSED",
        retry_count=1,
        adapter_result_digest="sha256:ad1",
        flaky_disagreement=False,
        elapsed_ms=120,
        caller_authority=QUALIFIED_EVALUATOR_BOUNDARY,
    )
    assert out_happy.state == GateState.SATISFIED


def test_caller_authority_fails_closed():
    """Verify unauthorized callers fail closed across all GateCache methods."""
    cache = GateCache()
    bad_auth = "rogue_caller"

    with pytest.raises(PermissionError):
        cache.put("key", GateOutput(GateState.SATISFIED), {}, caller_authority=bad_auth)

    out_lookup = cache.evaluate_cache_lookup("k", {}, caller_authority=bad_auth)
    assert out_lookup.state == GateState.MISSING

    out_block = cache.evaluate_blocker_invalidation("b", [], caller_authority=bad_auth)
    assert out_block.state == GateState.MISSING

    out_digests = cache.evaluate_key_digests_and_dependency([], [], "complete", caller_authority=bad_auth)
    assert out_digests.state == GateState.MISSING

    out_adapter = cache.evaluate_adapter_outcome("PASSED", caller_authority=bad_auth)
    assert out_adapter.state == GateState.MISSING
