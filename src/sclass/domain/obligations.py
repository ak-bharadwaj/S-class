"""
S-Class Domain: Technical Obligations & Requirement Compiler.
Translates high-level user requests into formal technical obligations,
claims, and mandatory evidence requirements:
USER REQUEST -> REQUIREMENTS -> OBLIGATIONS -> CLAIMS -> EVIDENCE REQUIREMENTS

Invariants:
1. Every consequential goal must compile into concrete technical obligations.
2. Unresolved or stale technical obligations block task completion.
3. Obligations are identity-bound to tasks and workspaces.
"""

from __future__ import annotations
import re
import uuid
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple, Set

from sclass.domain.claim import Claim, ClaimType, ClaimScope
from sclass.domain.claim_graph import EvidenceRequirement


class ObligationStatus(str, Enum):
    """Authoritative state of a technical obligation."""
    PENDING = "PENDING"
    SATISFIED = "SATISFIED"
    FAILED = "FAILED"
    STALE = "STALE"
    REPAIR_REQUIRED = "REPAIR_REQUIRED"

    @property
    def is_resolved(self) -> bool:
        return self == ObligationStatus.SATISFIED


@dataclass(frozen=True)
class UserRequirement:
    """Atomic requirement parsed from user input."""
    req_id: str
    description: str
    category: str = "functional"  # "functional", "test", "security", "performance", "docs"
    mandatory: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "req_id": self.req_id,
            "description": self.description,
            "category": self.category,
            "mandatory": self.mandatory,
        }


@dataclass
class TechnicalObligation:
    """Concrete technical obligation derived from requirements."""
    obligation_id: str
    task_id: str
    req_id: str
    title: str
    description: str
    target_files: Tuple[str, ...] = field(default_factory=tuple)
    target_symbols: Tuple[str, ...] = field(default_factory=tuple)
    required_claim_types: Tuple[str, ...] = field(default_factory=lambda: (ClaimType.TEST_PASS.value,))
    mandatory: bool = True
    status: ObligationStatus = ObligationStatus.PENDING
    evidence_requirement_ids: Tuple[str, ...] = field(default_factory=tuple)
    satisfied_receipt_id: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def mark_satisfied(self, receipt_id: str) -> None:
        self.status = ObligationStatus.SATISFIED
        self.satisfied_receipt_id = receipt_id
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def mark_stale(self, reason: str = "") -> None:
        self.status = ObligationStatus.STALE
        self.satisfied_receipt_id = None
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def mark_failed(self, reason: str = "") -> None:
        self.status = ObligationStatus.FAILED
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def mark_repair_required(self) -> None:
        self.status = ObligationStatus.REPAIR_REQUIRED
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "obligation_id": self.obligation_id,
            "task_id": self.task_id,
            "req_id": self.req_id,
            "title": self.title,
            "description": self.description,
            "target_files": list(self.target_files),
            "target_symbols": list(self.target_symbols),
            "required_claim_types": list(self.required_claim_types),
            "mandatory": self.mandatory,
            "status": self.status.value,
            "evidence_requirement_ids": list(self.evidence_requirement_ids),
            "satisfied_receipt_id": self.satisfied_receipt_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TechnicalObligation:
        st_val = data.get("status", ObligationStatus.PENDING.value)
        return cls(
            obligation_id=data["obligation_id"],
            task_id=data["task_id"],
            req_id=data.get("req_id", "req_default"),
            title=data.get("title", ""),
            description=data.get("description", ""),
            target_files=tuple(data.get("target_files", [])),
            target_symbols=tuple(data.get("target_symbols", [])),
            required_claim_types=tuple(data.get("required_claim_types", [ClaimType.TEST_PASS.value])),
            mandatory=bool(data.get("mandatory", True)),
            status=ObligationStatus(st_val) if st_val in ObligationStatus._value2member_map_ else ObligationStatus.PENDING,
            evidence_requirement_ids=tuple(data.get("evidence_requirement_ids", [])),
            satisfied_receipt_id=data.get("satisfied_receipt_id"),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            updated_at=data.get("updated_at", datetime.now(timezone.utc).isoformat()),
        )


class RequirementCompiler:
    """
    Compiles user requests into structured requirements, technical obligations,
    claims, and evidence requirements.
    """

    @classmethod
    def compile_request(
        cls,
        user_request: str,
        task_id: str,
        workspace_context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[UserRequirement], List[TechnicalObligation], List[EvidenceRequirement]]:
        """
        Parses user request into requirements, technical obligations, and evidence requirements.
        """
        reqs: List[UserRequirement] = []
        obligations: List[TechnicalObligation] = []
        ev_reqs: List[EvidenceRequirement] = []

        lines = [line.strip() for line in (user_request or "").splitlines() if line.strip()]
        if not lines:
            lines = [user_request.strip()] if user_request and user_request.strip() else ["Default objective"]

        for idx, line in enumerate(lines):
            # Clean leading bullet points or numbers
            clean_text = re.sub(r"^(\*|-|\d+\.)\s*", "", line).strip()
            if not clean_text:
                continue

            req_id = f"req_{idx+1}_{uuid.uuid4().hex[:6]}"
            category = "functional"
            claim_type = ClaimType.EXECUTION.value
            if any(k in clean_text.lower() for k in ("test", "pytest", "spec", "verify")):
                category = "test"
                claim_type = ClaimType.TEST_PASS.value
            elif any(k in clean_text.lower() for k in ("security", "secret", "escape", "auth")):
                category = "security"
                claim_type = ClaimType.SECURITY.value
            elif any(k in clean_text.lower() for k in ("type", "mypy", "lint")):
                category = "quality"
                claim_type = ClaimType.TYPECHECK.value

            ur = UserRequirement(req_id=req_id, description=clean_text, category=category, mandatory=True)
            reqs.append(ur)

            ev_id = f"ev_req_{idx+1}_{uuid.uuid4().hex[:6]}"
            er = EvidenceRequirement(
                requirement_id=ev_id,
                kind=claim_type.upper(),
                description=f"Evidence confirming: {clean_text}",
                mandatory=True,
                expected_verifier=None,
            )
            ev_reqs.append(er)

            ob_id = f"ob_{idx+1}_{uuid.uuid4().hex[:6]}"
            ob = TechnicalObligation(
                obligation_id=ob_id,
                task_id=task_id,
                req_id=req_id,
                title=clean_text[:80],
                description=clean_text,
                required_claim_types=(claim_type,),
                mandatory=True,
                evidence_requirement_ids=(ev_id,),
            )
            obligations.append(ob)

        return reqs, obligations, ev_reqs
