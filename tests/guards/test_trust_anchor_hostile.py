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
import shutil
import subprocess
import sys
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
# F3: Six-Section Anchor Tamper Tests (Real Subprocess in Isolated Repositories)
# -----------------------------------------------------------------------------

def _setup_tmp_base_repo(repo_dir: Path, tamper_fn=None) -> Path:
    """Creates a real independent temporary git base repository on disk."""
    repo_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=str(repo_dir), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test Runner"], cwd=str(repo_dir), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(repo_dir), check=True, capture_output=True)

    gov_dir = repo_dir / "governance"
    gov_dir.mkdir(parents=True, exist_ok=True)
    anchors = json.loads((ROOT / "governance" / "TRUST-ANCHORS.json").read_text(encoding="utf-8"))
    if tamper_fn:
        tamper_fn(anchors)
    (gov_dir / "TRUST-ANCHORS.json").write_text(json.dumps(anchors, indent=2), encoding="utf-8")

    conf_dir = repo_dir / "10-CONFORMANCE"
    conf_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / "10-CONFORMANCE" / "state-machines.v6.0.1.json", conf_dir / "state-machines.v6.0.1.json")

    subprocess.run(["git", "add", "."], cwd=str(repo_dir), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "base commit"], cwd=str(repo_dir), check=True, capture_output=True)
    return repo_dir


def _execute_gate_subprocess(repo: Path, base_ref: str = "HEAD", pr_head: str = "HEAD") -> subprocess.CompletedProcess:
    """Executes the actual gate_trust_anchor.py CLI against the base repository."""
    gate_script = ROOT / "tools" / "gates" / "gate_trust_anchor.py"
    cmd = [
        sys.executable,
        str(gate_script),
        "--base-ref", base_ref,
        "--pr-head", pr_head,
        "--anchors-file", "governance/TRUST-ANCHORS.json",
        "--repo-root", str(repo),
    ]
    return subprocess.run(cmd, cwd=str(repo), capture_output=True, text=True)


def test_gate_rejects_package_original_hash_tamper(tmp_path):
    """Proves tampering with Section 1 (package_original_hashes) in real git repo is rejected."""
    # 1. Tampered base repo
    tampered_repo = _setup_tmp_base_repo(
        tmp_path / "repo1_tampered",
        tamper_fn=lambda a: a["package_original_hashes"].pop("00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md"),
    )
    res_tampered = _execute_gate_subprocess(tampered_repo)
    assert res_tampered.returncode != 0
    assert "TRUST ANCHORS SECTION 1 CORRUPTED" in res_tampered.stdout

    # 2. Unmodified clean base repo passes
    clean_repo = _setup_tmp_base_repo(tmp_path / "repo1_clean")
    res_clean = _execute_gate_subprocess(clean_repo)
    assert res_clean.returncode == 0
    assert "TRUST ANCHOR GATE: ACCEPTED" in res_clean.stdout


def test_gate_rejects_authorized_errata_tamper(tmp_path):
    """Proves tampering with Section 2 (authorized_errata) in real git repo violates single-hash rule."""
    tampered_repo = _setup_tmp_base_repo(
        tmp_path / "repo2_tampered",
        tamper_fn=lambda a: a["authorized_errata"]["10-CONFORMANCE/sclass_semantics_v6_0_1.py"]["authorized_hashes"].append("extra_hash_violating_single_hash_rule"),
    )
    res = _execute_gate_subprocess(tampered_repo)
    assert res.returncode != 0
    assert "TRUST ANCHORS SECTION 2 VIOLATION" in res.stdout
    assert "single-hash rule" in res.stdout


def test_gate_rejects_state_machine_expectations_tamper(tmp_path):
    """Proves tampering with Section 3 (state_machine_expectations) in real git repo is rejected."""
    def _tamper(a):
        a["state_machine_expectations"]["machines_count"] = 999

    tampered_repo = _setup_tmp_base_repo(tmp_path / "repo3_tampered", tamper_fn=_tamper)
    res = _execute_gate_subprocess(tampered_repo)
    assert res.returncode != 0
    assert "machines_count expected 999" in res.stdout


def test_gate_rejects_mutation_expectations_tamper(tmp_path):
    """Proves tampering with Section 4 (mutation_battery_expectations) in real git repo is rejected."""
    def _tamper(a):
        a["mutation_battery_expectations"]["required_mutations"]["delete_edge"] = "ACCEPT"

    tampered_repo = _setup_tmp_base_repo(tmp_path / "repo4_tampered", tamper_fn=_tamper)
    res = _execute_gate_subprocess(tampered_repo)
    assert res.returncode != 0
    assert "SECTION 4 VIOLATION" in res.stdout
    assert "delete_edge expectation must be REJECT" in res.stdout


def test_gate_rejects_baseline_hashes_tamper(tmp_path):
    """Proves tampering with Section 5 (baseline_hashes) in real git repo is rejected."""
    tampered_repo = _setup_tmp_base_repo(
        tmp_path / "repo5_tampered",
        tamper_fn=lambda a: a["baseline_hashes"].pop("manifest_path"),
    )
    res = _execute_gate_subprocess(tampered_repo)
    assert res.returncode != 0
    assert "TRUST ANCHORS SECTION 5 CORRUPTED" in res.stdout


def test_gate_rejects_authoritative_refs_tamper(tmp_path):
    """Proves tampering with Section 6 (authoritative_refs) in real git repo is rejected."""
    tampered_repo = _setup_tmp_base_repo(
        tmp_path / "repo6_tampered",
        tamper_fn=lambda a: a["authoritative_refs"].pop("main"),
    )
    res = _execute_gate_subprocess(tampered_repo)
    assert res.returncode != 0
    assert "TRUST ANCHORS SECTION 6 VIOLATION" in res.stdout
    assert "main" in res.stdout


def test_gate_accepts_clean_base(tmp_path):
    """Proves clean, unmodified base anchors pass gate_trust_anchor.py with exit code 0."""
    clean_repo = _setup_tmp_base_repo(tmp_path / "repo_clean")
    res = _execute_gate_subprocess(clean_repo)
    assert res.returncode == 0
    assert "TRUST ANCHOR GATE: ACCEPTED" in res.stdout


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
        if "candidate" in name or "reference_impl" in name:
            called_imports.append(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", tracking_import)
    from tools.gates.gate_trust_anchor import verify_pr_head_as_data, GIT_BIN
    base_candidates = ["origin/integration-r30-b1", "integration-r30-b1", "HEAD~1", "HEAD"]
    base_ref = "HEAD"
    for cand in base_candidates:
        if subprocess.run([GIT_BIN, "rev-parse", "--verify", cand], cwd=str(ROOT), capture_output=True).returncode == 0:
            base_ref = cand
            break
    verify_pr_head_as_data(base_ref, "HEAD", base_anchors)
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
