"""WI-112 Adapter Conformance Runner + 8-Mutant Battery (including fail-before proofs)."""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import tempfile
from typing import Any, Dict, List

import pytest

from sclass.qualification.conformance_runner import (
    DEFAULT_RESOURCE_LIMITS,
    ConformanceCheckFlags,
    ConformanceVerdict,
    ReferenceFixture,
    build_approval_context_payload,
    run_conformance_suite,
    validate_resource_limits,
)
from sclass.product.adapter_qualification_contract import (
    ADDITIONAL_PRODUCT_TESTS,
    FROZEN_ADAPTER_TESTS,
    QUALIFIED_EVALUATOR_BOUNDARY,
    evaluate_pd_f10_003_adapter_registration_authority,
    evaluate_pd_f10_004_execution_gate_enforcement,
    evaluate_pd_f10_005_qualification_matrix,
)
from sclass.product.gate import GateState


def _write_test_adapter(tmp_path: pathlib.Path, mode: str, state_file: pathlib.Path | None = None) -> tuple[pathlib.Path, str]:
    """Write a subprocess adapter script speaking adapter_protocol_v1.json in the requested mutant/honest mode."""
    script_path = tmp_path / f"adapter_{mode}.py"
    state_arg = repr(str(state_file or (tmp_path / f"state_{mode}.txt")))
    code = f'''import hashlib, json, pathlib, sys, time

MODE = {mode!r}
STATE_FILE = pathlib.Path({state_arg})
RAW = sys.stdin.read()
SELF_DIGEST = hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest()

if MODE == "sleep_pass":
    time.sleep(0.5)

try:
    req = json.loads(RAW)
except Exception:
    if MODE == "accept_all":
        req = {{
            "protocol_version": "1.0",
            "request_id": "bad-json-req",
            "test_name": "malformed_request",
            "adapter_id": "test-adapter",
            "category": "schema validators",
            "input_digest": "a" * 64,
            "payload": {{}},
        }}
    else:
        print(json.dumps({{
            "protocol_version": "1.0",
            "request_id": "parse-err",
            "result_id": "err-1",
            "adapter_id": "test-adapter",
            "adapter_version": "1.0.0",
            "adapter_digest": SELF_DIGEST,
            "category": "schema validators",
            "input_digest": "0" * 64,
            "verdict": "FAIL",
            "canonical_output": {{"error": "malformed_request"}},
            "resource_usage": {{"latency_s": 0.01, "cpu_s": 0.01, "memory_bytes": 1024, "tokens": 10}},
            "capabilities": ["schema validators"],
        }}))
        sys.exit(0)

if MODE != "accept_all":
    if req.get("protocol_version") != "1.0" or not req.get("request_id") or not req.get("payload") is not None and not isinstance(req.get("payload"), dict):
        pass

count = 1
if STATE_FILE.exists():
    count = int(STATE_FILE.read_text(encoding="utf-8")) + 1
STATE_FILE.write_text(str(count), encoding="utf-8")

self_digest = SELF_DIGEST
test_name = req.get("test_name", "")
payload = req.get("payload", {{}})
req_id = req.get("request_id", "unknown")
input_digest = req.get("input_digest", "0" * 64)
cat = req.get("category", "schema validators")

adapter_digest = self_digest
adapter_version = "1.0.0"
if MODE == "identity_drift" and count >= 2:
    adapter_digest = ("b" if self_digest[0] != "b" else "c") + self_digest[1:]
    adapter_version = "1.0.1"

result_id = "DUP-FIXED-ID" if MODE == "dup_result_id" else f"res-{{req_id}}-{{count}}"

# Compute expected semantic output for A1/A2 fixtures
val = payload.get("value")
if isinstance(val, int) and not isinstance(val, bool):
    computed = {{"valid": val >= 10, "doubled": val * 2, "mode": "computed"}}
else:
    computed = {{"valid": False, "error": "invalid_input"}}

if MODE == "accept_all":
    verdict = "PASS"
    canonical_output = computed
elif MODE == "always_reject":
    verdict = "FAIL"
    canonical_output = {{"valid": False, "forced_reject": True}}
elif MODE == "echo_fixture":
    if test_name in ("A1_reference_fixture_conformance", "A2_differential_result_detection"):
        verdict = "PASS" if (isinstance(val, int) and val >= 10) else "FAIL"
        canonical_output = dict(payload)
    elif req.get("protocol_version") != "1.0" or payload.get("simulate_fault") in ("unavailable_dependency", "security_boundary_failure", "identity_mismatch") or test_name == "malformed_request":
        verdict = "FAIL"
        canonical_output = {{"error": payload.get("simulate_fault", test_name)}}
    else:
        verdict = "PASS"
        canonical_output = {{"ok": True, "test_name": test_name}}
else:
    # Honest adapter
    if req.get("protocol_version") != "1.0":
        verdict = "FAIL"
        canonical_output = {{"error": "unexpected_protocol_version"}}
    elif payload.get("simulate_fault") in ("unavailable_dependency", "security_boundary_failure", "identity_mismatch"):
        verdict = "FAIL"
        canonical_output = {{"error": payload.get("simulate_fault")}}
    elif test_name == "malformed_request":
        verdict = "FAIL"
        canonical_output = {{"error": "malformed_request"}}
    elif test_name in ("A1_reference_fixture_conformance", "A2_differential_result_detection"):
        verdict = "PASS" if computed.get("valid") is True else "FAIL"
        canonical_output = computed
    else:
        verdict = "PASS"
        canonical_output = {{"ok": True, "test_name": test_name}}

resp = {{
    "protocol_version": "1.0",
    "request_id": req_id,
    "result_id": result_id,
    "adapter_id": req.get("adapter_id", "test-adapter"),
    "adapter_version": adapter_version,
    "adapter_digest": adapter_digest,
    "category": cat,
    "input_digest": input_digest,
    "verdict": verdict,
    "canonical_output": canonical_output,
    "resource_usage": {{"latency_s": 0.01, "cpu_s": 0.01, "memory_bytes": 1024, "tokens": 100}},
    "capabilities": [cat],
}}
if MODE == "extra_field":
    resp["self_attested_bypass"] = True
if MODE == "missing_field":
    del resp["resource_usage"]

print(json.dumps(resp))
'''
    # Write with fixed self digest placeholder patched consistently if needed
    raw_bytes = code.encode("utf-8")
    script_path.write_bytes(raw_bytes)
    digest = hashlib.sha256(raw_bytes).hexdigest()
    if "__SELF_DIGEST__" in code:
        # Replace placeholder with computed sha256 using fixed-length hex
        patched = code.replace("__SELF_DIGEST__", digest).encode("utf-8")
        # Keep deterministic digest over final file bytes
        script_path.write_bytes(patched)
        digest = hashlib.sha256(patched).hexdigest()
    return script_path, digest


