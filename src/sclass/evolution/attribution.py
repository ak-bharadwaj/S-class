"""
S-Class Evolution: Mechanism Attribution & Generalization Tracking.
Implements Directive Section 31:
- Records causal task attribution for every accepted edit:
    predicted affected tasks, actual improved tasks, unpredicted regressions, hit rate.
- Persists to .sclass/evolution/attribution.jsonl for learning which mechanisms generalize.
"""

from __future__ import annotations
import os
import json
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Set


@dataclass(frozen=True)
class AttributionRecord:
    edit_id: str
    component: str
    mechanism: str
    candidate_id: str
    predicted_affected_tasks: List[str]
    actual_improved_tasks: List[str]
    unpredicted_regressions: List[str]
    hit_rate: float
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AttributionTracker:
    """
    Computes mechanism-level predictive accuracy and maintains the attribution ledger.
    """

    def __init__(self, workspace_dir: str):
        self.workspace_dir = os.path.abspath(workspace_dir)
        self.ledger_dir = os.path.join(self.workspace_dir, ".sclass", "evolution")
        os.makedirs(self.ledger_dir, exist_ok=True)
        self.ledger_file = os.path.join(self.ledger_dir, "attribution.jsonl")
        self._records: List[AttributionRecord] = []

    def record_attribution(
        self,
        edit_id: str,
        component: str,
        mechanism: str,
        candidate_id: str,
        predicted_tasks: List[str],
        improved_tasks: List[str],
        regressed_tasks: List[str],
    ) -> AttributionRecord:
        pred_set = set(predicted_tasks)
        imp_set = set(improved_tasks)

        # Hit rate: percentage of predicted tasks that actually improved
        hits = len(pred_set & imp_set)
        hit_rate = hits / len(pred_set) if pred_set else (1.0 if not imp_set else 0.0)

        record = AttributionRecord(
            edit_id=edit_id,
            component=component,
            mechanism=mechanism,
            candidate_id=candidate_id,
            predicted_affected_tasks=list(predicted_tasks),
            actual_improved_tasks=list(improved_tasks),
            unpredicted_regressions=list(regressed_tasks),
            hit_rate=hit_rate,
        )

        with open(self.ledger_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record.to_dict()) + "\n")
        self._records.append(record)
        return record

    def get_records(self) -> List[AttributionRecord]:
        if not os.path.exists(self.ledger_file):
            return list(self._records)
        records: List[AttributionRecord] = []
        with open(self.ledger_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    data = json.loads(line.strip())
                    records.append(AttributionRecord(**data))
        return records
