"""WI-113 Qualification Record Generator (16 Master §6.8 fields; UNVERIFIED unless evidenced)."""
from __future__ import annotations

import hashlib
import pathlib
import re
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from sclass.product.adapter_qualification_contract import (
    ADDITIONAL_PRODUCT_TESTS,
    DECLARED_ADAPTER_CATEGORIES,
    FROZEN_ADAPTER_TESTS,
)
from sclass.product.oss_qualification_playbook import OSS_QUALIFICATION_FIELDS
from sclass.qualification.conformance_runner import ConformanceSuiteResult, ConformanceVerdict
from sclass.qualification.f10_validation import canonical_json, compute_sha256_json
from sclass.qualification.facts import FactsVerdict, FactsVerificationResult
from sclass.qualification.sandbox_runner import (
    AdvisoryLicenseResult,
    SandboxInstallResult,
    SandboxVerdict,
)

_SHA256_HEX_RE = re.compile(r"^[0-9a-fA-F]{64}$")

ORDERED_16_FIELDS: Tuple[str, ...] = (
    "upstream_repository",
    "immutable_ref",
    "license_obligations",
    "dependency_summary",
    "security_review",
    "test_ci_evidence",
    "install_digest",
    "os_runtime_assumptions",
    "consumed_api",
    "adapter_contract_version",
    "replacement_candidate",
    "fallback",
    "known_failure_modes",
    "qualification_status",
    "reviewer_reference",
    "record_digest",
)


def compute_record_generator_sha256() -> str:
    """Return LF-normalized sha256 of this record generator (TD-13)."""
    raw = pathlib.Path(__file__).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def _is_valid_sha256_hex(val: Any) -> bool:
    if type(val) is not str:
        return False
    cleaned = val.strip().lower()
    return bool(_SHA256_HEX_RE.match(cleaned)) and cleaned != "0" * 64


def is_valid_evidence_ref(ref: Any) -> bool:
    """Evidence ref must carry (file_path + non-zero 64-hex sha256) or non-empty runner_output_id."""
    if not isinstance(ref, Mapping):
        return False
    fp = ref.get("file_path")
    sha = ref.get("sha256")
    if type(fp) is str and fp.strip() and _is_valid_sha256_hex(sha):
        return True
    rid = ref.get("runner_output_id")
    if type(rid) is str and rid.strip():
        if "sha256" in ref and ref["sha256"] is not None and not _is_valid_sha256_hex(ref["sha256"]):
            return False
        return True
    return False


def _conformance_fully_passed(conf: Optional[ConformanceSuiteResult]) -> bool:
    if conf is None or conf.verdict != ConformanceVerdict.QUALIFIED:
        return False
    if set(conf.frozen_results.keys()) != set(FROZEN_ADAPTER_TESTS):
        return False
    if set(conf.additional_results.keys()) != set(ADDITIONAL_PRODUCT_TESTS):
        return False
    if not all(v.get("result") == "PASS" for v in conf.frozen_results.values()):
        return False
    if not all(v.get("result") == "PASS" for v in conf.additional_results.values()):
        return False
    return True


