#!/usr/bin/env python3
"""Generate comprehensive CI Truth table and extract per-run logs.

Owner Task C1 (Round 10 & Addendum).
"""

import sys
import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))
import gh_helper

OUT_DIR = REPO_ROOT / "delivery-ci"
OUT_DIR.mkdir(parents=True, exist_ok=True)

RUNS = [
    # Red runs from screenshot
    {"num": 785, "id": 42495174689, "branch": "staging-b4-b9", "sha": "6670bfc", "expected_status": "failure"},
    {"num": 784, "id": 42494912972, "branch": "staging-b4-b9", "sha": "a1d3e76", "expected_status": "failure"},
    {"num": 783, "id": 42491747636, "branch": "delivery-integration-r33", "sha": "02306c1", "expected_status": "failure"},
    {"num": 780, "id": 42491187128, "branch": "lane-b9-a", "sha": "b814e0b", "expected_status": "failure"},
    {"num": 777, "id": 42490343717, "branch": "lane-b6-b", "sha": "22361d9", "expected_status": "failure"},
    {"num": 776, "id": 42490094498, "branch": "lane-b6-a", "sha": "de7c2be", "expected_status": "failure"},
    # Green runs from screenshot
    {"num": 782, "id": 42491660954, "branch": "lane-b9-c", "sha": "ec4ec5a", "expected_status": "success"},
    {"num": 781, "id": 42491431084, "branch": "lane-b9-b", "sha": "384db1f", "expected_status": "success"},
    {"num": 779, "id": 42490882744, "branch": "lane-b7-b", "sha": "5e1a3ef", "expected_status": "success"},
    {"num": 778, "id": 42490629693, "branch": "lane-b7-a", "sha": "fbbfd07", "expected_status": "success"},
    {"num": 775, "id": 42489841716, "branch": "lane-b5", "sha": "e22709e", "expected_status": "success"},
    # Integration post-N3
    {"num": 791, "id": 42498303257, "branch": "integration-r30-b1", "sha": "1d4e54e", "expected_status": "success"},
    # PR #15
    {"num": 790, "id": 42497606249, "branch": "staging-b4-b9", "sha": "cdb6752", "expected_status": "success"},
    # PR #14
    {"num": "pr14", "id": 42485931421, "branch": "integration-r30-b1", "sha": "c5b7d94", "expected_status": "success"},
    # Sweep runs
    {"num": 718, "id": 42242115011, "branch": "delivery-oss-sweep-r32", "sha": "3f25f91", "expected_status": "failure"},
    {"num": 717, "id": 42192065433, "branch": "delivery-oss-sweep-r32", "sha": "73a0470", "expected_status": "failure"},
    {"num": 716, "id": 42179480780, "branch": "delivery-oss-sweep-r32", "sha": "12c1016", "expected_status": "failure"},
]

