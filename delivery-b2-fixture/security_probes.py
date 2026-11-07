"""Security and negative probes for lane-b2-fixture."""
import sys
import pytest

from sclass.product.fixture_runner import (
    DEFAULT_MASTER_SHA256,
    EvaluatorRegistry,
    FixtureRunner,
    parse_master_fixtures,
    verify_master_sha256,
)
from sclass.product.gate import GateOutput, GateState

MASTER_PATH = "/mnt/c/Users/dorni/Downloads/S-CLASS-R32-PACKAGE/S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md"


def probe_hash_tampering_fails_closed():
    """Verify hash tampering fails closed."""
    for bad_hash in [
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "340db97857a7716b1aac2c1b44bc60b32642e3d8074d02720c2333cea278b400",
        "",
    ]:
        try:
            verify_master_sha256(MASTER_PATH, bad_hash)
            assert False, "Should have failed closed on bad master hash"
        except ValueError:
            pass
    print("[PROBE 1] Master SHA-256 tampering fails closed: PASSED")


def probe_missing_evaluator_never_passes():
    """Verify missing evaluators never return SATISFIED or PASS."""
    empty_reg = EvaluatorRegistry()
    runner = FixtureRunner(registry=empty_reg)
    manifest = runner.run(MASTER_PATH, DEFAULT_MASTER_SHA256)
    assert manifest["counts"]["ran_match"] == 0
    assert manifest["counts"]["not_run"] == 132 + 17
    for res in manifest["results"]:
        assert res["status"] == "NOT_RUN"
    print("[PROBE 2] Missing evaluators never return PASS: PASSED")


def probe_mock_never_produces_real_result():
    """Verify mock evaluators never produce RAN-MATCH or RAN."""
    reg = EvaluatorRegistry()
    reg.register(
        "PD-CH5-007",
        lambda rec: GateOutput(state=GateState.SATISFIED),
        name="FAKE_probe_evaluator",
    )
    runner = FixtureRunner(registry=reg)
    manifest = runner.run(MASTER_PATH, DEFAULT_MASTER_SHA256)
    for res in manifest["results"]:
        if res["must_id"] == "PD-CH5-007":
            assert res["status"] == "MOCK"
            assert res["status"] != "RAN-MATCH"
    print("[PROBE 3] Mock evaluators strictly flagged as MOCK: PASSED")


def main():
    print("=" * 60)
    print("SECURITY & NEGATIVE PROBES: LANE-B2-FIXTURE")
    print("=" * 60)
    probe_hash_tampering_fails_closed()
    probe_missing_evaluator_never_passes()
    probe_mock_never_produces_real_result()
    print("=" * 60)
    print("ALL 3 PROBE BATTERIES PASSED")
    print("=" * 60)


if __name__ == "__main__":
    main()
