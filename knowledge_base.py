"""
S-Class EOS Fast Knowledge Base Engine (knowledge_base.py)

Applies profile-driven selective retrieval policies with:
- In-memory result caching (_KB_CACHE) for zero-latency repeated lookups
- Inverted keyword indexing (_KB_INDEX) for O(1) keyword matching
- Profile-driven target file filtering across all index and cache paths
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

# In-Memory Cache and Inverted Index
_KB_CACHE: Dict[str, List[Dict[str, Any]]] = {}
_KB_INDEX: Dict[str, List[Dict[str, Any]]] = {}


@dataclass
class KnowledgeEntry:
    category: str
    title: str
    content: str
    tags: List[str] = field(default_factory=list)


class KnowledgeBaseManager:
    """Manages profile-driven selective knowledge retrieval with in-memory caching and inverted indexing."""

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
    def _build_inverted_index(workspace_dir: Optional[str] = None, force_refresh: bool = False) -> None:
        """Builds an inverted keyword index for O(1) keyword lookups."""
        if _KB_INDEX and not force_refresh:
            return

        if force_refresh:
            _KB_INDEX.clear()
            _KB_CACHE.clear()

        kb_dir = KnowledgeBaseManager.get_kb_dir(workspace_dir)
        KnowledgeBaseManager.initialize_kb(workspace_dir)

        if not os.path.exists(kb_dir):
            return

        for fname in os.listdir(kb_dir):
            if fname.endswith(".json"):
                filepath = os.path.join(kb_dir, fname)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        entries = json.load(f)
                    
                    annotated_entries = []
                    for entry in entries:
                        tagged_entry = dict(entry)
                        tagged_entry["_source_file"] = fname
                        annotated_entries.append(tagged_entry)

                        words = entry.get("title", "").lower().split() + entry.get("tags", [])
                        for w in words:
                            w_clean = w.lower().strip()
                            if w_clean not in _KB_INDEX:
                                _KB_INDEX[w_clean] = []
                            _KB_INDEX[w_clean].append(tagged_entry)

                    _KB_CACHE[fname] = annotated_entries
                except Exception as e:
                    logger.error(f"Error indexing KB file '{fname}': {e}")

    @staticmethod
    def refresh_index(workspace_dir: Optional[str] = None) -> None:
        """Forces immediate index rebuild on disk mutation."""
        KnowledgeBaseManager._build_inverted_index(workspace_dir, force_refresh=True)

    @staticmethod
    def query_knowledge_base(goal: str, profile: str = "full", workspace_dir: Optional[str] = None, force_refresh: bool = False) -> Dict[str, List[Dict[str, Any]]]:
        """Queries the knowledge base enforcing profile-driven selective file filtering."""
        KnowledgeBaseManager._build_inverted_index(workspace_dir, force_refresh=force_refresh)

        goal_lower = goal.lower()
        target_files = RETRIEVAL_POLICIES.get(profile.lower(), RETRIEVAL_POLICIES["full"])
        results: Dict[str, List[Dict[str, Any]]] = {
            "coding_standards": [],
            "architecture_patterns": [],
            "failed_approaches": [],
            "reusable_modules": []
        }

        # O(1) Inverted Index Lookup with mandatory profile target file filtering
        query_words = [w.strip() for w in goal_lower.split() if len(w.strip()) > 2]
        matched_entries = set()

        for word in query_words:
            if word in _KB_INDEX:
                for entry in _KB_INDEX[word]:
                    # Profile-driven selective retrieval gate
                    if entry.get("_source_file") in target_files:
                        matched_entries.add(json.dumps(entry))

        # Fallback to cached target file scanning if keyword match yielded nothing
        if not matched_entries:
            for fname in target_files:
                for entry in _KB_CACHE.get(fname, []):
                    matched_entries.add(json.dumps(entry))

        for entry_json in matched_entries:
            entry = json.loads(entry_json)
            cat = entry.get("category", "coding_standards")
            if cat in results:
                # Remove internal _source_file meta tag before returning
                clean_entry = {k: v for k, v in entry.items() if k != "_source_file"}
                results[cat].append(clean_entry)

        logger.info(f"[KnowledgeBaseManager] Profile-driven query completed for profile '{profile}': returned {sum(len(v) for v in results.values())} entries from target files {target_files}")
        return results
