"""
S-Class Domain: Universal Project Truth & Invalidation (RC.5).
Formally models:
- TruthState lifecycle: PROPOSED, ASSUMED, OBSERVED, VERIFIED, INVALIDATED (Law L6)
- Dependency-graph mutation invalidation: files & AST symbols (Law L7)
- Unscoped claim fail-closed invalidation (Law L7)
- Memory subordination (Law L10)
"""
from __future__ import annotations
import uuid
import json
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple, Set

from sclass.domain.evidence import ObservedReceipt


class TruthState(str, Enum):
    PROPOSED = "PROPOSED"
    ASSUMED = "ASSUMED"
    OBSERVED = "OBSERVED"
    VERIFIED = "VERIFIED"
    INVALIDATED = "INVALIDATED"


@dataclass
class TruthDependency:
    files: Tuple[str, ...] = field(default_factory=tuple)
    symbols: Tuple[str, ...] = field(default_factory=tuple)
    file_hashes: Dict[str, str] = field(default_factory=dict)
    workspace_fingerprint: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "files": list(self.files),
            "symbols": list(self.symbols),
            "file_hashes": dict(self.file_hashes),
            "workspace_fingerprint": self.workspace_fingerprint,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TruthDependency:
        return cls(
            files=tuple(data.get("files", [])),
            symbols=tuple(data.get("symbols", [])),
            file_hashes=dict(data.get("file_hashes", {})),
            workspace_fingerprint=data.get("workspace_fingerprint"),
        )


@dataclass
class TruthRecord:
    truth_id: str
    claim_id: str
    statement: str
    state: TruthState
    receipt: Optional[ObservedReceipt] = None
    dependencies: TruthDependency = field(default_factory=TruthDependency)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    invalidation_reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "truth_id": self.truth_id,
            "claim_id": self.claim_id,
            "statement": self.statement,
            "state": self.state.value if isinstance(self.state, TruthState) else str(self.state),
            "receipt": self.receipt.to_dict() if self.receipt else None,
            "dependencies": self.dependencies.to_dict(),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "invalidation_reason": self.invalidation_reason,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TruthRecord:
        rcpt_data = data.get("receipt")
        receipt = ObservedReceipt.from_dict(rcpt_data) if rcpt_data else None
        dep_data = data.get("dependencies", {})
        dependencies = TruthDependency.from_dict(dep_data) if dep_data else TruthDependency()
        state_val = data.get("state", TruthState.PROPOSED.value)
        return cls(
            truth_id=data["truth_id"],
            claim_id=data["claim_id"],
            statement=data.get("statement", ""),
            state=TruthState(state_val) if state_val in TruthState._value2member_map_ else TruthState.PROPOSED,
            receipt=receipt,
            dependencies=dependencies,
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            invalidation_reason=data.get("invalidation_reason"),
            metadata=dict(data.get("metadata", {})),
        )


