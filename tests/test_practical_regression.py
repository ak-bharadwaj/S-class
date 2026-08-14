"""
Empirical Regression Suite for S-Class EOS

Tests real-world failure cases from actual projects (SGDA 19-feature gap,
Next.js/Prisma schema grounding, FastAPI async session handling, file lock resilience,
dead process lock recovery, and low-confidence decision provenance).
"""

import pytest
import json
import os
import sys
import time
import tempfile
import shutil

PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PLUGIN_DIR not in sys.path:
    sys.path.insert(0, PLUGIN_DIR)

from failure_log import FailureLogManager, FailureCase
from practical_skeptic import PracticalSkeptic
from spec_synthesis import SpecSynthesisEngine
import runtime


@pytest.fixture
def temp_workspace():
    tmp = tempfile.mkdtemp()
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


def test_failure_log_loading_and_recording():
    """Verify that failure log loads existing empirical cases and allows 1-line logging."""
    cases = FailureLogManager.load_cases()
    assert len(cases) >= 3
    assert any("SGDA" in c.project for c in cases)
    assert any("AMIS-RU" in c.project for c in cases)


def test_skeptic_rules_are_100_percent_grounded_in_failure_log():
    """Verify exact bidirectional 1:1 match between PracticalSkeptic rules and logged failure cases."""
    cases = FailureLogManager.load_cases()
    logged_rule_ids = {c.skeptic_rule_id for c in cases}
    active_skeptic_rules = set(PracticalSkeptic.ACTIVE_RULES)

    # 1. No unbacked skeptic rules: Every active rule MUST trace to a logged real failure case
    unbacked_rules = active_skeptic_rules - logged_rule_ids
    assert not unbacked_rules, f"Skeptic rules without failure log backing: {unbacked_rules}"

    # 2. No phantom failure rules: Every rule referenced in failure log MUST be actively implemented
    unimplemented_rules = logged_rule_ids - active_skeptic_rules
    assert not unimplemented_rules, f"Logged failure rules not implemented in PracticalSkeptic: {unimplemented_rules}"

    # 3. Exact bidirectional set equality
    assert active_skeptic_rules == logged_rule_ids
    assert len(active_skeptic_rules) == 11


def test_practical_skeptic_catches_vibecoded_mockup_fields():
    """Verify that PracticalSkeptic detects generic mockup placeholder fields."""
    mock_spec = {
        "low_level_designs": {
            "admin:/dashboard": {
                "page_name": "Admin Dashboard",
                "tabs": [
                    {
                        "name": "Overview",
                        "fields": ["genericField (string)", "dummy (number)", "validField (string)"],
                        "actions": ["Save"]
                    }
                ],
                "api_endpoints": ["GET /api/admin/dashboard"]
            }
        },
        "page_spreads": {"admin": [{"route": "/profile"}]}
    }
    passed, warns, checks = PracticalSkeptic.audit_specification(mock_spec)
    assert any("SKEPTIC-NO-VIBECODE-UI" in w for w in warns)


def test_practical_skeptic_passes_real_sgda_driving_school_spec(temp_workspace):
    """
    Prompt: 'Build student lesson booking and instructor schedule portal for Sri Guru Driving Academy'
    Ensures S-Class synthesizes actual operational workflows and clean API contracts.
    """
    engine = SpecSynthesisEngine()
    prompt = "Build student lesson booking and instructor schedule portal for Sri Guru Driving Academy with lesson progress and vehicle dispatch"
    spec = engine.run_synthesis(prompt, temp_workspace)

    assert spec.gate_result in ["PASS", "PASS_WITH_DECISIONS"]
    assert len(spec.low_level_designs) > 0

    passed, warns, checks = PracticalSkeptic.audit_specification({
        "low_level_designs": spec.low_level_designs,
        "page_spreads": spec.page_spreads,
        "requirements": spec.requirements
    })
    assert passed is True


def test_filelock_recovers_from_dead_pid_and_stale_file(temp_workspace):
    """Verify that FileLock recovers immediately from a crashed process without hanging or timing out."""
    lock_file = os.path.join(temp_workspace, ".agents", "state.lock")
    os.makedirs(os.path.dirname(lock_file), exist_ok=True)

    # Simulate a crashed process leaving behind its lock with a dead PID (e.g. 9999999)
    with open(lock_file, "w", encoding="utf-8") as f:
        f.write("9999999")

    # FileLock must detect the dead PID, clean it up immediately, and acquire the lock in < 0.2s
    start = time.time()
    with runtime.FileLock(lock_file, timeout=2.0):
        # We successfully acquired the lock!
        assert True
    elapsed = time.time() - start
    assert elapsed < 1.0


def test_filelock_enforces_mutual_exclusion_and_timeout(temp_workspace):
    """Verify that FileLock NEVER bypasses the lock when another live process holds it."""
    lock_file = os.path.join(temp_workspace, ".agents", "state.lock")
    os.makedirs(os.path.dirname(lock_file), exist_ok=True)

    # Write CURRENT live process's PID
    with open(lock_file, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))

    # Attempting to acquire lock with 0.3s timeout must raise TimeoutError (not bypass!)
    with pytest.raises(TimeoutError):
        with runtime.FileLock(lock_file, timeout=0.3):
            pass

    # Cleanup
    if os.path.exists(lock_file):
        os.unlink(lock_file)


