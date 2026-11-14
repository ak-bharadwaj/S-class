#!/usr/bin/env python3
"""Branch Baselines Evaluation & Test Classification Tool (Roadmap B01 / Defect 3).

Evaluates clean-install full test suite outcomes across all 5 authoritative refs:
  - main        (447caf96e356a836b0455ac6d845a6729a9e007f)
  - h0          (e60a089dbdd8d14394009f1c9661967d8d5b7b74)
  - h1a         (9c6e0fc9d21219f48c0235f3dc69687063f84061)
  - h1b         (8b012f2dadf8785481b36e48598e34cc8a80c92f)
  - integration (4af5aba9d9898bb10dd2e859cc6d8a4572fac157)

For each ref:
  1. Archives clean source tree at exact commit SHA into a temporary environment.
  2. Executes full pytest suite with JUnit XML reporting.
  3. Classifies every testcase outcome as PASSED, ENV (with capability named), or CODE.
  4. Generates structured JSON and Markdown comparison evidence.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import platform
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List

_REPO_ROOT = Path(__file__).resolve().parents[1]
_TOOLS_DIR = _REPO_ROOT / "tools"
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

import run_full_suite_classified as C

AUTHORITATIVE_REFS = {
    "main": "447caf96e356a836b0455ac6d845a6729a9e007f",
    "h0": "e60a089dbdd8d14394009f1c9661967d8d5b7b74",
    "h1a": "9c6e0fc9d21219f48c0235f3dc69687063f84061",
    "h1b": "8b012f2dadf8785481b36e48598e34cc8a80c92f",
    "integration": "4af5aba9d9898bb10dd2e859cc6d8a4572fac157",
}


def resolve_ref_sha(ref_name: str) -> str:
    # Try git rev-parse for local or remote ref, fallback to canonical constant
    for candidate in [f"origin/{ref_name}", ref_name, AUTHORITATIVE_REFS.get(ref_name, "")]:
        if not candidate:
            continue
        try:
            res = subprocess.run(
                ["git", "rev-parse", candidate],
                cwd=str(_REPO_ROOT),
                capture_output=True,
                text=True,
                check=True,
            )
            sha = res.stdout.strip()
            if len(sha) == 40:
                return sha
        except Exception:
            pass
    return AUTHORITATIVE_REFS.get(ref_name, "unknown")


def evaluate_ref(ref_name: str, ref_sha: str, tmp_base: Path) -> dict:
    print(f"\nEvaluating ref '{ref_name}' at commit {ref_sha}...")
    work_dir = tmp_base / ref_name
    work_dir.mkdir(parents=True, exist_ok=True)

    # Clean archive extraction of the exact ref tree
    p1 = subprocess.Popen(["git", "archive", ref_sha], cwd=str(_REPO_ROOT), stdout=subprocess.PIPE)
    p2 = subprocess.Popen(["tar", "-x", "-C", str(work_dir)], stdin=p1.stdout)
    p1.stdout.close()
    p2.communicate()

    xml_path = work_dir / "junit.xml"
    start_time = datetime.datetime.now()

    env_vars = dict(os.environ)
    master_path = work_dir / "docs" / "design" / "S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md"
    if master_path.exists():
        env_vars["SCLASS_MASTER_PATH"] = str(master_path)

    # Run pytest on the extracted tree
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        f"--junitxml={xml_path}",
        "-q",
    ]
    proc = subprocess.run(cmd, cwd=str(work_dir), env=env_vars, capture_output=True, text=True)
    duration = (datetime.datetime.now() - start_time).total_seconds()

    parsed = C.parse_junit_xml(xml_path)

    # Pytest non-zero exit validation
    if proc.returncode != 0 and len(parsed["code"]) == 0:
        parsed["code"].append({
            "node_id": "pytest::process_exit",
            "status": "ERROR",
            "category": "CODE",
            "capability": None,
            "description": f"Pytest process exited with non-zero code {proc.returncode} unrepresented in JUnit test failures",
            "details": proc.stderr or proc.stdout,
            "time": 0.0,
        })

    n_passed = len(parsed["passed"])
    n_env = len(parsed["env"])
    n_code = len(parsed["code"])
    total_collected = n_passed + n_env + n_code

    env_by_cap: dict[str, int] = {}
    for item in parsed["env"]:
        cap = item.get("capability") or "unknown_capability"
        env_by_cap[cap] = env_by_cap.get(cap, 0) + 1

    status = "PASS" if n_code == 0 else "FAIL"

    print(f"  Result: {n_passed} passed, {n_env} env, {n_code} code failures ({status}) in {duration:.2f}s")
    if env_by_cap:
        print(f"  ENV breakdown: {env_by_cap}")

    return {
        "ref_name": ref_name,
        "ref_sha": ref_sha,
        "total_collected": total_collected,
        "passed_count": n_passed,
        "env_items_count": n_env,
        "code_failures_count": n_code,
        "duration_seconds": duration,
        "env_summary_by_capability": env_by_cap,
        "status": status,
        "env_items": parsed["env"],
        "code_failures": parsed["code"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate full suite outcomes across all branch baselines")
    parser.add_argument("--output-json", type=Path, default=_REPO_ROOT / "delivery-evidence" / "branch_baselines_classification.json")
    parser.add_argument("--output-md", type=Path, default=_REPO_ROOT / "delivery-evidence" / "branch_baselines_classification.md")
    args = parser.parse_args()

    results: Dict[str, dict] = {}

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        for ref_name in ("main", "h0", "h1a", "h1b", "integration"):
            sha = resolve_ref_sha(ref_name)
            results[ref_name] = evaluate_ref(ref_name, sha, tmp_path)

    # Build report data
    report_data = {
        "schema": "sclass/branch-baselines-classification/v1",
        "generated_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "authoritative_refs": {name: res["ref_sha"] for name, res in results.items()},
        "metrics_by_ref": {
            name: {
                "ref_sha": res["ref_sha"],
                "total_collected": res["total_collected"],
                "passed_count": res["passed_count"],
                "env_items_count": res["env_items_count"],
                "code_failures_count": res["code_failures_count"],
                "duration_seconds": res["duration_seconds"],
                "status": res["status"],
                "env_breakdown": res["env_summary_by_capability"],
            }
            for name, res in results.items()
        },
        "all_refs_pass": all(res["status"] == "PASS" for res in results.values()),
    }

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report_data, indent=2), encoding="utf-8")

    # Generate Markdown
    lines = [
        "# S-Class Branch Baselines Clean-Install Evaluation & Test Classification",
        "",
        f"- **Generated at:** {report_data['generated_at_utc']}",
        f"- **Platform:** `{report_data['platform']}`",
        f"- **Python Version:** `{report_data['python_version']}`",
        "",
        "## Multi-Branch Verification Matrix",
        "",
        "| Branch / Ref | Commit SHA | Total Collected | Passed | ENV Exclusions | CODE Failures | Result | Duration |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ]

    for name in ("main", "h0", "h1a", "h1b", "integration"):
        res = results[name]
        sha_short = res["ref_sha"][:8]
        lines.append(
            f"| `{name}` | `{sha_short}` ({res['ref_sha']}) | {res['total_collected']} | {res['passed_count']} | {res['env_items_count']} | {res['code_failures_count']} | **{res['status']}** | {res['duration_seconds']:.2f}s |"
        )

    lines.extend([
        "",
        "## ENV Capability Exclusions Detail (by Ref)",
        "",
    ])

    for name in ("main", "h0", "h1a", "h1b", "integration"):
        res = results[name]
        lines.append(f"### Ref `{name}` ({res['ref_sha'][:8]})")
        if res["env_summary_by_capability"]:
            lines.append("| Missing Capability | Items Affected |")
            lines.append("| :--- | :--- |")
            for cap, cnt in sorted(res["env_summary_by_capability"].items()):
                lines.append(f"| `{cap}` | {cnt} |")
        else:
            lines.append("*0 ENV capability exclusions.*")
        lines.append("")

    args.output_md.write_text("\n".join(lines), encoding="utf-8")

    print("\n" + "=" * 90)
    print("BRANCH BASELINES CLASSIFICATION SUMMARY")
    print("=" * 90)
    print(f"{'Ref':<14} | {'Commit SHA':<40} | {'Total':<6} | {'Passed':<6} | {'ENV':<5} | {'CODE':<5} | {'Status'}")
    print("-" * 90)
    for name in ("main", "h0", "h1a", "h1b", "integration"):
        res = results[name]
        print(f"{name:<14} | {res['ref_sha']:<40} | {res['total_collected']:<6} | {res['passed_count']:<6} | {res['env_items_count']:<5} | {res['code_failures_count']:<5} | {res['status']}")
    print("-" * 90)
    print(f"Wrote report to {args.output_md} and {args.output_json}")

    return 0 if report_data["all_refs_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
