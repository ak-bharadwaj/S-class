"""Authoritative Structured Output Contract Validator for Verification Adapters (D8).

Enforces:
1. Require exact tool identity in every JSON result object.
2. Reject the entire JSON list if even one item fails or does not satisfy the complete passing contract.
3. Reject invalid failure-counter types, including strings and booleans.
4. Reject invalid UTF-8 strictly; do not decode corrupted output using replacement characters.
5. Require explicit successful status and valid positive numeric result counters.
6. Reject missing counters and nonzero failed/error counts.
7. Reject bare success-like text without a validated, tool-specific summary.
8. Empty or whitespace-only stdout with exit code zero fails closed.
9. Malformed / error markers in stdout or stderr fail closed.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Tuple


def _is_pos_num(val: Any) -> bool:
    """Returns True if val is a positive number (int or float) and NOT a bool or str."""
    return isinstance(val, (int, float)) and not isinstance(val, bool) and val > 0


def _validate_tool_dict(verifier_id: str, parsed: Dict[str, Any]) -> Tuple[bool, str]:
    """Validates a single tool dictionary against schema, identity, status, counters, and types."""
    if not isinstance(parsed, dict):
        return False, "Result item is not a JSON object"

    # 1. Exact Tool Identity Requirement (D8 Finding 1)
    if "tool" not in parsed:
        return False, f"Missing required 'tool' identity field: expected '{verifier_id}'"
    if parsed["tool"] != verifier_id:
        return False, f"Wrong tool identity: expected '{verifier_id}', got '{parsed['tool']}'"
    if len(parsed) == 1:
        return False, f"Tool-only JSON payload without status or counters rejected for {verifier_id}"

    # 2. Explicit failure check
    if parsed.get("passed") is False:
        return False, "Explicit passed=False in result payload"
    status_str = str(parsed.get("status", "")).lower()
    if status_str in ("failed", "error", "failure", "blocked", "failing"):
        return False, f"Non-passing status in result payload: {parsed.get('status')}"

    # 3. Nonzero failure / error counts check & type validation (D8 Finding 3)
    for err_key in ("failed", "failures", "errors", "num_failures", "failed_checks", "survived"):
        if err_key in parsed:
            val = parsed[err_key]
            # Must be a numeric int or float, NOT a boolean, NOT a string, NOT None, etc.
            if isinstance(val, bool) or not isinstance(val, (int, float)):
                return False, f"Invalid type for failure counter '{err_key}': expected numeric, got {type(val).__name__}"
            if val != 0:
                return False, f"Nonzero failure counter '{err_key}' ({val}) in result payload"

    # 4. Explicit successful status check
    has_success_status = (
        parsed.get("passed") is True
        or status_str in ("passed", "ok", "success")
    )
    if not has_success_status:
        return False, "Missing explicit successful status in result payload"

    # 5. Tool-specific positive numeric counters check & type validation
    if verifier_id == "locust":
        reqs = None
        for k in ("total_requests", "requests", "num_requests", "num_reqs"):
            if k in parsed:
                reqs = parsed[k]
                break
        if reqs is None:
            return False, "Missing required request counter in locust result"
        if isinstance(reqs, bool) or not isinstance(reqs, (int, float)):
            return False, f"Invalid type for locust request counter: expected numeric, got {type(reqs).__name__}"
        if reqs <= 0:
            return False, f"Non-positive request counter in locust result: {reqs}"
        return True, ""

    elif verifier_id == "schemathesis":
        checks = None
        for k in ("checks", "total_checks", "passed_checks"):
            if k in parsed:
                checks = parsed[k]
                break
        if checks is None:
            if "passed" in parsed and not isinstance(parsed["passed"], bool) and isinstance(parsed["passed"], (int, float)):
                checks = parsed["passed"]
            elif "total" in parsed and not isinstance(parsed["total"], bool) and isinstance(parsed["total"], (int, float)):
                checks = parsed["total"]
        if checks is None:
            return False, "Missing required check counter in schemathesis result"
        if isinstance(checks, bool) or not isinstance(checks, (int, float)):
            return False, f"Invalid type for schemathesis check counter: expected numeric, got {type(checks).__name__}"
        if checks <= 0:
            return False, f"Non-positive check counter in schemathesis result: {checks}"
        return True, ""

    elif verifier_id == "playwright":
        passed_cnt = None
        if "tests" in parsed:
            passed_cnt = parsed["tests"]
        elif "passed" in parsed and not isinstance(parsed["passed"], bool) and isinstance(parsed["passed"], (int, float)):
            passed_cnt = parsed["passed"]
        elif "total" in parsed:
            passed_cnt = parsed["total"]
        if passed_cnt is None:
            return False, "Missing required test counter in playwright result"
        if isinstance(passed_cnt, bool) or not isinstance(passed_cnt, (int, float)):
            return False, f"Invalid type for playwright test counter: expected numeric, got {type(passed_cnt).__name__}"
        if passed_cnt <= 0:
            return False, f"Non-positive test counter in playwright result: {passed_cnt}"
        return True, ""

    elif verifier_id == "testcontainers":
        cnt = None
        for k in ("containers", "passed", "tests", "num_containers"):
            if k in parsed:
                cnt = parsed[k]
                break
        if cnt is None:
            return False, "Missing required container/test counter in testcontainers result"
        if isinstance(cnt, bool) or not isinstance(cnt, (int, float)):
            return False, f"Invalid type for testcontainers counter: expected numeric, got {type(cnt).__name__}"
        if cnt <= 0:
            return False, f"Non-positive counter in testcontainers result: {cnt}"
        return True, ""

    elif verifier_id == "cosmic-ray":
        score = parsed.get("mutation_score")
        killed = parsed.get("killed")
        total_mut = parsed.get("total_mutations")

        for k, v in [("mutation_score", score), ("killed", killed), ("total_mutations", total_mut)]:
            if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float))):
                return False, f"Invalid type for cosmic-ray {k}: expected numeric, got {type(v).__name__}"

        has_counter = _is_pos_num(score) or _is_pos_num(killed) or _is_pos_num(total_mut)
        if not has_counter:
            return False, "Missing or non-positive mutation score/killed counter in cosmic-ray result"
        return True, ""

    return False, f"Unknown verifier ID {verifier_id}"


def validate_adapter_structured_output(
    verifier_id: str,
    stdout: bytes,
    stderr: bytes,
) -> Tuple[bool, str]:
    """Validates external tool output against the adapter-specific structured-result contract (D8)."""
    if not stdout or not stdout.strip():
        return False, "Empty verifier output with exit code zero (missing evidence)"

    # Strict UTF-8 decoding validation (D8 Finding 4)
    try:
        text = stdout.decode("utf-8", errors="strict").strip()
    except (UnicodeDecodeError, ValueError) as exc:
        return False, f"Invalid UTF-8 in verifier stdout stream: {exc}"

    if stderr:
        try:
            stderr.decode("utf-8", errors="strict")
        except (UnicodeDecodeError, ValueError) as exc:
            return False, f"Invalid UTF-8 in verifier stderr stream: {exc}"

    if b"Traceback (most recent call last)" in stderr:
        return False, "Traceback detected in verifier stderr"
    if b"INTERNALERROR" in stdout:
        return False, "INTERNALERROR detected in verifier stdout"
    if b"MALFORMED:" in stdout.upper() or b"CORRUPTED:" in stdout.upper():
        return False, "Malformed or corrupted marker in verifier stream"

    # -------------------------------------------------------------------------
    # 1. JSON Evaluation Path
    # -------------------------------------------------------------------------
    is_json_candidate = text.startswith("{") or (
        text.startswith("[") and bool(re.match(r"^\[\s*[\{\[\"\'\d\-\w]", text)) and not bool(re.match(r"^\[[a-zA-Z\-_]+\]", text))
    )

    if is_json_candidate:
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            return False, f"JSON parse error in verifier stream: {exc}"

        # D8 Finding 2: Reject entire list if even one item fails structured contract
        if isinstance(parsed, list):
            if not parsed:
                return False, "Empty JSON result list"
            for idx, item in enumerate(parsed):
                if not isinstance(item, dict):
                    return False, f"JSON list item {idx} is not an object"
                ok, err_msg = _validate_tool_dict(verifier_id, item)
                if not ok:
                    return False, f"JSON list item {idx} failed structured contract: {err_msg}"
            return True, ""

        if isinstance(parsed, dict):
            return _validate_tool_dict(verifier_id, parsed)

    # -------------------------------------------------------------------------
    # 2. Text-Structured Summary Evaluation Path
    # -------------------------------------------------------------------------
    bare_strings = {
        "all 12 verifications passed cleanly",
        "passed cleanly",
        "success",
        "ok",
        "pass",
        "passed",
        "true",
        "verification succeeded",
        "everything passed",
        "0",
    }
    if text.lower() in bare_strings or (len(text.splitlines()) == 1 and not re.search(r"\d+", text)):
        return False, f"Bare success-like text without tool-specific summary rejected for {verifier_id}"

    if verifier_id == "locust":
        m = re.search(
            r"(?:Aggregated\s+([1-9]\d*)\s+0(?:\(0\.?0*%\))?|Total\s+Requests:\s*([1-9]\d*)\s*\|\s*Failures:\s*0\b|\[locust\]\s+summary:\s*([1-9]\d*)\s+requests\s+passed,\s*0\s+failed)",
            text,
            re.IGNORECASE,
        )
        if m and not re.search(r"\b[1-9]\d*\s+failed\b|Failures:\s*[1-9]\d*", text, re.IGNORECASE):
            return True, ""
        return False, "Output failed locust structured contract validation (missing Aggregated/Total summary table with request counts)"

    elif verifier_id == "schemathesis":
        m = re.search(
            r"(?:checks:\s*([1-9]\d*)\s+passed,\s*0\s+failed|===+\s*([1-9]\d*)\s+passed\s+in\s+[\d\.]+s\s*===+|\[schemathesis\]\s+summary:\s*([1-9]\d*)\s+checks\s+passed,\s*0\s+failed)",
            text,
            re.IGNORECASE,
        )
        if m and not re.search(r"\b[1-9]\d*\s+failed\b", text, re.IGNORECASE):
            return True, ""
        return False, "Output failed schemathesis structured contract validation (missing checks/passed summary counts)"

    elif verifier_id == "playwright":
        m = re.search(
            r"(?:===+\s*([1-9]\d*)\s+passed(?:\s+in\s+[\d\.]+s)?\s*===+|\b([1-9]\d*)\s+passed\s+(?:in|\()\s*[\d\.]+s?\)?|\[playwright\]\s+summary:\s*([1-9]\d*)\s+tests\s+passed,\s*0\s+failed)",
            text,
            re.IGNORECASE,
        )
        if m and not re.search(r"\b[1-9]\d*\s+failed\b", text, re.IGNORECASE):
            return True, ""
        return False, "Output failed playwright structured contract validation (missing passed test summary counts)"

    elif verifier_id == "testcontainers":
        m = re.search(
            r"(?:===+\s*([1-9]\d*)\s+passed.*===+.*containers?\s+healthy|\[testcontainers\]\s+summary:\s*([1-9]\d*)\s+tests\s+passed,\s*0\s+failed,\s*containers\s+healthy)",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        if m and not re.search(r"\b[1-9]\d*\s+failed\b", text, re.IGNORECASE):
            return True, ""
        return False, "Output failed testcontainers structured contract validation (missing test summary counts and container health status)"

    elif verifier_id == "cosmic-ray":
        m = re.search(
            r"(?:complete:\s*mutation\s+score\s+([\d\.]+)%?,\s*killed:\s*([1-9]\d*),\s*survived:\s*0,\s*errors:\s*0|\[cosmic-ray\]\s+summary:\s*mutation\s+score\s+([\d\.]+)%?,\s*killed:\s*([1-9]\d*),\s*errors:\s*0)",
            text,
            re.IGNORECASE,
        )
        if m and not re.search(r"\berrors:\s*[1-9]\d*|\bsurvived:\s*[1-9]\d*", text, re.IGNORECASE):
            return True, ""
        return False, "Output failed cosmic-ray structured contract validation (missing mutation score / killed mutant counts)"

    return False, f"Output failed {verifier_id} structured contract validation (missing required format and numeric counters)"