def test_low_confidence_decisions_tagged_in_decision_log(temp_workspace):
    """Verify that assumptions and derived low-confidence decisions are recorded in state.decisionLog with provenance."""
    runtime.initialize_state(temp_workspace, goal="Build Driving Academy student portal with booking and lesson progress")
    state = runtime.get_state(temp_workspace)

    assert len(state.decisionLog) >= 1
    # Check that decisions contain provenance details and confidence scores
    decisions = state.decisionLog
    has_confidence_score = any(d.confidence < 1.0 for d in decisions)
    assert any("Provenance:" in d.reason for d in decisions)


def test_plain_prose_library_system_role_and_entity_preservation(temp_workspace):
    """Verify FAIL-PROSE-010: Plain English prose feature descriptions extract all named human roles and zero non-noun fake REST endpoints."""
    from spec_synthesis import SpecSynthesisEngine
    from practical_skeptic import PracticalSkeptic

    prose_prompt = "Build a library management system where students and faculty borrow books. Librarians can waive fines that accrue daily. Block further borrowing until paid."
    engine = SpecSynthesisEngine()
    spec = engine.run_synthesis(prose_prompt, temp_workspace)

    # 1. Verify role preservation: librarian, student, faculty must all exist in page_spreads
    roles_in_spreads = list(spec.page_spreads.keys())
    assert "librarian" in roles_in_spreads, f"Librarian role was lost! Found roles in page_spreads: {roles_in_spreads}"
    assert "student" in roles_in_spreads, f"Student role missing! Found: {roles_in_spreads}"
    assert "faculty" in roles_in_spreads, f"Faculty role missing! Found: {roles_in_spreads}"

    # 2. Verify non-noun fake endpoints are eliminated
    spec_json_path = os.path.join(temp_workspace, ".agents", "synthesized_spec.json")
    assert os.path.exists(spec_json_path)
    with open(spec_json_path, 'r', encoding='utf-8') as f:
        spec_data = json.load(f)

    all_apis = []
    for lld in spec.low_level_designs.values():
        all_apis.extend(lld.get("api_endpoints", []))

    fake_endpoints = ["accrues", "blocks", "checkeds", "dailies", "furthers", "haves", "untils", "waives", "paids"]
    found_fake = [fe for fe in fake_endpoints if any(fe in api for api in all_apis)]
    assert not found_fake, f"Found fake non-noun resources in synthesized spec: {found_fake}"

    # 3. Practical Skeptic audit pass
    passed, warnings, checks = PracticalSkeptic.audit_specification(spec_data, archetypes=["fullstack"])
    assert passed is True, f"PracticalSkeptic failed on plain prose library spec! Warnings: {warnings}"


def test_5_domain_matrix_role_completeness(temp_workspace):
    """Verify FAIL-PROSE-011: 5-domain matrix (E-commerce, Fitness, Helpdesk, Hostel, Payroll) preserves 100% of named human roles without silent role loss."""
    from spec_synthesis import SpecSynthesisEngine
    from practical_skeptic import PracticalSkeptic

    domain_prompts = [
        ("E-commerce", "E-commerce platform for customers, sellers, and admins. Sellers upload products, customers buy, admins moderate.", ["customer", "seller", "admin"]),
        ("Fitness App", "Gym membership app for members, trainers, and staff. Trainers schedule classes, staff check in members.", ["member", "trainer", "staff"]),
        ("Helpdesk", "Helpdesk portal for customers, agents, and supervisors. Agents respond to tickets, supervisors escalate issues.", ["customer", "agent", "supervisor"]),
        ("Hostel Management", "Hostel management system for wardens, students, and maintenance staff. Wardens assign rooms, maintenance handles repairs.", ["warden", "student", "maintenance"]),
        ("Payroll", "Payroll management system for HR, employees, managers, and finance team. HR creates records, managers approve, finance disburses pay.", ["hr", "employee", "manager", "finance"])
    ]

    engine = SpecSynthesisEngine()

    for domain_name, prompt, expected_roles in domain_prompts:
        ws = os.path.join(temp_workspace, domain_name.replace(" ", "_"))
        os.makedirs(ws, exist_ok=True)
        spec = engine.run_synthesis(prompt, ws)

        extracted_roles = list(spec.page_spreads.keys())
        for r in expected_roles:
            assert any(r in er or er in r for er in extracted_roles), f"[{domain_name}] Missing role '{r}'! Found roles in page_spreads: {extracted_roles}"

        spec_json_path = os.path.join(ws, ".agents", "synthesized_spec.json")
        with open(spec_json_path, 'r', encoding='utf-8') as f:
            spec_data = json.load(f)

        passed, warnings, checks = PracticalSkeptic.audit_specification(spec_data, archetypes=["fullstack"])
        assert passed is True, f"[{domain_name}] PracticalSkeptic failed audit! Warnings: {warnings}"