class ProjectTruth:
    """Authoritative project truth manager maintaining verified claims, state, and dependencies."""

    def __init__(self, workspace_dir: str):
        self.workspace_dir = workspace_dir
        self.records: Dict[str, TruthRecord] = {}

    def propose(self, claim_id: str, statement: str) -> TruthRecord:
        rec = TruthRecord(
            truth_id=f"tr_{uuid.uuid4().hex[:10]}",
            claim_id=claim_id,
            statement=statement,
            state=TruthState.PROPOSED,
        )
        self.records[claim_id] = rec
        return rec

    def assume(self, assumption_id: str, statement: str) -> TruthRecord:
        rec = TruthRecord(
            truth_id=f"tr_{uuid.uuid4().hex[:10]}",
            claim_id=assumption_id,
            statement=statement,
            state=TruthState.ASSUMED,
        )
        self.records[assumption_id] = rec
        return rec

    def record_observation(self, claim_id: str, receipt: Any) -> TruthRecord:
        rec = self.records.get(claim_id)
        if rec is None:
            rec = TruthRecord(
                truth_id=f"tr_{uuid.uuid4().hex[:10]}",
                claim_id=claim_id,
                statement=getattr(receipt, "statement", f"Observed {claim_id}"),
                state=TruthState.OBSERVED,
                receipt=receipt,
            )
        else:
            rec.state = TruthState.OBSERVED
            rec.receipt = receipt
            rec.updated_at = datetime.now(timezone.utc).isoformat()
        self.records[claim_id] = rec
        return rec

    def verify(
        self,
        claim_id: str,
        receipt: Any,
        files: Optional[List[str]] = None,
        symbols: Optional[List[str]] = None,
    ) -> TruthRecord:
        deps = TruthDependency(
            files=tuple(files or []),
            symbols=tuple(symbols or []),
            workspace_fingerprint=getattr(receipt, "workspace_fingerprint", None),
        )
        rec = self.records.get(claim_id)
        if rec is None:
            rec = TruthRecord(
                truth_id=f"tr_{uuid.uuid4().hex[:10]}",
                claim_id=claim_id,
                statement=getattr(receipt, "statement", f"Verified {claim_id}"),
                state=TruthState.VERIFIED,
                receipt=receipt,
                dependencies=deps,
            )
        else:
            rec.state = TruthState.VERIFIED
            rec.receipt = receipt
            rec.dependencies = deps
            rec.updated_at = datetime.now(timezone.utc).isoformat()
        self.records[claim_id] = rec
        return rec

    def invalidate(self, truth_id: str, reason: str) -> TruthRecord:
        target_rec: Optional[TruthRecord] = None
        for rec in self.records.values():
            if rec.truth_id == truth_id or rec.claim_id == truth_id:
                target_rec = rec
                break
        if target_rec is None:
            target_rec = TruthRecord(
                truth_id=truth_id,
                claim_id=truth_id,
                statement="Unknown",
                state=TruthState.INVALIDATED,
                invalidation_reason=reason,
            )
            self.records[truth_id] = target_rec
        else:
            target_rec.state = TruthState.INVALIDATED
            target_rec.invalidation_reason = reason
            target_rec.updated_at = datetime.now(timezone.utc).isoformat()
        return target_rec

    def is_verified(self, claim_id: str) -> bool:
        rec = self.records.get(claim_id)
        if rec is None:
            return False
        return rec.state == TruthState.VERIFIED

    def invalidate_mutations(
        self,
        mutated_files: Optional[Set[str]] = None,
        mutated_symbols: Optional[Set[str]] = None,
    ) -> List[str]:
        mut_files = set(mutated_files or [])
        mut_syms = set(mutated_symbols or [])
        invalidated_ids: List[str] = []

        for cid, rec in list(self.records.items()):
            if rec.state != TruthState.VERIFIED:
                continue

            dep_files = set(rec.dependencies.files)
            dep_symbols = set(rec.dependencies.symbols)

            should_invalidate = False

            # Unscoped claim: no file or symbol dependencies (workspace-wide claim).
            # Law L7: Fails closed on any workspace mutation!
            if not dep_files and not dep_symbols:
                if mut_files:
                    should_invalidate = True
            else:
                # Scoped claim: check file overlap
                matched_files = dep_files.intersection(mut_files)
                if matched_files:
                    if dep_symbols and mut_syms:
                        # Fine-grained symbol invalidation: only invalidate if touched symbol overlaps
                        if dep_symbols.intersection(mut_syms):
                            should_invalidate = True
                    else:
                        should_invalidate = True

            if should_invalidate:
                rec.state = TruthState.INVALIDATED
                rec.invalidation_reason = f"Workspace mutation in dependencies: files={mut_files}, symbols={mut_syms}"
                rec.updated_at = datetime.now(timezone.utc).isoformat()
                invalidated_ids.append(cid)

        return invalidated_ids

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workspace_dir": self.workspace_dir,
            "records": {cid: rec.to_dict() for cid, rec in self.records.items()},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], workspace_dir: str = "") -> ProjectTruth:
        ws = workspace_dir or data.get("workspace_dir", "")
        pt = cls(workspace_dir=ws)
        rec_dict = data.get("records", {})
        for cid, r_data in rec_dict.items():
            pt.records[cid] = TruthRecord.from_dict(r_data)
        return pt
