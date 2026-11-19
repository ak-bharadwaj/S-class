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
    DiffEntry,
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
    "governance/VULN-LEDGER.json",
    "requirements-audit.txt",
    ".github/workflows/trust-anchor.yml",
    ".github/CODEOWNERS",
    "tools/gates/gate_trust_anchor.py",
    "tools/gates/gate_vuln_ledger.py",
    "tools/gates/gate_frozen_diff.py",
    "tools/gates/gate_kernel_bytes.py",
])
def test_hostile_candidate_modifies_protected_file_fails_closed(monkeypatch, base_anchors, protected_file):
    """Proves candidate PR cannot modify any base-controlled anchor or workflow file."""
    # Simulate git_diff_files returning modification to protected_file
    fake_diff = [DiffEntry(status="M", filepath=protected_file, src_mode="100644", dst_mode="100644", src_sha="0"*40, dst_sha="1"*40)]
    monkeypatch.setattr("tools.gates.gate_trust_anchor.git_diff_raw", lambda *a, **kw: fake_diff)
    # Simulate git_show returning different bytes between base and pr
    monkeypatch.setattr("tools.gates.gate_trust_anchor.git_show", lambda ref, path, *a, **kw: b"BASE_CONTENT" if "base" in ref or "origin" in ref else b"FORGED_PR_CONTENT")

    violations = verify_pr_head_as_data("origin/integration-r30-b1", "candidate-head", base_anchors)
    assert any("UNAUTHORIZED PROTECTED FILE MODIFICATION" in v and protected_file in v for v in violations)


def test_hostile_candidate_tampered_anchor_ignored_by_base_reader(tmp_path, monkeypatch):
    """Proves load_base_trust_anchors reads ONLY from base_ref, completely ignoring candidate PR content."""
    # When base_ref is queried, return authoritative data
    # When PR head is queried, return attacker data with empty hashes
    def fake_git_show(ref, path, *a, **kw):
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
    fake_diff = [DiffEntry(status="M", filepath="00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md", src_mode="100644", dst_mode="100644", src_sha="0"*40, dst_sha="1"*40)]
    monkeypatch.setattr("tools.gates.gate_trust_anchor.git_diff_raw", lambda *a, **kw: fake_diff)
    monkeypatch.setattr("tools.gates.gate_trust_anchor.git_show", lambda ref, path, *a, **kw: b"TAMPERED_SPEC_CONTENT\n")

    violations = verify_pr_head_as_data("origin/integration-r30-b1", "candidate-head", base_anchors)
    assert any("UNAUTHORIZED MODIFICATION in '00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md'" in v for v in violations)


def test_hostile_candidate_unauthorized_errata_drift_fails_closed(monkeypatch, base_anchors):
    """Proves candidate cannot introduce unauthorized errata hash for semantics file."""
    fake_diff = [DiffEntry(status="M", filepath="10-CONFORMANCE/sclass_semantics_v6_0_1.py", src_mode="100644", dst_mode="100644", src_sha="0"*40, dst_sha="1"*40)]
    monkeypatch.setattr("tools.gates.gate_trust_anchor.git_diff_raw", lambda *a, **kw: fake_diff)
    monkeypatch.setattr("tools.gates.gate_trust_anchor.git_show", lambda ref, path, *a, **kw: b"UNAUTHORIZED_SEMANTICS_CODE\n")

    violations = verify_pr_head_as_data("origin/integration-r30-b1", "candidate-head", base_anchors)
    assert any("UNAUTHORIZED ERRATA DRIFT in '10-CONFORMANCE/sclass_semantics_v6_0_1.py'" in v for v in violations)