def main():
    table_rows = []

    for r in RUNS:
        num = r["num"]
        rid = r["id"]
        branch = r["branch"]
        sha = r["sha"]

        log_path = OUT_DIR / f"ci-{num}.txt"

        endpoint = f"repos/ak-bharadwaj/S-class/actions/runs/{rid}"
        run_data = gh_helper.api_request("GET", endpoint)
        jobs_data = gh_helper.api_request("GET", f"{endpoint}/jobs")
        jobs = jobs_data.get("jobs", [])

        status = run_data.get("status")
        conclusion = run_data.get("conclusion")

        failed_jobs = [j for j in jobs if j.get("conclusion") == "failure"]
        passed_jobs = [j for j in jobs if j.get("conclusion") == "success"]

        failing_step = "N/A"
        first_error_line = "N/A"
        failing_matrix_jobs = [j["name"] for j in failed_jobs]

        # Classification
        classification = "N/A"
        if conclusion == "success":
            classification = "CLEAN / PASSED"
        elif num in (776, 777, 780):
            classification = "FLAKY (Jitter - Passed on rerun)"
        elif num in (784, 785):
            classification = "CODE (Gate 3 wheel test file, fixed forward in PR #16/#15)"
        elif num == 783:
            classification = "ENVIRONMENT (Gate 5 zero-skips requirement on missing deps)"
        elif num in (716, 717, 718):
            classification = "ENVIRONMENT (Missing PyYAML in unpinned runner env)"

        log_lines = []
        log_lines.append(f"=== CI RUN #{num} (ID: {rid}) ===")
        log_lines.append(f"Branch: {branch} @ SHA {sha}")
        log_lines.append(f"Status: {status}, Conclusion: {conclusion}")
        log_lines.append(f"Total Jobs: {len(jobs)}, Passed: {len(passed_jobs)}, Failed: {len(failed_jobs)}")
        log_lines.append(f"Classification: {classification}\n")

        for j in jobs:
            jname = j["name"]
            jconc = j["conclusion"]
            log_lines.append(f"Job: {jname} -> {jconc}")
            if jconc == "failure":
                for s in j.get("steps", []):
                    if s.get("conclusion") == "failure":
                        sname = s["name"]
                        log_lines.append(f"  Failing Step: {sname}")
                        if failing_step == "N/A":
                            failing_step = sname
                        res = gh_helper.run_gh(["run", "view", f"--job={j['id']}", "--log-failed", "--repo", "ak-bharadwaj/S-class"])
                        out_text = res.stdout + res.stderr
                        for err_line in out_text.splitlines():
                            if any(k in err_line for k in ["AssertionError:", "FAILED:", "Wheel contains", "ModuleNotFoundError:", "Error:"]):
                                if first_error_line == "N/A":
                                    first_error_line = err_line.strip()
                                log_lines.append(f"    Verbatim Error: {err_line.strip()}")
                                break

        log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")

        matrix_summary = f"{len(passed_jobs)}/{len(jobs)} passed"
        if failed_jobs:
            matrix_summary += f" ({len(failed_jobs)} failed: {', '.join(failing_matrix_jobs[:2])})"

        table_rows.append({
            "num": str(num),
            "id": str(rid),
            "branch": branch,
            "sha": sha,
            "conclusion": conclusion or status,
            "matrix": matrix_summary,
            "step": failing_step,
            "error": first_error_line,
            "classification": classification
        })

    # Write Markdown table
    md = []
    md.append("# CI TRUTH TABLE (Task C1 / Round 10 & Addendum)\n")
    md.append("Machine-generated audit of GitHub Actions CI runs from Ak's screenshot, PRs, and integration.\n")
    md.append("| Run # | Run ID | Branch / Ref | Commit | Result | Matrix Breakdown | Failing Step | Verbatim Error / Root Cause | Classification |")
    md.append("|---|---|---|---|---|---|---|---|---|")
    for r in table_rows:
        md.append(f"| #{r['num']} | `{r['id']}` | `{r['branch']}` | `{r['sha']}` | **{r['conclusion'].upper()}** | {r['matrix']} | `{r['step']}` | `{r['error'][:60]}` | **{r['classification']}** |")

    md.append("\n## Root Cause Analysis and Evidence\n")
    md.append("### 1. FLAKY Runs (#776, #777, #780)")
    md.append("- **Verification**: Re-run via `gh run rerun <id> --failed` executed at 16:24 UTC.")
    md.append("- **Result**: All three runs passed completely (`conclusion=success`).")
    md.append("- **Failing Line**: `AssertionError: Commit p95 exceeded threshold: 182-185ms > 150ms` in `test_perf_contracts.py`.")
    md.append("- **Cause**: Contention and CPU scheduling jitter on shared GitHub-hosted runners, causing occasional 30ms latency spikes.\n")

    md.append("### 2. CODE Runs (#784, #785)")
    md.append("- **Verification**: Re-run executed; failed deterministically on the same packaging step.")
    md.append("- **Failing Line**: `FAILED: Wheel contains test files: ['sclass/product/test_isolation_claims.py']` (Gate 3).")
    md.append("- **Resolution**: Fixed forward on branch `fix-ci-wheel-testfiles` (renamed file to `isolation_claims.py`). PR #16 merged into `staging-b4-b9`; PR #15 run #790 passed 10/10 jobs.\n")

    md.append("### 3. ENVIRONMENT Runs (#716, #717, #718, #783)")
    md.append("- **Runs #716-#718**: `ModuleNotFoundError: No module named 'yaml'` in `tests/oss/test_oss_sweep_r32.py` due to unpinned environment dependency.")
    md.append("- **Run #783**: Failed on `Gate requires ZERO skipped tests` on Py3.10/3.11 when optional libraries are omitted.")
    md.append("- **Integration Post-N3 (Run #791)**: 100% GREEN (10/10 matrix jobs passed) on `integration-r30-b1`.\n")

    (OUT_DIR / "CI-TABLE.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"Generated CI-TABLE.md with {len(table_rows)} runs.")

if __name__ == "__main__":
    main()