def _reference_fixtures() -> List[ReferenceFixture]:
    return [
        ReferenceFixture(
            fixture_id="REF-PASS-1",
            payload={"value": 15},
            expected_verdict="PASS",
            expected_canonical_output={"valid": True, "doubled": 30, "mode": "computed"},
        ),
        ReferenceFixture(
            fixture_id="REF-FAIL-1",
            payload={"value": 3},
            expected_verdict="FAIL",
            expected_canonical_output={"valid": False, "doubled": 6, "mode": "computed"},
        ),
    ]


def test_honest_adapter_passes_all_14_plus_a1_a2_a3(tmp_path: pathlib.Path) -> None:
    script, digest = _write_test_adapter(tmp_path, "honest")
    res = run_conformance_suite(
        command=[sys.executable, str(script)],
        adapter_id="honest-schema-adapter",
        adapter_version="1.0.0",
        adapter_digest=digest,
        category="schema validators",
        reference_fixtures=_reference_fixtures(),
        resource_limits=DEFAULT_RESOURCE_LIMITS,
    )
    assert res.verdict == ConformanceVerdict.QUALIFIED
    assert set(res.frozen_results.keys()) == set(FROZEN_ADAPTER_TESTS)
    assert set(res.additional_results.keys()) == set(ADDITIONAL_PRODUCT_TESTS)
    assert all(r["result"] == "PASS" for r in res.frozen_results.values())
    assert all(r["result"] == "PASS" for r in res.additional_results.values())

    # Drive PD-F10-005 directly from real runner report
    gate_005 = evaluate_pd_f10_005_qualification_matrix(
        res.frozen_results,
        res.additional_results,
        conformance_report=res.to_report_dict(),
        authority=QUALIFIED_EVALUATOR_BOUNDARY,
    )
    assert gate_005.state == GateState.SATISFIED


