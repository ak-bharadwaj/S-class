#!/usr/bin/env python3
"""Check CI workflow runs and check-runs for a given branch or PR."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gh_helper

def check_runs_for_ref(ref: str):
    data = gh_helper.api_request("GET", f"repos/ak-bharadwaj/S-class/commits/{ref}/check-runs")
    check_runs = data.get("check_runs", [])
    print(f"Total check runs for {ref}: {len(check_runs)}")
    for cr in check_runs:
        print(f"  - {cr['name']}: status={cr['status']}, conclusion={cr.get('conclusion')}, url={cr.get('html_url')}")
    return check_runs

def get_latest_action_runs(branch: str = None, limit: int = 5):
    endpoint = f"repos/ak-bharadwaj/S-class/actions/runs?per_page={limit}"
    if branch:
        endpoint += f"&branch={branch}"
    data = gh_helper.api_request("GET", endpoint)
    runs = data.get("workflow_runs", [])
    for r in runs:
        print(f"Run #{r['id']} ({r['name']}): status={r['status']}, conclusion={r['conclusion']}, branch={r['head_branch']}, event={r['event']}, commit={r['head_sha'][:8]}")
    return runs

if __name__ == "__main__":
    branch = sys.argv[1] if len(sys.argv) > 1 else "staging-b4-b9"
    print(f"=== Action runs on {branch} ===")
    get_latest_action_runs(branch)
    print("\n=== Check runs on origin/staging-b4-b9 (6670bfc0) ===")
    check_runs_for_ref("6670bfc03cb5f14f24d3596893f734bbfce5e8bd")