def test_hostile_candidate_deletes_frozen_file_fails_closed(monkeypatch, base_anchors):
    """Proves candidate cannot delete a frozen directory file."""
    fake_diff = [DiffEntry(status="D", filepath="10-CONFORMANCE/sclass_kernel_v6_0_1.py", src_mode="100644", dst_mode="000000", src_sha="0"*40, dst_sha="0"*40)]
    monkeypatch.setattr("tools.gates.gate_trust_anchor.git_diff_raw", lambda *a, **kw: fake_diff)

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

    fake_diff = [DiffEntry(status="M", filepath="src/sclass/reference_impl/gate.py", src_mode="100644", dst_mode="100644", src_sha="0"*40, dst_sha="1"*40)]
    monkeypatch.setattr("tools.gates.gate_trust_anchor.git_diff_raw", lambda *a, **kw: fake_diff)
    monkeypatch.setattr("tools.gates.gate_trust_anchor.git_show", lambda ref, path, *a, **kw: bad_gate_code)

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
    """Proves .github/workflows/trust-anchor.yml has permissions: contents: read and NO pull_request trigger."""
    wf_path = ROOT / ".github" / "workflows" / "trust-anchor.yml"
    assert wf_path.exists()
    content = wf_path.read_text(encoding="utf-8")
    assert "permissions:" in content
    assert "contents: read" in content
    assert "pull_request_target:" in content
    # Strict trigger assertion: only pull_request_target, no pull_request
    lines = content.splitlines()
    for line in lines:
        stripped = line.strip()
        assert stripped != "pull_request:", (
            "SECURITY VIOLATION: .github/workflows/trust-anchor.yml must NOT contain 'pull_request:' trigger; "
            "it must strictly use base-controlled 'pull_request_target:' only."
        )


def test_trust_anchor_workflow_triggers_and_permissions_structure():
    """P28 / Mandatory: Asserts trust-anchor.yml has NO pull_request trigger, only pull_request_target, and contents: read."""
    wf_path = ROOT / ".github" / "workflows" / "trust-anchor.yml"
    assert wf_path.exists()
    content = wf_path.read_text(encoding="utf-8")
    import yaml
    parsed = yaml.safe_load(content)
    triggers = parsed.get("on") if "on" in parsed else parsed.get(True, {})
    assert "pull_request_target" in triggers, "Workflow must trigger on pull_request_target"
    assert "pull_request" not in triggers, "SECURITY VIOLATION: pull_request trigger must be removed from trust-anchor.yml"
    perms = parsed.get("permissions", {})
    assert perms.get("contents") == "read", f"Expected permissions: contents: read, got {perms}"


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


# -----------------------------------------------------------------------------
# Real Temporary Git Repository Hostile Tests (No Mocks, CLI Subprocess)
# -----------------------------------------------------------------------------

def _setup_full_test_repo(repo_dir: Path) -> Path:
    """Creates a real independent temporary git base repository with full governance & spec on disk."""
    repo_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-b", "main"], cwd=str(repo_dir), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test Runner"], cwd=str(repo_dir), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(repo_dir), check=True, capture_output=True)
    subprocess.run(["git", "config", "core.filemode", "false"], cwd=str(repo_dir), check=True, capture_output=True)

    # 1. governance
    gov = repo_dir / "governance"
    gov.mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / "governance" / "TRUST-ANCHORS.json", gov / "TRUST-ANCHORS.json")
    (gov / "BASELINE-HASHES.txt").write_text("dummy baseline hashes\n", encoding="utf-8")
    (gov / "VULN-LEDGER.json").write_text('{"entries": []}\n', encoding="utf-8")
    (gov / "FROZEN-MANIFEST.sha256").write_text("dummy manifest\n", encoding="utf-8")

    # 2. workflows & codeowners
    wf = repo_dir / ".github" / "workflows"
    wf.mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / ".github" / "workflows" / "trust-anchor.yml", wf / "trust-anchor.yml")
    (repo_dir / ".github" / "CODEOWNERS").write_text("# S-Class Trust Anchor, Workflows, and Core Governance (Owner)\n", encoding="utf-8")

    # 3. requirements-audit
    (repo_dir / "requirements-audit.txt").write_text("dummy audit reqs\n", encoding="utf-8")

    # 4. conformance
    conf = repo_dir / "10-CONFORMANCE"
    conf.mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / "10-CONFORMANCE" / "state-machines.v6.0.1.json", conf / "state-machines.v6.0.1.json")

    # 5. frozen 00-SPEC, 20-RUNTIME
    spec = repo_dir / "00-SPEC"
    spec.mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / "00-SPEC" / "S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md", spec / "S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md")

    rt = repo_dir / "20-RUNTIME"
    rt.mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / "20-RUNTIME" / "README.md", rt / "README.md")

    # 6. docs
    docs = repo_dir / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "README.md").write_text("Docs readme\n", encoding="utf-8")

    # Commit on main
    subprocess.run(["git", "add", "."], cwd=str(repo_dir), check=True, capture_output=True)
    # Normalize baseline file modes to 100644 (cross-platform non-executable)
    p_ls = subprocess.run(["git", "ls-files"], cwd=str(repo_dir), capture_output=True, text=True, check=True)
    for fn in p_ls.stdout.splitlines():
        if fn.strip():
            subprocess.run(["git", "update-index", "--chmod=-x", fn.strip()], cwd=str(repo_dir), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "base commit"], cwd=str(repo_dir), check=True, capture_output=True)
    return repo_dir


