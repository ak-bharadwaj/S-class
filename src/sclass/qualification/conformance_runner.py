"""WI-112 Adapter Conformance Runner (14 Frozen Tests + A1/A2/A3, Protocol v1)."""
from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

import jsonschema

from sclass.product.adapter_qualification_contract import (
    ADDITIONAL_PRODUCT_TESTS,
    DECLARED_ADAPTER_CATEGORIES,
    EXTENSION_CATEGORIES,
    FROZEN_ADAPTER_TESTS,
)
from sclass.qualification.f10_validation import (
    DEFAULT_RESOURCE_LIMITS,
    build_approval_context_payload,
    canonical_json,
    check_stale_evidence,
    compute_sha256_json,
    detect_differential_disagreement,
    validate_resource_limits,
    verify_non_agent_approval_set,
)

PROTOCOL_VERSION = "1.0"
SCHEMA_PATH = pathlib.Path(__file__).resolve().parent / "schemas/adapter_protocol_v1.json"


class ConformanceVerdict(str, Enum):
    QUALIFIED = "QUALIFIED"
    UNQUALIFIED = "UNQUALIFIED"


@dataclass(frozen=True)
class ReferenceFixture:
    fixture_id: str
    payload: Mapping[str, Any]
    expected_verdict: str  # "PASS" | "FAIL"
    expected_canonical_output: Mapping[str, Any]


@dataclass(frozen=True)
class ConformanceCheckFlags:
    enforce_a1_fail_oracle: bool = True
    enforce_a1_pass_oracle: bool = True
    enforce_a1_semantic_compute: bool = True
    enforce_a2_differential: bool = True
    enforce_a3_digest_pinning: bool = True
    enforce_timeout_kill: bool = True
    enforce_identity_consistency: bool = True
    enforce_strict_schema: bool = True
    enforce_unique_result_ids: bool = True
    enforce_adversarial_probes: bool = True
    enforce_positive_frozen_oracles: bool = True


@dataclass(frozen=True)
class ConformanceSuiteResult:
    adapter_id: str
    adapter_version: str
    adapter_digest: str
    category: str
    verdict: ConformanceVerdict
    frozen_results: Mapping[str, Mapping[str, Any]]
    additional_results: Mapping[str, Mapping[str, Any]]
    provenance_bindings: Tuple[Mapping[str, Any], ...]
    latency_breaches: Tuple[str, ...]
    failure_reasons: Tuple[str, ...]
    report_digest: str

    def to_report_dict(self) -> Dict[str, Any]:
        body = {
            "runner_id": "sclass.qualification.conformance_runner.v1",
            "protocol_version": PROTOCOL_VERSION,
            "adapter_id": self.adapter_id,
            "adapter_version": self.adapter_version,
            "adapter_digest": self.adapter_digest,
            "category": self.category,
            "verdict": self.verdict.value,
            "frozen_results": {k: dict(v) for k, v in self.frozen_results.items()},
            "additional_results": {k: dict(v) for k, v in self.additional_results.items()},
            "provenance_bindings": [dict(p) for p in self.provenance_bindings],
            "latency_breaches": list(self.latency_breaches),
            "failures": list(self.failure_reasons),
            "report_digest": self.report_digest,
        }
        return body


def _load_protocol_schema() -> Dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _build_validators() -> Tuple[jsonschema.Draft202012Validator, jsonschema.Draft202012Validator]:
    schema = _load_protocol_schema()
    req_schema = {"$schema": schema["$schema"], "$defs": schema["$defs"], "$ref": "#/$defs/request"}
    resp_schema = {"$schema": schema["$schema"], "$defs": schema["$defs"], "$ref": "#/$defs/response"}
    return jsonschema.Draft202012Validator(req_schema), jsonschema.Draft202012Validator(resp_schema)


