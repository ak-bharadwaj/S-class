#!/usr/bin/env python3
"""Extract CI truth for required runs into delivery-ci/."""
import os
import sys
import json
import subprocess
from pathlib import Path

# Repo root
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))
import gh_helper

DELIVERY_CI = REPO_ROOT / "delivery-ci"
DELIVERY_CI.mkdir(parents=True, exist_ok=True)

RUN_MAP = {
    "716": 42179480780,
    "717": 42192065433,
    "718": 42242115011,
    "pr13": 42484511346,
    "pr14": 42485495793,
    "pr15": 42497606249,
}

def get_run_details(run_id: int):
    endpoint = f"repos/ak-bharadwaj/S-class/actions/runs/{run_id}"
    run_info = gh_helper.api_request("GET", endpoint)
    jobs_info = gh_helper.api_request("GET", f"{endpoint}/jobs")
    return run_info, jobs_info.get("jobs", [])

def extract_for_run(run_key: str, run_id: int):
    run_info, jobs = get_run_details(run_id)
    out_file = DELIVERY_CI / f"ci-{run_key}.txt"

    workflow_name = run_info.get("name", "Unknown")
    run_number = run_info.get("run_number")
    conclusion = run_info.get("conclusion")
    status = run_info.get("status")
    html_url = run_info.get("html_url")
    head_branch = run_info.get("head_branch")
    head_sha = run_info.get("head_sha")

    lines = []
    lines.append(f"Workflow: {workflow_name}")
    lines.append(f"Run ID: {run_id}")
    lines.append(f"Run Number: {run_number}")
    lines.append(f"Branch: {head_branch}")
    lines.append(f"Commit: {head_sha}")
    lines.append(f"Status: {status}")
    lines.append(f"Conclusion: {conclusion}")
    lines.append(f"URL: {html_url}")
    lines.append("")

    failed_jobs = [j for j in jobs if j.get("conclusion") == "failure"]
    if not failed_jobs:
        lines.append(f"Result: SUCCESS - all {len(jobs)} jobs passed.")
        for j in jobs:
            lines.append(f"  Job: {j['name']} -> conclusion={j.get('conclusion')}")
    else:
        lines.append(f"Result: FAILURE - {len(failed_jobs)} of {len(jobs)} jobs failed.")
        lines.append("")
        for j in failed_jobs:
            job_name = j["name"]
            job_id = j["id"]
            job_url = j.get("html_url")
            lines.append(f"--- Job: {job_name} (ID: {job_id}) ---")
            lines.append(f"Job URL: {job_url}")

            # Find failing step
            failing_steps = [s for s in j.get("steps", []) if s.get("conclusion") == "failure"]
            for step in failing_steps:
                lines.append(f"Failing Step: {step['name']}")
                lines.append(f"Step Status: {step['status']}, Conclusion: {step.get('conclusion')}")

                # Fetch log via gh run view --job=<id> --log-failed
                res = gh_helper.run_gh(["run", "view", f"--job={job_id}", "--log-failed", "--repo", "ak-bharadwaj/S-class"])
                first_error = None
                log_lines = res.stdout.splitlines() + res.stderr.splitlines()
                for line in log_lines:
                    if "FAILED:" in line or "##[error]" in line or "Error:" in line or "error:" in line:
                        first_error = line.strip()
                        break
                if not first_error and log_lines:
                    # Pick last 3 lines or non-empty line
                    for l in reversed(log_lines):
                        if l.strip():
                            first_error = l.strip()
                            break

                lines.append(f"First Failing Error Line Verbatim: {first_error if first_error else 'N/A'}")
                lines.append("Failing Log Snippet:")
                # Include relevant log snippet
                relevant_lines = [l for l in log_lines if any(k in l for k in ["FAILED", "FAIL", "Error", "error", "Process completed"])]
                lines.extend(relevant_lines[:20] if relevant_lines else log_lines[-15:])
            lines.append("")

    content = "\n".join(lines) + "\n"
    out_file.write_text(content, encoding="utf-8")
    print(f"Wrote {out_file} ({len(lines)} lines)")
    return content

if __name__ == "__main__":
    if len(sys.argv) > 2:
        k = sys.argv[1]
        rid = int(sys.argv[2])
        print(f"Extracting CI truth for {k} (run {rid})...")
        extract_for_run(k, rid)
    else:
        for key, run_id in RUN_MAP.items():
            print(f"Extracting CI truth for {key} (run {run_id})...")
            extract_for_run(key, run_id)
