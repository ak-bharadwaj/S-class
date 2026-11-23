"""W14 & W16 test: Omission matrix regression test asserting zero unlisted fail-opens."""
from __future__ import annotations

import pathlib
import sys
import pytest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
for _p in (_REPO_ROOT / "src", _REPO_ROOT / "tools", _REPO_ROOT / "10-CONFORMANCE"):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from omission_matrix import run_omission_matrix, EXEMPT_KEYS
from sclass.product.gate import GateState, GateOutput
from sclass.product.isolation_claims import (
    QUALIFIED_EVALUATOR_BOUNDARY,
    evaluate_pd_ch4_010_test_input_write_isolation,
    evaluate_pd_ch4_014_authorized_delta_scope,
    evaluate_pd_ch4_005_evidence_freshness_identity,
    evaluate_b4_e_gate,
)
from sclass.product.execution_flow_testinput import (
    REQUIRED_TEST_INPUT_KEYS,
    evaluate_pd_ch3_010_flow_baseline_binding,
    evaluate_pd_ch4_009_test_input_set_binding,
    evaluate_b4_d_gate,
)
from sclass.product.adapter_diff_spec_anchors import (
    evaluate_pd_ch3_020_spec_change_replay_point,
    evaluate_b4_b_gate,
)
from sclass.product.threat_eval_regression_gate import (
    evaluate_pd_ch9_005_data_retention_policy,
    evaluate_b9_a_gate,
)
from sclass.product.wire_session_consequential_gate import (
    evaluate_pd_ch7_009_protocol_idempotent_retries,
    evaluate_b7_a_gate,
)
from sclass.product.f8_step_pack import evaluate_f8_step_pack
from sclass.product.f4_lane_selection import evaluate_f4_lane_selection
from sclass.product.lifecycle_p0b import evaluate_pd_ch2_007_p8_retry_budget
from sclass.product.lifecycle_p3b import evaluate_pd_ch2_020_decidable_invariants
from sclass.product.artifacts import validate_artifact
from sclass.product.metrics import evaluate_f9_metric
from sclass.product.trust_model import InMemoryHostAttestationSource


def test_omission_matrix_zero_unexpected_fail_opens():
    """W18: Omission matrix executes across all active MUSTs with 0 unexpected fail-opens."""
    keys_tested, decision_bearing, unexpected, fixed_count, exempt_count, inert = run_omission_matrix()
    assert keys_tested >= 550, f"Expected >= 550 keys tested, got {keys_tested}"
    assert decision_bearing >= 450, f"Expected >= 450 decision-bearing keys, got {decision_bearing}"
    assert len(unexpected) == 0, f"Unexpected fail-opens detected ({len(unexpected)}): {unexpected[:5]}"
    assert fixed_count == 64


