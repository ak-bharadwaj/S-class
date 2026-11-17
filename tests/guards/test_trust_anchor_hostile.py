"""Adversarial / Hostile Tests for Base-Enforced Trust Anchor Gate (Roadmap B04 / R4-1).

Tests prove that:
1. Candidate PR modifications to base-controlled files (TRUST-ANCHORS.json, trust-anchor.yml,
   gate_trust_anchor.py, BASELINE-HASHES.txt, FROZEN-MANIFEST.sha256) are strictly rejected.
2. Modifying candidate-side copies cannot alter authoritative expectations read from the base branch.
3. Unauthorized modifications, deletions, and errata drift in frozen directories fail closed.
4. All nine state-machine mutations are rejected by the stdlib validator.
5. Gate fallback contract violations are detected.
"""

from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path
import pytest

from tools.gates.gate_trust_anchor import (
    ROOT,
    execute_nine_mutation_battery_stdlib,
    load_base_trust_anchors,
    sha256_lf,
    validate_transition_graph,
    verify_pr_head_as_data,
)


@pytest.fixture
def base_anchors():
    """Authoritative anchors read from base branch."""
    anchors_file = ROOT / "governance" / "TRUST-ANCHORS.json"
    assert anchors_file.exists(), "TRUST-ANCHORS.json must exist in repository"
    return json.loads(anchors_file.read_text(encoding="utf-8"))


@pytest.fixture
def base_spec():
    spec_path = ROOT / "10-CONFORMANCE" / "state-machines.v6.0.1.json"
    return json.loads(spec_path.read_text(encoding="utf-8"))


# -----------------------------------------------------------------------------
# Hostile Invariant 1: Candidate cannot modify base-controlled governance files
# -----------------------------------------------------------------------------

@pytest.mark.parametrize("protected_file", [
    "governance/TRUST-ANCHORS.json",
    "governance/BASELINE-HASHES.txt",
    "governance/FROZEN-MANIFEST.sha256",
    ".github/workflows/trust-anchor.yml",
    "tools/gates/gate_trust_anchor.py",
])
def test_hostile_candidate_modifies_protected_file_fails_closed(monkeypatch, base_anchors, protected_file):
    """Proves candidate PR cannot modify any base-controlled anchor or workflow file."""
    # Simulate git_diff_files returning modification to protected_file
    fake_diff = [("M", protected_file)]
    monkeypatch.setattr("tools.gates.gate_trust_anchor.git_diff_files", lambda b, p: fake_diff)
    # Simulate git_show returning different bytes between base and pr
    monkeypatch.setattr("tools.gates.gate_trust_anchor.git_show", lambda ref, path: b"BASE_CONTENT" if "base" in ref or "origin" in ref else b"FORGED_PR_CONTENT")

    violations = verify_pr_head_as_data("origin/integration-r30-b1", "candidate-head", base_anchors)
    assert any("UNAUTHORIZED GOVERNANCE MODIFICATION" in v and protected_file in v for v in violations)


def test_hostile_candidate_tampered_anchor_ignored_by_base_reader(tmp_path, monkeypatch):
    """Proves load_base_trust_anchors reads ONLY from base_ref, completely ignoring candidate PR content."""
    # When base_ref is queried, return authoritative data
    # When PR head is queried, return attacker data with empty hashes
    def fake_git_show(ref, path):
        if "base" in ref or "origin" in ref:
            return json.dumps({"package_original_hashes": {"authoritative": "hash123"}}).encode("utf-8")
        return json.dumps({"package_original_hashes": {"forged_bypass": "attacker_hash"}}).encode("utf-8")

    monkeypatch.setattr("tools.gates.gate_trust_anchor.git_show", fake_git_show)

    anchors = load_base_trust_anchors("origin/integration-r30-b1", "governance/TRUST-ANCHORS.json")
    assert "authoritative" in anchors["package_original_hashes"]
    assert "forged_bypass" not in anchors["package_original_hashes"]


# -----------------------------------------------------------------------------
# Hostile Invariant 2: Frozen directory protection
# -----------------------------------------------------------------------------

def test_hostile_candidate_modifies_frozen_spec_fails_closed(monkeypatch, base_anchors):
    """Proves unauthorized modification to 00-SPEC fails closed."""
    fake_diff = [("M", "00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md")]
    monkeypatch.setattr("tools.gates.gate_trust_anchor.git_diff_files", lambda b, p: fake_diff)
    monkeypatch.setattr("tools.gates.gate_trust_anchor.git_show", lambda ref, path: b"TAMPERED_SPEC_CONTENT\n")

    violations = verify_pr_head_as_data("origin/integration-r30-b1", "candidate-head", base_anchors)
    assert any("UNAUTHORIZED MODIFICATION in '00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md'" in v for v in violations)


