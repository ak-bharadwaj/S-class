"""
S-Class EOS Selective Knowledge Base Engine (knowledge_base.py)

Applies profile-driven retrieval policies:
- BUG_FIX   -> Retrieves Failed Approaches & Reusable Fixes
- RESEARCH  -> Retrieves Architecture Patterns & Design Guidelines
- HOTFIX    -> Retrieves Recent Incidents & Known Regressions
- FULL      -> Retrieves Architecture Patterns & Coding Standards
"""

import os
import json
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

logger = logging.getLogger("sclass_knowledge_base")


# Selective Knowledge Retrieval Policies
RETRIEVAL_POLICIES: Dict[str, List[str]] = {
    "bug_fix": ["failed_approaches.json", "reusable_modules.json"],
    "research": ["architecture_patterns.json", "coding_standards.json"],
    "hotfix": ["failed_approaches.json", "coding_standards.json"],
    "refactor": ["architecture_patterns.json", "coding_standards.json"],
    "full": ["coding_standards.json", "architecture_patterns.json", "failed_approaches.json", "reusable_modules.json"]
}


@dataclass
class KnowledgeEntry:
    category: str
    title: str
    content: str
    tags: List[str] = field(default_factory=list)


class KnowledgeBaseManager:
    """Manages profile-driven selective organizational knowledge retrieval and storage."""

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
            ],
            "reusable_modules.json": [
                {
                    "category": "reusable_modules",
                    "title": "JWT Auth Middleware Snippet",
                    "content": "Use standardized JWT Bearer token validation with automated token refresh handler.",
                    "tags": ["auth", "jwt"]
                }
            ]
        }

        for filename, data in defaults.items():
            filepath = os.path.join(kb_dir, filename)
            if not os.path.exists(filepath):
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)

    @staticmethod
    def query_knowledge_base(goal: str, profile: str = "full", workspace_dir: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
        """Selectively queries the knowledge base according to profile-driven retrieval policies."""
        kb_dir = KnowledgeBaseManager.get_kb_dir(workspace_dir)
        KnowledgeBaseManager.initialize_kb(workspace_dir)

        goal_lower = goal.lower()
        target_files = RETRIEVAL_POLICIES.get(profile.lower(), RETRIEVAL_POLICIES["full"])
        results: Dict[str, List[Dict[str, Any]]] = {
            "coding_standards": [],
            "architecture_patterns": [],
            "failed_approaches": [],
            "reusable_modules": []
        }

        for fname in target_files:
            filepath = os.path.join(kb_dir, fname)
            if os.path.exists(filepath):
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

        logger.info(f"[KnowledgeBaseManager] Selectively queried KB for profile '{profile}': loaded files {target_files}")
        return results
