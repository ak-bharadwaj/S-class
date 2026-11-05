#!/usr/bin/env python3
"""
Independent Re-check of 10 Cells from Regenerated Evidence Columns.
Implements STEP 4 of TASK OSS-EVIDENCE-R31.
"""
import json
import os
import random
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DOC_PATH = os.path.join(ROOT, "product", "OSS-QUALIFICATION-RECORDS.md")
RAW_DIR = os.path.join(ROOT, "product", "oss-evidence", "raw")
MANIFEST_PATH = os.path.join(ROOT, "product", "oss-evidence", "MANIFEST.json")

# Seed selection: print seed as required
SEED = 20261105
random.seed(SEED)
print(f"Random seed for 10-cell selection: {SEED}")

# 1. Parse R9-39..R9-65 table from document
with open(DOC_PATH, "r", encoding="utf-8") as f:
    text = f.read()

table_match = re.search(r"(\| Record \| Tool \| Phase \| Role \| Version .*?\n\n### Judgment per record)", text, re.DOTALL)
assert table_match, "Could not find R9-39..R9-65 table"
table_block = table_match.group(1).strip()
table_lines = [l.strip() for l in table_block.splitlines() if l.strip().startswith("|")]

headers = [h.strip() for h in table_lines[0].split("|")[1:-1]]
data_rows = []
for line in table_lines[2:]:
    parts = [p.strip() for p in line.split("|")[1:-1]]
    if len(parts) == len(headers):
        data_rows.append(dict(zip(headers, parts)))

print(f"Parsed {len(data_rows)} rows from R9-39..R9-65 table.")

# Evidence columns eligible for factual verification
EVIDENCE_COLS = [
    "Version (PyPI/npm)", "First release", "Last release", "Licence (metadata)",
    "Licence (raw LICENSE file)", "Requires Python", "Stars", "Pushed at", "Advisories"
]

all_cells = []
for r in data_rows:
    rec_id = r["Record"]
    tool = r["Tool"]
    for col in EVIDENCE_COLS:
        all_cells.append((rec_id, tool, col, r[col]))

# Sample 10 random cells
sampled_cells = random.sample(all_cells, 10)

def derive_expected(rec_id, tool, col):
    # Mapping to raw files
    gh_map = {
        "bashlex": "bashlex", "tree-sitter-bash": "tree-sitter-bash", "mvdan-sh": "mvdan-sh",
        "shellcheck": "shellcheck", "pyright": "pyright", "pyre-check": "pyre-check",
        "diff-cover": "diff-cover", "import-linter": "import-linter", "detect-secrets": "detect-secrets",
        "pytest-timeout": "pytest-timeout", "pytest-rerunfailures": "pytest-rerunfailures",
        "pytest-randomly": "pytest-randomly", "pytest-xdist": "pytest-xdist", "pip-licenses": "pip-licenses",
        "licensecheck": "licensecheck", "scancode-toolkit": "scancode", "in-toto": "in-toto",
        "sigstore": "sigstore-python", "scorecard": "scorecard", "promptfoo": "promptfoo",
        "garak": "garak", "pyrit": "pyrit", "pygls": "pygls", "lsprotocol": "lsprotocol",
        "sarif-tools": "sarif-tools", "opengrep": "opengrep", "pr-agent": "pr-agent"
    }
    gh_key = gh_map.get(tool)
    
    # Load raw JSONs if present
    pypi_file = os.path.join(RAW_DIR, f"pypi__{tool}.json")
    npm_file = os.path.join(RAW_DIR, f"npm__{tool}.json")
    gh_repo_file = os.path.join(RAW_DIR, f"gh_repo__{gh_key}.json") if gh_key else None
    gh_rel_file = os.path.join(RAW_DIR, f"gh_release_latest__{gh_key}.json") if gh_key else None
    gh_lic_file = os.path.join(RAW_DIR, f"gh_license__{gh_key}.txt") if gh_key else None
    gh_adv_file = os.path.join(RAW_DIR, f"gh_advisories__{gh_key}.json") if gh_key else None
    osv_file = os.path.join(RAW_DIR, f"osv_pypi__{tool}.json")

    pypi_data = json.load(open(pypi_file, encoding="utf-8")) if os.path.exists(pypi_file) else None
    npm_data = json.load(open(npm_file, encoding="utf-8")) if os.path.exists(npm_file) else None
    gh_repo_data = json.load(open(gh_repo_file, encoding="utf-8")) if (gh_repo_file and os.path.exists(gh_repo_file)) else None
    gh_rel_data = json.load(open(gh_rel_file, encoding="utf-8")) if (gh_rel_file and os.path.exists(gh_rel_file)) else None

    if col == "Stars":
        if gh_repo_data and "stargazers_count" in gh_repo_data:
            return str(gh_repo_data["stargazers_count"])
        return "NOT RETRIEVED"

    elif col == "Pushed at":
        if gh_repo_data and "pushed_at" in gh_repo_data:
            return gh_repo_data["pushed_at"]
        return "NOT RETRIEVED"

    elif col == "Version (PyPI/npm)":
        if pypi_data and pypi_data.get("info", {}).get("version"):
            return pypi_data["info"]["version"]
        elif npm_data and npm_data.get("version"):
            return npm_data["version"]
        elif gh_rel_data and gh_rel_data.get("tag_name"):
            return gh_rel_data["tag_name"]
        return "NOT RETRIEVED"

    elif col == "Requires Python":
        if pypi_data:
            return pypi_data.get("info", {}).get("requires_python") or "n/a"
        return "n/a"

    elif col == "Licence (raw LICENSE file)":
        if gh_lic_file and os.path.exists(gh_lic_file):
            txt = open(gh_lic_file, encoding="utf-8", errors="replace").read().lower()
            if "apache license" in txt and "version 2.0" in txt:
                return "Apache-2.0"
            elif "gnu general public license" in txt and "version 3" in txt:
                return "GPL-3.0"
            elif "mit license" in txt or "permission is hereby granted, free of charge" in txt:
                return "MIT"
            elif "bsd 2-clause" in txt:
                return "BSD-2-Clause"
            elif "bsd 3-clause" in txt:
                return "BSD-3-Clause"
            elif "mozilla public license" in txt and "2.0" in txt:
                return "MPL-2.0"
            elif "gnu lesser general public license" in txt and "2.1" in txt:
                return "LGPL-2.1"
            return "Present (see raw text)"
        return "NOT RETRIEVED"

    elif col == "Licence (metadata)":
        if pypi_data:
            l = (pypi_data.get("info", {}).get("license") or "").strip()
            if l:
                return l.splitlines()[0][:35].replace("|", "/")
            classifiers = [c for c in pypi_data.get("info", {}).get("classifiers", []) if c.startswith("License ::")]
            if classifiers:
                return ("classifier: " + classifiers[0].split("::")[-1].strip()).replace("|", "/")
        elif npm_data and npm_data.get("license"):
            return npm_data["license"]
        elif gh_repo_data and gh_repo_data.get("license", {}):
            return gh_repo_data["license"].get("spdx_id") or "NOT RETRIEVED"
        return "NOT RETRIEVED"

    elif col == "First release":
        if pypi_data and "releases" in pypi_data:
            dates = []
            for ver, fls in pypi_data["releases"].items():
                for f in fls:
                    if "upload_time" in f:
                        dates.append(f["upload_time"][:10])
            if dates:
                dates.sort()
                return dates[0]
        elif gh_repo_data and "created_at" in gh_repo_data:
            return gh_repo_data["created_at"][:10]
        return "NOT RETRIEVED"

    elif col == "Last release":
        if pypi_data and "releases" in pypi_data:
            dates = []
            for ver, fls in pypi_data["releases"].items():
                for f in fls:
                    if "upload_time" in f:
                        dates.append(f["upload_time"][:10])
            if dates:
                dates.sort()
                return dates[-1]
        elif gh_rel_data and "published_at" in gh_rel_data:
            return gh_rel_data["published_at"][:10]
        elif gh_repo_data and "pushed_at" in gh_repo_data:
            return gh_repo_data["pushed_at"][:10]
        return "NOT RETRIEVED"

    elif col == "Advisories":
        adv_json = json.load(open(gh_adv_file)) if (gh_adv_file and os.path.exists(gh_adv_file)) else None
        osv_json = json.load(open(osv_file)) if os.path.exists(osv_file) else None
        adv_ids = []
        if isinstance(adv_json, list):
            for a in adv_json:
                if isinstance(a, dict) and "ghsa_id" in a:
                    adv_ids.append(a["ghsa_id"])
        if isinstance(osv_json, dict) and "vulns" in osv_json:
            for v in osv_json.get("vulns", []):
                vid = v.get("id")
                if vid and vid not in adv_ids:
                    adv_ids.append(vid)
        if not adv_ids:
            return "0"
        return f"{len(adv_ids)} ({', '.join(adv_ids[:2])})"

    return "UNKNOWN"

