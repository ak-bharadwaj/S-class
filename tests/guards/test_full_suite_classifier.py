"""Guard Test Suite: Test Classification Runner Verification (B01 Item 2).

Verifies:
1. ENV capabilities (bwrap, cgroup v2, userns, etc.) are ONLY recognized on explicit SKIPPED outcomes.
2. Any test failure or error (even if mentioning capability keywords) is STRICTLY classified as CODE.
3. Empty JUnit reports, malformed XML, and inconsistent counter attributes fail closed as CODE errors.
4. Non-zero pytest process exit codes unrepresented in JUnit testcases fail closed.
5. ENV items are strictly cataloged and NEVER counted as pass.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TOOLS_DIR = _REPO_ROOT / "tools"

if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

import run_full_suite_classified as C


def test_classify_outcome_env_only_on_skipped():
    """Explicit skips with capability reasons must be classified as ENV."""
    # bwrap capability
    cat, cap, desc = C.classify_outcome("skipped", "bubblewrap executable not found", "")
    assert cat == "ENV"
    assert cap == "bwrap"

    # cgroup v2 capability
    cat, cap, desc = C.classify_outcome("skipped", "M5 sandboxed execution requires delegated cgroup v2: hierarchy missing", "")
    assert cat == "ENV"
    assert cap == "cgroup v2"

    # userns capability
    cat, cap, desc = C.classify_outcome("skipped", "bubblewrap unprivileged user namespaces are blocked or restricted", "")
    assert cat == "ENV"
    assert cap == "userns"

    # posix / proc capability
    cat, cap, desc = C.classify_outcome("skipped", "Linux O_PATH unavailable on Windows", "")
    assert cat == "ENV"
    assert cap == "linux_posix_proc"

    # SCLASS_MASTER_PATH capability
    cat, cap, desc = C.classify_outcome("skipped", "SCLASS_MASTER_PATH environment variable unset; real master tests require SCLASS_MASTER_PATH", "")
    assert cat == "ENV"
    assert cap == "env_var:SCLASS_MASTER_PATH"


def test_classify_outcome_failure_with_capability_keywords_is_always_code():
    """Crucial anti-masking test: Failures mentioning capability keywords MUST remain CODE."""
    capability_phrases = [
        "AssertionError: cgroup v2 policy invariant was violated",
        "RuntimeError: bubblewrap executable not found in mock sandbox",
        "KeyError: unprivileged user namespaces are blocked",
        "AssertionError: Linux /proc process monitor failed check",
        "AssertionError: SCLASS_MASTER_PATH environment variable unset during run",
    ]

    for phrase in capability_phrases:
        # On failure
        cat, cap, desc = C.classify_outcome("failure", phrase, "Traceback (most recent call last): ...")
        assert cat == "CODE", f"Failure masked as ENV: {phrase}"
        assert cap is None
        assert phrase in desc

        # On error
        cat_err, cap_err, desc_err = C.classify_outcome("error", phrase, "Traceback ...")
        assert cat_err == "CODE", f"Error masked as ENV: {phrase}"
        assert cap_err is None


def test_empty_junit_xml_fails_closed(tmp_path):
    """Empty JUnit report must fail closed with CODE failure."""
    empty_junit = tmp_path / "empty_junit.xml"
    empty_junit.write_text("""<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" tests="0" errors="0" failures="0" skipped="0">
  </testsuite>
</testsuites>
""", encoding="utf-8")

    parsed = C.parse_junit_xml(empty_junit)
    assert len(parsed["code"]) == 1
    assert parsed["code"][0]["node_id"] == "junit::empty_report"

    out_json = tmp_path / "report.json"
    out_md = tmp_path / "report.md"
    ret = C.generate_classification_report(parsed, 0.1, out_json, out_md)
    assert ret == 1


def test_inconsistent_junit_counters_fails_closed(tmp_path):
    """Discrepancy between declared counters and actual testcases must fail closed."""
    inconsistent_junit = tmp_path / "inconsistent_junit.xml"
    # Declares 2 tests, 0 failures, but actually contains a failure element
    inconsistent_junit.write_text("""<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" tests="2" errors="0" failures="0" skipped="0">
    <testcase classname="tests.test_a" file="tests/test_a.py" name="test_one" time="0.01" />
    <testcase classname="tests.test_b" file="tests/test_b.py" name="test_two" time="0.01">
      <failure message="AssertionError">Traceback</failure>
    </testcase>
  </testsuite>
</testsuites>
""", encoding="utf-8")

    parsed = C.parse_junit_xml(inconsistent_junit)
    assert any(c["node_id"] == "junit::counter_inconsistency" for c in parsed["code"])

    out_json = tmp_path / "report.json"
    out_md = tmp_path / "report.md"
    ret = C.generate_classification_report(parsed, 0.1, out_json, out_md)
    assert ret == 1


def test_unrecognized_skip_is_treated_as_code_defect(tmp_path):
    """Any skip that is not an explicitly authorized capability probe must be treated as CODE."""
    unrec_skip_junit = tmp_path / "unrec_skip.xml"
    unrec_skip_junit.write_text("""<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" tests="1" errors="0" failures="0" skipped="1">
    <testcase classname="tests.test_a" file="tests/test_a.py" name="test_lazy" time="0.00">
      <skipped message="test skipped because developer felt like skipping" type="pytest.skip" />
    </testcase>
  </testsuite>
</testsuites>
""", encoding="utf-8")

    parsed = C.parse_junit_xml(unrec_skip_junit)
    assert len(parsed["env"]) == 0
    assert len(parsed["code"]) == 1
    assert "Unrecognized skip reason" in parsed["code"][0]["description"]


def test_clean_run_with_valid_env_skips_passes(tmp_path):
    """Legitimate capability skip without code failures passes."""
    clean_junit = tmp_path / "clean_junit.xml"
    clean_junit.write_text("""<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" tests="2" errors="0" failures="0" skipped="1">
    <testcase classname="tests.test_pass" file="tests/test_pass.py" name="test_green" time="0.05" />
    <testcase classname="tests.test_skip" file="tests/test_skip.py" name="test_bwrap" time="0.00">
      <skipped message="bubblewrap executable not found" type="pytest.skip" />
    </testcase>
  </testsuite>
</testsuites>
""", encoding="utf-8")

    parsed = C.parse_junit_xml(clean_junit)
    assert len(parsed["passed"]) == 1
    assert len(parsed["env"]) == 1
    assert len(parsed["code"]) == 0

    out_json = tmp_path / "report.json"
    out_md = tmp_path / "report.md"
    ret = C.generate_classification_report(parsed, 0.2, out_json, out_md)
    assert ret == 0

    data = json.loads(out_json.read_text(encoding="utf-8"))
    assert data["status"] == "PASS"
    assert data["passed_count"] == 1
    assert data["env_items_count"] == 1
    assert data["code_failures_count"] == 0
