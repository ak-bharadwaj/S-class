#!/usr/bin/env python3
"""T8 Final Self-Verification Gate for Block 3 (S2 Qualification Factory + Debt)."""
from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys
from typing import Dict, List, Tuple

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
for _p in (REPO_ROOT, REPO_ROOT / "src", REPO_ROOT / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from sclass.product.oss_qualification_playbook import OSS_QUALIFICATION_FIELDS
from sclass.product.registry_table import REGISTRY_TABLE_ROWS
from sclass.qualification.adapter_registry import load_qualified_adapters
from sclass.qualification.record_generator import verify_qualification_record

EXPECTED_MASTER_SHA256 = "340db97857a7716b1aac2c1b44bc60b32642e3d8074d02720c2333cea278b4ff"

FROZEN_13: Dict[str, str] = {
    "00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md": "53c02b13085dc3e1dcf75b9e8c306704d83bf37175b73a6be1a4b6ab7823ebb1",
    "10-CONFORMANCE/c1-vectors.v6.0.1.json": "db58744d9829f7cac2ec7715a93d30d20a0d9ba6912d01f563504564e85b2da8",
    "10-CONFORMANCE/c1_independent.js": "3d70c4791c63d8c6d1dc2724fac5012424067a2c0dd39f6432c1edf0af1abcec",
    "10-CONFORMANCE/coverage-map.v6.0.1.json": "722893054b29448238cb7cca5a149b6262d3cc606a4aeb2711c91e45a7dd6a20",
    "10-CONFORMANCE/sclass_kernel_v6_0_1.py": "d0f8f124dd55aab5cfb68d8c7d644eccf2694f52016c2e4a2132e6d6cef5575c",
    "10-CONFORMANCE/sclass_semantics_v6_0_1.py": "7ecc935246b057a3414faa3cfce36daa4f1be2a198c8265cb224990052064592",
    "10-CONFORMANCE/spec_integrity.py": "c3c68772e2b4ae2a945d88c9cb71e2609d5626541f7bfacbc1294e628a384932",
    "10-CONFORMANCE/state-machines.v6.0.1.json": "24f159e6f72179ea66365b585f085727f6ef48420a09eae8c6024cb0bb51fdad",
    "10-CONFORMANCE/test_sclass_v6_0_1_conformance.py": "ca4dafd9ab75096e9d92a3b15fbbac8693d03c172da444847657d42fd3b79158",
    "20-RUNTIME/README.md": "254c1a31d9a10a308c96d9c9212c487168c690f269c156bc3076b3ffdf19901f",
    "20-RUNTIME/requirements.txt": "ceeace8d072b469f31ba1a26f2c40677f225d090f76fee996ffe0f7498023c15",
    "20-RUNTIME/sclass_runtime_v6_0_1.py": "c43845feb5e7842ebc81100ed3b7f1be8d4143fa3187978673c37ce614fdefff",
    "20-RUNTIME/test_sclass_runtime_v6_0_1.py": "53d20129e7003c7b19b4bbf62f1f71a68001acfacd4818446063ca58f90b0455",
}

PROTECTED_PATHS = (
    ".github",
    "governance/",
    "tools/gates",
    "tests/guards",
    "docs/KERNEL-CHANGES.md",
    "tools/baseline_hashes.py",
    "tools/evaluate_branch_baselines.py",
)

NAMING_TRAP_PREFIXES = (
    "tools/block3_",
    "tools/b3_",
    "tools/run_b3_",
    "delivery-b4-b9",
)

BLOCK3_MUSTS_9 = (
    "PD-CH2-062",
    "PD-CH3-011",
    "PD-F10-001",
    "PD-F10-002",
    "PD-F10-003",
    "PD-F10-004",
    "PD-F10-005",
    "PD-F10-006",
    "PD-F10-007",
)

T6_EXPECTED_18 = (
    "jsonschema", "pytest", "coverage.py", "mypy", "ripgrep",
    "stdlib-ast", "bandit", "pip-audit", "cyclonedx-bom", "stdlib-unittest",
    "hypothesis", "cosmic-ray", "tree-sitter", "ast-grep", "pyright",
    "gitleaks", "pr-agent", "coderabbit",
)


def _sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_cmd(args: List[str], *, check_zero: bool = True) -> Tuple[int, str]:
    proc = subprocess.run(
        args,
        cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if check_zero and proc.returncode != 0:
        raise AssertionError(
            f"Command failed (rc={proc.returncode}): {' '.join(args)}\n{proc.stdout}"
        )
    return proc.returncode, proc.stdout


def main() -> int:
    print("=== VERIFY BLOCK 3 FINAL ===")

    # 1. Frozen 13/13 + Master SHA-256
    for rel, exp_sha in FROZEN_13.items():
        got = _sha256_file(REPO_ROOT / rel)
        assert got == exp_sha, f"Frozen hash mismatch for {rel}: {got} != {exp_sha}"
    master_sha = _sha256_file(REPO_ROOT / "docs/design/S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md")
    assert master_sha == EXPECTED_MASTER_SHA256, f"Master sha mismatch: {master_sha}"
    print(f"[PASS] Frozen files: {len(FROZEN_13)}/13 verified; Master SHA-256 verified")

    # 2. Protected paths & naming-trap files unchanged vs integration-r30-b1 (if ref exists)
    rc_ref, _ = _run_cmd(["git", "rev-parse", "--verify", "integration-r30-b1"], check_zero=False)
    if rc_ref == 0:
        _, diff_prot = _run_cmd(["git", "diff", "--name-only", "integration-r30-b1", "--", *PROTECTED_PATHS])
        assert not diff_prot.strip(), f"Protected paths modified vs integration-r30-b1:\n{diff_prot}"
        _, diff_all = _run_cmd(["git", "diff", "--name-only", "integration-r30-b1"])
        for rel in diff_all.splitlines():
            for pref in NAMING_TRAP_PREFIXES:
                assert not rel.startswith(pref), f"Naming-trap file modified: {rel}"
        print("[PASS] Protected-path diff empty and naming-trap files untouched vs integration-r30-b1")
    else:
        print("[SKIP] integration-r30-b1 ref absent in shallow CI clone")

    # 3. LF-only (0 CRLF) on Block 3 code, tests, tools, and generated artifacts
    lf_targets: List[pathlib.Path] = []
    for folder, pat in (
        (REPO_ROOT / "src/sclass/qualification", "*.py"),
        (REPO_ROOT / "src/sclass/qualification/schemas", "*.json"),
        (REPO_ROOT / "tests/block3", "*.py"),
        (REPO_ROOT / "product/qualification", "*.json"),
        (REPO_ROOT / "product/qualification/evidence", "*.json"),
        (REPO_ROOT / "product/qualification/records", "*.json"),
        (REPO_ROOT / "product/qualification/transcripts", "*.txt"),
    ):
        if folder.is_dir():
            lf_targets.extend(sorted(folder.glob(pat)))
    for extra in (
        "product/MUST-RESULT-TABLE.csv",
        "product/oss-evidence/sweep/generate_qualification_records.py",
        "product/oss-evidence/sweep/qualification_records_r32.md",
        "src/sclass/product/adapter_diff_spec_anchors.py",
        "src/sclass/product/adapter_qualification_contract.py",
        "src/sclass/product/audit_export.py",
        "src/sclass/product/lifecycle_p5.py",
        "src/sclass/product/lifecycle_p7.py",
        "src/sclass/product/registry.py",
        "src/sclass/product/registry_table.py",
        "tools/audit_negative_branches.py",
        "tools/run_qualification_factory.py",
        "tools/run_td17_fixtures.py",
        "tools/verify_block3_final.py",
    ):
        p = REPO_ROOT / extra
        if p.is_file():
            lf_targets.append(p)
    crlf_hits = [str(p.relative_to(REPO_ROOT)) for p in lf_targets if b"\r" in p.read_bytes()]
    assert not crlf_hits, f"CRLF detected in Block 3 files: {crlf_hits}"
    print(f"[PASS] LF-only (0 CRLF) verified across {len(lf_targets)} Block 3 files")

    # 4. Forbidden hardcoded adapters / caller boolean absent in src/
    src_hits_default: List[str] = []
    for pyf in (REPO_ROOT / "src").rglob("*.py"):
        if "DEFAULT_QUALIFIED_ADAPTERS" in pyf.read_text(encoding="utf-8"):
            src_hits_default.append(str(pyf.relative_to(REPO_ROOT)))
    assert not src_hits_default, f"DEFAULT_QUALIFIED_ADAPTERS still in src: {src_hits_default}"
    reg_src = (REPO_ROOT / "src/sclass/product/registry.py").read_text(encoding="utf-8")
    assert "adapter_qualified" not in reg_src, "adapter_qualified caller boolean still in registry.py"
    adapters = load_qualified_adapters(REPO_ROOT / "product/qualification/qualified_adapters.json")
    assert adapters == {}, f"Expected 0 qualified adapters by default, got {adapters}"
    print("[PASS] DEFAULT_QUALIFIED_ADAPTERS absent in src/, adapter_qualified absent in registry.py, qualified_adapters == {}")

    # 5. All 9 Block 3 MUSTs present in REGISTRY_TABLE_ROWS
    row_map = {r["must_id"]: r for r in REGISTRY_TABLE_ROWS}
    for mid in BLOCK3_MUSTS_9:
        assert mid in row_map, f"Missing Block 3 MUST {mid} in REGISTRY_TABLE_ROWS"
    print(f"[PASS] All 9 Block 3 MUSTs present in REGISTRY_TABLE_ROWS")

    # 6. All 18 qualification records verified with 16 fields and valid record_digest
    for tid in T6_EXPECTED_18:
        rec_p = REPO_ROOT / "product/qualification/records" / f"{tid}.json"
        rec = json.loads(rec_p.read_text(encoding="utf-8"))
        for f in OSS_QUALIFICATION_FIELDS:
            assert f in rec, f"{tid} missing 16-field key {f}"
        ok, msg = verify_qualification_record(rec)
        assert ok, f"{tid} verification failed: {msg}"
    td17 = json.loads((REPO_ROOT / "product/qualification/td17_fixture_results.json").read_text(encoding="utf-8"))
    assert td17["executed_count"] + td17["not_executable_count"] == 129
    assert td17["mismatches"] == []
    print("[PASS] 18 T6 records digest-verified (16 fields) + TD-17 129/129 verified")

    # 7. Run pytest (Block 3 suite + guards + registry completeness + result table regeneration drift + audit export)
    pytest_args = [
        sys.executable, "-m", "pytest", "-q",
        "tests/block3/",
        "tests/guards/",
        "tests/block2/test_registry_completeness.py",
        "tests/block2/test_result_table_outcomes.py",
        "tests/block2/test_audit_export.py",
        "tests/product/test_adapter_qualification_contract.py",
        "tests/product/test_block4_9_integration.py",
        "tests/product/test_lifecycle_p5.py",
        "tests/product/test_lifecycle_p7.py",
    ]
    if sys.platform == "win32":
        # Windows Application Control blocks unsigned pip.exe shims inside %TEMP% venvs (WinError 4551);
        # sandbox_runner uses `python -m pip`, and Linux CI runs full un-ignored tests/guards/.
        pytest_args.append("--ignore=tests/guards/test_offline_install_guard.py")
        print("[ENV-WIN32] Ignoring tests/guards/test_offline_install_guard.py locally (WinError 4551 WDAC); full tests/guards/ runs in Linux CI", flush=True)
    _run_cmd(pytest_args)
    print("[PASS] Pytest Block 3 + guards + drift + contract/lifecycle suites green", flush=True)

    # 8. Run all Block 2 & Block 3-9 detectors/runners
    _run_cmd([sys.executable, "tools/verify_block2_final.py"])
    _, anb_out = _run_cmd([sys.executable, "tools/audit_negative_branches.py"])
    assert "MUSTs lacking negative tests (scheduled for Block 3): 0" in anb_out, anb_out
    _run_cmd([sys.executable, "tools/scan_negative_branches.py"])
    _run_cmd([sys.executable, "tools/run_hand_mutants_r6.py"])
    _run_cmd([sys.executable, "tools/audit_inert_keys.py"])
    _run_cmd([
        sys.executable, "tools/run_all_b3_fixtures.py",
        "--master-path", "docs/design/S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md",
    ])
    _run_cmd([
        sys.executable, "tools/run_all_b4_b9_fixtures.py",
        "--master-path", "docs/design/S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md",
    ])
    print("[PASS] All detectors & fixture runners (verify_block2_final, audit_negative_branches=0, scan_negative_branches, hand_mutants, inert_keys, B3, B4-B9) PASSED")
    print("VERIFY_BLOCK3_FINAL: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
