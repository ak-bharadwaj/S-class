"""Guard Test Suite: Test Classification Runner Verification (B01 Item 2).

Verifies:
1. ENV capabilities (bwrap, cgroup v2, userns, etc.) are ONLY recognized on explicit SKIPPED outcomes.
2. Any test failure or error (even if mentioning capability keywords) is STRICTLY classified as CODE.
3. Empty JUnit reports, malformed XML, and inconsistent counter attributes fail closed as CODE errors.
4. Non-zero pytest process exit codes unrepresented in JUnit testcases fail closed.
5. ENV items are strictly cataloged and NEVER counted as pass.
6. Conflicting outcome elements (skipped+failure, skipped+error, multiple outcomes) in a testcase
   fail closed as invalid JUnit / CODE failures and can NEVER produce an overall PASS.
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


# ---------------------------------------------------------------------------
# Defect 2: Conflicting Outcome Elements Guard Tests
# ---------------------------------------------------------------------------

def test_junit_skipped_plus_failure_fails_closed(tmp_path):
    """Testcase containing both skipped and failure must fail closed with ValueError."""
    conflict_junit = tmp_path / "skipped_plus_failure.xml"
    conflict_junit.write_text("""<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" tests="1" failures="1" errors="0" skipped="1">
    <testcase classname="tests.test_conflict" file="tests/test_conflict.py" name="conflicting-outcome" time="0.01">
      <skipped message="bubblewrap executable not found"/>
      <failure message="AssertionError">Invariant violated</failure>
    </testcase>
  </testsuite>
</testsuites>
""", encoding="utf-8")

    with pytest.raises(ValueError, match="MALFORMED JUNIT CONFLICT.*conflicting outcome elements"):
        C.parse_junit_xml(conflict_junit)


def test_junit_skipped_plus_error_fails_closed(tmp_path):
    """Testcase containing both skipped and error must fail closed with ValueError."""
    conflict_junit = tmp_path / "skipped_plus_error.xml"
    conflict_junit.write_text("""<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" tests="1" failures="0" errors="1" skipped="1">
    <testcase classname="tests.test_conflict" file="tests/test_conflict.py" name="conflicting-outcome-err" time="0.01">
      <skipped message="M5 sandboxed execution requires delegated cgroup v2: hierarchy missing"/>
      <error message="RuntimeError">Crash occurred</error>
    </testcase>
  </testsuite>
</testsuites>
""", encoding="utf-8")

    with pytest.raises(ValueError, match="MALFORMED JUNIT CONFLICT.*conflicting outcome elements"):
        C.parse_junit_xml(conflict_junit)


def test_junit_multiple_conflicting_outcome_elements_fails_closed(tmp_path):
    """Testcase with multiple failures and skipped elements must fail closed with ValueError."""
    conflict_junit = tmp_path / "multi_conflict.xml"
    conflict_junit.write_text("""<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" tests="1" failures="2" errors="0" skipped="1">
    <testcase classname="tests.test_conflict" file="tests/test_conflict.py" name="multi-outcome" time="0.01">
      <skipped message="bubblewrap executable not found"/>
      <failure message="AssertionError">First failure</failure>
      <failure message="AssertionError">Second failure</failure>
    </testcase>
  </testsuite>
</testsuites>
""", encoding="utf-8")

    with pytest.raises(ValueError, match="MALFORMED JUNIT CONFLICT.*conflicting outcome elements"):
        C.parse_junit_xml(conflict_junit)


def test_conflicting_junit_never_produces_pass(tmp_path, monkeypatch):
    """End-to-end: Conflicting JUnit XML in classified CLI runner must NEVER produce a PASS."""
    conflict_junit = tmp_path / "conflict.xml"
    conflict_junit.write_text("""<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" tests="1" failures="1" errors="0" skipped="1">
    <testcase classname="tests.test_conflict" file="tests/test_conflict.py" name="conflicting-outcome" time="0.01">
      <skipped message="bubblewrap executable not found"/>
      <failure message="AssertionError">Invariant violated</failure>
    </testcase>
  </testsuite>
</testsuites>
""", encoding="utf-8")

    out_json = tmp_path / "report.json"
    out_md = tmp_path / "report.md"

    test_args = [
        "run_full_suite_classified.py",
        "--junit-xml", str(conflict_junit),
        "--output-json", str(out_json),
        "--output-md", str(out_md),
        "--parse-only",
    ]
    monkeypatch.setattr(sys, "argv", test_args)

    ret = C.main()
    assert ret != 0, "Conflicting JUnit must fail closed (return non-zero)"

    data = json.loads(out_json.read_text(encoding="utf-8"))
    assert data["status"] == "FAIL", f"Expected FAIL but got {data['status']}"
    assert data["code_failures_count"] > 0
