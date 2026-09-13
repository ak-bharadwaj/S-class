"""
S-Class Control: Resource & Action Impact Analysis (Blast Radius).
Computes risk level, sensitive target classification, and operator escalation requirements.
"""

from __future__ import annotations
import os
import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum

from sclass.domain.action import ActionRequest


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


SENSITIVE_PATH_PATTERNS = [
    r"(^|/)\.git(/|$)",
    r"(^|/)\.sclass(/|$)",
    r"(^|/)\.agents(/|$)",
    r"(^|/)\.env(\..+)?$",
    r"(^|/)secrets?(\..+)?$",
    r"(^|/)credentials?(\..+)?$",
    r"(^|/)id_rsa.*$",
    r"(^|/)\.ssh(/|$)",
    r"(^|/)pyproject\.toml$",
    r"(^|/)setup\.py$",
    r"(^|/)package\.json$",
    r"(^|/)package-lock\.json$",
    r"(^|/)Dockerfile.*$",
    r"(^|/)docker-compose.*\.ya?ml$",
    r"(^|/)\.github/workflows(/|$)",
    r".*migration.*\.py$",
    r".*migration.*\.sql$",
    r".*auth.*",
    r".*payment.*",
    r".*security.*",
]


@dataclass(frozen=True)
class ImpactAnalysis:
    """Quantitative and categorical assessment of an action's blast radius."""
    risk_level: RiskLevel
    score: float  # 0.0 to 1.0
    sensitive_targets: List[str] = field(default_factory=list)
    requires_human_approval: bool = False
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "risk_level": self.risk_level.value,
            "score": round(self.score, 3),
            "sensitive_targets": self.sensitive_targets,
            "requires_human_approval": self.requires_human_approval,
            "reasons": self.reasons,
        }


class ImpactAnalyzer:
    """Calculates operational and security impact for agent actions."""

    @staticmethod
    def analyze_action(request: ActionRequest) -> ImpactAnalysis:
        reasons: List[str] = []
        sensitive: List[str] = []
        base_score = 0.1

        # Check target path sensitivity
        target_norm = (request.target or "").replace("\\", "/")
        for pat in SENSITIVE_PATH_PATTERNS:
            if re.search(pat, target_norm, re.IGNORECASE):
                sensitive.append(request.target)
                reasons.append(f"Target matches sensitive path pattern: {pat}")
                base_score += 0.4
                break

        # Check tool / action verb
        if request.action in ("delete_file", "rmdir", "drop_table"):
            base_score += 0.4
            reasons.append(f"Destructive action verb: {request.action}")
        elif request.action in ("file_edit", "write_file"):
            base_score += 0.1
        elif request.action in ("run_command", "bash", "terminal"):
            cmd = str(request.parameters.get("command", ""))
            if any(danger in cmd.lower() for danger in ("rm -rf", "drop database", "mkfs", "dd if=")):
                base_score += 0.7
                reasons.append("Catastrophic command invocation pattern detected")
            else:
                base_score += 0.25

        score = min(1.0, base_score)

        if score >= 0.8:
            risk = RiskLevel.CRITICAL
            req_approval = True
        elif score >= 0.5:
            risk = RiskLevel.HIGH
            req_approval = bool(sensitive)
        elif score >= 0.3:
            risk = RiskLevel.MEDIUM
            req_approval = False
        else:
            risk = RiskLevel.LOW
            req_approval = False

        return ImpactAnalysis(
            risk_level=risk,
            score=score,
            sensitive_targets=sensitive,
            requires_human_approval=req_approval,
            reasons=reasons,
        )
