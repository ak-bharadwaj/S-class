"""
S-Class Personal Failure Log & Regression Harness

Tracks real-world failure modes from actual projects (e.g. SGDA 19-feature gap audit,
AMIS-RU FastAPI async session handling, Next.js/Prisma data-flow disconnects).
Acts as the empirical regression testbed for S-Class.
"""

import os
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

    @classmethod
    def load_cases(cls, path: str = FAILURE_LOG_PATH) -> List[FailureCase]:
        if not os.path.exists(path):
            cls.save_cases([FailureCase(**c) for c in INITIAL_FAILURE_CASES], path)
            return [FailureCase(**c) for c in INITIAL_FAILURE_CASES]
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return [FailureCase(**c) for c in data]
        except Exception as e:
            logger.warning(f"Error loading failure log from {path}: {e}")
            return [FailureCase(**c) for c in INITIAL_FAILURE_CASES]

    @classmethod
    def save_cases(cls, cases: List[FailureCase], path: str = FAILURE_LOG_PATH) -> None:
        dir_name = os.path.dirname(os.path.abspath(path))
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump([c.to_dict() for c in cases], f, indent=2)

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
            date_logged=datetime.now(timezone.utc).isoformat() + "Z",
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
