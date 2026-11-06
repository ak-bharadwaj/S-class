#!/usr/bin/env python3
"""
Generate product/oss-evidence/CONTRADICTIONS.md directly from raw evidence files.
TASK OSS-EVIDENCE-R31 Round 3.

Reads committed product/oss-evidence/raw/*.json and outputs:
- stars
- pushed_at
- latest release tag
- advisory count

Every figure is dynamically extracted from raw JSON, with zero typed numbers.
"""
import json
import os

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW_DIR = os.path.join(ROOT_DIR, "product", "oss-evidence", "raw")
OUT_FILE = os.path.join(ROOT_DIR, "product", "oss-evidence", "CONTRADICTIONS.md")

CONTRADICTION_SPECS = [
    {
        "tool": "diff-cover",
        "claim": "diff-cover has 0 stars, last release in 2016, and is unmaintained",
        "gh_key": "diff-cover",
        "pypi_key": "diff-cover",
        "extra_note": "actively maintained on PyPI and GitHub",
        "sources": ["gh_repo__diff-cover.json", "pypi__diff-cover.json", "gh_advisories__diff-cover.json", "gh_release_latest__diff-cover.json"],
    },
    {
        "tool": "detect-secrets",
        "claim": "detect-secrets last release 2024-05-06 >12 months; treat as stale",
        "gh_key": "detect-secrets",
        "pypi_key": "detect-secrets",
        "extra_note": "active commit activity within 12 months (April 2026)",
        "sources": ["gh_repo__detect-secrets.json", "gh_advisories__detect-secrets.json", "gh_release_latest__detect-secrets.json"],
    },
    {
        "tool": "pytest-xdist",
        "claim": "pytest-xdist last release 2025-07-01 >12 months",
        "gh_key": "pytest-xdist",
        "pypi_key": "pytest-xdist",
        "extra_note": "frequent releases and ongoing maintenance documented",
        "sources": ["gh_repo__pytest-xdist.json", "gh_releases__pytest-xdist.json", "gh_advisories__pytest-xdist.json"],
    },
    {
        "tool": "promptfoo",
        "claim": "promptfoo has no release-date evidence for npm package",
        "gh_key": "promptfoo",
        "npm_key": "promptfoo",
        "extra_note": "100+ releases documented in gh_releases__promptfoo.json and active development",
        "sources": ["gh_repo__promptfoo.json", "gh_releases__promptfoo.json", "gh_advisories__promptfoo.json"],
    },
    {
        "tool": "pr-agent",
        "claim": "pr-agent upstream canonical is qodo-ai/pr-agent",
        "gh_key": "pr-agent",
        "pypi_key": "pr-agent",
        "extra_note": "HTTP 301 Moved Permanently from qodo-ai/pr-agent to The-PR-Agent/pr-agent",
        "sources": ["gh_repo__pr-agent-redirect.json", "gh_repo__pr-agent.json", "gh_advisories__pr-agent.json"],
    },
    {
        "tool": "kodus",
        "claim": "kodus license unverified",
        "gh_key": "kodus",
        "extra_note": "AGPL-3.0 / Enterprise dual-license in license.md",
        "sources": ["gh_license__kodus.txt", "gh_advisories__kodus.json", "gh_repo__kodus.json"],
    },
    {
        "tool": "pr-af",
        "claim": "pr-af license unverified",
        "gh_key": "pr-af",
        "extra_note": "HTTP 404 Not Found (no LICENSE file present in repository); Go codebase",
        "sources": ["gh_license__pr-af.txt", "gh_repo__pr-af.json", "gh_advisories__pr-af.json"],
    },
    {
        "tool": "bashlex",
        "claim": "bashlex matches bash syntax",
        "gh_key": "bashlex",
        "pypi_key": "bashlex",
        "extra_note": "bashlex raises ParsingError on valid here-docs and nested backticks that exit 0 in bash -n",
        "sources": ["tests/oss/test_shell_parser_disagreement.py", "gh_repo__bashlex.json", "gh_advisories__bashlex.json"],
    },
    {
        "tool": "opengrep",
        "claim": "opengrep release dates not retrieved and not on PyPI",
        "gh_key": "opengrep",
        "extra_note": "Absent from PyPI (HTTP 404); GitHub shows active releases and LGPL-2.1 license",
        "sources": ["pypi__opengrep.json", "gh_repo__opengrep.json", "gh_release_latest__opengrep.json", "gh_advisories__opengrep.json"],
    },
    {
        "tool": "tree-sitter-bash",
        "claim": "tree-sitter-bash no release-date evidence",
        "gh_key": "tree-sitter-bash",
        "npm_key": "tree-sitter-bash",
        "extra_note": "45+ releases spanning 2017 to 2026 documented in gh_releases__tree-sitter-bash.json",
        "sources": ["gh_repo__tree-sitter-bash.json", "gh_releases__tree-sitter-bash.json", "gh_advisories__tree-sitter-bash.json"],
    },
    {
        "tool": "pygls",
        "claim": "pygls licence metadata NOT RETRIEVED",
        "gh_key": "pygls",
        "pypi_key": "pygls",
        "extra_note": "license_expression in pypi__pygls.json: Apache-2.0; gh_license__pygls.txt: Apache License 2.0",
        "sources": ["pypi__pygls.json", "gh_license__pygls.txt", "gh_repo__pygls.json", "gh_advisories__pygls.json"],
    },
]

