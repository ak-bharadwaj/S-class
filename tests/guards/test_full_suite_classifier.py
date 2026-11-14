"""Guard Test Suite: Test Classification Runner Verification (B01 Item 2).

Verifies:
1. ENV capabilities (bwrap, cgroup v2, userns, etc.) are correctly identified from skip/error text.
2. ENV items are strictly cataloged and NEVER counted as pass.
3. Code defects (e.g. AssertionError, KeyError) are strictly classified as CODE failures.
4. CODE failures cause the runner to return non-zero exit code (failing the job).
5. Structured report generation adheres to schema.
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


def test_classify_outcome_env_capabilities():
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

    # SCLASS_MASTER_PATH capability
    cat, cap, desc = C.classify_outcome("skipped", "SCLASS_MASTER_PATH environment variable unset; real master tests require SCLASS_MASTER_PATH", "")
    assert cat == "ENV"
    assert cap == "env_var:SCLASS_MASTER_PATH"


def test_classify_outcome_code_failure():
    cat, cap, desc = C.classify_outcome("failure", "AssertionError: 1 != 2", "Traceback ...")
    assert cat == "CODE"
    assert cap is None
    assert "AssertionError" in desc


def test_parse_junit_xml_and_generate_report(tmp_path):
    fake_junit = tmp_path / "fake_junit.xml"
    fake_junit.write_text("""<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" tests="4" errors="0" failures="1" skipped="2">
    <testcase classname="tests.test_one" file="tests/test_one.py" name="test_pass" time="0.01" />
    <testcase classname="tests.test_two" file="tests/test_two.py" name="test_skip_bwrap" time="0.00">
      <skipped message="bubblewrap executable not found" type="pytest.skip" />
    </testcase>
    <testcase classname="tests.test_three" file="tests/test_three.py" name="test_skip_cgroup" time="0.00">
      <skipped message="requires delegated cgroup v2: not writable" type="pytest.skip" />
    </testcase>
    <testcase classname="tests.test_four" file="tests/test_four.py" name="test_code_fail" time="0.02">
      <failure message="assert state.is_valid is True">Traceback ...</failure>
    </testcase>
  </testsuite>
</testsuites>
""", encoding="utf-8")

    parsed = C.parse_junit_xml(fake_junit)
    assert len(parsed["passed"]) == 1
    assert len(parsed["env"]) == 2
    assert len(parsed["code"]) == 1

    out_json = tmp_path / "report.json"
    out_md = tmp_path / "report.md"
    exit_code = C.generate_classification_report(parsed, 1.23, out_json, out_md)

    # Must exit 1 because of CODE failure
    assert exit_code == 1

    data = json.loads(out_json.read_text(encoding="utf-8"))
    assert data["total_collected"] == 4
    assert data["passed_count"] == 1
    assert data["env_items_count"] == 2
    assert data["code_failures_count"] == 1
    assert data["status"] == "FAIL"
    assert "bwrap" in data["env_summary_by_capability"]
    assert "cgroup v2" in data["env_summary_by_capability"]

    md_text = out_md.read_text(encoding="utf-8")
    assert "Missing host/environment capabilities (NEVER counted as pass)" in md_text
    assert "`bwrap`" in md_text
    assert "`cgroup v2`" in md_text
    assert "CODE Failures" in md_text


def test_clean_run_with_zero_code_failures(tmp_path):
    fake_junit = tmp_path / "fake_junit_clean.xml"
    fake_junit.write_text("""<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" tests="2" errors="0" failures="0" skipped="1">
    <testcase classname="tests.test_one" file="tests/test_one.py" name="test_pass" time="0.01" />
    <testcase classname="tests.test_two" file="tests/test_two.py" name="test_skip_bwrap" time="0.00">
      <skipped message="bubblewrap executable not found" type="pytest.skip" />
    </testcase>
  </testsuite>
</testsuites>
""", encoding="utf-8")

    parsed = C.parse_junit_xml(fake_junit)
    out_json = tmp_path / "report.json"
    out_md = tmp_path / "report.md"
    exit_code = C.generate_classification_report(parsed, 0.5, out_json, out_md)

    # Must exit 0 because CODE failures is 0
    assert exit_code == 0
    data = json.loads(out_json.read_text(encoding="utf-8"))
    assert data["status"] == "PASS"
    assert data["passed_count"] == 1
    assert data["env_items_count"] == 1
    assert data["code_failures_count"] == 0
