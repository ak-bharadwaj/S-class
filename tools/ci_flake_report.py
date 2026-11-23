"""T12: Report CI jobs that failed on an earlier attempt and passed on a later attempt."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from typing import Any, Dict, List


def gh_api_json(endpoint: str) -> Any:
    raw = subprocess.check_output(["gh", "api", endpoint], text=True, encoding="utf-8")
    return json.loads(raw)


def gh_api_text(endpoint: str) -> str:
    res = subprocess.run(
        ["gh", "api", endpoint],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return res.stdout if res.returncode == 0 else ""


def find_flaked_jobs(repo: str, run_id: int) -> List[Dict[str, Any]]:
    run_info = gh_api_json(f"repos/{repo}/actions/runs/{run_id}")
    max_attempt = int(run_info.get("run_attempt", 1))
    by_name: Dict[str, Dict[int, Dict[str, Any]]] = {}

    for attempt in range(1, max_attempt + 1):
        data = gh_api_json(f"repos/{repo}/actions/runs/{run_id}/attempts/{attempt}/jobs?per_page=100")
        for job in data.get("jobs", []):
            by_name.setdefault(job["name"], {})[attempt] = job

    flakes: List[Dict[str, Any]] = []
    for name, attempts in sorted(by_name.items()):
        failed_attempts = [a for a, j in sorted(attempts.items()) if j.get("conclusion") == "failure"]
        passed_attempts = [a for a, j in sorted(attempts.items()) if j.get("conclusion") == "success"]
        if failed_attempts and passed_attempts and max(passed_attempts) > min(failed_attempts):
            failed_tests: List[str] = []
            for fa in failed_attempts:
                job_id = attempts[fa]["id"]
                log_txt = gh_api_text(f"repos/{repo}/actions/jobs/{job_id}/logs")
                for m in re.finditer(r"(?:FAILED|ERROR)\s+([^\s]+::[^\s]+)", log_txt):
                    if m.group(1) not in failed_tests:
                        failed_tests.append(m.group(1))
            flakes.append(
                {
                    "job_name": name,
                    "failed_attempts": failed_attempts,
                    "passed_attempts": passed_attempts,
                    "failed_tests": failed_tests,
                }
            )
    return flakes


def main() -> int:
    parser = argparse.ArgumentParser(description="Report CI job flakes across run attempts")
    parser.add_argument("--repo", default="ak-bharadwaj/S-class")
    parser.add_argument("--run-id", type=int, default=45012077485)
    args = parser.parse_args()

    flakes = find_flaked_jobs(args.repo, args.run_id)
    print(f"Flake report for {args.repo} run {args.run_id}: {len(flakes)} flaked job(s)")
    for f in flakes:
        print(
            f"  JOB: {f['job_name']} | failed_attempts={f['failed_attempts']} | "
            f"passed_attempts={f['passed_attempts']} | failed_tests={f['failed_tests']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