def _invoke_adapter_process(
    command: Sequence[str],
    request_obj: Optional[Mapping[str, Any]],
    *,
    raw_stdin_override: Optional[str] = None,
    resp_validator: jsonschema.Draft202012Validator,
    limits: Mapping[str, Any],
    check_flags: ConformanceCheckFlags,
    allow_bad_request: bool = False,
) -> Dict[str, Any]:
    """Execute one isolated adapter process invocation speaking protocol v1."""
    if raw_stdin_override is not None:
        stdin_text = raw_stdin_override
    else:
        assert request_obj is not None
        stdin_text = json.dumps(dict(request_obj), sort_keys=True)

    hard_stop = float(limits["hard_stop_s"])
    timeout_arg = hard_stop if check_flags.enforce_timeout_kill else max(hard_stop, 10.0)
    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            list(command),
            input=stdin_text,
            capture_output=True,
            text=True,
            timeout=timeout_arg,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "status": "MISSING",
            "reason": "TIMEOUT",
            "verdict": "MISSING",
            "latency_s": time.monotonic() - t0,
        }
    except Exception as exc:
        return {
            "status": "MISSING",
            "reason": f"INVOKE_ERROR:{type(exc).__name__}",
            "verdict": "MISSING",
            "latency_s": time.monotonic() - t0,
        }

    elapsed = time.monotonic() - t0
    if proc.returncode != 0:
        return {
            "status": "MISSING",
            "reason": f"CRASH:rc={proc.returncode}",
            "verdict": "MISSING",
            "latency_s": elapsed,
        }

    lines = [ln for ln in (proc.stdout or "").splitlines() if ln.strip()]
    if len(lines) != 1:
        return {
            "status": "MISSING",
            "reason": "PARTIAL_OR_DUPLICATE_FRAME",
            "verdict": "MISSING",
            "latency_s": elapsed,
        }

    try:
        resp = json.loads(lines[0])
    except Exception:
        return {
            "status": "MISSING",
            "reason": "MALFORMED_RESPONSE_JSON",
            "verdict": "MISSING",
            "latency_s": elapsed,
        }

    if not isinstance(resp, dict):
        return {
            "status": "MISSING",
            "reason": "MALFORMED_RESPONSE_NON_OBJECT",
            "verdict": "MISSING",
            "latency_s": elapsed,
        }

    if check_flags.enforce_strict_schema:
        errors = sorted(resp_validator.iter_errors(resp), key=lambda e: e.path)
        if errors:
            return {
                "status": "MISSING",
                "reason": f"MALFORMED_RESPONSE_SCHEMA:{errors[0].message}",
                "verdict": "MISSING",
                "response": resp,
                "latency_s": elapsed,
            }

    if not allow_bad_request and request_obj is not None and check_flags.enforce_strict_schema:
        if resp.get("request_id") != request_obj.get("request_id"):
            return {
                "status": "MISSING",
                "reason": "REQUEST_ID_MISMATCH",
                "verdict": "MISSING",
                "response": resp,
                "latency_s": elapsed,
            }
        if resp.get("input_digest") != request_obj.get("input_digest"):
            return {
                "status": "MISSING",
                "reason": "INPUT_DIGEST_MISMATCH",
                "verdict": "MISSING",
                "response": resp,
                "latency_s": elapsed,
            }
        if resp.get("category") != request_obj.get("category"):
            return {
                "status": "MISSING",
                "reason": "CATEGORY_MISMATCH",
                "verdict": "MISSING",
                "response": resp,
                "latency_s": elapsed,
            }

    usage = resp.get("resource_usage")
    if isinstance(usage, Mapping):
        if (
            float(usage.get("cpu_s", 0)) > float(limits["cpu_s"])
            or int(usage.get("memory_bytes", 0)) > int(limits["memory_bytes"])
            or int(usage.get("tokens", 0)) > int(limits["tokens"])
        ):
            return {
                "status": "MISSING",
                "reason": "RESOURCE_EXHAUSTION",
                "verdict": "MISSING",
                "response": resp,
                "latency_s": elapsed,
            }

    latency_breach = elapsed > float(limits["latency_soft_s"])
    return {
        "status": "OK",
        "verdict": resp.get("verdict", "MISSING"),
        "response": resp,
        "latency_s": elapsed,
        "latency_breach": latency_breach,
    }