def test_l992_resource_limits_fail_closed() -> None:
    ok, reasons = validate_resource_limits(DEFAULT_RESOURCE_LIMITS)
    assert ok is True and reasons == ()

    for bad_key in ("latency_soft_s", "cpu_s", "memory_bytes", "tokens", "max_executions", "hard_stop_s"):
        missing = dict(DEFAULT_RESOURCE_LIMITS)
        del missing[bad_key]
        ok_m, r_m = validate_resource_limits(missing)
        assert ok_m is False

        zero = dict(DEFAULT_RESOURCE_LIMITS)
        zero[bad_key] = 0
        ok_z, r_z = validate_resource_limits(zero)
        assert ok_z is False

        neg = dict(DEFAULT_RESOURCE_LIMITS)
        neg[bad_key] = -1
        ok_n, r_n = validate_resource_limits(neg)
        assert ok_n is False

    # Unbounded / above-default without policy override fails PD-F10-004
    too_big = dict(DEFAULT_RESOURCE_LIMITS)
    too_big["tokens"] = 999_999
    gate_004 = evaluate_pd_f10_004_execution_gate_enforcement(
        authorized_request={"id": "REQ-1"},
        execution_lease={"lease_id": "L-1"},
        budget_reservation={"cost": 10},
        fence={"fence_id": "F-1"},
        resource_limits=too_big,
        authority=QUALIFIED_EVALUATOR_BOUNDARY,
    )
    assert gate_004.state == GateState.MISSING
    assert gate_004.must_id == "PD-F10-004"


def test_pd_f10_003_requires_non_agent_approval_set() -> None:
    # Caller boolean alone without ApprovalSet must fail closed
    out_bool_only = evaluate_pd_f10_003_adapter_registration_authority(
        actor="lead-architect",
        operation="REGISTER_ADAPTER",
        canonical_write_authorized=True,
        authority=QUALIFIED_EVALUATOR_BOUNDARY,
    )
    assert out_bool_only.state == GateState.MISSING
    assert out_bool_only.must_id == "PD-F10-003"

    # Real non-agent ApprovalSet succeeds
    ctx = build_approval_context_payload(
        requester_principal_id="ci-bot",
        approver_principal_id="human-maintainer",
        approver_role="security-reviewer",
        adapter_digest="sha256:" + "a" * 64,
    )
    out_ok = evaluate_pd_f10_003_adapter_registration_authority(
        actor="human-maintainer",
        operation="REGISTER_ADAPTER",
        approval_set=ctx["approval_set"],
        approval_context=ctx["approval_context"],
        authority=QUALIFIED_EVALUATOR_BOUNDARY,
    )
    assert out_ok.state == GateState.SATISFIED

    # Agent registration attempt via ApprovalSet fails closed
    agent_ctx = build_approval_context_payload(
        requester_principal_id="ci-bot",
        approver_principal_id="agent",
        approver_role="agent",
        adapter_digest="sha256:" + "a" * 64,
    )
    out_agent = evaluate_pd_f10_003_adapter_registration_authority(
        actor="agent",
        operation="REGISTER_ADAPTER",
        approval_set=agent_ctx["approval_set"],
        approval_context=agent_ctx["approval_context"],
        authority=QUALIFIED_EVALUATOR_BOUNDARY,
    )
    assert out_agent.state == GateState.MISSING
    assert out_agent.must_id == "PD-F10-003"


def test_mutant_1_accept_all_caught_and_fail_before(tmp_path: pathlib.Path) -> None:
    script, digest = _write_test_adapter(tmp_path, "accept_all")
    # Fail-before when A1 fail oracle & adversarial fault checks are disabled
    weak = run_conformance_suite(
        command=[sys.executable, str(script)],
        adapter_id="m-accept-all",
        adapter_version="1.0.0",
        adapter_digest=digest,
        category="schema validators",
        reference_fixtures=_reference_fixtures(),
        resource_limits=DEFAULT_RESOURCE_LIMITS,
        check_flags=ConformanceCheckFlags(
            enforce_a1_fail_oracle=False,
            enforce_adversarial_probes=False,
        ),
    )
    assert weak.verdict == ConformanceVerdict.QUALIFIED

    # Caught with full checks enabled
    strict = run_conformance_suite(
        command=[sys.executable, str(script)],
        adapter_id="m-accept-all",
        adapter_version="1.0.0",
        adapter_digest=digest,
        category="schema validators",
        reference_fixtures=_reference_fixtures(),
        resource_limits=DEFAULT_RESOURCE_LIMITS,
    )
    assert strict.verdict == ConformanceVerdict.UNQUALIFIED
    assert strict.additional_results["A1_reference_fixture_conformance"]["result"] == "FAIL"


