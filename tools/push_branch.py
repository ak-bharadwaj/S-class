#!/usr/bin/env python3
"""Push a branch to origin safely with authenticated token."""
import os
import sys
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gh_helper

def push_branch(branch: str, repo_path: str = "."):
    token = gh_helper.get_token()
    repo_url = f"https://x-access-token:{token}@github.com/ak-bharadwaj/S-class.git"
    cmd = ["git", "-c", "credential.helper=", "push", "-u", repo_url, f"{branch}:{branch}"]
    print(f"Pushing {branch} to origin...")
    res = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True)
    print(res.stdout + res.stderr)
    if res.returncode != 0:
        sys.exit(res.returncode)
    print("Push succeeded!")

if __name__ == "__main__":
    b = sys.argv[1] if len(sys.argv) > 1 else "fix-ci-wheel-testfiles"
    r = sys.argv[2] if len(sys.argv) > 2 else "."
    push_branch(b, r)
