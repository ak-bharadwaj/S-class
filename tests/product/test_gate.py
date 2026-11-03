"""Unit tests for shared GateState and GateOutput vocabulary (Lane B)."""
import pytest
from dataclasses import FrozenInstanceError

from sclass.product.gate import GateOutput, GateState


def test_gate_state_enumeration_values():
    """Verify GateState enum members and string values."""
    assert GateState.SATISFIED == "SATISFIED"
    assert GateState.MISSING == "MISSING"
    assert GateState.BLOCKED_ON_HUMAN == "BLOCKED_ON_HUMAN"
    assert len(GateState) == 3


def test_gate_output_minimal_instantiation():
    """Verify minimal instantiation with state only."""
    out = GateOutput(GateState.SATISFIED)
    assert out.state == GateState.SATISFIED
    assert out.must_id is None
    assert out.detail is None
    assert out.failures == []
    assert out.explain == {}
    assert str(out) == "SATISFIED"
    assert out == "SATISFIED"


def test_gate_output_satisfied_always_formats_as_satisfied():
    """Verify SATISFIED state always formats as 'SATISFIED' even if must_id is set."""
    out = GateOutput(GateState.SATISFIED, must_id="PD-F2-001")
    assert str(out) == "SATISFIED"
    assert out == "SATISFIED"


def test_gate_output_with_must_id_and_detail():
    """Verify string formatting with must_id."""
    out_missing = GateOutput(GateState.MISSING, must_id="PD-F2-001", detail="Missing input")
    assert str(out_missing) == "MISSING[PD-F2-001]"
    assert out_missing == "MISSING[PD-F2-001]"
    assert out_missing.detail == "Missing input"

    out_blocked = GateOutput(GateState.BLOCKED_ON_HUMAN, must_id="PD-F3-006", detail="Need user")
    assert str(out_blocked) == "BLOCKED_ON_HUMAN[PD-F3-006]"
    assert out_blocked == "BLOCKED_ON_HUMAN[PD-F3-006]"


def test_gate_output_equality_rules():
    """Verify string and GateOutput equality semantics."""
    out1 = GateOutput(GateState.MISSING, must_id="PD-F2-001")
    out2 = GateOutput(GateState.MISSING, must_id="PD-F2-001")
    out3 = GateOutput(GateState.MISSING, must_id="PD-F2-002")
    out4 = GateOutput(GateState.BLOCKED_ON_HUMAN, must_id="PD-F2-001")

    # Equivalence between GateOutput instances
    assert out1 == out2
    assert out1 != out3
    assert out1 != out4

    # String equivalence
    assert out1 == "MISSING[PD-F2-001]"
    assert out1 != "MISSING[PD-F2-002]"
    assert out1 != "SATISFIED"

    # Incompatible types
    assert out1 != 123
    assert out1 != None
    assert out1 != ["MISSING[PD-F2-001]"]


def test_gate_output_to_dict_serialization():
    """Verify to_dict serialization schema conformance."""
    out = GateOutput(
        GateState.MISSING,
        must_id="PD-F3-002",
        detail="Target digest mismatch",
        failures=["MISSING[PD-F3-002]"],
        explain={"reason": "digest_mismatch"},
    )
    d = out.to_dict()
    assert d == {
        "state": "MISSING",
        "failures": ["MISSING[PD-F3-002]"],
        "explain": {
            "reason": "digest_mismatch",
            "detail": "Target digest mismatch",
        },
    }

    # Verify fallback where failures is empty but must_id is present
    out_empty_fails = GateOutput(GateState.MISSING, must_id="PD-F3-001")
    d2 = out_empty_fails.to_dict()
    assert d2["state"] == "MISSING"
    assert d2["failures"] == ["MISSING[PD-F3-001]"]
    assert d2["explain"] == {}


def test_gate_output_immutability():
    """Verify GateOutput instances are frozen dataclasses."""
    out = GateOutput(GateState.SATISFIED)
    with pytest.raises(FrozenInstanceError):
        out.state = GateState.MISSING  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        out.must_id = "PD-001"  # type: ignore[misc]
