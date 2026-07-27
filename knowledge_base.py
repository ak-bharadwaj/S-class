"""
S-Class EOS Pre-Planning Knowledge Base Layer (knowledge_base.py)

Queries organizational memory (coding standards, architectural decisions,
failed approaches, reusable implementations) BEFORE planning begins to prevent
re-learning past lessons on every run.
"""

import os
import json
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

logger = logging.getLogger("sclass_knowledge_base")


@dataclass
class KnowledgeEntry:
    category: str  # coding_standards | architecture_patterns | failed_approaches | reusable_modules
    title: str
    content: str
    tags: List[str] = field(default_factory=list)


class KnowledgeBaseManager:
    """Manages pre-planning organizational knowledge retrieval and storage."""

    @staticmethod
    def get_kb_dir(workspace_dir: Optional[str] = None) -> str:
        cwd = workspace_dir if workspace_dir else os.getcwd()
        return os.path.join(cwd, ".agents", "knowledge_base")

    @staticmethod
    def initialize_kb(workspace_dir: Optional[str] = None) -> None:
        """Initializes default organizational knowledge base files if missing."""
        kb_dir = KnowledgeBaseManager.get_kb_dir(workspace_dir)
        os.makedirs(kb_dir, exist_ok=True)

        defaults = {
            "coding_standards.json": [
                {
                    "category": "coding_standards",
                    "title": "Strict TypeScript & Non-Null Integrity",
                    "content": "Use explicit type annotations, avoid 'any', and handle null/undefined checks explicitly.",
                    "tags": ["typescript", "standards"]
                }
            ],
            "architecture_patterns.json": [
                {
                    "category": "architecture_patterns",
                    "title": "Decoupled Service Architecture",
                    "content": "Separate database access layer, business logic controllers, and API DTO representations.",
                    "tags": ["architecture", "api"]
                }
            ],
            "failed_approaches.json": [
                {
                    "category": "failed_approaches",
                    "title": "Avoid Unbounded In-Memory Caching",
                    "content": "Unbounded in-memory objects cause memory leaks under load. Use SQLite or Redis with TTL.",
                    "tags": ["caching", "memory"]
                }
            ]
        }

        for filename, data in defaults.items():
            filepath = os.path.join(kb_dir, filename)
            if not os.path.exists(filepath):
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)

    @staticmethod
    def query_knowledge_base(goal: str, workspace_dir: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
        """Queries the knowledge base for relevant standards, patterns, and past lessons matching the goal."""
        kb_dir = KnowledgeBaseManager.get_kb_dir(workspace_dir)
        KnowledgeBaseManager.initialize_kb(workspace_dir)

        goal_lower = goal.lower()
        results: Dict[str, List[Dict[str, Any]]] = {
            "coding_standards": [],
            "architecture_patterns": [],
            "failed_approaches": [],
            "reusable_modules": []
        }

        for fname in os.listdir(kb_dir):
            if fname.endswith(".json"):
                filepath = os.path.join(kb_dir, fname)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        entries = json.load(f)
                    for entry in entries:
                        cat = entry.get("category", "coding_standards")
                        tags = [t.lower() for t in entry.get("tags", [])]
                        content = entry.get("content", "").lower()
                        title = entry.get("title", "").lower()

                        if any(t in goal_lower for t in tags) or any(w in title or w in content for w in goal_lower.split() if len(w) > 3):
                            if cat in results:
                                results[cat].append(entry)
                except Exception as e:
                    logger.error(f"Error reading KB file '{fname}': {e}")

        return results
