#!/usr/bin/env python3
"""Investigate failing steps and error lines for red runs."""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))
import gh_helper

RED_RUNS = {
    785: 42495174689,
    784: 42494912972,
    783: 42491747636,
    780: 42491187128,
    777: 42490343717,
    776: 42490094498,
}

def inspect_run(run_num, run_id):
    print(f"\n==================== RUN #{run_num} (ID: {run_id}) ====================")
    endpoint = f"repos/ak-bharadwaj/S-class/actions/runs/{run_id}"
    run_info = gh_helper.api_request("GET", endpoint)
    jobs_info = gh_helper.api_request("GET", f"{endpoint}/jobs")
    jobs = jobs_info.get("jobs", [])
    failed_jobs = [j for j in jobs if j.get("conclusion") == "failure"]
    print(f"Total jobs: {len(jobs)}, Failed jobs: {len(failed_jobs)}")
    for j in failed_jobs:
        job_name = j["name"]
        job_id = j["id"]
        print(f"\n--- Job: {job_name} (ID: {job_id}) ---")
        for s in j.get("steps", []):
            if s.get("conclusion") == "failure":
                print(f"  Failing Step: {s['name']}")
                res = gh_helper.run_gh(["run", "view", f"--job={job_id}", "--log-failed", "--repo", "ak-bharadwaj/S-class"])
                lines = res.stdout.splitlines() + res.stderr.splitlines()
                # Find error line
                err_lines = [l for l in lines if any(k in l for k in ["FAILED:", "##[error]", "E   ", "Error:", "error:"])]
                print(f"  Failing Line(s): {err_lines[:3]}")

if __name__ == "__main__":
    for num, rid in RED_RUNS.items():
        inspect_run(num, rid)
