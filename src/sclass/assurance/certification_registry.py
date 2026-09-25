"""
S-Class Assurance: Production Certification Registry & Anti-Contamination Gate.
Enforces Non-Negotiable Rule 3:
Test doubles MUST NEVER contribute to production certification evidence.
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sclass.core.errors import SecurityViolationError


@dataclass(frozen=True)
class CertificationEvidenceRecord:
    evidence_id: str
    target_gate: str
    test_path: str
    synthetic_double: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    registered_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class CertificationRegistry:
    """
    Authoritative registry governing evidence admission for production certification gates.
    Strictly forbids test-double and synthetic simulation receipts from contributing
    to production certification (e.g. G2 real runtime, G7 rollout readiness, S-Class).
    """

    def __init__(self) -> None:
        self._records: Dict[str, CertificationEvidenceRecord] = {}

    def register_evidence(
        self,
        evidence_id: str,
        target_gate: str,
        test_path: str,
        synthetic_double: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CertificationEvidenceRecord:
        """
        Registers evidence for a target certification gate.
        Enforces Rule 3: Test doubles MUST NEVER contribute to production certification evidence.
        If synthetic_double=True (or marked synthetic in metadata), raises SecurityViolationError.
        """
        meta = dict(metadata or {})
        is_synthetic = (
            synthetic_double
            or meta.get("synthetic_double") is True
            or meta.get("is_synthetic") is True
            or meta.get("test_double") is True
            or meta.get("simulation") is True
            or "synthetic" in test_path.lower()
        )

        if is_synthetic:
            raise SecurityViolationError(
                f"TEST-DOUBLE CONTAMINATION REJECTED: Evidence '{evidence_id}' from '{test_path}' "
                f"has synthetic_double=True and is strictly rejected as production certification evidence "
                f"for gate '{target_gate}'. Test doubles must never contribute to production certification evidence."
            )

        record = CertificationEvidenceRecord(
            evidence_id=evidence_id,
            target_gate=target_gate,
            test_path=test_path,
            synthetic_double=False,
            metadata=meta,
        )
        self._records[evidence_id] = record
        return record

    def admit_evidence(
        self,
        evidence: Union[Dict[str, Any], Any],
        target_gate: str = "G2",
        test_path: str = "",
    ) -> CertificationEvidenceRecord:
        """
        Adjudicates an evidence item or receipt for production certification admission.
        Fails closed if the evidence item originated from a synthetic double or simulation.
        """
        if isinstance(evidence, dict):
            ev_id = evidence.get("evidence_id") or evidence.get("receipt_id") or "ev_unknown"
            synthetic = bool(
                evidence.get("synthetic_double")
                or evidence.get("is_synthetic")
                or evidence.get("test_double")
                or evidence.get("simulation")
                or evidence.get("is_fake")
            )
            meta = dict(evidence.get("metadata") or {})
            path = test_path or str(evidence.get("source") or "")
        else:
            ev_id = getattr(evidence, "evidence_id", getattr(evidence, "receipt_id", "ev_unknown"))
            synthetic = bool(
                getattr(evidence, "synthetic_double", False)
                or getattr(evidence, "is_synthetic", False)
                or getattr(evidence, "test_double", False)
                or getattr(evidence, "is_fake", False)
            )
            meta = dict(getattr(evidence, "metadata", {}))
            path = test_path or str(getattr(evidence, "source", getattr(evidence, "verifier", "")))

        return self.register_evidence(
            evidence_id=ev_id,
            target_gate=target_gate,
            test_path=path,
            synthetic_double=synthetic,
            metadata=meta,
        )

    def is_eligible_for_production(self, evidence: Any) -> bool:
        """Returns True if evidence is strictly authentic and not synthetic double."""
        if isinstance(evidence, dict):
            if (
                evidence.get("synthetic_double") is True
                or evidence.get("is_synthetic") is True
                or evidence.get("test_double") is True
                or evidence.get("simulation") is True
                or evidence.get("is_fake") is True
            ):
                return False
        elif (
            getattr(evidence, "synthetic_double", False)
            or getattr(evidence, "is_synthetic", False)
            or getattr(evidence, "test_double", False)
            or getattr(evidence, "is_fake", False)
        ):
            return False
        return True

    def get_registered_evidence(self, target_gate: Optional[str] = None) -> List[CertificationEvidenceRecord]:
        if target_gate:
            return [r for r in self._records.values() if r.target_gate == target_gate]
        return list(self._records.values())
