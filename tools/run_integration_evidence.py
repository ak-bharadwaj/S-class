#!/usr/bin/env python3
"""Run comprehensive verification on merged integration tree (M6)."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
OUT_DIR = REPO_ROOT / "delivery-integration-r33"
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
        [pytest12, "-v", "tests/guards/test_frozen_integrity_guard.py"],
        OUT_DIR / "frozen_integrity.log"
    )

    # Fixture runners
    failed += run_cmd([py12, "tools/run_all_b1_fixtures.py", "--master-path", master_path], OUT_DIR / "b1_fixtures.log")
    failed += run_cmd([py12, "tools/run_block2_fixtures.py", "--master-path", master_path], OUT_DIR / "b2_fixtures.log")
    failed += run_cmd([py12, "tools/run_all_b3_fixtures.py", "--master", master_path], OUT_DIR / "b3_fixtures.log")

    # Auditor
    failed += run_cmd([py12, "tools/block3_audit.py", "delivery-b3-wave2/REPORT-ROUND8.md"], OUT_DIR / "block3_audit.log")

    # Integration tests on all versions
    for ver in ["3.10", "3.11", "3.12", "3.13"]:
        py = f"/home/runner/venv-{ver}/bin/python3"
        pytest = f"/home/runner/venv-{ver}/bin/pytest"
        failed += run_cmd([py, "tools/run_all_b3_fixtures.py", "--master", master_path], OUT_DIR / f"fixture_runner_{ver}.log")
        failed += run_cmd([pytest, "-v", "tests/product/test_block3_integration.py"], OUT_DIR / f"integration_tests_{ver}.log")

    print(f"Integration verification complete. Failed commands: {failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
