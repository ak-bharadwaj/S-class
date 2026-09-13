"""
Tests for Phase 6: The Five Product Demos.
Validates:
Demo 1: False test claim -> REJECTED
Demo 2: Dangerous command -> DENY with reason and policy ID
Demo 3: Secret exfiltration -> DENY with SECRET classification
Demo 4: Post-verification mutation -> VERIFICATION INVALIDATED
Demo 5: Cross-agent continuity -> verified state preserved from Claude to Codex
"""

from sclass.product.demos import ProductDemos


def test_demo_1_false_test_claim(tmp_path):
    res = ProductDemos.run_demo_1_false_test_claim(str(tmp_path))
    assert res["success"]
    assert res["sclass_verdict"] == "REJECT"
    assert res["actual_failures"] == 2


def test_demo_2_dangerous_command(tmp_path):
    res = ProductDemos.run_demo_2_dangerous_command(str(tmp_path))
    assert res["success"]
    assert res["sclass_outcome"] == "DENY"
    assert "SCLASS-SEC" in res["policy_id"]


def test_demo_3_secret_exfiltration(tmp_path):
    res = ProductDemos.run_demo_3_secret_exfiltration(str(tmp_path))
    assert res["success"]
    assert res["sclass_outcome"] == "DENY"
    assert "SECRET" in res["policy_id"] or "secret" in res["reason"].lower()


def test_demo_4_post_verification_mutation(tmp_path):
    res = ProductDemos.run_demo_4_post_verification_mutation(str(tmp_path))
    assert res["success"]
    assert res["proof_stale"]
    assert res["sclass_action"] == "VERIFICATION INVALIDATED"


def test_demo_5_cross_agent_continuity(tmp_path):
    res = ProductDemos.run_demo_5_cross_agent_continuity(str(tmp_path))
    assert res["success"]
    assert res["transferred_verified_count"] >= 1
    assert "Fix test_refresh" in res["transferred_next_action"]
    assert len(res["transferred_blockers"]) > 0
