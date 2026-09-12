import pytest
from task_classifier import TaskClassifier, TaskCategory, ScopeTier


def test_classify_api_endpoint():
    res = TaskClassifier.classify_task("Implement FastAPI router endpoint for student registration")
    assert res["category"] == TaskCategory.API_ENDPOINT
    assert res["confidence"] > 0.4
    assert res["deterministic"] is True
    assert res["design_principle"] == "deterministic_over_adaptive"


def test_classify_auth_guard():
    res = TaskClassifier.classify_task("Add JWT RBAC authorization guard to protect admin routes")
    assert res["category"] == TaskCategory.AUTHORIZATION_GUARD
    assert res["confidence"] > 0.4
    assert res["deterministic"] is True


def test_classify_database_schema():
    res = TaskClassifier.classify_task("Generate Prisma migration and database schema for lesson bookings table")
    assert res["category"] == TaskCategory.DATABASE_MIGRATION
    assert res["confidence"] > 0.4


def test_classify_ui_component():
    res = TaskClassifier.classify_task("Build responsive Tailwind CSS card component for test scorecard view")
    assert res["category"] == TaskCategory.UI_COMPONENT


def test_scope_tiers():
    res1 = TaskClassifier.classify_task("Fix typo in docstring")
    assert res1["scope_tier"] == ScopeTier.TRIVIAL

    res2 = TaskClassifier.classify_task("Rewrite full system architecture for entire application")
    assert res2["scope_tier"] == ScopeTier.MAJOR

    # Even with the word "fix", large scope indicators (architecture, rewrite, entire) MUST take priority
    res3 = TaskClassifier.classify_task("Fix the entire enterprise architecture and rewrite the pipeline")
    assert res3["scope_tier"] == ScopeTier.MAJOR


def test_semantic_fallback_coverage():
    # Prompt with low keyword pattern hits should activate local semantic fallback
    res = TaskClassifier.classify_task("audit trail telemetry metrics investigation")
    assert res["category"] == TaskCategory.AUDIT_LOG

