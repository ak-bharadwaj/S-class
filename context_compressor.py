"""
S-Class EOS Context Compression & Summarization Engine (context_compressor.py)

Prevents context window overflow in long-running projects by compressing state,
decision logs, and builder outputs into a compact StructuredMemory representation.
"""

import os
import json
import logging
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional

logger = logging.getLogger("sclass_context_compressor")


@dataclass
class StructuredMemory:
    summary: str
    key_decisions: List[str] = field(default_factory=list)
    modified_targets: List[str] = field(default_factory=list)
    pending_risks: List[str] = field(default_factory=list)
    compression_ratio: float = 1.0


class ContextCompressor:
    """Compresses verbose execution state and decision logs into compact structured memory."""

    MAX_RAW_ENTRIES = 10

    @staticmethod
    def compress_context(state_dict: Dict[str, Any], max_decision_entries: int = 5) -> StructuredMemory:
        """Compresses decision log and task context into compact StructuredMemory."""
        decisions = state_dict.get("decisionLog", [])
        tasks = state_dict.get("tasks", [])
        goal = state_dict.get("planRationale", "System Execution")

        key_decisions = []
        for d in decisions[-max_decision_entries:]:
            key_decisions.append(f"{d.get('agent', 'system')}: {d.get('decision', '')} ({d.get('reason', '')})")

        modified_targets = []
        for t in tasks:
            modified_targets.extend(t.get("targets", []))

        modified_targets = sorted(list(set(modified_targets)))

        pending_risks = []
        if state_dict.get("reviewDepth") == "deep":
            pending_risks.append("Deep review active: verify security and boundary bounds")

        summary = f"Goal: '{goal}' | Completed Steps: {len(decisions)} | Active Targets: {len(modified_targets)}"

        raw_size = len(json.dumps(state_dict))
        compressed_size = len(summary) + len(json.dumps(key_decisions)) + len(json.dumps(modified_targets))
        ratio = round(compressed_size / max(raw_size, 1), 3)

        logger.info(f"[ContextCompressor] State compressed (Raw: {raw_size} B ➔ Compact: {compressed_size} B, Ratio: {ratio})")

        return StructuredMemory(
            summary=summary,
            key_decisions=key_decisions,
            modified_targets=modified_targets,
            pending_risks=pending_risks,
            compression_ratio=ratio
        )
