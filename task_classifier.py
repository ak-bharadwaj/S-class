"""
S-Class EOS V12 - Task Domain & Scope Classifier

Classifies raw user requests into distinct Task Domains (Algorithm, Library, CLI, API, Frontend, Fullstack),
determining whether frontend UI, web page spreads, database scaffolding, or Chrome visual verification are required.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set
import re
import os
import json


class TaskDomain(str, Enum):
    ALGORITHM = "algorithm"            # pure algorithm, data structure, math, in-memory logic
    BACKEND_LOGIC = "backend_logic"    # backend services, controllers, workers, business logic
    LIBRARY = "library"                # reusable library, SDK, utility package
    CLI = "cli"                        # CLI tools, command-line utilities, scripts
    API = "api"                        # headless REST/GraphQL/gRPC APIs
    FRONTEND = "frontend"              # UI components, styles, animations, client state
    FULLSTACK = "fullstack"            # end-to-end full-stack applications with UI + Backend


@dataclass
class TaskClassification:
    domain: TaskDomain
    requires_frontend_ui: bool
    requires_database: bool
    requires_visual_qa: bool
    primary_verification: str          # "unit_tests" | "browser_visual" | "cli_stdout" | "api_smoke"
    rationale: str
    detected_keywords: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "domain": self.domain.value,
            "requires_frontend_ui": self.requires_frontend_ui,
            "requires_database": self.requires_database,
            "requires_visual_qa": self.requires_visual_qa,
            "primary_verification": self.primary_verification,
            "rationale": self.rationale,
            "detected_keywords": self.detected_keywords
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TaskClassification':
        return cls(
            domain=TaskDomain(data.get("domain", TaskDomain.FULLSTACK.value)),
            requires_frontend_ui=data.get("requires_frontend_ui", True),
            requires_database=data.get("requires_database", True),
            requires_visual_qa=data.get("requires_visual_qa", True),
            primary_verification=data.get("primary_verification", "browser_visual"),
            rationale=data.get("rationale", ""),
            detected_keywords=data.get("detected_keywords", [])
        )


class TaskClassifier:
    """
    Analyzes prompt text, explicit configuration, and workspace hints to classify
    the task domain and determine evidence requirements.
    """

    ALGORITHM_KEYWORDS: Set[str] = {
        "algorithm", "algorithms", "rate limiter", "rate-limiter", "sliding window",
        "sliding-window", "token bucket", "leaky bucket", "fixed window", "cache",
        "lru cache", "lfu cache", "fifo", "binary search", "binary tree", "trie",
        "graph traversal", "dijkstra", "astar", "a*", "sort", "sorting", "quicksort",
        "mergesort", "hash map", "hash table", "hashmap", "data structure",
        "data structures", "in-memory", "in memory", "thread pool", "concurrency",
        "mutex", "semaphore", "ring buffer", "priority queue", "heap", "min-heap",
        "max-heap", "bloom filter", "hashing", "encryption", "decryption", "cipher",
        "regex", "parser", "lexer", "tokenizer", "ast parser", "math", "matrix",
        "vector calculation", "backtracking", "dynamic programming", "memoization"
    }

    CLI_KEYWORDS: Set[str] = {
        "cli", "command line", "command-line", "terminal command", "terminal tool",
        "console tool", "argparse", "click", "typer", "flag", "stdout", "stderr",
        "shell script", "bash script", "powershell script"
    }

    LIBRARY_KEYWORDS: Set[str] = {
        "sdk", "library", "helper function", "utility function", "utils", "utility module",
        "utility", "utilities", "logger", "logging", "helper", "helpers",
        "npm package", "pip package", "crate", "middleware", "decorator", "wrapper"
    }

    API_KEYWORDS: Set[str] = {
        "rest api", "graphql", "grpc", "endpoint", "webhook", "controller",
        "microservice", "backend service", "route handler", "api server"
    }

    FRONTEND_KEYWORDS: Set[str] = {
        "ui", "component", "screen", "page", "pages", "view", "views", "dashboard",
        "frontend", "front-end", "modal", "button", "form", "navbar", "sidebar",
        "layout", "tailwind", "css", "html", "react", "vue", "svelte", "nextjs",
        "responsive", "animation", "framer-motion", "chart", "table", "portal"
    }

    DATABASE_KEYWORDS: Set[str] = {
        "database", "db", "sql", "sqlite", "postgres", "postgresql", "mysql",
        "prisma", "schema", "migration", "table", "model", "entity", "orm",
        "mongodb", "redis", "query", "crud"
    }

    @classmethod
    def classify(cls, raw_request: str, workspace_dir: Optional[str] = None) -> TaskClassification:
        req_lower = raw_request.lower()

        # 1. Check for explicit overrides in sclass.config.json
        if workspace_dir:
            cfg_path = os.path.join(workspace_dir, "sclass.config.json")
            if os.path.exists(cfg_path):
                try:
                    with open(cfg_path, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                    if "taskDomain" in cfg:
                        dom_str = str(cfg["taskDomain"]).lower()
                        for dom in TaskDomain:
                            if dom.value == dom_str:
                                is_ui = dom in [TaskDomain.FRONTEND, TaskDomain.FULLSTACK]
                                return TaskClassification(
                                    domain=dom,
                                    requires_frontend_ui=cfg.get("requiresFrontendUi", is_ui),
                                    requires_database=cfg.get("requiresDatabase", dom in [TaskDomain.FULLSTACK, TaskDomain.API]),
                                    requires_visual_qa=cfg.get("requiresVisualQA", is_ui and not cfg.get("skipVisualQA", False)),
                                    primary_verification="browser_visual" if is_ui else "unit_tests",
                                    rationale=f"Explicitly configured taskDomain '{dom_str}' in sclass.config.json",
                                    detected_keywords=[]
                                )
                    if cfg.get("skipVisualQA") is True or cfg.get("requiresFrontendUi") is False:
                        return TaskClassification(
                            domain=TaskDomain.BACKEND_LOGIC,
                            requires_frontend_ui=False,
                            requires_database=True,
                            requires_visual_qa=False,
                            primary_verification="unit_tests",
                            rationale="Configured requiresFrontendUi=False or skipVisualQA=True in sclass.config.json",
                            detected_keywords=[]
                        )
                except Exception:
                    pass

        # 2. Check for explicit prompt tags e.g. [domain: algorithm] or [skip-visual]
        if "[domain: algorithm]" in req_lower or "[algorithm]" in req_lower:
            return TaskClassification(
                domain=TaskDomain.ALGORITHM,
                requires_frontend_ui=False,
                requires_database=False,
                requires_visual_qa=False,
                primary_verification="unit_tests",
                rationale="Explicit algorithm tag specified in prompt",
                detected_keywords=["[algorithm]"]
            )
        if "[skip-visual]" in req_lower or "[headless]" in req_lower or "[backend-only]" in req_lower:
            return TaskClassification(
                domain=TaskDomain.BACKEND_LOGIC,
                requires_frontend_ui=False,
                requires_database=True,
                requires_visual_qa=False,
                primary_verification="unit_tests",
                rationale="Explicit headless / skip-visual tag in prompt",
                detected_keywords=["[headless]"]
            )

        # 3. Match Keyword Signals
        algo_matches = [kw for kw in cls.ALGORITHM_KEYWORDS if re.search(r'\b' + re.escape(kw) + r'\b', req_lower)]
        cli_matches = [kw for kw in cls.CLI_KEYWORDS if re.search(r'\b' + re.escape(kw) + r'\b', req_lower)]
        # Check if "library" is referring to a physical book library rather than a software code library
        is_book_library = bool(re.search(r'\b(book|books|borrow|borrowing|librarian|library management|circulation)\b', req_lower))
        lib_matches = [
            kw for kw in cls.LIBRARY_KEYWORDS 
            if re.search(r'\b' + re.escape(kw) + r'\b', req_lower)
            and not (kw == "library" and is_book_library)
        ]
        api_matches = [kw for kw in cls.API_KEYWORDS if re.search(r'\b' + re.escape(kw) + r'\b', req_lower)]
        frontend_matches = [kw for kw in cls.FRONTEND_KEYWORDS if re.search(r'\b' + re.escape(kw) + r'\b', req_lower)]
        db_matches = [kw for kw in cls.DATABASE_KEYWORDS if re.search(r'\b' + re.escape(kw) + r'\b', req_lower)]

        has_frontend = len(frontend_matches) > 0 or is_book_library
        has_db = len(db_matches) > 0 or is_book_library

        has_heavy_algo = any(k in algo_matches for k in [
            "algorithm", "algorithms", "rate limiter", "rate-limiter", "sliding window",
            "sliding-window", "token bucket", "leaky bucket", "cache", "lru cache",
            "binary search", "binary tree", "trie", "graph traversal", "dijkstra",
            "astar", "sorting", "hash map", "hash table", "thread pool", "concurrency",
            "mutex", "semaphore", "bloom filter", "backtracking", "dynamic programming"
        ])

        # Explicit library / SDK requests take precedence over generic terms like 'math' or 'parser'
        if lib_matches and not has_frontend and not has_heavy_algo:
            return TaskClassification(
                domain=TaskDomain.LIBRARY,
                requires_frontend_ui=False,
                requires_database=has_db,
                requires_visual_qa=False,
                primary_verification="unit_tests",
                rationale=f"Detected library keywords ({', '.join(lib_matches[:3])})",
                detected_keywords=lib_matches
            )

        # Algorithmic tasks take highest precedence when no explicit UI is requested
        if algo_matches and not has_frontend:
            return TaskClassification(
                domain=TaskDomain.ALGORITHM,
                requires_frontend_ui=False,
                requires_database=has_db,
                requires_visual_qa=False,
                primary_verification="unit_tests",
                rationale=f"Detected algorithmic keywords ({', '.join(algo_matches[:3])}) without frontend UI requests",
                detected_keywords=algo_matches
            )

        # CLI tasks
        if cli_matches and not has_frontend:
            return TaskClassification(
                domain=TaskDomain.CLI,
                requires_frontend_ui=False,
                requires_database=has_db,
                requires_visual_qa=False,
                primary_verification="cli_stdout",
                rationale=f"Detected CLI keywords ({', '.join(cli_matches[:3])})",
                detected_keywords=cli_matches
            )

        # Library / SDK tasks fallback
        if lib_matches and not has_frontend:
            return TaskClassification(
                domain=TaskDomain.LIBRARY,
                requires_frontend_ui=False,
                requires_database=has_db,
                requires_visual_qa=False,
                primary_verification="unit_tests",
                rationale=f"Detected library keywords ({', '.join(lib_matches[:3])})",
                detected_keywords=lib_matches
            )

        # Headless API tasks
        if api_matches and not has_frontend:
            return TaskClassification(
                domain=TaskDomain.API,
                requires_frontend_ui=False,
                requires_database=has_db or True,
                requires_visual_qa=False,
                primary_verification="api_smoke",
                rationale=f"Detected headless API keywords ({', '.join(api_matches[:3])})",
                detected_keywords=api_matches
            )

        # Frontend-only tasks
        if has_frontend and not has_db and not api_matches:
            return TaskClassification(
                domain=TaskDomain.FRONTEND,
                requires_frontend_ui=True,
                requires_database=False,
                requires_visual_qa=True,
                primary_verification="browser_visual",
                rationale=f"Detected frontend keywords ({', '.join(frontend_matches[:3])}) without database needs",
                detected_keywords=frontend_matches
            )

        # Fullstack tasks (default for multi-tier web requests)
        detected = frontend_matches + db_matches + api_matches
        return TaskClassification(
            domain=TaskDomain.FULLSTACK,
            requires_frontend_ui=True,
            requires_database=True,
            requires_visual_qa=True,
            primary_verification="browser_visual",
            rationale="Defaulting to fullstack multi-tier application",
            detected_keywords=detected[:5]
        )