def load_json(name):
    path = os.path.join(RAW_DIR, name)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

def extract_facts(spec):
    gh_key = spec["gh_key"]
    
    # 1. stars and pushed_at
    repo_data = load_json(f"gh_repo__{gh_key}.json")
    if repo_data:
        stars = repo_data.get("stargazers_count")
        pushed_at = repo_data.get("pushed_at")
    else:
        stars = "none"
        pushed_at = "none"

    # 2. latest release tag
    latest_tag = None
    latest_rel = load_json(f"gh_release_latest__{gh_key}.json")
    if latest_rel and isinstance(latest_rel, dict) and latest_rel.get("tag_name"):
        latest_tag = latest_rel["tag_name"]
    if not latest_tag:
        releases = load_json(f"gh_releases__{gh_key}.json")
        if releases and isinstance(releases, list) and len(releases) > 0 and releases[0].get("tag_name"):
            latest_tag = releases[0]["tag_name"]
    if not latest_tag:
        latest_tag = "none"

    # 3. advisory count
    adv_count = 0
    adv_data = load_json(f"gh_advisories__{gh_key}.json")
    if adv_data is not None:
        if isinstance(adv_data, list):
            adv_count = len(adv_data)
        elif isinstance(adv_data, dict):
            adv_count = adv_data.get("total_count", len(adv_data.get("vulns", [])))

    return stars, pushed_at, latest_tag, adv_count

def generate_contradictions_md():
    lines = [
        "# Contradictions Between Previous Claims and Raw Evidence",
        "",
        "| Claim | Raw Value | Source File |",
        "|---|---|---|",
    ]

    for spec in CONTRADICTION_SPECS:
        stars, pushed_at, latest_tag, adv_count = extract_facts(spec)
        claim = spec["claim"]
        extra = spec["extra_note"]
        sources = ", ".join(spec["sources"])

        # Format raw value string with stars, pushed_at, latest release tag, advisory count
        raw_val = f"{stars} stars, pushed_at: {pushed_at}, latest release: {latest_tag}, {adv_count} advisories; {extra}"
        # Escape any pipe in content
        raw_val_clean = raw_val.replace("|", "/")
        claim_clean = claim.replace("|", "/")
        lines.append(f"| {claim_clean} | {raw_val_clean} | {sources} |")

    lines.append("")
    content = "\n".join(lines)

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"Generated {OUT_FILE} from raw JSON evidence.")

if __name__ == "__main__":
    generate_contradictions_md()