def test_targeted_omit_table_b1_fixed_fail_opens():
    """W16: Targeted omit tests proving all fixed fail-open sites fail closed when omitted."""
    auth = QUALIFIED_EVALUATOR_BOUNDARY

    # 1. isolation_claims: manifest_unchanged omitted -> MISSING
    r1 = evaluate_pd_ch4_010_test_input_write_isolation(
        ["src/f.py"], ["tests/t.py"], authority=auth
    )
    assert r1.state == GateState.MISSING

    # 2. isolation_claims: environment_digest_match omitted -> MISSING
    r2 = evaluate_pd_ch4_010_test_input_write_isolation(
        ["src/f.py"], ["tests/t.py"], manifest_unchanged=True, test_is_green=True, authority=auth
    )
    assert r2.state == GateState.MISSING

    # 3. isolation_claims: test_is_green omitted -> MISSING
    r3 = evaluate_pd_ch4_010_test_input_write_isolation(
        ["src/f.py"], ["tests/t.py"], manifest_unchanged=True, environment_digest_match=True, authority=auth
    )
    assert r3.state == GateState.MISSING

    # 4. isolation_claims: green_test_run omitted -> MISSING
    r4 = evaluate_pd_ch4_014_authorized_delta_scope(
        ["src/f.py"], ["src/f.py"], authority=auth
    )
    assert r4.state == GateState.MISSING

    # 5. isolation_claims: target_identity_match omitted -> MISSING
    r5 = evaluate_pd_ch4_005_evidence_freshness_identity(
        "sha256:r1", "sha256:r1", authority=auth
    )
    assert r5.state == GateState.MISSING

    # 6. execution_flow_testinput: rollback_inputs_bound omitted -> MISSING
    r6 = evaluate_pd_ch3_010_flow_baseline_binding(
        "MIGRATION", "sha256:b", verification_inputs_bound=True, authority=auth
    )
    assert r6.state == GateState.MISSING

    # 7. execution_flow_testinput: verification_inputs_bound omitted -> MISSING
    r7 = evaluate_pd_ch3_010_flow_baseline_binding(
        "MIGRATION", "sha256:b", rollback_inputs_bound=True, authority=auth
    )
    assert r7.state == GateState.MISSING

    # 8. execution_flow_testinput: is_before_red omitted -> MISSING
    r8 = evaluate_pd_ch4_009_test_input_set_binding(
        {k: "val" for k in REQUIRED_TEST_INPUT_KEYS}, authority=auth
    )
    assert r8.state == GateState.MISSING

    # 9. adapter_diff_spec_anchors: invalidated_evidence omitted -> MISSING
    r9 = evaluate_pd_ch3_020_spec_change_replay_point(
        "sha256:anc", ["sha256:ev1"], "P1", authority=auth
    )
    assert r9.state == GateState.MISSING

    # 10. threat_eval_regression_gate: recorded_action omitted -> MISSING
    r10 = evaluate_pd_ch9_005_data_retention_policy(
        within_retention_limit=True, has_policy_reference=True, authority=auth
    )
    assert r10.state == GateState.MISSING

    # 11. wire_session_consequential_gate: version_conflict_typed_error omitted on conflict -> MISSING
    r11 = evaluate_pd_ch7_009_protocol_idempotent_retries(
        True, conflict_detected=True, authority=auth
    )
    assert r11.state == GateState.MISSING

    # 12. f8_step_pack: bytes_equal omitted -> MISSING
    r12 = evaluate_f8_step_pack(
        {"golden_digest": "D1", "computed_digest": "D1"}, caller_authority=auth
    )
    assert r12.state == GateState.MISSING

    # 13. f4_lane_selection: rollback_capability omitted when MICRO requested -> computes STANDARD, fails lower check
    r13 = evaluate_f4_lane_selection(
        {"requested_lane": "MICRO", "estimated_files": 1, "modules": 1}, caller_authority=auth
    )
    assert r13.state == GateState.MISSING

    # 14. f4_lane_selection: ddl_present omitted on DDL requirement -> MISSING
    r14 = evaluate_f4_lane_selection(
        {"requested_lane": "STANDARD", "f1_artifact_class": "SCHEMA", "f1_required_representation": "DDL"},
        caller_authority=auth,
    )
    assert r14.state == GateState.MISSING

    # 15. lifecycle_p0b: is_p8_repair omitted -> MISSING
    r15 = evaluate_pd_ch2_007_p8_retry_budget(10, 2, authority=auth)
    assert r15.state == GateState.MISSING

    # 16. lifecycle_p3b: supported omitted on self-asserted PASS -> MISSING
    r16 = evaluate_pd_ch2_020_decidable_invariants(
        [{"name": "inv1", "fragment": "PROP", "claimed_pass": True}], authority=auth
    )
    assert r16.state == GateState.MISSING


def test_targeted_omit_table_b1_safe_defaults():
    """W16: Targeted omit tests proving safe default behavior on non-fail-open sites."""
    # artifacts.validate_artifact: check_digest defaults to True (fail-closed check enabled)
    # Digested artifact with wrong digest fails by default
    res = validate_artifact({"artifact_id": "A1", "artifact_class": "SCHEMA", "content_digest": "sha256:wrong", "content": "data"})
    assert res.is_valid is False

    # metrics.allow_replayed_digest: default True in evaluate_f9_metric enables replayed digest verification
    out_f9 = evaluate_f9_metric({"replayed_vector_digest": "d1"}, caller_authority=None)
    assert out_f9.state == GateState.MISSING  # Fails closed on authority

    # trust_model.InMemoryHostAttestationSource: user_presence_required defaults to True (fail-closed)
    env = InMemoryHostAttestationSource()
    assert env.get_host_attestation()["user_presence_required"] is True
