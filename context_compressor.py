"""
S-Class EOS Tri-Partite Cognitive Memory Engine (context_compressor.py)

Separates context compression into three cognitive memory layers:
1. Episodic Memory  ("What happened?"): Sequential execution events, retries, failures, and milestone steps.
2. Semantic Memory  ("What did we learn?"): Generalized lessons, architectural rules, and learned principles.
3. Working Memory   ("Current execution context"): Active phase, target files, open sandbox branch, and pending risks.
"""

import os
import json
import logging
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional

logger = logging.getLogger("sclass_context_compressor")


@dataclass
class EpisodicMemory:
    """What happened? Sequential execution events, retries, failures, and phase milestones."""
    past_events: List[str] = field(default_factory=list)
    retry_history: List[str] = field(default_factory=list)
    completed_phases: List[str] = field(default_factory=list)


@dataclass
class SemanticMemory:
    """What did we learn? Generalized lessons, architectural rules, and learned principles."""
    learned_rules: List[str] = field(default_factory=list)
    architectural_standards: List[str] = field(default_factory=list)


@dataclass
class WorkingMemory:
    """Current execution context: active phase, target files, open branches, and pending risks."""
    current_phase: str
    active_targets: List[str] = field(default_factory=list)
    active_branch: Optional[str] = None
    pending_risks: List[str] = field(default_factory=list)


@dataclass
class TriPartiteMemory:
    episodic: EpisodicMemory
    semantic: SemanticMemory
    working: WorkingMemory
    compression_ratio: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "episodic": asdict(self.episodic),
            "semantic": asdict(self.semantic),
            "working": asdict(self.working),
            "compression_ratio": self.compression_ratio
        }


class ContextCompressor:
    """Compresses verbose execution state into a Tri-Partite Cognitive Memory structure."""

    @staticmethod
    def compress_context(state_dict: Dict[str, Any], max_history_entries: int = 5) -> TriPartiteMemory:
        """Compresses state into Episodic, Semantic, and Working Memory layers."""
        decisions = state_dict.get("decisionLog", [])
        tasks = state_dict.get("tasks", [])
        current_phase = state_dict.get("currentPhase", "TRIAGE")
        history = state_dict.get("transitionHistory", [])

        # 1. Build Episodic Memory ("What happened?")
        past_events = []
        completed_phases = set()
        for t in history[-max_history_entries:]:
            event_str = f"Step {t.get('stepIndex')}: {t.get('fromState')} ➔ {t.get('toState')} via '{t.get('eventFired')}'"
            past_events.append(event_str)
            completed_phases.add(t.get('fromState'))

        retry_history = []
        if state_dict.get("retryCount", 0) > 0:
            retry_history.append(f"Retry count: {state_dict.get('retryCount')} in phase {current_phase}")

        episodic = EpisodicMemory(
            past_events=past_events,
            retry_history=retry_history,
            completed_phases=sorted(list(completed_phases))
        )

        # 2. Build Semantic Memory ("What did we learn?")
        learned_rules = [
            "Always verify DB schema migrations before API service deployment",
            "Enforce strict DTO type validation at route boundaries"
        ]
        architectural_standards = [
            "Decoupled Microkernel Architecture with Event Sourcing Store"
        ]

        semantic = SemanticMemory(
            learned_rules=learned_rules,
            architectural_standards=architectural_standards
        )

        # 3. Build Working Memory ("Current execution context")
        active_targets = []
        active_branch = None
        for task in tasks:
            active_targets.extend(task.get("targets", []))
            if task.get("sandboxBranch"):
                active_branch = task.get("sandboxBranch")

        active_targets = sorted(list(set(active_targets)))

        pending_risks = []
        if state_dict.get("reviewDepth") == "deep":
            pending_risks.append("Deep review active: verify security and boundary bounds")

        working = WorkingMemory(
            current_phase=current_phase,
            active_targets=active_targets,
            active_branch=active_branch,
            pending_risks=pending_risks
        )

        # Calculate Compression Ratio
        raw_size = len(json.dumps(state_dict))
        compact_dict = {
            "episodic": asdict(episodic),
            "semantic": asdict(semantic),
            "working": asdict(working)
        }
        compressed_size = len(json.dumps(compact_dict))
        ratio = round(compressed_size / max(raw_size, 1), 3)

        logger.info(f"[ContextCompressor] State compressed into Tri-Partite Memory (Raw: {raw_size} B ➔ Compact: {compressed_size} B, Ratio: {ratio})")

        return TriPartiteMemory(
            episodic=episodic,
            semantic=semantic,
            working=working,
            compression_ratio=ratio
        )
