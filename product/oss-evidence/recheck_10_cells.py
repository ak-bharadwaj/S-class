#!/usr/bin/env python3
"""
Standalone 10 Non-Trivial Cell Re-check (Round 2).
Shares ZERO code with regen_facts.py.
Randomly selects 10 non-trivial cells (excluding 'n/a' and 'NOT RETRIEVED')
using a fixed random seed, re-derives them directly from raw files, and asserts equality.
"""
import json
import os
import random
import re

SEED = 20261105
random.seed(SEED)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MD_FILE = os.path.join(ROOT, "product", "OSS-QUALIFICATION-RECORDS.md")
RAW_DIR = os.path.join(ROOT, "product", "oss-evidence", "raw")

# 1. Parse table from markdown
with open(MD_FILE, "r", encoding="utf-8") as f:
    text = f.read()

m = re.search(r"\| Record \| Tool \| Phase \| Role \| Version \(PyPI/npm\) \|.*?(?=\n\n### Judgment per record)", text, re.DOTALL)
assert m, "R9-39 .. R9-65 table not found in markdown"

lines = [l.strip() for l in m.group(0).splitlines() if l.strip().startswith("|")]
headers = [h.strip() for h in lines[0].split("|")[1:-1]]
data_rows = []
for l in lines[2:]:
    parts = [p.strip() for p in l.split("|")[1:-1]]
    if len(parts) == len(headers):
        data_rows.append(dict(zip(headers, parts)))

# 2. Collect eligible non-trivial cells
ELIGIBLE_COLS = [
    "Version (PyPI/npm)",
    "First release",
    "Last release",
    "Licence (metadata)",
    "Licence (raw LICENSE file)",
    "PyPI publisher / source URL",
    "Requires Python",
    "Stars",
    "Pushed at",
    "Advisories"
]

candidates = []
for row in data_rows:
    rec = row["Record"]
    tool = row["Tool"]
    for col in ELIGIBLE_COLS:
        val = row.get(col, "")
        if val and val not in ("n/a", "NOT RETRIEVED"):
            candidates.append((rec, tool, col, val))

# 3. Sample 10 cells
sampled_cells = random.sample(candidates, 10)

TOOL_MAP = {
    "bashlex": {"pypi": "bashlex", "gh": "bashlex"},
    "tree-sitter-bash": {"npm": "tree-sitter-bash", "gh": "tree-sitter-bash"},
    "mvdan-sh": {"gh": "mvdan-sh", "go": "mvdan-sh"},
    "shellcheck": {"gh": "shellcheck"},
    "pyright": {"pypi": "pyright", "npm": "pyright", "gh": "pyright"},
    "pyre-check": {"pypi": "pyre-check", "gh": "pyre-check"},
    "diff-cover": {"pypi": "diff-cover", "gh": "diff-cover"},
    "import-linter": {"pypi": "import-linter", "gh": "import-linter"},
    "detect-secrets": {"pypi": "detect-secrets", "gh": "detect-secrets"},
    "pytest-timeout": {"pypi": "pytest-timeout", "gh": "pytest-timeout"},
    "pytest-rerunfailures": {"pypi": "pytest-rerunfailures", "gh": "pytest-rerunfailures"},
    "pytest-randomly": {"pypi": "pytest-randomly", "gh": "pytest-randomly"},
    "pytest-xdist": {"pypi": "pytest-xdist", "gh": "pytest-xdist"},
    "pip-licenses": {"pypi": "pip-licenses", "gh": "pip-licenses"},
    "licensecheck": {"pypi": "licensecheck", "gh": "licensecheck"},
    "scancode-toolkit": {"pypi": "scancode-toolkit", "gh": "scancode"},
    "in-toto": {"pypi": "in-toto", "gh": "in-toto"},
    "sigstore": {"pypi": "sigstore", "gh": "sigstore-python"},
    "scorecard": {"gh": "scorecard", "go": "scorecard"},
    "promptfoo": {"npm": "promptfoo", "gh": "promptfoo"},
    "garak": {"pypi": "garak", "gh": "garak"},
    "pyrit": {"pypi": "pyrit", "gh": "pyrit"},
    "pygls": {"pypi": "pygls", "gh": "pygls"},
    "lsprotocol": {"pypi": "lsprotocol", "gh": "lsprotocol"},
    "sarif-tools": {"pypi": "sarif-tools", "gh": "sarif-tools"},
    "opengrep": {"pypi": "opengrep", "gh": "opengrep"},
    "pr-agent": {"pypi": "pr-agent", "gh": "pr-agent"},
}

