"""
S-Class EOS Automated Learning Engine (learning_engine.py)

Extracts successful bug fixes, architectural solutions, and pattern discoveries
during task execution and promotes approved knowledge candidates into the permanent Knowledge Base.
"""

import os
import sys
import json
import logging
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from knowledge_base import KnowledgeBaseManager

logger = logging.getLogger("sclass_learning")


@dataclass
class KnowledgeCandidate:
    candidate_id: str
    category: str  # coding_standards | architecture_patterns | failed_approaches | reusable_modules
    title: str
    content: str
    tags: List[str]
    confidence_score: float
    approved: bool = False


class LearningEngine:
    """Extracts knowledge candidates during execution and promotes them to the KB upon approval."""

    @staticmethod
    def get_candidates_file(workspace_dir: Optional[str] = None) -> str:
        cwd = workspace_dir if workspace_dir else os.getcwd()
        return os.path.join(cwd, ".agents", "knowledge_candidates.json")

    @staticmethod
    def capture_candidate(category: str, title: str, content: str, tags: List[str], confidence_score: float = 0.9, workspace_dir: Optional[str] = None) -> KnowledgeCandidate:
        """Captures a potential knowledge candidate from execution evaluations."""
        cand_file = LearningEngine.get_candidates_file(workspace_dir)
        os.makedirs(os.path.dirname(cand_file), exist_ok=True)

        candidates = []
        if os.path.exists(cand_file):
            try:
                with open(cand_file, "r", encoding="utf-8") as f:
                    candidates = json.load(f)
            except Exception:
                candidates = []

        cand_id = f"cand_{len(candidates) + 1}"
        candidate = KnowledgeCandidate(
            candidate_id=cand_id,
            category=category,
            title=title,
            content=content,
            tags=tags,
            confidence_score=confidence_score,
            approved=False
        )

        candidates.append(asdict(candidate))
        with open(cand_file, "w", encoding="utf-8") as f:
            json.dump(candidates, f, indent=2)

        logger.info(f"[LearningEngine] Captured Knowledge Candidate '{cand_id}': {title}")
        return candidate

    @staticmethod
    def promote_candidate(candidate_id: str, workspace_dir: Optional[str] = None) -> bool:
        """Promotes an approved knowledge candidate into the permanent Knowledge Base."""
        cand_file = LearningEngine.get_candidates_file(workspace_dir)
        if not os.path.exists(cand_file):
            return False

        with open(cand_file, "r", encoding="utf-8") as f:
            candidates = json.load(f)

        target = None
        for c in candidates:
            if c.get("candidate_id") == candidate_id:
                c["approved"] = True
                target = c
                break

        if not target:
            return False

        # Save updated candidates file
        with open(cand_file, "w", encoding="utf-8") as f:
            json.dump(candidates, f, indent=2)

        # Append entry into the target KB JSON file
        kb_dir = KnowledgeBaseManager.get_kb_dir(workspace_dir)
        KnowledgeBaseManager.initialize_kb(workspace_dir)
        kb_file = os.path.join(kb_dir, f"{target['category']}.json")
        if not os.path.exists(kb_file):
            kb_file = os.path.join(kb_dir, "coding_standards.json")

        kb_entries = []
        if os.path.exists(kb_file):
            with open(kb_file, "r", encoding="utf-8") as f:
                kb_entries = json.load(f)

        kb_entries.append({
            "category": target["category"],
            "title": target["title"],
            "content": target["content"],
            "tags": target["tags"]
        })

        with open(kb_file, "w", encoding="utf-8") as f:
            json.dump(kb_entries, f, indent=2)

        logger.info(f"[LearningEngine] Promoted Candidate '{candidate_id}' to permanent KB file '{os.path.basename(kb_file)}'!")
        return True
