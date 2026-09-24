#!/usr/bin/env python3
"""
Round-Robin Git Commit Utility for S-Class.
Alternates commits between collaborators:
  - Account 1: ak-bharadwaj <dornipaduakshith@gmail.com>
  - Account 2: tHarini1105 <harini0112005@gmail.com>
"""

import sys
import os
import subprocess

ACCOUNT_AK = ("ak-bharadwaj", "dornipaduakshith@gmail.com")
ACCOUNT_HARINI = ("tHarini1105", "harini0112005@gmail.com")


def get_last_commit_author() -> str:
    try:
        res = subprocess.run(
            ["git", "log", "-1", "--format=%an <%ae>"],
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout.strip()
    except Exception:
        return ""


def get_next_author(last_author: str):
    last_lower = last_author.lower()
    if "harini" in last_lower or "harini0112005" in last_lower:
        return ACCOUNT_AK
    else:
        return ACCOUNT_HARINI


def main():
    if len(sys.argv) < 2:
        print("Usage: python tools/roundrobin_commit.py -m \"<commit_message>\" [git options...]")
        sys.exit(1)

    last_author = get_last_commit_author()
    next_name, next_email = get_next_author(last_author)

    print(f"[RoundRobin] Last commit author: {last_author or 'None'}")
    print(f"[RoundRobin] Next commit author: {next_name} <{next_email}>")

    env = dict(os.environ)
    env["GIT_AUTHOR_NAME"] = next_name
    env["GIT_AUTHOR_EMAIL"] = next_email
    env["GIT_COMMITTER_NAME"] = next_name
    env["GIT_COMMITTER_EMAIL"] = next_email

    cmd = ["git", "commit"] + sys.argv[1:]
    res = subprocess.run(cmd, env=env)
    sys.exit(res.returncode)


if __name__ == "__main__":
    main()
