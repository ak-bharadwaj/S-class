"""
Tests for Enterprise Core Vertical Governed Pipeline.
"""

import pytest
from enterprise_pipeline import EnterpriseGovernancePipeline, PreGroundingResult, PipelineDecisionReceipt
from evidence_provider import default_provider_registry
from benchmark.hypothesis_parity.observation import StrategySpec


@pytest.fixture
def pipeline():
    return EnterpriseGovernancePipeline(default_provider_registry)


def test_pipeline_executes_clean_pass(pipeline):
    # Developer requests a multiplication invariant
    request = "Implement commutative integer multiplier."
    obligations = [{
        "obligation_id": "OB-MUL-COMMUTATIVE",
        "obligation_type": "property",
        "strategy_specs": {
            "a": StrategySpec(strategy_type="integers", params={"min_value": -100, "max_value": 100}),
            "b": StrategySpec(strategy_type="integers", params={"min_value": -100, "max_value": 100})
        },
        "max_examples": 25,
        "seed": 42
    }]

    def correct_generator(spec):
        def multiply_property(a: int, b: int) -> bool:
            return a * b == b * a
        return multiply_property

    target, receipt = pipeline.execute_governed_cycle(
        request_text=request,
        code_generator=correct_generator,
        custom_obligations=obligations
    )

    assert target is not None
    assert receipt.verdict == "PASS"
    assert receipt.pre_gen_grounded is True
    assert receipt.post_gen_verified is True
    assert receipt.obligations_passed == 1
    assert receipt.obligations_failed == 0
    assert receipt.provenance_hash != ""


def test_pipeline_blocks_on_zero_evaluated_evidence_insufficient_evidence(pipeline):
    # Request without custom obligations should be blocked due to INSUFFICIENT_EVIDENCE
    request = "Implement some unknown unverified helper."

    def generator(spec):
        return lambda x: x

    target, receipt = pipeline.execute_governed_cycle(
        request_text=request,
        code_generator=generator,
        custom_obligations=[]  # Zero obligations provided
    )

    assert target is None
    assert receipt.verdict == "BLOCK"
    assert receipt.post_gen_verified is False
    assert len(receipt.blocking_reasons) > 0
    assert "INSUFFICIENT_EVIDENCE" in receipt.blocking_reasons[0]


def test_pipeline_blocks_pre_generation_on_contradiction(pipeline):
    # Request contains mutually contradictory constraints
    request = "Implement filter where values must be positive and must allow negative values."

    def generator_should_not_run(spec):
        raise AssertionError("Code generator was invoked when pre-generation grounding should have failed!")

    target, receipt = pipeline.execute_governed_cycle(
        request_text=request,
        code_generator=generator_should_not_run
    )

    assert target is None
    assert receipt.verdict == "BLOCK"
    assert receipt.pre_gen_grounded is False
    assert receipt.post_gen_verified is False
    assert len(receipt.blocking_reasons) > 0
    assert "Pre-generation grounding failed" in receipt.blocking_reasons[0]


def test_pipeline_blocks_post_generation_on_property_counterexample(pipeline):
    # Developer requests absolute value, generator emits buggy identity
    request = "Implement absolute value calculator."
    obligations = [{
        "obligation_id": "OB-ABS-NON-NEGATIVE",
        "obligation_type": "property",
        "strategy_specs": {
            "x": StrategySpec(strategy_type="integers", params={"min_value": -50, "max_value": 50})
        },
        "max_examples": 25,
        "seed": 42
    }]

    def buggy_generator(spec):
        # Buggy implementation: returns negative numbers unchanged
        def abs_property(x: int) -> bool:
            abs_val = x  # Bug: should be abs(x)
            return abs_val >= 0
        return abs_property

    target, receipt = pipeline.execute_governed_cycle(
        request_text=request,
        code_generator=buggy_generator,
        custom_obligations=obligations
    )

    assert target is None
    assert receipt.verdict == "BLOCK"
    assert receipt.pre_gen_grounded is True
    assert receipt.post_gen_verified is False
    assert receipt.obligations_failed == 1
    assert len(receipt.blocking_reasons) > 0
    assert "TARGET_COUNTEREXAMPLE_FOUND" in receipt.blocking_reasons[0]


def test_pipeline_handles_generator_exception_gracefully(pipeline):
    request = "Generate matrix inverse routine."

    def crashing_generator(spec):
        raise RuntimeError("LLM rate limit or compilation error")

    target, receipt = pipeline.execute_governed_cycle(
        request_text=request,
        code_generator=crashing_generator,
        custom_obligations=[{"obligation_id": "OB-DUMMY", "obligation_type": "property"}]
    )

    assert target is None
    assert receipt.verdict == "BLOCK"
    assert receipt.pre_gen_grounded is True
    assert receipt.post_gen_verified is False
    assert "Code generation failed with exception" in receipt.blocking_reasons[0]
