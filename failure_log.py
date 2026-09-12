"""
S-Class Personal Failure Log & Regression Harness

Tracks real-world failure modes from actual projects (e.g. SGDA 19-feature gap audit,
AMIS-RU FastAPI async session handling, Next.js/Prisma data-flow disconnects).
Acts as the empirical regression testbed for S-Class.
"""

import os
import re
import json
import logging
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

logger = logging.getLogger("failure_log")

FAILURE_LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "regression_cases.json")


@dataclass
class FailureCase:
    """A single real-world failure mode observed on an actual project."""
    id: str
    project: str                             # e.g. "SGDA", "AMIS-RU", "SriGuruDrivingAcademy"
    stack: str                               # e.g. "nextjs_prisma", "fastapi_python", "react_tailwind"
    date_logged: str
    summary: str
    root_cause: str                          # e.g. "vibecoded_ui_scaffolding", "missing_db_relation_wiring"
    missing_contracts: List[str]             # e.g. ["student_progress_tracker", "instructor_vehicle_assignment"]
    skeptic_rule_id: str                     # e.g. "SKEPTIC-NO-VIBECODE-UI", "SKEPTIC-PRISMA-SCHEMA-GROUNDING"
    resolved: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FailureCase":
        valid_keys = {
            "id", "project", "stack", "date_logged", "summary",
            "root_cause", "missing_contracts", "skeptic_rule_id", "resolved"
        }
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)


# Seed with the actual recorded real-world failure cases
INITIAL_FAILURE_CASES: List[Dict[str, Any]] = [
    {
        "id": "FAIL-SGDA-001",
        "project": "SriGuruDrivingAcademy (SGDA)",
        "stack": "nextjs_prisma",
        "date_logged": "2026-08-10T14:30:00Z",
        "summary": "19-feature gap audit: UI generated generic mockup cards instead of binding to real Prisma schema and driving curriculum models",
        "root_cause": "vibecoded_ui_scaffolding",
        "missing_contracts": [
            "student_lesson_progress_tracker",
            "instructor_vehicle_live_assignment",
            "rto_test_readiness_scorecard",
            "slot_conflict_prevention_matrix",
            "payment_receipt_ledger_binding"
        ],
        "skeptic_rule_id": "SKEPTIC-PRISMA-SCHEMA-GROUNDING",
        "resolved": True
    },
    {
        "id": "FAIL-AMISRU-002",
        "project": "AMIS-RU Research Tooling",
        "stack": "fastapi_python",
        "date_logged": "2026-08-12T10:15:00Z",
        "summary": "FastAPI endpoint specs omitted async session commit lifecycle and Pydantic response models",
        "root_cause": "shallow_api_scaffolding",
        "missing_contracts": [
            "async_db_session_dependency",
            "pydantic_v2_response_model_typing",
            "http_exception_handler_paths"
        ],
        "skeptic_rule_id": "SKEPTIC-FASTAPI-ASYNC-TYPING",
        "resolved": True
    },
    {
        "id": "FAIL-PORTAL-003",
        "project": "Student / College Department Portal",
        "stack": "nextjs_prisma",
        "date_logged": "2026-08-13T16:00:00Z",
        "summary": "Role spreading generated flat standalone pages without role-scoped permission checks on dynamic routes",
        "root_cause": "unscoped_route_spread",
        "missing_contracts": [
            "role_guard_middleware_binding",
            "student_self_profile_security_tab",
            "admin_verification_action_drawer"
        ],
        "skeptic_rule_id": "SKEPTIC-ROLE-ROUTE-GUARD",
        "resolved": True
    }
]


