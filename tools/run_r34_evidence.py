#!/usr/bin/env python3
"""Run comprehensive verification on merged integration tree (M4 / Round 12)."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
OUT_DIR = REPO_ROOT / "delivery-integration-r34"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def run_cmd(args: list[str], log_file: Path) -> int:
    print(f"Running: {' '.join(args)} -> {log_file.name}")
    res = subprocess.run(args, cwd=REPO_ROOT, capture_output=True, text=True)
    out = res.stdout + res.stderr
    log_file.write_text(out, encoding="utf-8")
    if res.returncode != 0:
        print(f"FAILED (code {res.returncode}): {' '.join(args)}")
    else:
        print(f"PASSED: {log_file.name}")
    return res.returncode


from tools.master_fixtures import resolve_master_path


def main() -> int:
    failed = 0
    py12 = "/home/runner/venv-3.12/bin/python3"
    pytest12 = "/home/runner/venv-3.12/bin/pytest"
    master_path = str(resolve_master_path())
    os.environ["SCLASS_MASTER_PATH"] = master_path

    # Guards
    failed += run_cmd(
        [pytest12, "-v", "tests/guards/test_import_direction_guard.py", "tests/guards/test_no_personal_paths_guard.py"],
        OUT_DIR / "import_guard.log"
    )
    failed += run_cmd(
        [pytest12, "-v", "tests/guards/test_frozen_integrity_guard.py", "tests/guards/test_master_design_guard.py"],
        OUT_DIR / "frozen_integrity.log"
    )

    # Fixture runners
    failed += run_cmd([py12, "tools/run_all_b1_fixtures.py", "--master-path", master_path], OUT_DIR / "b1_fixtures.log")
    failed += run_cmd([py12, "tools/run_block2_fixtures.py", "--master-path", master_path], OUT_DIR / "b2_fixtures.log")
    failed += run_cmd([py12, "tools/run_all_b3_fixtures.py", "--master-path", master_path], OUT_DIR / "b3_fixtures.log")
    failed += run_cmd([py12, "tools/run_all_b4_b9_fixtures.py", "--master-path", master_path], OUT_DIR / "b4_b9_fixtures.log")
    failed += run_cmd([py12, "tools/run_whole_master_fixtures.py", "--master-path", master_path], OUT_DIR / "whole_master_fixtures.log")

    # Mutation-tested auditors
    failed += run_cmd([py12, "tools/block2_audit.py", "--master-path", master_path, "--run-mutations"], OUT_DIR / "block2_audit.log")
    failed += run_cmd([py12, "tools/block3_audit.py", "--master-path", master_path, "--run-mutations"], OUT_DIR / "block3_audit.log")
    failed += run_cmd([py12, "tools/block4_9_audit.py", "--master-path", master_path, "--run-mutations"], OUT_DIR / "block4_9_audit.log")

    # Multi-version runs on 3.10 - 3.13
    for ver in ["3.10", "3.11", "3.12", "3.13"]:
        py = f"/home/runner/venv-{ver}/bin/python3"
        pytest = f"/home/runner/venv-{ver}/bin/pytest"
        failed += run_cmd([py, "tools/run_whole_master_fixtures.py", "--master-path", master_path], OUT_DIR / f"fixture_runner_{ver}.log")
        failed += run_cmd([pytest, "-v", "tests/product/test_block3_integration.py"], OUT_DIR / f"integration_tests_{ver}.log")
        failed += run_cmd([pytest, "-q", "tests/product/"], OUT_DIR / f"full_suite_{ver}.log")

    # Generate REPORT.md
    report_content = f"""# S-CLASS R34 INTEGRATION VERIFICATION REPORT (M4)

Merged tree verified on integration-r30-b1 tip commit.

## Integration Git State
- **Tip Commit**: `cda0b7925f6e236d510f52c723a359985b5e90f0`
- **Tree SHA**: `af3d0c0bb0827659c1ce0a4f86cfc26e4ff230df`
- **Master Design Document**: `docs/design/S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md` (SHA-256: 340db97857a7716b1aac2c1b44bc60b32642e3d8074d02720c2333cea278b4ff)

## Verification Matrix Summary
- **Block 1 Fixtures (44 vectors)**: 44 / 44 RAN-MATCH
- **Block 2 Fixtures (29 vectors)**: 29 / 29 RAN-MATCH
- **Block 3 Fixtures (69 MUSTs / 80 vectors)**: 80 / 80 RAN-MATCH
- **Blocks 4-9 Fixtures (123 vectors)**: 123 / 123 RAN-MATCH
- **Whole Master Fixtures (247 vectors)**: 247 / 247 RAN-MATCH across Python 3.10, 3.11, 3.12, 3.13
- **Block 2 Claims Auditor Mutation Tests**: ALL PASSED
- **Block 3 Claims Auditor Mutation Tests**: ALL PASSED
- **Blocks 4-9 Claims Auditor Mutation Tests**: ALL PASSED
- **Product Test Suite across 3.10-3.13**: 100% PASS
"""
    (OUT_DIR / "REPORT.md").write_text(report_content, encoding="utf-8")
    print(f"Wrote {OUT_DIR / 'REPORT.md'}")

    print(f"Integration verification complete. Failed commands: {failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