def load_json(name):
    path = os.path.join(RAW_DIR, name)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

def load_raw_text(name):
    path = os.path.join(RAW_DIR, name)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    return None

def independently_rederive_cell(tool, col):
    info = TOOL_MAP[tool]
    pypi_k = info.get("pypi")
    npm_k = info.get("npm")
    gh_k = info.get("gh")

    if col == "Version (PyPI/npm)":
        if pypi_k:
            d = load_json(f"pypi__{pypi_k}.json")
            if d and d.get("info", {}).get("version"):
                return d["info"]["version"]
        if npm_k:
            d = load_json(f"npm__{npm_k}.json")
            if d and d.get("version"):
                return d["version"]
        if gh_k:
            d = load_json(f"gh_release_latest__{gh_k}.json")
            if d and d.get("tag_name"):
                return d["tag_name"]

    elif col == "First release":
        if pypi_k:
            d = load_json(f"pypi__{pypi_k}.json")
            if d and "releases" in d:
                times = [f["upload_time"][:10] for rel in d["releases"].values() for f in rel if "upload_time" in f]
                if times:
                    return min(times)
        if gh_k:
            d = load_json(f"gh_repo__{gh_k}.json")
            if d and "created_at" in d:
                return d["created_at"][:10]

    elif col == "Last release":
        if pypi_k:
            d = load_json(f"pypi__{pypi_k}.json")
            if d and "releases" in d:
                times = [f["upload_time"][:10] for rel in d["releases"].values() for f in rel if "upload_time" in f]
                if times:
                    return max(times)
        if gh_k:
            rel = load_json(f"gh_release_latest__{gh_k}.json")
            if rel and "published_at" in rel:
                return rel["published_at"][:10]
            repo = load_json(f"gh_repo__{gh_k}.json")
            if repo and "pushed_at" in repo:
                return repo["pushed_at"][:10]

    elif col == "Stars":
        if gh_k:
            d = load_json(f"gh_repo__{gh_k}.json")
            if d and "stargazers_count" in d:
                return str(d["stargazers_count"])

    elif col == "Pushed at":
        if gh_k:
            d = load_json(f"gh_repo__{gh_k}.json")
            if d and "pushed_at" in d:
                return d["pushed_at"]

    elif col == "Requires Python":
        if pypi_k:
            d = load_json(f"pypi__{pypi_k}.json")
            if d:
                return d.get("info", {}).get("requires_python") or "n/a"

    elif col == "Licence (metadata)":
        if pypi_k:
            d = load_json(f"pypi__{pypi_k}.json")
            if d and "info" in d:
                info_obj = d["info"]
                lexpr = info_obj.get("license_expression")
                if lexpr and str(lexpr).strip() and str(lexpr).lower() != "none":
                    return str(lexpr).strip()
                lfield = (info_obj.get("license") or "").strip()
                if lfield and lfield.lower() != "none":
                    return lfield.splitlines()[0][:35]
                classifiers = [c.split("::")[-1].strip() for c in info_obj.get("classifiers", []) if c.startswith("License ::")]
                if classifiers:
                    return classifiers[0]
        if npm_k:
            d = load_json(f"npm__{npm_k}.json")
            if d and d.get("license"):
                return str(d["license"]).strip()
        raw_text = load_raw_text(f"gh_license__{gh_k}.txt")
        if raw_text:
            tl = raw_text.lower()
            if "apache license" in tl and "version 2.0" in tl:
                return "Apache-2.0"
            elif "gnu general public license" in tl and "version 3" in tl:
                return "GPL-3.0"
            elif "mit license" in tl or "permission is hereby granted" in tl:
                return "MIT"
            elif "neither the name of" in tl or "bsd 3-clause" in tl:
                return "BSD-3-Clause"
            elif "bsd 2-clause" in tl or "redistribution and use" in tl:
                return "BSD-2-Clause"

    elif col == "Licence (raw LICENSE file)":
        raw_text = load_raw_text(f"gh_license__{gh_k}.txt")
        if raw_text:
            tl = raw_text.lower()
            if "apache license" in tl and "version 2.0" in tl:
                return "Apache-2.0"
            elif "gnu general public license" in tl and "version 3" in tl:
                return "GPL-3.0"
            elif "mit license" in tl or "permission is hereby granted" in tl:
                return "MIT"
            elif "neither the name of" in tl or "bsd 3-clause" in tl:
                return "BSD-3-Clause"
            elif "bsd 2-clause" in tl or "redistribution and use" in tl:
                return "BSD-2-Clause"
            elif "mozilla public license" in tl and "2.0" in tl:
                return "MPL-2.0"
            return "Present (see raw text)"

    elif col == "Advisories":
        adv_json = load_json(f"gh_advisories__{gh_k}.json")
        osv_json = load_json(f"osv_pypi__{pypi_k}.json") if pypi_k else None
        if not osv_json and npm_k:
            osv_json = load_json(f"osv_npm__{npm_k}.json")
        ids = []
        if isinstance(adv_json, list):
            for a in adv_json:
                if isinstance(a, dict) and "ghsa_id" in a:
                    ids.append(a["ghsa_id"])
        if isinstance(osv_json, dict) and "vulns" in osv_json:
            for v in osv_json["vulns"]:
                if v.get("id") and v["id"] not in ids:
                    ids.append(v["id"])
        if isinstance(adv_json, list) or isinstance(osv_json, dict):
            return "0" if not ids else f"{len(ids)} ({', '.join(ids[:2])})"

    elif col == "PyPI publisher / source URL":
        if pypi_k:
            d = load_json(f"pypi__{pypi_k}.json")
            if d:
                author = d.get("info", {}).get("author") or d.get("info", {}).get("author_email") or "None"
                home = d.get("info", {}).get("home_page") or d.get("info", {}).get("project_url") or "None"
                res = f"{author[:25]} / {home[:45]}"
                return res.replace("|", "/")
        if gh_k:
            d = load_json(f"gh_repo__{gh_k}.json")
            if d:
                res = f"{d.get('owner', {}).get('login', 'None')} / {d.get('html_url', 'None')}"
                return res.replace("|", "/")

    return "NOT DERIVED"

def main():
    print(f"Random Seed: {SEED}")
    print(f"Total eligible non-trivial cells: {len(candidates)}")
    print(f"Sampled 10 non-trivial cells for independent verification:\n")
    print(f"| # | Record | Tool | Column | Table Value | Re-derived Value | Match? |")
    print(f"|---|---|---|---|---|---|:---:|")

    mismatches = 0
    for idx, (rec, tool, col, table_val) in enumerate(sampled_cells, 1):
        derived_val = independently_rederive_cell(tool, col)
        is_match = (table_val == derived_val)
        if not is_match:
            mismatches += 1
        status = "PASS" if is_match else "FAIL"
        print(f"| {idx} | {rec} | {tool} | {col} | `{table_val}` | `{derived_val}` | **{status}** |")

    print(f"\nVerification summary: {10 - mismatches}/10 PASSED, {mismatches} mismatches.")
    assert mismatches == 0, f"Found {mismatches} cell value mismatches during re-check!"

if __name__ == "__main__":
    main()