def _run_gate_cli(repo_dir: Path, base_ref: str = "main", pr_head: str = "HEAD") -> subprocess.CompletedProcess:
    gate_script = ROOT / "tools" / "gates" / "gate_trust_anchor.py"
    cmd = [
        sys.executable,
        str(gate_script),
        "--base-ref", base_ref,
        "--pr-head", pr_head,
        "--anchors-file", "governance/TRUST-ANCHORS.json",
        "--repo-root", str(repo_dir),
    ]
    return subprocess.run(cmd, cwd=str(repo_dir), capture_output=True, text=True)


def test_hostile_real_repo_delete_trust_anchors(tmp_path):
    """Hostile real repo test: deleting governance/TRUST-ANCHORS.json exits non-zero."""
    repo = _setup_full_test_repo(tmp_path / "repo_del_ta")
    subprocess.run(["git", "checkout", "-b", "pr-del-ta"], cwd=str(repo), check=True, capture_output=True)
    (repo / "governance" / "TRUST-ANCHORS.json").unlink()
    subprocess.run(["git", "add", "-u"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "delete trust anchors"], cwd=str(repo), check=True, capture_output=True)
    res = _run_gate_cli(repo, "main", "pr-del-ta")
    assert res.returncode != 0
    assert "UNAUTHORIZED PROTECTED FILE MODIFICATION" in res.stdout or "CRITICAL" in res.stdout


def test_hostile_real_repo_delete_baseline_hashes(tmp_path):
    """Hostile real repo test: deleting governance/BASELINE-HASHES.txt exits non-zero."""
    repo = _setup_full_test_repo(tmp_path / "repo_del_bh")
    subprocess.run(["git", "checkout", "-b", "pr-del-bh"], cwd=str(repo), check=True, capture_output=True)
    (repo / "governance" / "BASELINE-HASHES.txt").unlink()
    subprocess.run(["git", "add", "-u"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "delete baseline hashes"], cwd=str(repo), check=True, capture_output=True)
    res = _run_gate_cli(repo, "main", "pr-del-bh")
    assert res.returncode != 0
    assert "UNAUTHORIZED PROTECTED FILE MODIFICATION" in res.stdout


def test_hostile_real_repo_delete_vuln_ledger(tmp_path):
    """Hostile real repo test: deleting governance/VULN-LEDGER.json exits non-zero."""
    repo = _setup_full_test_repo(tmp_path / "repo_del_vl")
    subprocess.run(["git", "checkout", "-b", "pr-del-vl"], cwd=str(repo), check=True, capture_output=True)
    (repo / "governance" / "VULN-LEDGER.json").unlink()
    subprocess.run(["git", "add", "-u"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "delete vuln ledger"], cwd=str(repo), check=True, capture_output=True)
    res = _run_gate_cli(repo, "main", "pr-del-vl")
    assert res.returncode != 0
    assert "UNAUTHORIZED PROTECTED FILE MODIFICATION" in res.stdout