def test_mutant_2_always_reject_caught_and_fail_before(tmp_path: pathlib.Path) -> None:
    script, digest = _write_test_adapter(tmp_path, "always_reject")
    weak = run_conformance_suite(
        command=[sys.executable, str(script)],
        adapter_id="m-always-reject",
        adapter_version="1.0.0",
        adapter_digest=digest,
        category="schema validators",
        reference_fixtures=_reference_fixtures(),
        resource_limits=DEFAULT_RESOURCE_LIMITS,
        check_flags=ConformanceCheckFlags(
            enforce_a1_pass_oracle=False,
            enforce_a1_semantic_compute=False,
            enforce_positive_frozen_oracles=False,
        ),
    )
    assert weak.verdict == ConformanceVerdict.QUALIFIED

    strict = run_conformance_suite(
        command=[sys.executable, str(script)],
        adapter_id="m-always-reject",
        adapter_version="1.0.0",
        adapter_digest=digest,
        category="schema validators",
        reference_fixtures=_reference_fixtures(),
        resource_limits=DEFAULT_RESOURCE_LIMITS,
    )
    assert strict.verdict == ConformanceVerdict.UNQUALIFIED
    assert strict.additional_results["A1_reference_fixture_conformance"]["result"] == "FAIL"


def test_mutant_3_pass_on_timeout_caught_and_fail_before(tmp_path: pathlib.Path) -> None:
    script, digest = _write_test_adapter(tmp_path, "sleep_pass")
    limits = dict(DEFAULT_RESOURCE_LIMITS)
    limits["hard_stop_s"] = 0.15
    limits["latency_soft_s"] = 0.1
    limits["cpu_s"] = 0.15

    weak = run_conformance_suite(
        command=[sys.executable, str(script)],
        adapter_id="m-sleep-pass",
        adapter_version="1.0.0",
        adapter_digest=digest,
        category="schema validators",
        reference_fixtures=_reference_fixtures(),
        resource_limits=limits,
        check_flags=ConformanceCheckFlags(enforce_timeout_kill=False),
    )
    assert weak.verdict == ConformanceVerdict.QUALIFIED

    strict = run_conformance_suite(
        command=[sys.executable, str(script)],
        adapter_id="m-sleep-pass",
        adapter_version="1.0.0",
        adapter_digest=digest,
        category="schema validators",
        reference_fixtures=_reference_fixtures(),
        resource_limits=limits,
    )
    assert strict.verdict == ConformanceVerdict.UNQUALIFIED
    assert strict.frozen_results["timeout"]["result"] == "FAIL"


def test_mutant_4_echo_fixture_caught_and_fail_before(tmp_path: pathlib.Path) -> None:
    script, digest = _write_test_adapter(tmp_path, "echo_fixture")
    weak = run_conformance_suite(
        command=[sys.executable, str(script)],
        adapter_id="m-echo",
        adapter_version="1.0.0",
        adapter_digest=digest,
        category="schema validators",
        reference_fixtures=_reference_fixtures(),
        resource_limits=DEFAULT_RESOURCE_LIMITS,
        check_flags=ConformanceCheckFlags(
            enforce_a1_semantic_compute=False,
            enforce_a2_differential=False,
        ),
    )
    assert weak.verdict == ConformanceVerdict.QUALIFIED

    strict = run_conformance_suite(
        command=[sys.executable, str(script)],
        adapter_id="m-echo",
        adapter_version="1.0.0",
        adapter_digest=digest,
        category="schema validators",
        reference_fixtures=_reference_fixtures(),
        resource_limits=DEFAULT_RESOURCE_LIMITS,
    )
    assert strict.verdict == ConformanceVerdict.UNQUALIFIED
    assert strict.additional_results["A1_reference_fixture_conformance"]["result"] == "FAIL"


