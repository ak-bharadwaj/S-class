"""
S-Class Evolution: Immutable Evolution History as Evidence.
Implements Directive Section 22:
- Appends every candidate edit to an immutable causal history:
    round, candidate_id, edit_id, component, hypothesis, diff_hash,
    delta_S, delta_C, accepted, outcome, bundle_size,
    predicted_affected, actual_affected.
- Preserves full lineage for causal attribution and prevents search cycling.
"""

from __future__ import annotations
import os
import json
import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional


@dataclass(frozen=True)
class HistoryEntry:
    round: int
    candidate_id: str
    edit_id: str
    component: str
    hypothesis: str
    diff_hash: str
    delta_S: float
    delta_C: float
    accepted: bool
    outcome: str
    bundle_size: int
    predicted_affected: List[str]
    actual_affected: List[str]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> HistoryEntry:
        return cls(**data)


class EvolutionHistory:
    """
    Immutable ledger of all proposed, evaluated, and accepted candidate edits.
    """

    def __init__(self, workspace_dir: str):
        self.workspace_dir = os.path.abspath(workspace_dir)
        self.history_dir = os.path.join(self.workspace_dir, ".sclass", "evolution")
        os.makedirs(self.history_dir, exist_ok=True)
        self.history_file = os.path.join(self.history_dir, "history.jsonl")
        self._entries: List[HistoryEntry] = []

    def record_edit(
        self,
        round_num: int,
        candidate_id: str,
        edit_id: str,
        component: str,
        hypothesis: str,
        diff: str,
        delta_S: float,
        delta_C: float,
        accepted: bool,
        outcome: str,
        bundle_size: int,
        predicted_affected: List[str],
        actual_affected: List[str],
    ) -> HistoryEntry:
        diff_h = hashlib.sha256(diff.encode("utf-8")).hexdigest()
        entry = HistoryEntry(
            round=round_num,
            candidate_id=candidate_id,
            edit_id=edit_id,
            component=component,
            hypothesis=hypothesis,
            diff_hash=diff_h,
            delta_S=delta_S,
            delta_C=delta_C,
            accepted=accepted,
            outcome=outcome,
            bundle_size=bundle_size,
            predicted_affected=list(predicted_affected),
            actual_affected=list(actual_affected),
        )
        with open(self.history_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry.to_dict()) + "\n")
        self._entries.append(entry)
        return entry

    def get_entries(self, round_num: Optional[int] = None) -> List[HistoryEntry]:
        if not os.path.exists(self.history_file):
            return [e for e in self._entries if round_num is None or e.round == round_num]

        entries: List[HistoryEntry] = []
        with open(self.history_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    entries.append(HistoryEntry.from_dict(json.loads(line.strip())))
        if round_num is not None:
            return [e for e in entries if e.round == round_num]
        return entries