class FailureLogManager:
    """Manages the persistent personal failure log and regression cases."""

    ANSI_ESCAPE_RE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

    @classmethod
    def load_cases(cls, path: str = FAILURE_LOG_PATH) -> List[FailureCase]:
        if not os.path.exists(path):
            cls.save_cases([FailureCase.from_dict(c) for c in INITIAL_FAILURE_CASES], path)
            return [FailureCase.from_dict(c) for c in INITIAL_FAILURE_CASES]
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return [FailureCase.from_dict(c) for c in data]
        except Exception as e:
            logger.warning(f"Error loading failure log from {path}: {e}")
            return [FailureCase.from_dict(c) for c in INITIAL_FAILURE_CASES]

    @classmethod
    def save_cases(cls, cases: List[FailureCase], path: str = FAILURE_LOG_PATH) -> None:
        dir_name = os.path.dirname(os.path.abspath(path))
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump([c.to_dict() for c in cases], f, indent=2, ensure_ascii=False)

    @classmethod
    def log_failure(
        cls,
        project: str,
        stack: str,
        summary: str,
        root_cause: str,
        missing_contracts: List[str],
        skeptic_rule_id: str,
        path: str = FAILURE_LOG_PATH
    ) -> FailureCase:
        """One-line logger for when S-Class misses something on a real project."""
        cases = cls.load_cases(path)
        new_id = f"FAIL-{project.upper().replace(' ', '')[:6]}-{len(cases) + 1:03d}"
        case = FailureCase(
            id=new_id,
            project=project,
            stack=stack,
            date_logged=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            summary=summary,
            root_cause=root_cause,
            missing_contracts=missing_contracts,
            skeptic_rule_id=skeptic_rule_id,
            resolved=True
        )
        cases.append(case)
        cls.save_cases(cases, path)
        logger.info(f"Logged real-world failure case {case.id} for {project}")
        return case

    @classmethod
    def extract_from_run_log(cls, log_content: str) -> Dict[str, Any]:
        """Parses a failed run log or test runner output to auto-extract failure details."""
        clean_content = cls.ANSI_ESCAPE_RE.sub('', log_content)
        summary = "Execution run failure"
        missing_contracts = []
        root_cause = "test_failure_or_exception"

        lines = clean_content.splitlines()
        failed_tests = [l.strip() for l in lines if any(k in l for k in ["FAILED", "ERROR", "FAIL", "AssertionError"])]
        assertions = [l.strip() for l in lines if "AssertionError" in l or "assert " in l]

        if failed_tests:
            summary = f"Run failure in {len(failed_tests)} test(s): " + "; ".join(failed_tests[:2])
            for ft in failed_tests[:5]:
                # extract test name as contract candidate
                if "::" in ft:
                    name_part = ft.split("::")[-1].split(" ")[0].split("[")[0]
                elif "test_" in ft:
                    match = re.search(r"test_[a-zA-Z0-9_]+", ft)
                    name_part = match.group(0) if match else "test_execution"
                else:
                    name_part = re.sub(r'[^a-zA-Z0-9_]', '_', ft[:30]).strip('_')
                if name_part:
                    contract_name = f"contract_{name_part}"
                    if contract_name not in missing_contracts:
                        missing_contracts.append(contract_name)

        if assertions:
            root_cause = f"assertion_mismatch: {assertions[0][:80]}"
        elif any("Traceback" in l for l in lines):
            root_cause = "unhandled_runtime_exception"

        if not missing_contracts:
            missing_contracts = ["execution_integrity_contract"]

        return {
            "summary": summary,
            "root_cause": root_cause,
            "missing_contracts": missing_contracts
        }


def sclass_learn_cli(args: Optional[List[str]] = None) -> int:
    """CLI handler for `sclass learn` command."""
    import argparse
    parser = argparse.ArgumentParser(
        prog="sclass learn",
        description="Append a new empirical failure case from a bad run directly to regression_cases.json"
    )
    parser.add_argument("--project", default="GeneralProject", help="Target project identifier")
    parser.add_argument("--stack", default="python_pytest", help="Technology stack (e.g. nextjs_prisma, fastapi_python)")
    parser.add_argument("--summary", help="Summary of failure mode")
    parser.add_argument("--root-cause", default="unhandled_edge_case", help="Root cause classification")
    parser.add_argument("--missing-contracts", help="Comma-separated missing contracts/invariants")
    parser.add_argument("--skeptic-rule-id", default="SKEPTIC-STRUCTURAL-GROUNDING", help="Mapped skeptic rule ID (defaults to grounded rule)")
    parser.add_argument("--from-run-log", help="Path to a test output or error log file to parse")
    parser.add_argument("--path", default=FAILURE_LOG_PATH, help="Path to regression_cases.json")

    parsed = parser.parse_args(args)

    summary = parsed.summary
    root_cause = parsed.root_cause
    missing_contracts = [c.strip() for c in parsed.missing_contracts.split(",")] if parsed.missing_contracts else []

    if parsed.from_run_log:
        if os.path.exists(parsed.from_run_log):
            with open(parsed.from_run_log, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            extracted = FailureLogManager.extract_from_run_log(content)
            if not summary:
                summary = extracted["summary"]
            if root_cause == "unhandled_edge_case":
                root_cause = extracted["root_cause"]
            if not missing_contracts:
                missing_contracts = extracted["missing_contracts"]
        else:
            print(f"Error: Log file not found: {parsed.from_run_log}")
            return 1

    if not summary:
        print("Error: --summary or --from-run-log is required.")
        return 1

    if not missing_contracts:
        missing_contracts = ["system_state_contract"]

    case = FailureLogManager.log_failure(
        project=parsed.project,
        stack=parsed.stack,
        summary=summary,
        root_cause=root_cause,
        missing_contracts=missing_contracts,
        skeptic_rule_id=parsed.skeptic_rule_id,
        path=parsed.path
    )

    print("==================================================================")
    print(f"[+] S-Class Learned New Empirical Regression Case: {case.id}")
    print(f"  Project:         {case.project} ({case.stack})")
    print(f"  Summary:         {case.summary}")
    print(f"  Root Cause:      {case.root_cause}")
    print(f"  Contracts Added: {', '.join(case.missing_contracts)}")
    print(f"  Skeptic Rule:    {case.skeptic_rule_id}")
    print(f"  Artifact Path:   {parsed.path}")
    print("==================================================================")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(sclass_learn_cli(sys.argv[1:]))

