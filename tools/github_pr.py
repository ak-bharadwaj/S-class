#!/usr/bin/env python3
"""Manage GitHub PRs and CI checks for S-Class integration."""
import json
import subprocess
import sys
import urllib.request
import urllib.error

REPO = "ak-bharadwaj/S-class"

def get_token() -> str:
    res = subprocess.run(
        ["/mnt/c/Program Files/Git/mingw64/bin/git-credential-manager.exe", "get"],
        input="protocol=https\nhost=github.com\n\n",
        capture_output=True,
        text=True,
        check=True
    )
    for line in res.stdout.splitlines():
        if line.startswith("password="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError("Password/token not found in git-credential-manager")

def api_request(method: str, path: str, data: dict = None) -> dict:
    token = get_token()
    url = f"https://api.github.com/{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "Antigravity-Agent"
    }
    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            content = resp.read().decode("utf-8")
            return json.loads(content) if content else {}
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="replace")
        print(f"HTTPError {e.code} for {url}: {err_msg}", file=sys.stderr)
        raise

if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "list"
    if action == "list":
        prs = api_request("GET", f"repos/{REPO}/pulls?state=open")
        for pr in prs:
            print(f"PR #{pr['number']}: {pr['title']} ({pr['head']['ref']} -> {pr['base']['ref']}) {pr['html_url']}")
    elif action == "create":
        head = sys.argv[2]
        base = sys.argv[3]
        title = sys.argv[4]
        body = sys.argv[5] if len(sys.argv) > 5 else ""
        res = api_request("POST", f"repos/{REPO}/pulls", {
            "title": title,
            "head": head,
            "base": base,
            "body": body
        })
        print(f"Created PR #{res['number']}: {res['html_url']}")
    elif action == "checks":
        ref = sys.argv[2]
        runs = api_request("GET", f"repos/{REPO}/commits/{ref}/check-runs")
        print(f"Check runs for {ref}: {runs.get('total_count', 0)}")
        for cr in runs.get("check_runs", []):
            print(f"  - {cr['name']}: {cr['status']} ({cr.get('conclusion')}) {cr.get('html_url')}")
    elif action == "actions":
        runs = api_request("GET", f"repos/{REPO}/actions/runs?per_page=10")
        for r in runs.get("workflow_runs", []):
            print(f"Run #{r['id']}: {r['name']} on {r['head_branch']} ({r['status']}, {r['conclusion']}) {r['html_url']}")
    elif action == "merge":
        pr_num = int(sys.argv[2])
        title = sys.argv[3] if len(sys.argv) > 3 else f"Merge PR #{pr_num}"
        res = api_request("PUT", f"repos/{REPO}/pulls/{pr_num}/merge", {
            "commit_title": title,
            "merge_method": "merge"
        })
        print(f"Merged PR #{pr_num}: {res.get('sha')} (merged={res.get('merged')})")
    elif action == "job":
        job_id = sys.argv[2]
        data = api_request("GET", f"repos/{REPO}/actions/jobs/{job_id}")
        for step in data.get("steps", []):
            print(f"  Step '{step['name']}': status={step['status']}, conclusion={step.get('conclusion')}")
