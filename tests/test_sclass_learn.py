import os
import json
import pytest
from failure_log import FailureLogManager, sclass_learn_cli, INITIAL_FAILURE_CASES


def test_sclass_learn_direct(tmp_path):
    reg_file = tmp_path / "regression_cases.json"
    
    # Run CLI function to learn a case
    args = [
        "--project", "TestPilot",
        "--stack", "fastapi_sqlite",
        "--summary", "Async session was closed before response streaming completed",
        "--root-cause", "premature_session_close",
        "--missing-contracts", "async_stream_session_guard,http_teardown_sync",
        "--skeptic-rule-id", "SKEPTIC-ASYNC-STREAM-SESSION",
        "--path", str(reg_file)
    ]
    ret = sclass_learn_cli(args)
    assert ret == 0
    
    # Verify file exists and has the case
    cases = FailureLogManager.load_cases(str(reg_file))
    assert len(cases) == len(INITIAL_FAILURE_CASES) + 1
    new_case = cases[-1]
    assert new_case.project == "TestPilot"
    assert new_case.root_cause == "premature_session_close"
    assert "async_stream_session_guard" in new_case.missing_contracts
    assert new_case.skeptic_rule_id == "SKEPTIC-ASYNC-STREAM-SESSION"


def test_sclass_learn_from_run_log(tmp_path):
    reg_file = tmp_path / "regression_cases.json"
    log_file = tmp_path / "pytest_run.log"
    log_content = """
============================= test session starts =============================
FAILED tests/test_auth.py::test_jwt_signature_expired - AssertionError: assert False is True
============================== 1 failed in 0.10s ==============================
"""
    log_file.write_text(log_content, encoding="utf-8")
    
    args = [
        "--project", "AuthService",
        "--stack", "python_pytest",
        "--from-run-log", str(log_file),
        "--path", str(reg_file)
    ]
    ret = sclass_learn_cli(args)
    assert ret == 0
    
    cases = FailureLogManager.load_cases(str(reg_file))
    assert len(cases) == len(INITIAL_FAILURE_CASES) + 1
    new_case = cases[-1]
    assert new_case.project == "AuthService"
    assert "test_jwt_signature_expired" in new_case.summary
    assert "contract_test_jwt_signature_expired" in new_case.missing_contracts
    # Verify date_logged matches standard ISO-8601 YYYY-MM-DDTHH:MM:SSZ without +00:00Z
    assert new_case.date_logged.endswith("Z")
    assert "+00:00" not in new_case.date_logged


def test_sclass_learn_ansi_and_unittest_logs(tmp_path):
    reg_file = tmp_path / "regression_cases.json"
    log_file = tmp_path / "colored_run.log"
    # Log with ANSI colors and unittest format
    log_content = "\x1b[31mERROR: test_database_connection_timeout (tests.test_db.DBTestCase)\x1b[0m\nTraceback (most recent call last):\nAssertionError: connection failed\n"
    log_file.write_text(log_content, encoding="utf-8")

    args = [
        "--project", "DBService",
        "--stack", "python_unittest",
        "--from-run-log", str(log_file),
        "--path", str(reg_file)
    ]
    ret = sclass_learn_cli(args)
    assert ret == 0

    cases = FailureLogManager.load_cases(str(reg_file))
    new_case = cases[-1]
    assert "\x1b" not in new_case.summary
    assert "\x1b" not in "".join(new_case.missing_contracts)
    assert "contract_test_database_connection_timeout" in new_case.missing_contracts
    # Verify default skeptic rule is properly grounded in PracticalSkeptic.ACTIVE_RULES
    assert new_case.skeptic_rule_id == "SKEPTIC-STRUCTURAL-GROUNDING"


def test_sclass_learn_preserves_utf8_characters(tmp_path):
    reg_file = tmp_path / "regression_cases.json"
    args = [
        "--project", "LegalSpec",
        "--stack", "python_pytest",
        "--summary", "Clause §6.17.E amendment was ignored — leading to contract breach",
        "--path", str(reg_file)
    ]
    ret = sclass_learn_cli(args)
    assert ret == 0

    raw_text = reg_file.read_text(encoding="utf-8")
    assert "§6.17.E" in raw_text
    assert "\\u00a7" not in raw_text


