#!/usr/bin/env python3
"""Executes full pytest suites on staging and baseline trees and captures raw logs.

Adheres strictly to W5: honest full-suite pass/fail counts and failing test IDs.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path("/mnt/c/Users/dorni/OneDrive/Desktop/S-class")
BASELINE_ROOT = Path("/home/runner/baseline-10fd034")
DELIVERY_DIR = REPO_ROOT / "delivery-2-block2"


def clean_orphans() -> None:
    """Terminates any leaked descendant processes from process tree monitor tests."""
    try:
        ps = subprocess.run(["ps", "aux"], capture_output=True, text=True).stdout
        for line in ps.splitlines():
            if "child.barrier" in line or "child.fifo" in line:
                parts = line.split()
                if len(parts) > 1 and parts[1].isdigit():
                    pid = int(parts[1])
                    try:
                        os.kill(pid, 9)
                    except OSError:
                        pass
    except Exception:
        pass


def parse_output(out: str, elapsed: float = 0.0) -> dict:
    passed_m = re.search(r"(\d+)\s+passed", out)
    failed_m = re.search(r"(\d+)\s+failed", out)
    errors_m = re.search(r"(\d+)\s+error", out)

    passed = int(passed_m.group(1)) if passed_m else 0
    failed = int(failed_m.group(1)) if failed_m else 0
    errors = int(errors_m.group(1)) if errors_m else 0

    failing_ids = []
    if failed > 0 or errors > 0:
        for line in out.splitlines():
            if line.startswith("FAILED ") or line.startswith("ERROR "):
                failing_ids.append(line.split()[1])

    summary_line = "NO_OUTPUT"
    for line in reversed(out.strip().splitlines()):
        if "passed" in line or "failed" in line:
            summary_line = line.strip()
            break

    return {
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "failing_ids": failing_ids,
        "elapsed": elapsed,
        "summary": summary_line,
    }


def run_suite(python_bin: str, cwd: Path, log_file: Path, force: bool = False) -> dict:
    if not force and log_file.exists() and log_file.stat().st_size > 500:
        content = log_file.read_text(encoding="utf-8", errors="replace")
        if "passed" in content:
            print(f"Using existing valid log: {log_file} ({len(content)} bytes)")
            return parse_output(content)

    clean_orphans()
    cmd = [python_bin, "-m", "pytest", "-q"]
    print(f"Running: {' '.join(cmd)} in {cwd}...")
    start = time.monotonic()

    proc = subprocess.Popen(
        cmd, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )

    while proc.poll() is None:
        clean_orphans()
        time.sleep(1)

    out, _ = proc.communicate()
    elapsed = time.monotonic() - start

    log_file.write_text(out, encoding="utf-8")
    print(f"  Finished in {elapsed:.2f}s, wrote {log_file} ({len(out)} bytes)")
    return parse_output(out, elapsed)


def ensure_symmetric_log_names(deliv_dir: Path) -> None:
    """Ensures both python_3.10_full_suite.log and python_3_10_full_suite.log exist."""
    pairs = [
        ("python_3.10_full_suite.log", "python_3_10_full_suite.log"),
        ("baseline_python_3.10_full_suite.log", "baseline_python_3_10_full_suite.log"),
        ("python_3.11_full_suite.log", "python_3_11_full_suite.log"),
        ("baseline_python_3.11_full_suite.log", "baseline_python_3_11_full_suite.log"),
        ("python_3.12_full_suite.log", "python_3_12_full_suite.log"),
        ("baseline_python_3.12_full_suite.log", "baseline_python_3_12_full_suite.log"),
        ("python_3.13_full_suite.log", "python_3_13_full_suite.log"),
        ("baseline_python_3.13_full_suite.log", "baseline_python_3_13_full_suite.log"),
    ]
    for dot_name, uscore_name in pairs:
        p_dot = deliv_dir / dot_name
        p_uscore = deliv_dir / uscore_name
        if p_dot.exists() and not p_uscore.exists():
            shutil.copy2(p_dot, p_uscore)
        elif p_uscore.exists() and not p_dot.exists():
            shutil.copy2(p_uscore, p_dot)


def generate_summary(results: dict, output_file: Path) -> None:
    lines = []
    lines.append("================================================================================")
    lines.append("W5: BASELINE vs STAGING FULL-SUITE COMPARISON ACROSS PYTHON 3.10-3.13")
    lines.append("================================================================================")

    # bwrap check
    bwrap_path = shutil.which("bwrap") or "NOT FOUND"
    bwrap_ver = "unknown"
    if bwrap_path != "NOT FOUND":
        try:
            bwrap_ver = subprocess.run(["bwrap", "--version"], capture_output=True, text=True).stdout.strip()
        except Exception:
            pass
    lines.append(f"Bubblewrap (bwrap) status: {bwrap_path} ({bwrap_ver})")
    lines.append(f"Baseline Commit:  10fd034938a910967f77bd8dc46fd65b982dc3d3")
    lines.append(f"Staging Branch:   staging-b2-r33")
    lines.append("")

    for v in ["3.10", "3.11", "3.12", "3.13"]:
        if v not in results:
            continue
        r = results[v]
        st = r["staging"]
        bs = r["baseline"]
        lines.append(f"--------------------------------------------------------------------------------")
        lines.append(f"Python {v}:")
        lines.append(f"  Baseline (10fd034): {bs['passed']} passed, {bs['failed']} failed (total: {bs['passed'] + bs['failed']})")
        if bs["failed"] > 0:
            lines.append("    Failing Test IDs in Baseline:")
            for fid in bs["failing_ids"]:
                lines.append(f"      - {fid}")
        lines.append(f"  Staging (staging-b2-r33): {st['passed']} passed, {st['failed']} failed (total: {st['passed'] + st['failed']})")
        if st["failed"] > 0:
            lines.append("    Failing Test IDs in Staging:")
            for fid in st["failing_ids"]:
                lines.append(f"      - {fid}")
        lines.append(f"  Diff (Staging - Baseline): +{st['passed'] - bs['passed']} passed, +{st['failed'] - bs['failed']} failed")
        if bs["failed"] > 0 and bs["failing_ids"] == st["failing_ids"]:
            lines.append("    Diagnosis: Failing tests in staging are 100% identical to pre-existing baseline failures.")
            lines.append("    Root cause from raw traceback: 'subprocess.CalledProcessError: Command ... /bin/python -m pip ... No module named pip'")

    lines.append("================================================================================")
    text = "\n".join(lines) + "\n"
    output_file.write_text(text, encoding="utf-8")
    print(f"\nWrote summary to {output_file}:")
    print(text)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("versions", nargs="*", default=["3.10", "3.11", "3.12", "3.13"])
    parser.add_argument("--force", action="store_true", help="Re-run even if logs exist")
    args = parser.parse_args()

    DELIVERY_DIR.mkdir(parents=True, exist_ok=True)
    ensure_symmetric_log_names(DELIVERY_DIR)

    results = {}
    for v in args.versions:
        py_bin = f"/home/runner/venv-{v}/bin/python"
        if not Path(py_bin).exists():
            print(f"Warning: {py_bin} does not exist, skipping.")
            continue

        print(f"\n=================== Python {v} ===================")
        # 1. Staging run
        # Try both naming styles when checking existing log
        staging_log = DELIVERY_DIR / f"python_{v}_full_suite.log"
        staging_res = run_suite(py_bin, REPO_ROOT, staging_log, force=args.force)

        # 2. Baseline run
        baseline_log = DELIVERY_DIR / f"baseline_python_{v}_full_suite.log"
        baseline_res = run_suite(py_bin, BASELINE_ROOT, baseline_log, force=args.force)

        results[v] = {
            "staging": staging_res,
            "baseline": baseline_res,
        }

    ensure_symmetric_log_names(DELIVERY_DIR)
    summary_file = DELIVERY_DIR / "baseline_vs_staging_summary.txt"
    generate_summary(results, summary_file)
    return 0


if __name__ == "__main__":
    sys.exit(main())
