#!/usr/bin/env python3
"""Create PR for staging-b4-b9 into integration-r30-b1."""
import sys
from pathlib import Path

# Add tools to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import gh_helper

def main():
    prs = gh_helper.api_request("GET", "repos/ak-bharadwaj/S-class/pulls?state=open")
    for pr in prs:
        if pr["head"]["ref"] == "staging-b4-b9" and pr["base"]["ref"] == "integration-r30-b1":
            print(f"PR already exists: #{pr['number']}: {pr['html_url']}")
            return pr["number"]

    pr = gh_helper.api_request("POST", "repos/ak-bharadwaj/S-class/pulls", {
        "title": "feat(blocks4-9): merge Blocks 4-9 complete implementation (CL authorized)",
        "head": "staging-b4-b9",
        "base": "integration-r30-b1",
        "body": "CL AUTHORIZED merge of Blocks 4-9 (14 lanes, 71 MUSTs, 123 fixtures) into integration-r30-b1."
    })
    print(f"Created PR #{pr['number']}: {pr['html_url']}")
    return pr["number"]

if __name__ == "__main__":
    main()