def test_mutant_5_stale_reuse_after_digest_change_caught_and_fail_before(tmp_path: pathlib.Path) -> None:
    script, digest = _write_test_adapter(tmp_path, "honest")
    superseded_digest = ("d" if digest[0] != "d" else "e") + digest[1:]

    weak = run_conformance_suite(
        command=[sys.executable, str(script)],
        adapter_id="m-stale",
        adapter_version="1.0.0",
        adapter_digest=digest,
        prior_evidence_adapter_digest=superseded_digest,
        category="schema validators",
        reference_fixtures=_reference_fixtures(),
        resource_limits=DEFAULT_RESOURCE_LIMITS,
        check_flags=ConformanceCheckFlags(enforce_a3_digest_pinning=False),
    )
    assert weak.verdict == ConformanceVerdict.QUALIFIED

    strict = run_conformance_suite(
        command=[sys.executable, str(script)],
        adapter_id="m-stale",
        adapter_version="1.0.0",
        adapter_digest=digest,
        prior_evidence_adapter_digest=superseded_digest,
        category="schema validators",
        reference_fixtures=_reference_fixtures(),
        resource_limits=DEFAULT_RESOURCE_LIMITS,
    )
    assert strict.verdict == ConformanceVerdict.UNQUALIFIED
    assert strict.additional_results["A3_stale_evidence_invalidation_after_adapter_change"]["result"] == "FAIL"


def test_mutant_6_identity_changes_between_runs_caught_and_fail_before(tmp_path: pathlib.Path) -> None:
    script, digest = _write_test_adapter(tmp_path, "identity_drift")
    state_f = tmp_path / "state_identity_drift.txt"

    if state_f.exists():
        state_f.unlink()
    weak = run_conformance_suite(
        command=[sys.executable, str(script)],
        adapter_id="m-id-drift",
        adapter_version="1.0.0",
        adapter_digest=digest,
        category="schema validators",
        reference_fixtures=_reference_fixtures(),
        resource_limits=DEFAULT_RESOURCE_LIMITS,
        check_flags=ConformanceCheckFlags(enforce_identity_consistency=False),
    )
    assert weak.verdict == ConformanceVerdict.QUALIFIED

    if state_f.exists():
        state_f.unlink()
    strict = run_conformance_suite(
        command=[sys.executable, str(script)],
        adapter_id="m-id-drift",
        adapter_version="1.0.0",
        adapter_digest=digest,
        category="schema validators",
        reference_fixtures=_reference_fixtures(),
        resource_limits=DEFAULT_RESOURCE_LIMITS,
    )
    assert strict.verdict == ConformanceVerdict.UNQUALIFIED
    assert strict.frozen_results["identity_version_mismatch"]["result"] == "FAIL"


@pytest.mark.parametrize("mode", ["extra_field", "missing_field"])
def test_mutant_7_extra_or_missing_output_fields_caught_and_fail_before(tmp_path: pathlib.Path, mode: str) -> None:
    script, digest = _write_test_adapter(tmp_path, mode)
    weak = run_conformance_suite(
        command=[sys.executable, str(script)],
        adapter_id=f"m-{mode}",
        adapter_version="1.0.0",
        adapter_digest=digest,
        category="schema validators",
        reference_fixtures=_reference_fixtures(),
        resource_limits=DEFAULT_RESOURCE_LIMITS,
        check_flags=ConformanceCheckFlags(enforce_strict_schema=False),
    )
    assert weak.verdict == ConformanceVerdict.QUALIFIED

    strict = run_conformance_suite(
        command=[sys.executable, str(script)],
        adapter_id=f"m-{mode}",
        adapter_version="1.0.0",
        adapter_digest=digest,
        category="schema validators",
        reference_fixtures=_reference_fixtures(),
        resource_limits=DEFAULT_RESOURCE_LIMITS,
    )
    assert strict.verdict == ConformanceVerdict.UNQUALIFIED
    assert strict.frozen_results["malformed_response"]["result"] == "FAIL"


def test_mutant_8_duplicate_result_ids_caught_and_fail_before(tmp_path: pathlib.Path) -> None:
    script, digest = _write_test_adapter(tmp_path, "dup_result_id")
    weak = run_conformance_suite(
        command=[sys.executable, str(script)],
        adapter_id="m-dup-id",
        adapter_version="1.0.0",
        adapter_digest=digest,
        category="schema validators",
        reference_fixtures=_reference_fixtures(),
        resource_limits=DEFAULT_RESOURCE_LIMITS,
        check_flags=ConformanceCheckFlags(enforce_unique_result_ids=False),
    )
    assert weak.verdict == ConformanceVerdict.QUALIFIED

    strict = run_conformance_suite(
        command=[sys.executable, str(script)],
        adapter_id="m-dup-id",
        adapter_version="1.0.0",
        adapter_digest=digest,
        category="schema validators",
        reference_fixtures=_reference_fixtures(),
        resource_limits=DEFAULT_RESOURCE_LIMITS,
    )
    assert strict.verdict == ConformanceVerdict.UNQUALIFIED
    assert strict.frozen_results["duplicate_output"]["result"] == "FAIL"