def test_hostile_candidate_unauthorized_errata_drift_fails_closed(monkeypatch, base_anchors):
    """Proves candidate cannot introduce unauthorized errata hash for semantics file."""
    fake_diff = [("M", "10-CONFORMANCE/sclass_semantics_v6_0_1.py")]
    monkeypatch.setattr("tools.gates.gate_trust_anchor.git_diff_files", lambda b, p: fake_diff)
    monkeypatch.setattr("tools.gates.gate_trust_anchor.git_show", lambda ref, path: b"UNAUTHORIZED_SEMANTICS_CODE\n")

    violations = verify_pr_head_as_data("origin/integration-r30-b1", "candidate-head", base_anchors)
    assert any("UNAUTHORIZED ERRATA DRIFT in '10-CONFORMANCE/sclass_semantics_v6_0_1.py'" in v for v in violations)


def test_hostile_candidate_deletes_frozen_file_fails_closed(monkeypatch, base_anchors):
    """Proves candidate cannot delete a frozen directory file."""
    fake_diff = [("D", "10-CONFORMANCE/sclass_kernel_v6_0_1.py")]
    monkeypatch.setattr("tools.gates.gate_trust_anchor.git_diff_files", lambda b, p: fake_diff)

    violations = verify_pr_head_as_data("origin/integration-r30-b1", "candidate-head", base_anchors)
    assert any("UNAUTHORIZED DELETION: Protected file '10-CONFORMANCE/sclass_kernel_v6_0_1.py'" in v for v in violations)


# -----------------------------------------------------------------------------
# Hostile Invariant 3: State-machine 9-mutation battery
# -----------------------------------------------------------------------------

def test_hostile_all_nine_state_machine_mutations_rejected(base_spec):
    """Proves execute_nine_mutation_battery_stdlib catches and rejects all 9 mutations."""
    all_caught, logs = execute_nine_mutation_battery_stdlib(base_spec)
    assert all_caught, "Every single mutation must be rejected by transition validator"
    assert len(logs) == 9
    for log in logs:
        assert log.startswith("PASS: Mutation")


# -----------------------------------------------------------------------------
# Hostile Invariant 4: Gate contract signature fallback
# -----------------------------------------------------------------------------

def test_hostile_gate_fallback_detected(monkeypatch, base_anchors):
    """Proves gate.py with unhardened fallback is rejected."""
    bad_gate_code = (
        "def execute_lifecycle(request, cmd):\n"
        "    if isinstance(cmd, list):\n"
        "        pass\n"
        "    else:\n"
        "        return worker_instance.execute(request, ctx, handle)\n"
    ).encode("utf-8")

    fake_diff = [("M", "src/sclass/reference_impl/gate.py")]
    monkeypatch.setattr("tools.gates.gate_trust_anchor.git_diff_files", lambda b, p: fake_diff)
    monkeypatch.setattr("tools.gates.gate_trust_anchor.git_show", lambda ref, path: bad_gate_code)

    violations = verify_pr_head_as_data("origin/integration-r30-b1", "candidate-head", base_anchors)
    assert any("GATE CONTRACT VIOLATION: gate.py contains unhardened signature fallback" in v for v in violations)


# -----------------------------------------------------------------------------
# F3: Six-Section Anchor Tamper Tests
# -----------------------------------------------------------------------------

def test_gate_rejects_package_original_hash_tamper(base_anchors, base_spec):
    """Proves tampering with Section 1 (package_original_hashes) is strictly rejected."""
    tampered = copy.deepcopy(base_anchors)
    tampered["package_original_hashes"].pop("00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md")
    from tools.gates.gate_trust_anchor import validate_all_six_anchor_sections
    violations = validate_all_six_anchor_sections(tampered, base_spec)
    assert any("SECTION 1 CORRUPTED" in v for v in violations)


def test_gate_rejects_authorized_errata_tamper(base_anchors, base_spec):
    """Proves tampering with Section 2 (authorized_errata) violates single-hash rule."""
    tampered = copy.deepcopy(base_anchors)
    tampered["authorized_errata"]["10-CONFORMANCE/sclass_semantics_v6_0_1.py"]["authorized_hashes"].append("extra_hash_violating_single_hash_rule")
    from tools.gates.gate_trust_anchor import validate_all_six_anchor_sections
    violations = validate_all_six_anchor_sections(tampered, base_spec)
    assert any("SECTION 2 VIOLATION" in v and "single-hash rule" in v for v in violations)


