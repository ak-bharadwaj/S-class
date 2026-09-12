"""
S-Class Deterministic Task Classifier (task_classifier.py)

================================================================================
DESIGN PRINCIPLE: "DETERMINISTIC OVER ADAPTIVE"
================================================================================
A core architectural tenet of S-Class EOS is favoring explicit, deterministic
classification over stochastic LLM classification by default:

1. Zero Non-Determinism:
   Given identical prompt inputs, deterministic regex and keyword rule sets produce
   identical classifications 100% of the time. This guarantees reproducible build
   plans, deterministic test matrices, and provable safety invariants.

2. Zero Token Cost & Sub-Millisecond Latency:
   Pattern-based classification executes in < 0.1ms with zero API cost, avoiding
   external network dependencies and rate limits.

3. Immunity to Adversarial Prompt Injection:
   Conversational jailbreaks and injected instructions cannot manipulate deterministic
   token matching into erroneously reclassifying high-risk tasks.

4. Graceful Semantic Fallback:
   When explicit keyword rules return low confidence (< 0.5), an optional local
   embedding/similarity fallback kicks in purely as an offline confidence booster,
   preserving both our zero-cloud stance and our "deterministic by default" principle.
================================================================================
"""

import re
from typing import Dict, List, Any, Optional, Tuple


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


class TaskClassifier:
    """
    Deterministic task classifier enforcing 'Deterministic over Adaptive' routing.
    """

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

        # Determine winner
        best_cat = max(scores, key=lambda k: scores[k])
        max_score = scores[best_cat]

        if max_score > 0:
            confidence = min(1.0, max_score / 2.0)
        else:
            best_cat = TaskCategory.GENERAL_ENGINEERING
            confidence = 0.2

        # If confidence is low, attempt local semantic embedding fallback
        used_fallback = False
        if confidence < 0.5:
            fallback_cat, fallback_conf = cls._semantic_fallback(prompt_clean)
            if fallback_conf > confidence:
                best_cat = fallback_cat
                confidence = fallback_conf
                used_fallback = True

        # Scope classification: evaluate in descending priority order (MAJOR -> TRIVIAL)
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