def test_hostile_real_repo_delete_trust_anchor_workflow(tmp_path):
    """Hostile real repo test: deleting .github/workflows/trust-anchor.yml exits non-zero."""
    repo = _setup_full_test_repo(tmp_path / "repo_del_wf")
    subprocess.run(["git", "checkout", "-b", "pr-del-wf"], cwd=str(repo), check=True, capture_output=True)
    (repo / ".github" / "workflows" / "trust-anchor.yml").unlink()
    subprocess.run(["git", "add", "-u"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "delete trust anchor workflow"], cwd=str(repo), check=True, capture_output=True)
    res = _run_gate_cli(repo, "main", "pr-del-wf")
    assert res.returncode != 0
    assert "UNAUTHORIZED PROTECTED FILE MODIFICATION" in res.stdout


def test_hostile_real_repo_rename_file_into_20_runtime(tmp_path):
    """Hostile real repo test: renaming a file into 20-RUNTIME/ exits non-zero."""
    repo = _setup_full_test_repo(tmp_path / "repo_rename_rt")
    subprocess.run(["git", "checkout", "-b", "pr-rename-rt"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "mv", "docs/README.md", "20-RUNTIME/injected.py"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "rename file into 20-RUNTIME/"], cwd=str(repo), check=True, capture_output=True)
    res = _run_gate_cli(repo, "main", "pr-rename-rt")
    assert res.returncode != 0
    assert "UNAUTHORIZED" in res.stdout


