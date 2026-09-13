"""
S-Class EOS V12 - Task Domain & Scope Classifier

Classifies raw user requests into distinct Task Domains (Algorithm, Library, CLI, API, Frontend, Fullstack),
determining whether frontend UI, web page spreads, database scaffolding, or Chrome visual verification are required.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set, Tuple
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


class TaskCategory:
    API_ENDPOINT = "api_endpoint"
    AUTHORIZATION_GUARD = "authorization_guard"
    STATE_TRANSITION = "state_transition"
    AUDIT_LOG = "audit_log"
    UI_COMPONENT = "ui_component"
    INTEGRATION_TEST = "integration_test"
    DATABASE_MIGRATION = "database_migration"
    SECURITY_REMEDIATION = "security_remediation"
    BUG_FIX = "bug_fix"
    GENERAL_ENGINEERING = "general_engineering"


class ScopeTier:
    TRIVIAL = "TRIVIAL"
    MINOR = "MINOR"
    MEDIUM = "MEDIUM"
    MAJOR = "MAJOR"


class TaskClassification(dict):
    """
    Hybrid dict/object representation of a task classification,
    supporting both attribute access (obj.domain) and dictionary access (obj['category']),
    satisfying both domain-driven orchestration and property-based contract fuzzing.
    """
    def __init__(
        self,
        domain: TaskDomain = TaskDomain.FULLSTACK,
        requires_frontend_ui: bool = True,
        requires_database: bool = True,
        requires_visual_qa: bool = True,
        primary_verification: str = "browser_visual",
        rationale: str = "",
        detected_keywords: Optional[List[str]] = None,
        category: str = TaskCategory.GENERAL_ENGINEERING,
        scope_tier: str = ScopeTier.MEDIUM,
        confidence: float = 0.5,
        matched_rules: Optional[List[str]] = None,
        deterministic: bool = True,
        design_principle: str = "deterministic_over_adaptive",
        **kwargs
    ):
        kw_list = list(detected_keywords) if detected_keywords is not None else []
        rule_list = list(matched_rules) if matched_rules is not None else []

        payload = {
            "domain": domain.value if isinstance(domain, TaskDomain) else str(domain),
            "requires_frontend_ui": requires_frontend_ui,
            "requires_database": requires_database,
            "requires_visual_qa": requires_visual_qa,
            "primary_verification": primary_verification,
            "rationale": rationale,
            "detected_keywords": kw_list,
            "category": category,
            "scope_tier": scope_tier,
            "confidence": confidence,
            "matched_rules": rule_list,
            "deterministic": deterministic,
            "design_principle": design_principle,
        }
        payload.update(kwargs)
        super().__init__(payload)

        self.domain = domain
        self.requires_frontend_ui = requires_frontend_ui
        self.requires_database = requires_database
        self.requires_visual_qa = requires_visual_qa
        self.primary_verification = primary_verification
        self.rationale = rationale
        self.detected_keywords = kw_list
        self.category = category
        self.scope_tier = scope_tier
        self.confidence = confidence
        self.matched_rules = rule_list
        self.deterministic = deterministic
        self.design_principle = design_principle

    def to_dict(self) -> Dict[str, Any]:
        return dict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TaskClassification':
        domain_val = data.get("domain", TaskDomain.FULLSTACK.value)
        try:
            dom = TaskDomain(domain_val)
        except Exception:
            dom = TaskDomain.FULLSTACK
        return cls(
            domain=dom,
            requires_frontend_ui=data.get("requires_frontend_ui", True),
            requires_database=data.get("requires_database", True),
            requires_visual_qa=data.get("requires_visual_qa", True),
            primary_verification=data.get("primary_verification", "browser_visual"),
            rationale=data.get("rationale", ""),
            detected_keywords=data.get("detected_keywords", []),
            category=data.get("category", TaskCategory.GENERAL_ENGINEERING),
            scope_tier=data.get("scope_tier", ScopeTier.MEDIUM),
            confidence=float(data.get("confidence", 0.5)),
            matched_rules=data.get("matched_rules", []),
            deterministic=bool(data.get("deterministic", True)),
            design_principle=data.get("design_principle", "deterministic_over_adaptive")
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
        "red-black tree", "red black tree", "avl tree", "b-tree", "tree", "bst",
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
        classification = cls._classify_domain(raw_request, workspace_dir)
        task_info = cls.classify_task(raw_request)

        classification.category = task_info["category"]
        classification.scope_tier = task_info["scope_tier"]
        classification.confidence = task_info["confidence"]
        classification.matched_rules = task_info["matched_rules"]
        classification.deterministic = task_info["deterministic"]
        classification.design_principle = task_info["design_principle"]

        classification["category"] = task_info["category"]
        classification["scope_tier"] = task_info["scope_tier"]
        classification["confidence"] = task_info["confidence"]
        classification["matched_rules"] = task_info["matched_rules"]
        classification["deterministic"] = task_info["deterministic"]
        classification["design_principle"] = task_info["design_principle"]

        return classification

    @classmethod
    def _classify_domain(cls, raw_request: str, workspace_dir: Optional[str] = None) -> TaskClassification:
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
            "binary search", "binary tree", "trie", "red-black tree", "red black tree",
            "avl tree", "b-tree", "tree", "bst", "graph traversal", "dijkstra",
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

    PATTERNS: Dict[str, List[re.Pattern]] = {
        TaskCategory.API_ENDPOINT: [
            re.compile(r"\b(api|endpoint|route|router|controller|fastapi|rest|graphql|post|get|put|delete)\b", re.I),
            re.compile(r"\b(request_handler|payload|response_model|http)\b", re.I)
        ],
        TaskCategory.AUTHORIZATION_GUARD: [
            re.compile(r"\b(auth|authorization|permission|role|rbac|abac|guard|jwt|token|spiffe|fence)\b", re.I),
            re.compile(r"\b(forbidden|unauthorized|credential|mfa)\b", re.I)
        ],
        TaskCategory.STATE_TRANSITION: [
            re.compile(r"\b(state|fsm|transition|lifecycle|event_store|checkpoint|replay)\b", re.I),
            re.compile(r"\b(workflow|saga|compensat)\b", re.I)
        ],
        TaskCategory.AUDIT_LOG: [
            re.compile(r"\b(audit|logging|telemetry|trace|metric|event_log|jsonl)\b", re.I),
            re.compile(r"\b(provenance|attestation|audit_trail)\b", re.I)
        ],
        TaskCategory.UI_COMPONENT: [
            re.compile(r"\b(ui|component|react|nextjs|tailwind|css|layout|screen|dialog|button|card|modal)\b", re.I),
            re.compile(r"\b(frontend|view|page|animation|motion)\b", re.I)
        ],
        TaskCategory.INTEGRATION_TEST: [
            re.compile(r"\b(test|pytest|harness|e2e|integration|unit_test|oracle|adversarial)\b", re.I),
            re.compile(r"\b(mock|fixture|hypothesis|invariant)\b", re.I)
        ],
        TaskCategory.DATABASE_MIGRATION: [
            re.compile(r"\b(database|migration|prisma|schema|sqlite|postgres|mongo|sql|table|column)\b", re.I),
            re.compile(r"\b(relation|foreign_key|index)\b", re.I)
        ],
        TaskCategory.SECURITY_REMEDIATION: [
            re.compile(r"\b(vulnerability|cve|injection|sqli|xss|secret|sanitize|shield|bandit|semgrep)\b", re.I)
        ],
        TaskCategory.BUG_FIX: [
            re.compile(r"\b(fix|bug|defect|issue|error|exception|crash|patch|repair|regression)\b", re.I)
        ]
    }

    SCOPE_PATTERNS = [
        (re.compile(r"\b(refactor|rewrite|architecture|pipeline|complete erp|entire|full system)\b", re.I), ScopeTier.MAJOR),
        (re.compile(r"\b(typo|docstring|comment|formatting|whitespace)\b", re.I), ScopeTier.TRIVIAL),
        (re.compile(r"\b(endpoint|table|component|module|feature|contract|subsystem)\b", re.I), ScopeTier.MEDIUM),
        (re.compile(r"\b(add field|patch|fix|tweak|adjust|one line|cleanup)\b", re.I), ScopeTier.MINOR),
    ]

    @classmethod
    def classify_task(cls, prompt: str) -> Dict[str, Any]:
        """
        Classifies task string using deterministic pattern analysis.
        Returns category, scope_tier, confidence, and matched rules.
        """
        prompt_clean = prompt.strip()
        matched_rules = []
        scores: Dict[str, float] = {cat: 0.0 for cat in cls.PATTERNS}

        for cat, pattern_list in cls.PATTERNS.items():
            for pat in pattern_list:
                matches = pat.findall(prompt_clean)
                if matches:
                    scores[cat] += len(matches) * 0.3
                    matched_rules.append(f"{cat}:{pat.pattern}")

        best_cat = max(scores, key=lambda k: scores[k])
        max_score = scores[best_cat]

        if max_score > 0:
            confidence = min(1.0, max_score / 2.0)
        else:
            best_cat = TaskCategory.GENERAL_ENGINEERING
            confidence = 0.2

        used_fallback = False
        if confidence < 0.5:
            fallback_cat, fallback_conf = cls._semantic_fallback(prompt_clean)
            if fallback_conf > confidence:
                best_cat = fallback_cat
                confidence = fallback_conf
                used_fallback = True

        scope_tier = ScopeTier.MEDIUM
        for pat, tier in cls.SCOPE_PATTERNS:
            if pat.search(prompt_clean):
                scope_tier = tier
                break

        return {
            "category": best_cat,
            "scope_tier": scope_tier,
            "confidence": confidence,
            "matched_rules": matched_rules,
            "deterministic": not used_fallback,
            "design_principle": "deterministic_over_adaptive"
        }

    @classmethod
    def _semantic_fallback(cls, prompt: str) -> Tuple[str, float]:
        """
        Local fallback when deterministic regex returns low confidence.
        Uses normalized token overlap similarity vector matching without external calls.
        """
        prompt_words = set(re.findall(r"\w+", prompt.lower()))
        prototypes = {
            TaskCategory.API_ENDPOINT: "build api route http web service controller endpoint payload",
            TaskCategory.AUTHORIZATION_GUARD: "security guard authentication role permission token access rbac",
            TaskCategory.STATE_TRANSITION: "state machine transition lifecycle fsm workflow saga event",
            TaskCategory.AUDIT_LOG: "audit log logging telemetry trace metric event trail",
            TaskCategory.UI_COMPONENT: "user interface design frontend styling component visual screen css",
            TaskCategory.INTEGRATION_TEST: "automated software test suite verification coverage check pytest",
            TaskCategory.DATABASE_MIGRATION: "database model schema relational entity table migration prisma",
            TaskCategory.SECURITY_REMEDIATION: "vulnerability cve injection sqli xss sanitize shield bandit semgrep",
            TaskCategory.BUG_FIX: "fix defect crash bug error exception patch problem issue",
            TaskCategory.GENERAL_ENGINEERING: "task implement script engineering utility general helper"
        }

        best_cat = TaskCategory.GENERAL_ENGINEERING
        best_jaccard = 0.0
        for cat, proto in prototypes.items():
            proto_words = set(proto.split())
            intersection = prompt_words & proto_words
            union = prompt_words | proto_words
            jaccard = len(intersection) / len(union) if union else 0.0
            if jaccard > best_jaccard:
                best_jaccard = jaccard
                best_cat = cat

        return best_cat, min(0.65, best_jaccard * 2.0)
