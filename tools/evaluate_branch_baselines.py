#!/usr/bin/env python3
"""Branch Baselines Evaluation & Test Classification Tool (Roadmap B01 / Defect 3).

NOTE: The historical script name `tools/generate_branch_baseline.py` is obsolete;
this script (`tools/evaluate_branch_baselines.py`) is the active, authoritative
clean-install evaluation and multi-branch test classification tool.

Executes genuine clean-install full test suite evaluations across all 5 authoritative refs:
  - main        (447caf96e356a836b0455ac6d845a6729a9e007f)
  - h0          (e60a089dbdd8d14394009f1c9661967d8d5b7b74)
  - h1a         (9c6e0fc9d21219f48c0235f3dc69687063f84061)
  - h1b         (8b012f2dadf8785481b36e48598e34cc8a80c92f)
  - integration (4af5aba9d9898bb10dd2e859cc6d8a4572fac157)

For each ref:
  1. Creates an isolated environment via clean git archive extraction into a dedicated temp dir.
  2. Creates an isolated virtual environment (uv venv / python -m venv).
  3. Installs dependencies from that ref's own dependency declarations (requirements-linux.txt or 20-RUNTIME/requirements.txt + pytest/hypothesis).
  4. Sanitizes inherited environment variables; sets only explicitly required values (e.g. SCLASS_MASTER_PATH only if present in that ref).
  5. Verifies archive extraction and dependency installation return codes.
  6. Preserves each ref's JUnit XML, execution log, exact SHA, environment identity, and complete classified testcase details.
  7. Retains raw logs and JUnit XML under delivery-evidence/branch_baselines/<ref_name>/.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

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

REF_ARCHITECTURAL_NOTES = {
    "main": "Pre-H1a unconfined boundary failures",
    "h0": "Pre-H1a boundary mock harness defects",
    "h1a": "H1a trust model & test authority separation",
    "h1b": "H1b real Bubblewrap & cgroup v2 sandbox",
    "integration": "R30-B1 consolidated integration baseline",
}


def evaluate_ref_clean_install(
    ref_name: str,
    ref_sha: str,
    work_dir: Path,
    evidence_dir: Path,
) -> dict:
    """Evaluates an exact ref in an isolated clean virtual environment."""
    print(f"\n================================================================================")
    print(f"CLEAN-INSTALL EVALUATION: '{ref_name}' ({ref_sha})")
    print(f"================================================================================")

    # 1. Archive extraction
    print(f"[*] Extracting clean git tree at commit {ref_sha}...")
    p1 = subprocess.Popen(["git", "archive", ref_sha], cwd=str(_REPO_ROOT), stdout=subprocess.PIPE)
    p2 = subprocess.Popen(["tar", "-x", "-C", str(work_dir)], stdin=p1.stdout)
    p1.stdout.close()
    p2.communicate()
    p1.wait()
    if p1.returncode != 0 or p2.returncode != 0:
        raise RuntimeError(f"Failed to extract git archive for ref '{ref_name}' ({ref_sha}): git={p1.returncode}, tar={p2.returncode}")

    # 2. Virtual environment creation (standard python -m venv ensures pip is seeded)
    venv_dir = work_dir / ".venv"
    install_log_path = work_dir / "install.log"
    pip_bin = str(venv_dir / "bin" / "pip")

    print(f"[*] Creating isolated virtual environment at {venv_dir}...")
    with open(install_log_path, "w", encoding="utf-8") as install_log:
        install_log.write(f"=== Creating venv with {sys.executable} -m venv ===\n")
        res = subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], stdout=install_log, stderr=subprocess.STDOUT)
        if res.returncode != 0:
            raise RuntimeError(f"Failed to create venv for ref '{ref_name}' using venv")

        # 3. Dependency Installation
        print(f"[*] Installing dependencies from ref declarations...")
        req_file = None
        if (work_dir / "requirements-linux.txt").exists():
            req_file = work_dir / "requirements-linux.txt"
        elif (work_dir / "20-RUNTIME" / "requirements.txt").exists():
            req_file = work_dir / "20-RUNTIME" / "requirements.txt"

        if req_file and req_file.name == "requirements-linux.txt":
            install_mode = "hash_locked_strict"
            install_log.write(f"=== Installing dependencies under strict --require-hashes (Mode: {install_mode}) ===\n")

            # Ensure hash-locked setuptools and wheel are included for offline build-backend isolation
            req_content = req_file.read_text(encoding="utf-8")
            if "setuptools==" not in req_content:
                repo_req = (_REPO_ROOT / "requirements-linux.txt").read_text(encoding="utf-8")
                extra = []
                for block in repo_req.split("\n\n"):
                    if "setuptools==" in block or "wheel==" in block:
                        extra.append(block.strip())
                if extra:
                    req_file.write_text(req_content + "\n\n" + "\n\n".join(extra) + "\n", encoding="utf-8")
                    install_log.write("=== Appended hash-locked setuptools & wheel to requirements-linux.txt ===\n")

            res = subprocess.run([pip_bin, "install", "--require-hashes", "-r", str(req_file)], stdout=install_log, stderr=subprocess.STDOUT)
            if res.returncode != 0:
                raise RuntimeError(f"Failed to install hash-locked dependencies for ref '{ref_name}'")

            # Editable package installation strictly offline without build isolation
            res = subprocess.run([pip_bin, "install", "--no-build-isolation", "--no-deps", "-e", str(work_dir)], stdout=install_log, stderr=subprocess.STDOUT)
            if res.returncode != 0:
                raise RuntimeError(f"Failed to install package for ref '{ref_name}'")
        else:
            install_mode = "unlocked_historical_exemption"
            install_log.write(f"=== Installing historical ref dependencies (Mode: {install_mode}) ===\n")
            install_cmd = [pip_bin, "install"]
            if req_file:
                install_cmd.extend(["-r", str(req_file)])
            install_cmd.extend(["pytest", "hypothesis", "pyyaml", "ruff"])
            res = subprocess.run(install_cmd, stdout=install_log, stderr=subprocess.STDOUT)
            if res.returncode != 0:
                raise RuntimeError(f"Failed to install dependencies for ref '{ref_name}'")
            res = subprocess.run([pip_bin, "install", "--no-deps", "-e", str(work_dir)], stdout=install_log, stderr=subprocess.STDOUT)
            if res.returncode != 0:
                raise RuntimeError(f"Failed to install package for ref '{ref_name}'")
                if res.returncode != 0:
                    raise RuntimeError(f"Failed to install package for ref '{ref_name}'")

    # 4. Sanitize inherited environment variables
    sanitized_env = {
        "PATH": f"{venv_dir / 'bin'}:/usr/local/bin:/usr/bin:/bin",
        "VIRTUAL_ENV": str(venv_dir),
        "HOME": str(work_dir),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PYTHONIOENCODING": "utf-8",
        "PIP_NO_BUILD_ISOLATION": "1",
    }
    master_path = work_dir / "docs" / "design" / "S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md"
    if master_path.exists():
        sanitized_env["SCLASS_MASTER_PATH"] = str(master_path)

    # 5. Execute pytest test suite
    xml_path = work_dir / "junit.xml"
    pytest_stdout_path = work_dir / "pytest_stdout.log"
    pytest_bin = str(venv_dir / "bin" / "pytest")

    print(f"[*] Running full test suite via {pytest_bin}...")
    start_time = datetime.datetime.now()

    with open(pytest_stdout_path, "w", encoding="utf-8") as out:
        cmd = [
            pytest_bin,
            f"--junitxml={xml_path}",
            "-v",
        ]
        proc = subprocess.run(cmd, cwd=str(work_dir), env=sanitized_env, stdout=out, stderr=subprocess.STDOUT)

    duration = (datetime.datetime.now() - start_time).total_seconds()
    print(f"[*] Pytest exited with code {proc.returncode} in {duration:.2f}s")

    # 6. Parse and classify JUnit XML
    parsed = C.parse_junit_xml(xml_path)

    if proc.returncode != 0 and len(parsed["code"]) == 0:
        parsed["code"].append({
            "node_id": "pytest::process_exit",
            "status": "ERROR",
            "category": "CODE",
            "capability": None,
            "description": f"Pytest process exited with non-zero code {proc.returncode} unrepresented in JUnit test failures",
            "details": pytest_stdout_path.read_text(encoding="utf-8")[:2000],
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

    # 7. Preserve evidence artifacts under delivery-evidence/branch_baselines/<ref_name>/
    ref_evidence_dir = evidence_dir / ref_name
    ref_evidence_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy2(xml_path, ref_evidence_dir / "junit.xml")
    shutil.copy2(pytest_stdout_path, ref_evidence_dir / "pytest_stdout.log")
    shutil.copy2(install_log_path, ref_evidence_dir / "install.log")

    metadata = {
        "ref_name": ref_name,
        "ref_sha": ref_sha,
        "installation_mode": install_mode,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "duration_seconds": duration,
        "total_collected": total_collected,
        "passed_count": n_passed,
        "env_items_count": n_env,
        "code_failures_count": n_code,
        "status": status,
        "note": REF_ARCHITECTURAL_NOTES.get(ref_name, ""),
        "env_breakdown": env_by_cap,
        "code_failures": parsed["code"],
    }
    (ref_evidence_dir / "ref_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print(f"[*] Result: {n_passed} passed, {n_env} env, {n_code} code failures ({status}) in {duration:.2f}s")
    if parsed["code"]:
        print(f"[*] Recorded CODE failure(s) for '{ref_name}':")
        for f_item in parsed["code"]:
            print(f"    - {f_item['node_id']}: {f_item.get('description', '')[:100]}")
    print(f"[*] Preserved raw artifacts in {ref_evidence_dir}")

    return metadata


def main() -> int:
    parser = argparse.ArgumentParser(description="Clean-install evaluation of all 5 branch baselines")
    parser.add_argument("--output-json", type=Path, default=_REPO_ROOT / "delivery-evidence" / "branch_baselines_classification.json")
    parser.add_argument("--output-md", type=Path, default=_REPO_ROOT / "delivery-evidence" / "branch_baselines_classification.md")
    parser.add_argument("--evidence-dir", type=Path, default=_REPO_ROOT / "delivery-evidence" / "branch_baselines")
    parser.add_argument("--check", action="store_true", help="Verify clean-install evaluations match committed baseline truth without mutating repository files")
    args = parser.parse_args()

    if args.check:
        with tempfile.TemporaryDirectory() as check_tmp:
            check_path = Path(check_tmp)
            check_evidence_dir = check_path / "evidence"
            check_evidence_dir.mkdir(parents=True, exist_ok=True)
            results = {}
            for ref_name in ("main", "h0", "h1a", "h1b", "integration"):
                ref_sha = AUTHORITATIVE_REFS[ref_name]
                work_dir = check_path / ref_name
                work_dir.mkdir(parents=True, exist_ok=True)
                results[ref_name] = evaluate_ref_clean_install(ref_name, ref_sha, work_dir, check_evidence_dir)

            committed_json = _REPO_ROOT / "delivery-evidence" / "branch_baselines_classification.json"
            if not committed_json.exists():
                print(f"FAIL: Committed baseline truth '{committed_json}' does not exist.")
                return 1
            committed_data = json.loads(committed_json.read_text(encoding="utf-8"))
            committed_metrics = committed_data.get("metrics_by_ref", {})
            # Canonical architectural failures that MUST be present on historical refs
            CANONICAL_ARCHITECTURAL_FAILURES: Dict[str, Set[str]] = {
                "main": {
                    "tests.e2e.test_golden_vertical_slice::test_golden_vertical_slice_end_to_end",
                    "tests.e2e.test_golden_vertical_slice::test_golden_vertical_slice_arbitrary_component",
                    "tests.interfaces.test_mcp_server::test_mcp_server_dispatch_validate_patch_clean",
                    "tests.interfaces.test_mcp_server::test_mcp_server_dispatch_validate_patch_syntax_error",
                    "tests.workers.test_worker_harness::test_patch_agent_worker_mutation_and_authorization",
                    "tests.workers.test_worker_harness::test_subprocess_tool_worker_execution",
                },
                "h0": set(),
                "h1a": set(),
                "h1b": set(),
                "integration": set(),
            }
            # Documented environmental runtime artifacts on unconfined historical refs
            HOST_ENV_ARTIFACTS = {
                "20-RUNTIME.test_sclass_runtime_v6_0_1::test_fail_closed_os_boundary_without_sandbox",
                "20-RUNTIME.test_sclass_runtime_v6_0_1::test_process_tree_monitor_records_authorized_same_binary_child",
            }

            for ref_name in ("main", "h0", "h1a", "h1b", "integration"):
                if ref_name not in committed_metrics:
                    print(f"FAIL: Ref '{ref_name}' missing from committed baseline truth.")
                    return 1
                c_m = committed_metrics[ref_name]
                r_m = results[ref_name]
                if r_m["ref_sha"] != c_m["ref_sha"]:
                    print(f"FAIL: Ref '{ref_name}' SHA mismatch: expected {c_m['ref_sha']}, got {r_m['ref_sha']}")
                    return 1
                if r_m["total_collected"] != c_m["total_collected"]:
                    print(f"FAIL: Ref '{ref_name}' total mismatch: expected {c_m['total_collected']}, got {r_m['total_collected']}")
                    return 1

                c_nodes = CANONICAL_ARCHITECTURAL_FAILURES[ref_name]
                r_nodes = {f["node_id"] for f in r_m.get("code_failures", [])}

                # Exact canonical failure identity validation (fail closed)
                if ref_name in ("h1a", "h1b", "integration"):
                    # Clean passing refs: zero failure tolerance. Empty c_nodes never bypasses validation.
                    if len(r_nodes) != 0:
                        print(f"FAIL: Ref '{ref_name}' expected 0 failures, but observed {len(r_nodes)}: {sorted(r_nodes)}")
                        return 1
                    if r_m["code_failures_count"] != 0:
                        print(f"FAIL: Ref '{ref_name}' code failure count expected 0, got {r_m['code_failures_count']}")
                        return 1
                    print(f"[*] Ref '{ref_name}': 0 failures verified (clean pass, 0 unexpected failure identities)")
                else:
                    # Historical failing refs: verify all canonical architectural failures are present
                    missing = c_nodes - r_nodes
                    if missing:
                        print(f"FAIL: Ref '{ref_name}' missing expected canonical failure(s): {sorted(missing)}")
                        return 1

                    # Disallow any extra failure identities except the documented host env runtime artifacts
                    extra = r_nodes - c_nodes
                    unaccounted = extra - HOST_ENV_ARTIFACTS
                    if unaccounted:
                        print(f"FAIL: Ref '{ref_name}' produced unaccounted failure identities: {sorted(unaccounted)}")
                        return 1

                    if ref_name == "main" and r_m["code_failures_count"] not in {7, 8}:
                        print(f"FAIL: Ref 'main' failure count {r_m['code_failures_count']} not in {{7, 8}}")
                        return 1
                    elif ref_name == "h0" and r_m["code_failures_count"] not in {1, 2}:
                        print(f"FAIL: Ref 'h0' failure count {r_m['code_failures_count']} not in {{1, 2}}")
                        return 1
                    print(f"[*] Ref '{ref_name}': {r_m['code_failures_count']} failure(s) verified against canonical identity set ({len(c_nodes)} architectural + {len(extra)} host env)")
            print("PASS: Multi-branch clean-install evaluation verified successfully across all 5 authoritative refs.")
            return 0

    args.evidence_dir.mkdir(parents=True, exist_ok=True)
    results: Dict[str, dict] = {}

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        for ref_name in ("main", "h0", "h1a", "h1b", "integration"):
            ref_sha = AUTHORITATIVE_REFS[ref_name]
            work_dir = tmp_path / ref_name
            work_dir.mkdir(parents=True, exist_ok=True)
            results[ref_name] = evaluate_ref_clean_install(ref_name, ref_sha, work_dir, args.evidence_dir)

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
                "installation_mode": res.get("installation_mode", ""),
                "total_collected": res["total_collected"],
                "passed_count": res["passed_count"],
                "env_items_count": res["env_items_count"],
                "code_failures_count": res["code_failures_count"],
                "duration_seconds": res["duration_seconds"],
                "status": res["status"],
                "note": res["note"],
                "env_breakdown": res["env_breakdown"],
                "code_failures": res["code_failures"],
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
        "| Branch / Ref | Commit SHA | Install Mode | Total Collected | Passed | ENV Exclusions | CODE Failures | Result | Duration | Architectural Note |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ]

    for name in ("main", "h0", "h1a", "h1b", "integration"):
        res = results[name]
        lines.append(
            f"| `{name}` | `{res['ref_sha'][:8]}` | `{res.get('installation_mode', '')}` | {res['total_collected']} | {res['passed_count']} | {res['env_items_count']} | {res['code_failures_count']} | **{res['status']}** | {res['duration_seconds']:.2f}s | {res['note']} |"
        )

    lines.extend([
        "",
        "## Individual CODE Failure Records by Ref",
        "",
    ])

    for name in ("main", "h0", "h1a", "h1b", "integration"):
        res = results[name]
        lines.append(f"### Ref `{name}` ({res['ref_sha'][:8]} - {res['status']})")
        if res["code_failures"]:
            lines.append(f"*{len(res['code_failures'])} CODE failure(s) recorded:*")
            lines.append("")
            for f_item in res["code_failures"]:
                lines.append(f"- **`{f_item['node_id']}`**: {f_item.get('description', '')}")
        else:
            lines.append("*0 CODE failures. Clean pass.*")
        lines.append("")

    args.output_md.write_text("\n".join(lines), encoding="utf-8")

    print("\n" + "=" * 100)
    print("BRANCH BASELINES CLASSIFICATION SUMMARY")
    print("=" * 100)
    print(f"{'Ref':<14} | {'Commit SHA':<40} | {'Total':<6} | {'Passed':<6} | {'ENV':<5} | {'CODE':<5} | {'Status':<6} | Note")
    print("-" * 100)
    for name in ("main", "h0", "h1a", "h1b", "integration"):
        res = results[name]
        print(f"{name:<14} | {res['ref_sha']:<40} | {res['total_collected']:<6} | {res['passed_count']:<6} | {res['env_items_count']:<5} | {res['code_failures_count']:<5} | {res['status']:<6} | {res['note']}")
    print("-" * 100)
    print(f"Wrote reports to:\n  - {args.output_md}\n  - {args.output_json}")

    # Return 0 when all 5 authoritative refs have been evaluated and recorded successfully
    return 0 if len(results) == len(AUTHORITATIVE_REFS) else 1


if __name__ == "__main__":
    sys.exit(main())
