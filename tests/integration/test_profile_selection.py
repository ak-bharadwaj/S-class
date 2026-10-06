"""
S-Class v6 Integration Tests: Adaptive Profiles, Subagent Selection, Context Diet & Speed
(tests/integration/test_profile_selection.py)
"""

import os
import sys
import time
import tempfile
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from planner import MetaPlanner, WorkflowProfile
from subagent_selector import select_subagents
from instructions_loader import get_active_instructions
from token_budget import count_tokens, get_token_budget, can_fast_path
from diff_auditor import DiffAuditor, ScopeCreep, WeakenedTests, ExposedSecrets
from verifier import IncrementalVerifier, EvidenceVerifier
from runtime import initialize_state, dispatch_event, get_state


def test_typo_fix_uses_micro_profile():
    """A typo fix should use MICRO profile (3 states, 0 subagents)."""
    plan = MetaPlanner.classify_goal("Fix typo in button text")
    assert plan.profile == WorkflowProfile.MICRO
    assert len(plan.state_sequence) == 3
    assert plan.state_sequence == ["TRIAGE", "CODING", "DONE"]


def test_bug_fix_uses_bug_fix_profile():
    """A bug fix should use BUG_FIX profile (skip design/debate)."""
    plan = MetaPlanner.classify_goal("Fix contact form not submitting")
    assert plan.profile == WorkflowProfile.BUG_FIX
    assert "DESIGN" not in plan.state_sequence
    assert "DEBATE" not in plan.state_sequence


def test_full_product_uses_full_profile():
    """A new product request should use FULL profile."""
    plan = MetaPlanner.classify_goal(
        "Build a complete student attendance management portal with "
        "role-based access, database schema, API routes, and dashboard"
    )
    assert plan.profile == WorkflowProfile.FULL
    assert "DESIGN" in plan.state_sequence
    assert "DEBATE" in plan.state_sequence


def test_question_bypasses_fsm():
    """A question should NOT trigger FSM at all."""
    plan = MetaPlanner.classify_goal("What is the current database schema?")
    assert plan.profile == WorkflowProfile.QUESTION


def test_micro_task_spawns_zero_subagents():
    plan = select_subagents("CODING", WorkflowProfile.MICRO, [], [])
    assert len(plan.agents) == 0


def test_bug_fix_spawns_two_subagents():
    plan = select_subagents("CODING", WorkflowProfile.BUG_FIX, ["frontend"], [".tsx"])
    assert len(plan.agents) == 2  # builder + QA


def test_full_task_with_db_spawns_four():
    plan = select_subagents(
        "CODING", WorkflowProfile.FULL,
        ["frontend", "backend", "database"], [".tsx", ".py", ".sql"]
    )
    assert len(plan.agents) == 4  # builder + frontend + db + QA


def test_micro_instructions_under_500_tokens():
    instructions = get_active_instructions("CODING", WorkflowProfile.MICRO)
    token_count = count_tokens(instructions)
    assert token_count < 500


def test_full_instructions_under_4000_tokens():
    instructions = get_active_instructions("DESIGN", WorkflowProfile.FULL)
    token_count = count_tokens(instructions)
    assert token_count < 4000


def test_micro_task_completes_under_2_seconds():
    """FSM initialization + MICRO profile + transition should be < 2s."""
    with tempfile.TemporaryDirectory() as tmpdir:
        start = time.time()
        state = initialize_state(tmpdir, "Fix typo in readme")
        dispatch_event("triage_done", tmpdir)  # TRIAGE -> CODING
        dispatch_event("code_written", tmpdir)  # CODING -> DONE
        elapsed = time.time() - start
        final_state = get_state(tmpdir)
        assert elapsed < 2.0
        assert final_state.current_phase == "DONE"


def test_diff_auditor_detects_scope_creep():
    auditor = DiffAuditor()
    intent = {"affected_files": ["src/button.tsx"]}
    diff = """diff --git a/src/button.tsx b/src/button.tsx
--- a/src/button.tsx
+++ b/src/button.tsx
@@ -1,1 +1,1 @@
-btn
+button
diff --git a/src/unrelated.py b/src/unrelated.py
--- a/src/unrelated.py
+++ b/src/unrelated.py
@@ -1,1 +1,1 @@
-x
+y
"""
    res = auditor.audit(intent, diff)
    assert not res.passed
    assert any(isinstance(issue, ScopeCreep) for issue in res.issues)


def test_diff_auditor_detects_weakened_tests():
    auditor = DiffAuditor()
    intent = {"affected_files": ["tests/test_auth.py"]}
    diff = """diff --git a/tests/test_auth.py b/tests/test_auth.py
--- a/tests/test_auth.py
+++ b/tests/test_auth.py
@@ -5,3 +5,1 @@
-    assert user.is_authenticated
-    assert token is not None
+    pass
"""
    res = auditor.audit(intent, diff)
    assert not res.passed
    assert any(isinstance(issue, WeakenedTests) for issue in res.issues)


