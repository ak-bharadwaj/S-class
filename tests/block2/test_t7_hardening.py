"""Tests for T7: F0 hardening re-audit (fail-closed defaults)."""
from __future__ import annotations

from sclass.product.gate import GateState
from sclass.product.lifecycle_p5 import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    evaluate_pd_ch2_036_adapter_qualification,
)


def test_lifecycle_p5_is_f10_qualified_defaults_false() -> None:
    out = evaluate_pd_ch2_036_adapter_qualification(
        "pytest-sclass",
        authority=QUALIFIED_EVALUATOR_BOUNDARY,
    )
    assert out.state == GateState.MISSING
    assert out.must_id == "PD-CH2-036"