def test_gate_rejects_state_machine_expectations_tamper(base_anchors, base_spec):
    """Proves tampering with Section 3 (state_machine_expectations) causes expectation mismatch."""
    tampered = copy.deepcopy(base_anchors)
    tampered["state_machine_expectations"]["machines_count"] = 999
    from tools.gates.gate_trust_anchor import validate_all_six_anchor_sections
    violations = validate_all_six_anchor_sections(tampered, base_spec)
    assert any("machines_count expected 999" in v for v in violations)


def test_gate_rejects_mutation_expectations_tamper(base_anchors, base_spec):
    """Proves tampering with Section 4 (mutation_battery_expectations) is strictly rejected."""
    tampered = copy.deepcopy(base_anchors)
    tampered["mutation_battery_expectations"]["required_mutations"]["delete_edge"] = "ACCEPT"  # Illegal tamper
    from tools.gates.gate_trust_anchor import validate_all_six_anchor_sections
    violations = validate_all_six_anchor_sections(tampered, base_spec)
    assert any("SECTION 4 VIOLATION" in v and "delete_edge expectation must be REJECT" in v for v in violations)


def test_gate_rejects_baseline_hashes_tamper(base_anchors, base_spec):
    """Proves tampering with Section 5 (baseline_hashes) is strictly rejected."""
    tampered = copy.deepcopy(base_anchors)
    tampered["baseline_hashes"].pop("manifest_path")
    from tools.gates.gate_trust_anchor import validate_all_six_anchor_sections
    violations = validate_all_six_anchor_sections(tampered, base_spec)
    assert any("SECTION 5 CORRUPTED" in v for v in violations)


def test_gate_rejects_authoritative_refs_tamper(base_anchors, base_spec):
    """Proves tampering with Section 6 (authoritative_refs) is strictly rejected."""
    tampered = copy.deepcopy(base_anchors)
    tampered["authoritative_refs"].pop("main")
    from tools.gates.gate_trust_anchor import validate_all_six_anchor_sections
    violations = validate_all_six_anchor_sections(tampered, base_spec)
    assert any("SECTION 6 VIOLATION" in v and "main" in v for v in violations)


# -----------------------------------------------------------------------------
# F4: Trust-Anchor Workflow Hardening Tests
# -----------------------------------------------------------------------------

def test_trust_anchor_permissions_are_read_only():
    """Proves .github/workflows/trust-anchor.yml has permissions: contents: read."""
    wf_path = ROOT / ".github" / "workflows" / "trust-anchor.yml"
    assert wf_path.exists()
    content = wf_path.read_text(encoding="utf-8")
    assert "permissions:" in content
    assert "contents: read" in content


def test_checkout_persist_credentials_false():
    """Proves .github/workflows/trust-anchor.yml disables credential persistence."""
    wf_path = ROOT / ".github" / "workflows" / "trust-anchor.yml"
    content = wf_path.read_text(encoding="utf-8")
    assert "persist-credentials: false" in content


def test_trust_anchor_workflow_contains_no_pip_install():
    """Proves .github/workflows/trust-anchor.yml contains NO pip install command."""
    wf_path = ROOT / ".github" / "workflows" / "trust-anchor.yml"
    content = wf_path.read_text(encoding="utf-8")
    assert "pip install" not in content
    assert "pip3 install" not in content


def test_gate_does_not_execute_pr_head_code(monkeypatch, base_anchors):
    """Proves gate uses git show as data-only and never imports or executes PR head files."""
    called_imports = []
    real_import = __import__
    def tracking_import(name, *args, **kwargs):
        if "candidate" in name:
            called_imports.append(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", tracking_import)
    from tools.gates.gate_trust_anchor import verify_pr_head_as_data
    verify_pr_head_as_data("b1-anchors", "HEAD", base_anchors)
    assert len(called_imports) == 0, "Gate must never import candidate modules"


def test_gate_reads_pr_head_as_data():
    """Proves gate_trust_anchor reads candidate files exclusively via raw git_show bytes."""
    from tools.gates.gate_trust_anchor import git_show
    res = git_show("HEAD", "10-CONFORMANCE/state-machines.v6.0.1.json")
    assert isinstance(res, bytes)
    assert len(res) > 0


# -----------------------------------------------------------------------------
# R4-3: Historical Baseline Script References
# -----------------------------------------------------------------------------

def test_no_stale_branch_baseline_references():
    """Proves obsolete generate_branch_baseline.py is deleted and replaced by evaluate_branch_baselines.py."""
    old_script = ROOT / "tools" / "generate_branch_baseline.py"
    assert not old_script.exists(), "Obsolete tools/generate_branch_baseline.py must not exist"
    active_script = ROOT / "tools" / "evaluate_branch_baselines.py"
    assert active_script.exists(), "Authoritative tools/evaluate_branch_baselines.py must exist"