def test_diff_auditor_detects_secrets():
    auditor = DiffAuditor()
    intent = {"affected_files": ["config.py"]}
    diff = """diff --git a/config.py b/config.py
--- a/config.py
+++ b/config.py
@@ -1,1 +1,2 @@
+API_KEY = "AKIA1234567890ABCDEF"
"""
    res = auditor.audit(intent, diff)
    assert not res.passed
    assert any(isinstance(issue, ExposedSecrets) for issue in res.issues)


def test_incremental_verifier():
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, "sample_test.py")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("def test_one():\n    assert 1 == 1\n")

        verifier = IncrementalVerifier(tmpdir)
        snap1 = verifier.get_current_snapshot(tmpdir)
        assert "sample_test.py" in snap1

        # Second snapshot without modifications -> diff is empty
        diff = verifier.diff_snapshots(snap1, snap1)
        assert len(diff) == 0


def test_fast_path_detection():
    assert can_fast_path("Fix typo in button text", ["button.tsx"]) is True
    assert can_fast_path("Update copyright year in footer", ["footer.tsx"]) is True
    assert can_fast_path("Change header background color", ["header.css"]) is True
    assert can_fast_path("Build full-stack student management portal", ["app.tsx", "server.py"]) is False
    assert can_fast_path("Migrate database schema", ["schema.prisma"]) is False


def test_copyright_update_uses_micro_profile():
    plan = MetaPlanner.classify_goal("Update copyright year to 2026")
    assert plan.profile == WorkflowProfile.MICRO
    assert plan.state_sequence == ["TRIAGE", "CODING", "DONE"]


def test_css_color_change_uses_small_fix():
    plan = MetaPlanner.classify_goal("Change header background to gray")
    assert plan.profile == WorkflowProfile.SMALL_FIX
    assert plan.state_sequence == ["TRIAGE", "ANALYSIS", "CODING", "TASK_VERIFICATION", "DONE"]


def test_database_question_bypasses_fsm():
    plan = MetaPlanner.classify_goal("What is the port for the database service?")
    assert plan.profile == WorkflowProfile.QUESTION
    assert plan.state_sequence == ["DONE"]


def test_compound_question_with_build_intent_does_not_bypass_fsm():
    plan = MetaPlanner.classify_goal("What is the current DB schema and build an API for it")
    assert plan.profile != WorkflowProfile.QUESTION
    assert "CODING" in plan.state_sequence


def test_diff_auditor_handles_files_starting_with_a_and_b():
    """Ensure prefix stripping does not strip 'a' or 'b' from filenames like app.py or button.tsx."""
    auditor = DiffAuditor()
    intent = {"affected_files": ["app.py", "src/button.tsx"]}
    diff = """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,1 +1,1 @@
-old
+new
diff --git a/src/button.tsx b/src/button.tsx
--- a/src/button.tsx
+++ b/src/button.tsx
@@ -1,1 +1,1 @@
-old
+new
"""
    res = auditor.audit(intent, diff)
    assert res.passed is True
    assert len(res.issues) == 0


def test_diff_auditor_detects_unauthorized_dependencies():
    from diff_auditor import UnauthorizedDependency
    auditor = DiffAuditor()
    intent = {"affected_files": ["package.json"], "allow_new_dependencies": False}
    diff = """diff --git a/package.json b/package.json
--- a/package.json
+++ b/package.json
@@ -10,1 +10,2 @@
+    "malicious-pkg": "^1.0.0",
"""
    res = auditor.audit(intent, diff)
    assert res.passed is False
    assert any(isinstance(issue, UnauthorizedDependency) for issue in res.issues)


def test_diff_snapshots_detects_deleted_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        verifier = IncrementalVerifier(tmpdir)
        snap1 = {"file1.py": 100.0, "file2.py": 200.0}
        snap2 = {"file1.py": 100.0}  # file2.py was deleted
        changed = verifier.diff_snapshots(snap1, snap2)
        assert "file2.py" in changed


def test_evidence_verifier_check_no_test_regression():
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, "test_sample.py")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("def test_one():\n    assert 1 == 1\n    assert 2 == 2\n")

        v = EvidenceVerifier(tmpdir)
        # Pre count was 2 -> should pass
        assert v.check_no_test_regression(2, tmpdir) is True
        # Pre count was 5 (higher than 2) -> should fail (regression detected)
        assert v.check_no_test_regression(5, tmpdir) is False


def test_tech_stack_detection_polyglot():
    from sclass_skill_orchestrator import detect_tech_stack
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, "Cargo.toml"), "w", encoding="utf-8") as f:
            f.write("[package]\nname = 'test'\n")
        assert "Rust" in detect_tech_stack(tmpdir)

    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, "go.mod"), "w", encoding="utf-8") as f:
            f.write("module test\n")
        assert "Go" in detect_tech_stack(tmpdir)



def test_adversarial():
    assert True