recheck_results = []
mismatches = 0

print("\n--- 10-CELL RECHECK TABLE ---")
print("| # | Record | Tool | Column | Expected (from Raw File) | Actual (in Document) | Result | Source File |")
print("|---|---|---|---|---|---|:---:|---|")

out_lines = [
    f"# Independent 10-Cell Re-check Verification (Seed: {SEED})",
    "",
    "| # | Record | Tool | Column | Expected (from Raw File) | Actual (in Document) | Match | Source Raw File |",
    "|:---:|---|---|---|---|---|:---:|---|"
]

for idx, (rec_id, tool, col, actual_val) in enumerate(sampled_cells, 1):
    expected_val = derive_expected(rec_id, tool, col)
    # Determine source file
    src_file = "raw evidence"
    if col in ("Stars", "Pushed at"):
        src_file = f"gh_repo__{tool}.json"
    elif col in ("Version (PyPI/npm)", "First release", "Last release", "Requires Python"):
        src_file = f"pypi__{tool}.json" if os.path.exists(os.path.join(RAW_DIR, f"pypi__{tool}.json")) else f"gh_repo__{tool}.json"
    elif col == "Licence (raw LICENSE file)":
        src_file = f"gh_license__{tool}.txt"
    elif col == "Advisories":
        src_file = f"gh_advisories__{tool}.json / osv"

    match = (expected_val == actual_val)
    if not match:
        mismatches += 1
    res_str = "MATCH" if match else "MISMATCH"
    
    print(f"| {idx} | {rec_id} | {tool} | {col} | `{expected_val}` | `{actual_val}` | **{res_str}** | `{src_file}` |")
    out_lines.append(f"| {idx} | {rec_id} | {tool} | {col} | `{expected_val}` | `{actual_val}` | **{res_str}** | `{src_file}` |")

out_lines.append("")
out_lines.append(f"**Verification Outcome:** {10 - mismatches} / 10 cells matched exactly. Mismatches: {mismatches}.")

out_recheck_path = os.path.join(ROOT, "delivery-oss-evidence-r31", "raw_recheck_10_cells.txt")
with open(out_recheck_path, "w", encoding="utf-8") as f:
    f.write("\n".join(out_lines) + "\n")

print(f"\nWrote recheck table to {out_recheck_path}")
if mismatches > 0:
    print(f"STOP: Found {mismatches} mismatches!")
    sys.exit(1)
else:
    print("SUCCESS: 0 mismatches found across all 10 independent cell checks.")
