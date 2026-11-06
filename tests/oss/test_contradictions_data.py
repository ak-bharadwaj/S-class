#!/usr/bin/env python3
"""
Test Parity Between CONTRADICTIONS.md Figures and Raw JSON Evidence.
TASK OSS-EVIDENCE-R31 Round 3.

Fails if any figure in CONTRADICTIONS.md differs from the committed raw JSON.
Specifically validates:
- promptfoo: 26868 stars
- detect-secrets: 4665 stars, 2026-04-02 pushed_at
- pytest-xdist: 1931 stars
- tree-sitter-bash: 335 stars
- opengrep: 3286 stars, v1.33.1 latest release tag
"""
import json
import os
import re
import pytest

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MD_FILE = os.path.join(ROOT_DIR, "product", "oss-evidence", "CONTRADICTIONS.md")
RAW_DIR = os.path.join(ROOT_DIR, "product", "oss-evidence", "raw")

def load_raw_json(name):
    path = os.path.join(RAW_DIR, name)
    assert os.path.exists(path), f"Raw evidence file missing: {path}"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def parse_contradictions():
    assert os.path.exists(MD_FILE), f"CONTRADICTIONS.md missing: {MD_FILE}"
    with open(MD_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    lines = [l.strip() for l in content.splitlines() if l.strip().startswith("|")]
    assert len(lines) >= 3, "CONTRADICTIONS.md table has insufficient rows"
    
    rows = []
    for l in lines[2:]:
        parts = [p.strip() for p in l.split("|")[1:-1]]
        if len(parts) >= 3:
            claim, raw_val, sources = parts[0], parts[1], parts[2]
            rows.append({
                "claim": claim,
                "raw_val": raw_val,
                "sources": sources
            })
    return rows

def test_contradictions_data_matches_raw_json():
    rows = parse_contradictions()
    assert len(rows) >= 11, f"Expected at least 11 contradiction rows, found {len(rows)}"

    tool_checks = {
        "promptfoo": {
            "gh_key": "promptfoo",
            "required_stars": 26868,
            "required_tag": "0.125.1",
        },
        "detect-secrets": {
            "gh_key": "detect-secrets",
            "required_stars": 4665,
            "required_pushed_prefix": "2026-04-02",
        },
        "pytest-xdist": {
            "gh_key": "pytest-xdist",
            "required_stars": 1931,
        },
        "tree-sitter-bash": {
            "gh_key": "tree-sitter-bash",
            "required_stars": 335,
        },
        "opengrep": {
            "gh_key": "opengrep",
            "required_stars": 3286,
            "required_tag": "v1.33.1",
        },
        "diff-cover": {
            "gh_key": "diff-cover",
            "required_stars": 850,
        },
        "pr-agent": {
            "gh_key": "pr-agent",
            "required_stars": 15006,
        },
        "kodus": {
            "gh_key": "kodus",
            "required_stars": 1565,
            "required_advisories": 9,
        },
        "pr-af": {
            "gh_key": "pr-af",
            "required_stars": 665,
        },
        "bashlex": {
            "gh_key": "bashlex",
            "required_stars": 652,
        },
        "pygls": {
            "gh_key": "pygls",
            "required_stars": 813,
        },
    }

    for tool_name, check in tool_checks.items():
        # Find row mentioning this tool in claim
        matching_rows = [r for r in rows if tool_name in r["claim"]]
        assert len(matching_rows) == 1, f"Expected exactly 1 row for {tool_name}, found {len(matching_rows)}"
        row = matching_rows[0]
        raw_val = row["raw_val"]

        # 1. Verify against raw repo JSON
        gh_key = check["gh_key"]
        repo_data = load_raw_json(f"gh_repo__{gh_key}.json")
        expected_stars = repo_data["stargazers_count"]
        expected_pushed_at = repo_data["pushed_at"]

        # Parse stars from raw_val
        m_stars = re.search(r"(\d+)\s+stars", raw_val)
        assert m_stars, f"Could not find stars count in row for {tool_name}: {raw_val}"
        found_stars = int(m_stars.group(1))
        assert found_stars == expected_stars, f"{tool_name} stars mismatch: markdown={found_stars}, raw={expected_stars}"

        # If required_stars specified, check exact CL value
        if "required_stars" in check:
            assert found_stars == check["required_stars"], f"{tool_name} CL required stars mismatch: found={found_stars}, expected={check['required_stars']}"

        # Parse pushed_at from raw_val
        m_pushed = re.search(r"pushed_at:\s*([^\s,;]+)", raw_val)
        assert m_pushed, f"Could not find pushed_at in row for {tool_name}: {raw_val}"
        found_pushed_at = m_pushed.group(1)
        assert found_pushed_at == expected_pushed_at, f"{tool_name} pushed_at mismatch: markdown={found_pushed_at}, raw={expected_pushed_at}"

        if "required_pushed_prefix" in check:
            assert found_pushed_at.startswith(check["required_pushed_prefix"]), f"{tool_name} pushed_at does not start with {check['required_pushed_prefix']}: {found_pushed_at}"

        # Parse latest release tag
        m_tag = re.search(r"latest release:\s*([^\s,;]+)", raw_val)
        assert m_tag, f"Could not find latest release tag in row for {tool_name}: {raw_val}"
        found_tag = m_tag.group(1)

        # Check raw latest release JSON if exists
        expected_tag = None
        lat_path = os.path.join(RAW_DIR, f"gh_release_latest__{gh_key}.json")
        if os.path.exists(lat_path):
            with open(lat_path, "r", encoding="utf-8") as f:
                d = json.load(f)
                if isinstance(d, dict) and d.get("tag_name"):
                    expected_tag = d["tag_name"]
        if not expected_tag:
            rel_path = os.path.join(RAW_DIR, f"gh_releases__{gh_key}.json")
            if os.path.exists(rel_path):
                with open(rel_path, "r", encoding="utf-8") as f:
                    d = json.load(f)
                    if isinstance(d, list) and len(d) > 0 and d[0].get("tag_name"):
                        expected_tag = d[0]["tag_name"]
        if not expected_tag:
            expected_tag = "none"

        assert found_tag == expected_tag, f"{tool_name} tag mismatch: markdown={found_tag}, raw={expected_tag}"
        if "required_tag" in check:
            assert found_tag == check["required_tag"], f"{tool_name} CL required tag mismatch: found={found_tag}, expected={check['required_tag']}"

        # Parse advisories
        m_adv = re.search(r"(\d+)\s+advisories", raw_val)
        assert m_adv, f"Could not find advisories count in row for {tool_name}: {raw_val}"
        found_adv = int(m_adv.group(1))

        adv_path = os.path.join(RAW_DIR, f"gh_advisories__{gh_key}.json")
        expected_adv = 0
        if os.path.exists(adv_path):
            with open(adv_path, "r", encoding="utf-8") as f:
                d = json.load(f)
                if isinstance(d, list):
                    expected_adv = len(d)
                elif isinstance(d, dict):
                    expected_adv = d.get("total_count", len(d.get("vulns", [])))
        assert found_adv == expected_adv, f"{tool_name} advisories mismatch: markdown={found_adv}, raw={expected_adv}"
        if "required_advisories" in check:
            assert found_adv == check["required_advisories"], f"{tool_name} required advisories mismatch: found={found_adv}, expected={check['required_advisories']}"

if __name__ == "__main__":
    test_contradictions_data_matches_raw_json()
    print("All contradiction data verified against raw JSON evidence successfully!")