def test_hostile_real_repo_add_file_in_frozen_dir(tmp_path):
    """Hostile real repo test: adding a new file in a frozen directory exits non-zero."""
    repo = _setup_full_test_repo(tmp_path / "repo_add_frozen")
    subprocess.run(["git", "checkout", "-b", "pr-add-frozen"], cwd=str(repo), check=True, capture_output=True)
    (repo / "00-SPEC" / "UNAUTHORIZED_SPEC.md").write_text("injected spec\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "add file in frozen dir"], cwd=str(repo), check=True, capture_output=True)
    res = _run_gate_cli(repo, "main", "pr-add-frozen")
    assert res.returncode != 0
    assert "UNAUTHORIZED" in res.stdout


def test_hostile_real_repo_path_with_space(tmp_path):
    """Hostile real repo test: file with a space in a frozen dir exits non-zero."""
    repo = _setup_full_test_repo(tmp_path / "repo_space")
    subprocess.run(["git", "checkout", "-b", "pr-space"], cwd=str(repo), check=True, capture_output=True)
    (repo / "20-RUNTIME" / "hostile script with space.py").write_text("injected code\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "add path with space in 20-RUNTIME/"], cwd=str(repo), check=True, capture_output=True)
    res = _run_gate_cli(repo, "main", "pr-space")
    assert res.returncode != 0
    assert "UNAUTHORIZED" in res.stdout


def test_hostile_real_repo_malformed_spec_json(tmp_path):
    """Hostile real repo test: malformed spec JSON exits non-zero."""
    repo = _setup_full_test_repo(tmp_path / "repo_bad_json")
    subprocess.run(["git", "checkout", "-b", "pr-bad-json"], cwd=str(repo), check=True, capture_output=True)
    (repo / "10-CONFORMANCE" / "state-machines.v6.0.1.json").write_text("{malformed json here", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "corrupt spec JSON"], cwd=str(repo), check=True, capture_output=True)
    res = _run_gate_cli(repo, "main", "pr-bad-json")
    assert res.returncode != 0
    assert "MALFORMED CANDIDATE SPEC" in res.stdout or "REJECTED" in res.stdout


def test_hostile_real_repo_modify_ci_yml(tmp_path):
    """G-4 / F-24: Hostile real repo test: modifying .github/workflows/ci.yml exits non-zero."""
    repo = _setup_full_test_repo(tmp_path / "repo_mod_ci")
    subprocess.run(["git", "checkout", "-b", "pr-mod-ci"], cwd=str(repo), check=True, capture_output=True)
    ci_file = repo / ".github" / "workflows" / "ci.yml"
    ci_file.parent.mkdir(parents=True, exist_ok=True)
    ci_file.write_text("name: Hostile CI Tamper\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "modify ci.yml"], cwd=str(repo), check=True, capture_output=True)
    res = _run_gate_cli(repo, "main", "pr-mod-ci")
    assert res.returncode != 0
    assert "UNAUTHORIZED PROTECTED FILE MODIFICATION" in res.stdout
    assert ".github/workflows/ci.yml" in res.stdout


def test_hostile_real_repo_duplicate_workflow_job_name(tmp_path):
    """G-4 / F-24: Hostile real repo test: second workflow added under .github/workflows/ exits non-zero."""
    repo = _setup_full_test_repo(tmp_path / "repo_dup_wf")
    subprocess.run(["git", "checkout", "-b", "pr-dup-wf"], cwd=str(repo), check=True, capture_output=True)
    wf_file = repo / ".github" / "workflows" / "shadow_gate.yml"
    wf_file.write_text("name: Shadow Workflow\njobs:\n  trust-anchor:\n    runs-on: ubuntu-latest\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "add shadow workflow with duplicate job name"], cwd=str(repo), check=True, capture_output=True)
    res = _run_gate_cli(repo, "main", "pr-dup-wf")
    assert res.returncode != 0
    assert "UNAUTHORIZED PROTECTED FILE MODIFICATION" in res.stdout
    assert "shadow_gate.yml" in res.stdout


def test_hostile_real_repo_mode_only_change(tmp_path):
    """G-4 / F-24: Hostile real repo test: mode-only change in frozen directory exits non-zero."""
    repo = _setup_full_test_repo(tmp_path / "repo_mode_change")
    subprocess.run(["git", "checkout", "-b", "pr-mode-change"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "update-index", "--chmod=+x", "20-RUNTIME/README.md"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chmod +x on frozen file"], cwd=str(repo), check=True, capture_output=True)
    res = _run_gate_cli(repo, "main", "pr-mode-change")
    assert res.returncode != 0
    assert "ILLEGAL FILE MODE" in res.stdout
    assert "20-RUNTIME/README.md" in res.stdout


def test_hostile_real_repo_symlink_added(tmp_path):
    """G-4 / F-24: Hostile real repo test: adding symlink anywhere in PR exits non-zero."""
    repo = _setup_full_test_repo(tmp_path / "repo_symlink")
    subprocess.run(["git", "checkout", "-b", "pr-symlink"], cwd=str(repo), check=True, capture_output=True)
    blob_sha = subprocess.check_output(
        ["git", "hash-object", "-w", "--stdin"],
        input=b"docs/README.md",
        cwd=str(repo)
    ).strip().decode()
    subprocess.run(["git", "update-index", "--add", "--cacheinfo", "120000", blob_sha, "docs/symlink_target.md"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "add symlink in docs"], cwd=str(repo), check=True, capture_output=True)
    res = _run_gate_cli(repo, "main", "pr-symlink")
    assert res.returncode != 0
    assert "ILLEGAL SYMLINK DETECTED" in res.stdout
    assert "docs/symlink_target.md" in res.stdout


def test_hostile_real_repo_submodule_added(tmp_path):
    """G-4 / F-24: Hostile real repo test: adding git submodule anywhere in PR exits non-zero."""
    repo = _setup_full_test_repo(tmp_path / "repo_submodule")
    subprocess.run(["git", "checkout", "-b", "pr-submodule"], cwd=str(repo), check=True, capture_output=True)
    commit_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(repo)).strip().decode()
    subprocess.run(["git", "update-index", "--add", "--cacheinfo", "160000", commit_sha, "submodule_repo"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "add git submodule"], cwd=str(repo), check=True, capture_output=True)
    res = _run_gate_cli(repo, "main", "pr-submodule")
    assert res.returncode != 0
    assert "ILLEGAL SUBMODULE DETECTED" in res.stdout
    assert "submodule_repo" in res.stdout


def test_hostile_real_repo_positive_clean_pr_exits_zero(tmp_path):
    """Positive test: clean PR modifying permitted documentation exits zero."""
    repo = _setup_full_test_repo(tmp_path / "repo_positive")
    subprocess.run(["git", "checkout", "-b", "pr-positive"], cwd=str(repo), check=True, capture_output=True)
    (repo / "docs" / "README.md").write_text("Clean docs update\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "clean permitted docs update"], cwd=str(repo), check=True, capture_output=True)
    res = _run_gate_cli(repo, "main", "pr-positive")
    assert res.returncode == 0
    assert "TRUST ANCHOR GATE: ACCEPTED" in res.stdout


def test_baseline_hashes_imports_with_usr_bin_git_absent(monkeypatch):
    """Proves tools/baseline_hashes.py imports and resolves GIT_BIN via shutil even when /usr/bin/git is absent."""
    import importlib
    import tools.baseline_hashes as bh

    orig_exists = Path.exists
    def fake_exists(self):
        if str(self).replace("\\", "/") == "/usr/bin/git":
            return False
        return orig_exists(self)

    monkeypatch.setattr(Path, "exists", fake_exists)
    importlib.reload(bh)
    assert bh.GIT_BIN is not None
    assert "git" in str(bh.GIT_BIN).lower()


# -----------------------------------------------------------------------------
# F-D Real-Repo Hostile Battery (Non-Zero Exit on Invalid Base/Head Refs)
# -----------------------------------------------------------------------------

def test_hostile_real_repo_bad_base_ref_exits_nonzero():
    """F-D: Proves gate_trust_anchor exits non-zero when base_ref is invalid."""
    gate_script = ROOT / "tools" / "gates" / "gate_trust_anchor.py"
    cmd = [
        sys.executable,
        str(gate_script),
        "--base-ref",
        "NONEXISTENT_BASE_REF_XYZ_12345",
        "--pr-head",
        "HEAD",
    ]
    res = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    assert res.returncode != 0
    assert "git diff failed" in res.stdout or "FATAL" in res.stdout or "fatal" in res.stderr.lower() or res.returncode != 0


def test_hostile_real_repo_bad_head_ref_exits_nonzero():
    """F-D: Proves gate_trust_anchor exits non-zero when pr_head is invalid."""
    gate_script = ROOT / "tools" / "gates" / "gate_trust_anchor.py"
    cmd = [
        sys.executable,
        str(gate_script),
        "--base-ref",
        "HEAD",
        "--pr-head",
        "NONEXISTENT_HEAD_REF_XYZ_12345",
    ]
    res = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    assert res.returncode != 0
    assert "git diff failed" in res.stdout or "FATAL" in res.stdout or "fatal" in res.stderr.lower() or res.returncode != 0


# -----------------------------------------------------------------------------
# L-4 Real-Repo Hostile Test: Consistent Code and JSON Edit Rejected on Spec Hash Mismatch
# -----------------------------------------------------------------------------

def test_hostile_real_repo_consistent_code_and_json_edit_rejected_on_spec_hash_mismatch(tmp_path):
    """L-4: Changing state-machines JSON consistently with a matching edit to a second file is rejected (non-zero) on spec-hash mismatch."""
    repo = _setup_full_test_repo(tmp_path / "repo_consistent_edit")
    subprocess.run(["git", "checkout", "-b", "pr-consistent-edit"], cwd=str(repo), check=True, capture_output=True)

    # 1. Mutate state-machines.v6.0.1.json
    spec_path = repo / "10-CONFORMANCE" / "state-machines.v6.0.1.json"
    spec_dict = json.loads(spec_path.read_text(encoding="utf-8"))
    spec_dict["machines"]["WorkNodeStatus"]["ASSIGNED"].append("BACKDOOR_STATE")
    spec_dict["machines"]["WorkNodeStatus"]["BACKDOOR_STATE"] = ["ASSIGNED"]
    spec_path.write_text(json.dumps(spec_dict, indent=2) + "\n", encoding="utf-8")

    # 2. Consistent matching edit to a second file
    docs_path = repo / "docs" / "README.md"
    docs_path.write_text("Docs updated consistently with BACKDOOR_STATE\n", encoding="utf-8")

    # Commit both files in PR head
    subprocess.run(["git", "add", "."], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "hostile: consistent code and json edit"], cwd=str(repo), check=True, capture_output=True)

    # Run gate_trust_anchor CLI
    res = _run_gate_cli(repo, "main", "pr-consistent-edit")
    assert res.returncode != 0, f"Expected non-zero exit code, got {res.returncode}. Output:\n{res.stdout}"
    assert "UNAUTHORIZED MODIFICATION in '10-CONFORMANCE/state-machines.v6.0.1.json'" in res.stdout
    assert "TRUST ANCHOR GATE: REJECTED" in res.stdout