def run_conformance_suite(
    *,
    command: Sequence[str],
    adapter_id: str,
    adapter_version: str,
    adapter_digest: str,
    category: str,
    reference_fixtures: Sequence[ReferenceFixture],
    resource_limits: Optional[Mapping[str, Any]] = None,
    policy_override_authorized: bool = False,
    prior_evidence_adapter_digest: Optional[str] = None,
    replacement_command: Optional[Sequence[str]] = None,
    replacement_adapter_id: Optional[str] = None,
    replacement_adapter_version: Optional[str] = None,
    replacement_adapter_digest: Optional[str] = None,
    check_flags: ConformanceCheckFlags = ConformanceCheckFlags(),
) -> ConformanceSuiteResult:
    """Run all 14 frozen adapter tests + A1/A2/A3 against an adapter process."""
    limits = resource_limits if resource_limits is not None else DEFAULT_RESOURCE_LIMITS
    limits_ok, limit_reasons = validate_resource_limits(
        limits, policy_override_authorized=policy_override_authorized
    )

    frozen_out: Dict[str, Dict[str, Any]] = {
        t: {"result": "FAIL", "detail": "not executed"} for t in sorted(FROZEN_ADAPTER_TESTS)
    }
    additional_out: Dict[str, Dict[str, Any]] = {
        t: {"result": "FAIL", "detail": "not executed"} for t in sorted(ADDITIONAL_PRODUCT_TESTS)
    }
    failures: List[str] = []
    latency_breaches: List[str] = []
    provenance_bindings: List[Dict[str, Any]] = []

    if type(category) is not str or category in EXTENSION_CATEGORIES or category not in DECLARED_ADAPTER_CATEGORIES:
        failures.append(f"UNDECLARED_OR_EXTENSION_CATEGORY:{category}")

    if not limits_ok:
        failures.extend(limit_reasons)
        frozen_out["resource_exhaustion"] = {"result": "FAIL", "detail": ",".join(limit_reasons)}
        report_digest = compute_sha256_json({
            "adapter_id": adapter_id,
            "adapter_digest": adapter_digest,
            "failures": failures,
        })
        return ConformanceSuiteResult(
            adapter_id=adapter_id,
            adapter_version=adapter_version,
            adapter_digest=adapter_digest,
            category=category,
            verdict=ConformanceVerdict.UNQUALIFIED,
            frozen_results=frozen_out,
            additional_results=additional_out,
            provenance_bindings=(),
            latency_breaches=(),
            failure_reasons=tuple(failures),
            report_digest=report_digest,
        )

    req_validator, resp_validator = _build_validators()
    seen_result_ids: Set[str] = set()
    observed_identities: Set[Tuple[str, str]] = set()
    schema_failures: List[str] = []
    duplicate_failures: List[str] = []
    crash_failures: List[str] = []
    partial_failures: List[str] = []
    timeout_failures: List[str] = []
    resource_failures: List[str] = []
    identity_failures: List[str] = []

    req_counter = 0

    def _next_req(test_name: str, payload: Mapping[str, Any], proto: str = PROTOCOL_VERSION) -> Dict[str, Any]:
        nonlocal req_counter
        req_counter += 1
        in_dig = compute_sha256_json(dict(payload))
        return {
            "protocol_version": proto,
            "request_id": f"req-{req_counter:04d}",
            "test_name": test_name,
            "adapter_id": adapter_id,
            "category": category,
            "input_digest": in_dig,
            "resource_limits": {k: limits[k] for k in ("latency_soft_s", "cpu_s", "memory_bytes", "tokens", "max_executions", "hard_stop_s")},
            "payload": dict(payload),
        }

    def _observe(test_label: str, invoke_res: Dict[str, Any], req_obj: Optional[Mapping[str, Any]]) -> None:
        if invoke_res.get("latency_breach"):
            latency_breaches.append(test_label)
        reason = str(invoke_res.get("reason", ""))
        if reason == "TIMEOUT":
            timeout_failures.append(test_label)
        elif reason.startswith("CRASH:"):
            crash_failures.append(test_label)
        elif reason == "PARTIAL_OR_DUPLICATE_FRAME":
            partial_failures.append(test_label)
        elif reason == "RESOURCE_EXHAUSTION":
            resource_failures.append(test_label)
        elif reason.startswith("MALFORMED_RESPONSE") or reason.endswith("_MISMATCH"):
            schema_failures.append(f"{test_label}:{reason}")

        resp = invoke_res.get("response")
        if isinstance(resp, Mapping):
            rid = resp.get("result_id")
            if check_flags.enforce_unique_result_ids and type(rid) is str:
                if rid in seen_result_ids:
                    duplicate_failures.append(f"{test_label}:{rid}")
                seen_result_ids.add(rid)

            r_ver = resp.get("adapter_version")
            r_dig = resp.get("adapter_digest")
            if check_flags.enforce_identity_consistency and type(r_ver) is str and type(r_dig) is str:
                observed_identities.add((r_ver, r_dig))
                if (r_ver, r_dig) != (adapter_version, adapter_digest):
                    identity_failures.append(f"{test_label}:{r_ver}@{r_dig}")

            if req_obj is not None:
                provenance_bindings.append({
                    "test_label": test_label,
                    "adapter_id": adapter_id,
                    "adapter_version": resp.get("adapter_version"),
                    "adapter_digest": resp.get("adapter_digest"),
                    "input_digest": req_obj.get("input_digest"),
                    "limits_digest": compute_sha256_json(req_obj.get("resource_limits")),
                    "result_id": rid,
                    "verdict": resp.get("verdict"),
                })

    # 1. capability_discovery
    cap_req = _next_req("capability_discovery", {"query": "capabilities"})
    assert not list(req_validator.iter_errors(cap_req))
    cap_res = _invoke_adapter_process(command, cap_req, resp_validator=resp_validator, limits=limits, check_flags=check_flags)
    _observe("capability_discovery", cap_res, cap_req)
    cap_resp = cap_res.get("response") or {}
    caps = cap_resp.get("capabilities", [])
    if (
        cap_res["status"] == "OK"
        and (not check_flags.enforce_positive_frozen_oracles or (cap_res["verdict"] == "PASS" and isinstance(caps, list) and category in caps))
    ):
        frozen_out["capability_discovery"] = {"result": "PASS", "result_id": cap_resp.get("result_id")}
    else:
        frozen_out["capability_discovery"] = {"result": "FAIL", "detail": cap_res.get("reason", "CAPABILITY_DISCOVERY_FAILED")}

    # 2. A1 reference fixture conformance (pass + fail oracles + semantic computation)
    a1_errors: List[str] = []
    a1_pass_outputs: List[Tuple[ReferenceFixture, Dict[str, Any], Dict[str, Any]]] = []
    if not reference_fixtures:
        a1_errors.append("NO_REFERENCE_FIXTURES")
    for fix in reference_fixtures:
        f_req = _next_req("A1_reference_fixture_conformance", fix.payload)
        f_res = _invoke_adapter_process(command, f_req, resp_validator=resp_validator, limits=limits, check_flags=check_flags)
        _observe(f"A1:{fix.fixture_id}", f_res, f_req)
        if f_res["status"] != "OK":
            a1_errors.append(f"{fix.fixture_id}:{f_res.get('reason')}")
            continue
        f_resp = f_res["response"]
        got_v = f_resp.get("verdict")
        if fix.expected_verdict == "PASS" and check_flags.enforce_a1_pass_oracle and got_v != "PASS":
            a1_errors.append(f"{fix.fixture_id}:EXPECTED_PASS_GOT_{got_v}")
        if fix.expected_verdict == "FAIL" and check_flags.enforce_a1_fail_oracle and got_v == "PASS":
            a1_errors.append(f"{fix.fixture_id}:ACCEPT_ALL_ON_EXPECTED_FAIL")
        if check_flags.enforce_a1_semantic_compute:
            if canonical_json(f_resp.get("canonical_output")) != canonical_json(fix.expected_canonical_output):
                a1_errors.append(f"{fix.fixture_id}:SEMANTIC_OUTPUT_MISMATCH")
        a1_pass_outputs.append((fix, f_req, f_resp))

    if not a1_errors:
        additional_out["A1_reference_fixture_conformance"] = {"result": "PASS", "fixtures_checked": len(reference_fixtures)}
    else:
        additional_out["A1_reference_fixture_conformance"] = {"result": "FAIL", "detail": ";".join(a1_errors)}

    # 3. A2 differential detection (run independent second invocation on first fixture + check disagreement detection)
    a2_errors: List[str] = []
    if check_flags.enforce_a2_differential:
        if not a1_pass_outputs:
            a2_errors.append("NO_A1_OUTPUT_FOR_DIFFERENTIAL")
        else:
            fix0, req0, resp0 = a1_pass_outputs[0]
            req0_b = _next_req("A2_differential_result_detection", fix0.payload)
            res0_b = _invoke_adapter_process(command, req0_b, resp_validator=resp_validator, limits=limits, check_flags=check_flags)
            _observe("A2_differential", res0_b, req0_b)
            if res0_b["status"] != "OK":
                a2_errors.append(f"SECONDARY_INVOKE_FAILED:{res0_b.get('reason')}")
            else:
                resp0_b = res0_b["response"]
                ok_diff, msg_diff = detect_differential_disagreement(
                    resp0.get("canonical_output", {}),
                    resp0_b.get("canonical_output", {}),
                    {"adapter_digest": resp0.get("adapter_digest"), "input_digest": req0["input_digest"]},
                    {"adapter_digest": resp0_b.get("adapter_digest"), "input_digest": req0_b["input_digest"]},
                )
                if not ok_diff:
                    a2_errors.append(f"DIFFERENTIAL_DISAGREEMENT:{msg_diff}")
                # Oracle check: verify differential detector catches synthetic disagreement
                synth_ok, _ = detect_differential_disagreement(
                    resp0.get("canonical_output", {}),
                    {"synthetic_disagreement": True},
                    {"adapter_digest": resp0.get("adapter_digest")},
                    {"adapter_digest": resp0.get("adapter_digest")},
                )
                if synth_ok:
                    a2_errors.append("DIFFERENTIAL_ORACLE_FAILED_TO_DETECT_MISMATCH")
    if not a2_errors:
        additional_out["A2_differential_result_detection"] = {"result": "PASS"}
    else:
        additional_out["A2_differential_result_detection"] = {"result": "FAIL", "detail": ";".join(a2_errors)}

    # 4. A3 stale-evidence invalidation after adapter digest change
    if check_flags.enforce_a3_digest_pinning:
        if prior_evidence_adapter_digest is not None:
            fresh_ok, fresh_msg = check_stale_evidence(prior_evidence_adapter_digest, adapter_digest)
            if not fresh_ok:
                additional_out["A3_stale_evidence_invalidation_after_adapter_change"] = {
                    "result": "FAIL",
                    "detail": fresh_msg,
                }
            else:
                additional_out["A3_stale_evidence_invalidation_after_adapter_change"] = {"result": "PASS"}
        else:
            # Verify A3 oracle detects a digest change
            stale_ok, _ = check_stale_evidence(adapter_digest, "f" * 64 if adapter_digest != "f" * 64 else "e" * 64)
            if stale_ok:
                additional_out["A3_stale_evidence_invalidation_after_adapter_change"] = {
                    "result": "FAIL",
                    "detail": "A3_ORACLE_FAILED_TO_INVALIDATE",
                }
            else:
                additional_out["A3_stale_evidence_invalidation_after_adapter_change"] = {"result": "PASS"}
    else:
        additional_out["A3_stale_evidence_invalidation_after_adapter_change"] = {"result": "PASS", "detail": "CHECK_DISABLED"}

    # 5. Adversarial frozen tests (must NEVER return PASS when enforce_adversarial_probes is True)
    # 5a. malformed_request
    mal_res = _invoke_adapter_process(
        command,
        None,
        raw_stdin_override="{corrupt-json",
        resp_validator=resp_validator,
        limits=limits,
        check_flags=check_flags,
        allow_bad_request=True,
    )
    _observe("malformed_request", mal_res, None)
    if not check_flags.enforce_adversarial_probes or mal_res.get("verdict") != "PASS":
        frozen_out["malformed_request"] = {"result": "PASS"}
    else:
        frozen_out["malformed_request"] = {"result": "FAIL", "detail": "ACCEPT_ALL_ON_MALFORMED_REQUEST"}

    # 5b. unavailable_dependency
    dep_req = _next_req("unavailable_dependency", {"simulate_fault": "unavailable_dependency"})
    dep_res = _invoke_adapter_process(command, dep_req, resp_validator=resp_validator, limits=limits, check_flags=check_flags)
    _observe("unavailable_dependency", dep_res, dep_req)
    if not check_flags.enforce_adversarial_probes or dep_res.get("verdict") != "PASS":
        frozen_out["unavailable_dependency"] = {"result": "PASS"}
    else:
        frozen_out["unavailable_dependency"] = {"result": "FAIL", "detail": "PASS_ON_UNAVAILABLE_DEPENDENCY"}

    # 5c. unexpected_protocol_message
    proto_req = _next_req("unexpected_protocol_message", {"op": "unknown"}, proto="99.0")
    proto_res = _invoke_adapter_process(command, proto_req, resp_validator=resp_validator, limits=limits, check_flags=check_flags, allow_bad_request=True)
    _observe("unexpected_protocol_message", proto_res, proto_req)
    if not check_flags.enforce_adversarial_probes or proto_res.get("verdict") != "PASS":
        frozen_out["unexpected_protocol_message"] = {"result": "PASS"}
    else:
        frozen_out["unexpected_protocol_message"] = {"result": "FAIL", "detail": "PASS_ON_UNEXPECTED_PROTOCOL"}

    # 5d. security_boundary_failure
    sec_req = _next_req("security_boundary_failure", {"simulate_fault": "security_boundary_failure", "path": "../../etc/passwd"})
    sec_res = _invoke_adapter_process(command, sec_req, resp_validator=resp_validator, limits=limits, check_flags=check_flags)
    _observe("security_boundary_failure", sec_res, sec_req)
    if not check_flags.enforce_adversarial_probes or sec_res.get("verdict") != "PASS":
        frozen_out["security_boundary_failure"] = {"result": "PASS"}
    else:
        frozen_out["security_boundary_failure"] = {"result": "FAIL", "detail": "PASS_ON_SECURITY_BOUNDARY_BREACH"}

    # 6. recovery (must succeed on valid probe after faulted runs)
    rec_payload = dict(reference_fixtures[0].payload) if reference_fixtures else {"value": 15}
    rec_req = _next_req("recovery", rec_payload)
    rec_res = _invoke_adapter_process(command, rec_req, resp_validator=resp_validator, limits=limits, check_flags=check_flags)
    _observe("recovery", rec_res, rec_req)
    if rec_res["status"] == "OK" and (not check_flags.enforce_positive_frozen_oracles or rec_res.get("verdict") == "PASS"):
        frozen_out["recovery"] = {"result": "PASS"}
    else:
        frozen_out["recovery"] = {"result": "FAIL", "detail": rec_res.get("reason", "RECOVERY_FAILED")}

    # 7. replacement (verify replacement or self-replacement contract)
    if replacement_command is not None and replacement_adapter_id and replacement_adapter_version and replacement_adapter_digest:
        rep_req = {
            "protocol_version": PROTOCOL_VERSION,
            "request_id": "req-replacement",
            "test_name": "capability_discovery",
            "adapter_id": replacement_adapter_id,
            "category": category,
            "input_digest": compute_sha256_json({"replacement": replacement_adapter_id}),
            "resource_limits": {k: limits[k] for k in ("latency_soft_s", "cpu_s", "memory_bytes", "tokens", "max_executions", "hard_stop_s")},
            "payload": {"query": "capabilities"},
        }
        rep_res = _invoke_adapter_process(replacement_command, rep_req, resp_validator=resp_validator, limits=limits, check_flags=check_flags)
        if rep_res["status"] == "OK" and rep_res.get("verdict") == "PASS":
            frozen_out["replacement"] = {"result": "PASS"}
        else:
            frozen_out["replacement"] = {"result": "FAIL", "detail": rep_res.get("reason", "REPLACEMENT_FAILED")}
    else:
        # Verify replacement invalidation oracle (new adapter digest supersedes old)
        stale_ok, _ = check_stale_evidence(adapter_digest, "1" * 64 if adapter_digest != "1" * 64 else "2" * 64)
        frozen_out["replacement"] = {"result": "PASS"} if not stale_ok else {"result": "FAIL", "detail": "REPLACEMENT_INVALIDATION_FAILED"}

    # 8. Observation-backed frozen tests across all suite invocations
    frozen_out["identity_version_mismatch"] = (
        {"result": "FAIL", "detail": ";".join(identity_failures)}
        if identity_failures or (check_flags.enforce_identity_consistency and len(observed_identities) > 1)
        else {"result": "PASS"}
    )
    frozen_out["malformed_response"] = (
        {"result": "FAIL", "detail": ";".join(schema_failures)}
        if schema_failures
        else {"result": "PASS"}
    )
    frozen_out["timeout"] = (
        {"result": "FAIL", "detail": ";".join(timeout_failures)}
        if timeout_failures
        else {"result": "PASS"}
    )
    frozen_out["crash"] = (
        {"result": "FAIL", "detail": ";".join(crash_failures)}
        if crash_failures
        else {"result": "PASS"}
    )
    frozen_out["partial_output"] = (
        {"result": "FAIL", "detail": ";".join(partial_failures)}
        if partial_failures
        else {"result": "PASS"}
    )
    frozen_out["duplicate_output"] = (
        {"result": "FAIL", "detail": ";".join(duplicate_failures)}
        if duplicate_failures
        else {"result": "PASS"}
    )
    frozen_out["resource_exhaustion"] = (
        {"result": "FAIL", "detail": ";".join(resource_failures)}
        if resource_failures
        else {"result": "PASS"}
    )

    all_passed = (
        not failures
        and all(v["result"] == "PASS" for v in frozen_out.values())
        and all(v["result"] == "PASS" for v in additional_out.values())
    )
    if not all_passed:
        for k, v in list(frozen_out.items()) + list(additional_out.items()):
            if v["result"] != "PASS":
                failures.append(f"{k}:{v.get('detail', 'FAIL')}")

    verdict = ConformanceVerdict.QUALIFIED if all_passed else ConformanceVerdict.UNQUALIFIED
    report_digest = compute_sha256_json({
        "adapter_id": adapter_id,
        "adapter_version": adapter_version,
        "adapter_digest": adapter_digest,
        "category": category,
        "verdict": verdict.value,
        "frozen_results": frozen_out,
        "additional_results": additional_out,
        "provenance_bindings": provenance_bindings,
        "failures": failures,
    })
    return ConformanceSuiteResult(
        adapter_id=adapter_id,
        adapter_version=adapter_version,
        adapter_digest=adapter_digest,
        category=category,
        verdict=verdict,
        frozen_results=frozen_out,
        additional_results=additional_out,
        provenance_bindings=tuple(provenance_bindings),
        latency_breaches=tuple(latency_breaches),
        failure_reasons=tuple(dict.fromkeys(failures)),
        report_digest=report_digest,
    )