def generate_qualification_record(
    *,
    tool_id: str,
    category: str,
    as_of: str,
    facts_result: Optional[FactsVerificationResult] = None,
    sandbox_result: Optional[SandboxInstallResult] = None,
    advisory_result: Optional[AdvisoryLicenseResult] = None,
    conformance_result: Optional[ConformanceSuiteResult] = None,
    field_values: Optional[Mapping[str, Any]] = None,
    field_evidence_refs: Optional[Mapping[str, Mapping[str, Any]]] = None,
    dropped: bool = False,
    drop_reason: Optional[str] = None,
    extra_reasons: Sequence[str] = (),
) -> Dict[str, Any]:
    """Build a canonical 16-field qualification record (UNVERIFIED unless evidenced)."""
    assert set(ORDERED_16_FIELDS) == OSS_QUALIFICATION_FIELDS

    vals = dict(field_values or {})
    ev_refs = dict(field_evidence_refs or {})

    reasons: List[str] = list(extra_reasons)
    if facts_result is not None:
        reasons.extend(facts_result.reasons)
    if sandbox_result is not None:
        reasons.extend(sandbox_result.reasons)
    if advisory_result is not None:
        reasons.extend(advisory_result.reasons)
    if conformance_result is not None:
        reasons.extend(conformance_result.failure_reasons)
    if dropped:
        reasons.append(drop_reason or "DROPPED_BY_POLICY")

    # Auto-derive evidenced fields from T3 / T4 outputs when real hashes/IDs exist
    if sandbox_result is not None and sandbox_result.install_succeeded and _is_valid_sha256_hex(sandbox_result.install_digest):
        if _is_valid_sha256_hex(sandbox_result.transcript_sha256) and sandbox_result.transcript_path:
            vals.setdefault("install_digest", sandbox_result.install_digest)
            ev_refs.setdefault(
                "install_digest",
                {
                    "file_path": sandbox_result.transcript_path,
                    "sha256": sandbox_result.transcript_sha256,
                },
            )

    if conformance_result is not None and _is_valid_sha256_hex(conformance_result.report_digest):
        vals.setdefault(
            "test_ci_evidence",
            {
                "verdict": conformance_result.verdict.value,
                "frozen_passed": sum(1 for v in conformance_result.frozen_results.values() if v.get("result") == "PASS"),
                "additional_passed": sum(1 for v in conformance_result.additional_results.values() if v.get("result") == "PASS"),
            },
        )
        ev_refs.setdefault(
            "test_ci_evidence",
            {
                "runner_output_id": f"conformance:{conformance_result.adapter_id}",
                "sha256": conformance_result.report_digest,
            },
        )

    # Determine overall qualification_status (Errata 1 win conditions #2 & #3)
    t2_ok = facts_result is not None and facts_result.verdict == FactsVerdict.VERIFIED
    t3_transcript_sha = sandbox_result.transcript_sha256 if sandbox_result is not None else ""
    t3_ok = (
        sandbox_result is not None
        and sandbox_result.install_succeeded
        and _is_valid_sha256_hex(t3_transcript_sha)
        and sandbox_result.verdict == SandboxVerdict.VERIFIED
        and (advisory_result is None or advisory_result.verdict == SandboxVerdict.VERIFIED)
    )
    t4_ok = _conformance_fully_passed(conformance_result)
    is_f10_cat = category in DECLARED_ADAPTER_CATEGORIES
    never_auth = (
        tool_id.strip().lower() == "pr-agent"
        or (facts_result is not None and "NEVER_AUTHORITY_TOOL" in facts_result.reasons)
    )
    is_blocked = (
        (facts_result is not None and facts_result.verdict == FactsVerdict.BLOCKED)
        or (sandbox_result is not None and sandbox_result.verdict == SandboxVerdict.BLOCKED)
        or (advisory_result is not None and advisory_result.verdict == SandboxVerdict.BLOCKED)
    )
    is_l1_only = (
        never_auth
        or (facts_result is not None and facts_result.tier_eligibility == "L1_ONLY")
    )

    if dropped:
        qual_status = "DROPPED"
    elif is_blocked:
        qual_status = "BLOCKED"
    elif t2_ok and t3_ok and t4_ok and is_f10_cat and not never_auth:
        qual_status = "QUALIFIED"
    elif is_l1_only:
        qual_status = "L1_ONLY"
    else:
        qual_status = "UNVERIFIED"

    header = {
        "tool_id": tool_id,
        "category": category,
        "as_of": as_of,
        "generator_sha256": compute_record_generator_sha256(),
        "t2_verdict": facts_result.verdict.value if facts_result is not None else "UNRUN",
        "t3_verdict": sandbox_result.verdict.value if sandbox_result is not None else "UNRUN",
        "t3_transcript_sha256": t3_transcript_sha if _is_valid_sha256_hex(t3_transcript_sha) else "",
        "t4_verdict": conformance_result.verdict.value if conformance_result is not None else "UNRUN",
        "reasons": list(dict.fromkeys(reasons)),
    }

    rec: Dict[str, Any] = {"_header": header}
    for field in ORDERED_16_FIELDS:
        if field == "qualification_status":
            rec[field] = qual_status
        elif field == "record_digest":
            continue
        else:
            val = vals.get(field)
            ev_ref = ev_refs.get(field)
            has_val = val is not None and (not isinstance(val, str) or bool(val.strip())) and (not isinstance(val, (list, dict)) or len(val) > 0)
            if has_val and is_valid_evidence_ref(ev_ref):
                rec[field] = {
                    "status": "VERIFIED",
                    "value": val,
                    "evidence_ref": dict(ev_ref),
                }
            else:
                rec[field] = "UNVERIFIED"

    rec["record_digest"] = compute_sha256_json(rec)
    return rec


def verify_qualification_record(record: Mapping[str, Any]) -> Tuple[bool, str]:
    """Verify 16-field schema, evidence refs, QUALIFIED prerequisites, and canonical record_digest."""
    if not isinstance(record, Mapping):
        return False, "Record is not a mapping"

    actual_fields = set(record.keys()) - {"_header"}
    if actual_fields != OSS_QUALIFICATION_FIELDS:
        return False, f"Record fields mismatch: expected 16 OSS_QUALIFICATION_FIELDS, got {sorted(actual_fields)}"

    rec_digest = record.get("record_digest")
    if not _is_valid_sha256_hex(rec_digest):
        return False, "Invalid or placeholder record_digest"

    payload_no_dig = {k: v for k, v in record.items() if k != "record_digest"}
    expected_digest = compute_sha256_json(payload_no_dig)
    if rec_digest != expected_digest:
        return False, f"record_digest mismatch: {rec_digest} != {expected_digest}"

    header = record.get("_header")
    if not isinstance(header, Mapping) or not _is_valid_sha256_hex(header.get("generator_sha256")):
        return False, "Missing or invalid _header.generator_sha256"

    for field in ORDERED_16_FIELDS:
        if field in ("qualification_status", "record_digest"):
            continue
        val = record.get(field)
        if val == "UNVERIFIED":
            continue
        if isinstance(val, Mapping) and val.get("status") == "VERIFIED" and is_valid_evidence_ref(val.get("evidence_ref")):
            continue
        return False, f"Field {field} is neither UNVERIFIED nor supported by valid evidence_ref"

    q_status = record.get("qualification_status")
    if q_status == "QUALIFIED":
        if str(header.get("tool_id", "")).strip().lower() == "pr-agent":
            return False, "pr-agent can never reach QUALIFIED"
        if header.get("t2_verdict") != "VERIFIED":
            return False, "QUALIFIED requires T2 VERIFIED"
        if not _is_valid_sha256_hex(header.get("t3_transcript_sha256")):
            return False, "QUALIFIED requires valid T3 transcript sha256"
        if header.get("t4_verdict") != "QUALIFIED":
            return False, "QUALIFIED requires T4 conformance QUALIFIED"
        if header.get("category") not in DECLARED_ADAPTER_CATEGORIES:
            return False, "QUALIFIED requires canonical F10 category"

    return True, "OK"
