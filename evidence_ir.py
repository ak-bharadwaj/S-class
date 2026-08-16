"""
evidence_ir.py - S-Class EOS V11.2 Common Evidence Intermediate Representation (IR)

Defines the unified ontology, epistemic status taxonomy, and canonical evidence receipt
contract across all external OSS verification engines (Pyright, Ruff, Hypothesis, Schemathesis, LibCST, etc.).
"""

import enum
import hashlib
import json
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone


class EpistemicStatus(str, enum.Enum):
    TOOL_NOT_AVAILABLE = "TOOL_NOT_AVAILABLE"
    TOOL_EXECUTION_FAILED = "TOOL_EXECUTION_FAILED"
    TOOL_OUTPUT_INVALID = "TOOL_OUTPUT_INVALID"
    TARGET_VERIFICATION_FAILED = "TARGET_VERIFICATION_FAILED"
    TARGET_TYPE_ERRORS = "TARGET_TYPE_ERRORS"
    TARGET_STATIC_VIOLATIONS = "TARGET_STATIC_VIOLATIONS"
    TARGET_COUNTEREXAMPLE_FOUND = "TARGET_COUNTEREXAMPLE_FOUND"
    TARGET_CONTRACT_VIOLATED = "TARGET_CONTRACT_VIOLATED"
    TARGET_CLEAN = "TARGET_CLEAN"


@dataclass
class UnifiedEvidenceReceipt:
    """Canonical Intermediate Representation (IR) for all S-Class evidence receipts."""
    obligation_id: str
    provider_type: str  # "type_verifier", "static_analyzer", "property_verifier", "api_contract_verifier"
    engine_name: str    # "Pyright", "Ruff", "Hypothesis", "Schemathesis"
    engine_version: Optional[str]  # Real semantic version or None; NEVER fabricated
    status: EpistemicStatus
    passed: bool
    target_name: str
    target_identifier: str
    target_source_hash: str
    execution_metadata: Dict[str, Any] = field(default_factory=dict)
    diagnostics: List[Dict[str, Any]] = field(default_factory=list)
    reproducible_cases: List[Dict[str, Any]] = field(default_factory=list)
    provenance_hash: str = ""
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()
        if isinstance(self.status, str):
            try:
                self.status = EpistemicStatus(self.status)
            except ValueError:
                self.status = EpistemicStatus.TOOL_OUTPUT_INVALID
        # Authority Invariant: passed is strictly True iff status is TARGET_CLEAN
        if self.status != EpistemicStatus.TARGET_CLEAN:
            self.passed = False
        if not self.provenance_hash:
            self.provenance_hash = self.compute_provenance_hash()

    def compute_provenance_hash(self) -> str:
        payload = {
            "obligation_id": self.obligation_id,
            "provider_type": self.provider_type,
            "engine_name": self.engine_name,
            "engine_version": self.engine_version,
            "status": self.status.value if isinstance(self.status, EpistemicStatus) else str(self.status),
            "passed": self.passed,
            "target_name": self.target_name,
            "target_identifier": self.target_identifier,
            "target_source_hash": self.target_source_hash,
            "execution_metadata": self.execution_metadata,
            "diagnostics": self.diagnostics,
            "reproducible_cases": self.reproducible_cases,
        }
        canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value if isinstance(self.status, EpistemicStatus) else str(self.status)
        return data


def compute_source_hash(target_callable_or_path: Any) -> str:
    """Computes a deterministic SHA-256 hash of the target source implementation or file."""
    import inspect
    import os
    if isinstance(target_callable_or_path, str):
        if os.path.isfile(target_callable_or_path):
            with open(target_callable_or_path, "rb") as f:
                return hashlib.sha256(f.read()).hexdigest()
        else:
            return hashlib.sha256(target_callable_or_path.encode("utf-8")).hexdigest()
    elif callable(target_callable_or_path):
        try:
            source = inspect.getsource(target_callable_or_path)
            qualname = getattr(target_callable_or_path, "__qualname__", str(target_callable_or_path))
            return hashlib.sha256(f"{qualname}:{source}".encode("utf-8")).hexdigest()
        except Exception:
            qualname = getattr(target_callable_or_path, "__qualname__", str(target_callable_or_path))
            return hashlib.sha256(qualname.encode("utf-8")).hexdigest()
    return hashlib.sha256(str(target_callable_or_path).encode("utf-8")).hexdigest()
