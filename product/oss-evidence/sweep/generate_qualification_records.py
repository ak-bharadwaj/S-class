import os
import re
import json
import yaml
import glob
from datetime import datetime

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
CANDIDATES_YAML = os.path.join(REPO_ROOT, "product/oss-evidence/sweep/candidates.yaml")
RAW_SWEEP = os.path.join(REPO_ROOT, "product/oss-evidence/sweep/raw")
RAW_R31 = os.path.join(REPO_ROOT, "product/oss-evidence/raw")
TARGET_MD = os.path.join(REPO_ROOT, "product/OSS-QUALIFICATION-RECORDS.md")
STANDALONE_MD = os.path.join(REPO_ROOT, "product/oss-evidence/sweep/qualification_records_r32.md")

OVERLAP_TOOLS = {
    "pyre-check", "pyrit", "ruff", "semgrep", "pr-agent", "qodo-pr-agent", "promptfoo", "pyright-mismatch-control"
}

def clean_filename(s):
    return re.sub(r'[^a-zA-Z0-9_\-\.]', '_', s)

def load_json(p):
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                return json.load(f)
        except Exception:
            return None
    return None

def load_text(p):
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                return f.read()
        except Exception:
            return None
    return None

def classify_license(license_text, gh_spdx=None):
    if not license_text:
        if gh_spdx:
            spdx = gh_spdx.upper()
            if spdx in ["MIT", "APACHE-2.0", "BSD-2-CLAUSE", "BSD-3-CLAUSE", "ISC", "UNLICENSE", "CC0-1.0"]:
                return "PERMISSIVE", gh_spdx, None
            if "GPL-3.0" in spdx or "GPL-2.0" in spdx or "AGPL" in spdx:
                return "STRONG-COPYLEFT", gh_spdx, None
            if "LGPL" in spdx or "MPL" in spdx or "EPL" in spdx:
                return "WEAK-COPYLEFT", gh_spdx, None
            return "PROPRIETARY/UNKNOWN", gh_spdx, None
        return "MISSING", "NONE", None

    txt_upper = license_text.upper()
    if "APACHE LICENSE" in txt_upper or "APACHE-2.0" in txt_upper:
        return "PERMISSIVE", "Apache-2.0", "Apache License"
    if "MIT LICENSE" in txt_upper or "PERMISSION IS HEREBY GRANTED" in txt_upper:
        return "PERMISSIVE", "MIT", "Permission is hereby granted, free of charge"
    if "BSD 3-CLAUSE" in txt_upper or "REDISTRIBUTION AND USE IN SOURCE AND BINARY FORMS" in txt_upper:
        return "PERMISSIVE", "BSD-3-Clause", "Redistribution and use in source and binary forms"
    if "BSD 2-CLAUSE" in txt_upper:
        return "PERMISSIVE", "BSD-2-Clause", "Redistribution and use in source and binary forms"
    if "MOZILLA PUBLIC LICENSE" in txt_upper or "MPL 2.0" in txt_upper:
        return "WEAK-COPYLEFT", "MPL-2.0", "Mozilla Public License"
    if "LESSER GENERAL PUBLIC LICENSE" in txt_upper or "LGPL" in txt_upper:
        return "WEAK-COPYLEFT", "LGPL-2.1-or-later", "Lesser General Public License"
    if "GNU GENERAL PUBLIC LICENSE" in txt_upper or "GPL" in txt_upper:
        return "STRONG-COPYLEFT", "GPL-3.0", "GNU General Public License"

    if gh_spdx:
        return "PERMISSIVE", gh_spdx, None

    return "PROPRIETARY/UNKNOWN", "UNKNOWN", None

# Cache directory listings once for high performance
RAW_SWEEP_FILES = set(os.listdir(RAW_SWEEP)) if os.path.exists(RAW_SWEEP) else set()
RAW_R31_FILES = set(os.listdir(RAW_R31)) if os.path.exists(RAW_R31) else set()

def extract_dates_and_versions(tool_id, repo_name):
    safe_id = clean_filename(tool_id)
    safe_repo = clean_filename(repo_name) if repo_name else safe_id

    # 1. repo created
    repo_created = None
    for d, d_files in [(RAW_SWEEP, RAW_SWEEP_FILES), (RAW_R31, RAW_R31_FILES)]:
        fn1 = f"gh_repo__{safe_repo}.json"
        fn2 = f"gh_repo__{safe_id}.json"
        p = None
        if fn1 in d_files:
            p = os.path.join(d, fn1)
        elif fn2 in d_files:
            p = os.path.join(d, fn2)
        if p and os.path.exists(p):
            data = load_json(p)
            if data and data.get("created_at"):
                repo_created = data["created_at"][:10]
                break

    # 2. github releases
    first_gh = None
    latest_gh = None
    for d, d_files in [(RAW_SWEEP, RAW_SWEEP_FILES), (RAW_R31, RAW_R31_FILES)]:
        fn1 = f"gh_releases__{safe_id}.json"
        fn2 = f"gh_releases__{safe_repo}.json"
        p = None
        if fn1 in d_files:
            p = os.path.join(d, fn1)
        elif fn2 in d_files:
            p = os.path.join(d, fn2)
        if p and os.path.exists(p):
            data = load_json(p)
            if isinstance(data, list) and len(data) > 0:
                dates = [r.get("published_at", "")[:10] for r in data if r.get("published_at")]
                if dates:
                    first_gh = min(dates)
                if data[0].get("tag_name"):
                    latest_gh = data[0]["tag_name"]
                break
        fn_latest = f"gh_release_latest__{safe_id}.json"
        if fn_latest in d_files and not latest_gh:
            data = load_json(os.path.join(d, fn_latest))
            if isinstance(data, dict) and data.get("tag_name"):
                latest_gh = data["tag_name"]

    # 3. registry releases (PyPI or npm)
    first_reg = None
    latest_reg = None
    
    # check PyPI in R31 and sweep
    for d, d_files in [(RAW_SWEEP, RAW_SWEEP_FILES), (RAW_R31, RAW_R31_FILES)]:
        pypi_matches = [os.path.join(d, f) for f in d_files if f.startswith(f"pypi_{safe_id}_") or f == f"pypi__{safe_id}.json"]
        if pypi_matches:
            pdata = load_json(pypi_matches[0])
            if pdata:
                if "info" in pdata and pdata["info"].get("version"):
                    latest_reg = pdata["info"]["version"]
                if "releases" in pdata and isinstance(pdata["releases"], dict):
                    reg_dates = []
                    for v, files in pdata["releases"].items():
                        for f in files:
                            if f.get("upload_time"):
                                reg_dates.append(f["upload_time"][:10])
                    if reg_dates:
                        first_reg = min(reg_dates)
                break

    # check npm in R31 and sweep
    for d, d_files in [(RAW_SWEEP, RAW_SWEEP_FILES), (RAW_R31, RAW_R31_FILES)]:
        npm_matches = [os.path.join(d, f) for f in d_files if f.startswith(f"npm_{safe_id}_") or f == f"npm__{safe_id}.json"]
        if npm_matches:
            ndata = load_json(npm_matches[0])
            if ndata:
                if "dist-tags" in ndata and ndata["dist-tags"].get("latest"):
                    latest_reg = ndata["dist-tags"]["latest"]
                if "time" in ndata and isinstance(ndata["time"], dict):
                    ndates = [v[:10] for k, v in ndata["time"].items() if k not in ["created", "modified"] and len(v) >= 10]
                    if ndates:
                        first_reg = min(ndates)
                break

    # Calculate earliest date for Age
    all_dates = [d for d in [repo_created, first_gh, first_reg] if d]
    earliest_date = min(all_dates) if all_dates else None
    
    age_years = None
    if earliest_date:
        d0 = datetime.fromisoformat(earliest_date)
        d_ref = datetime.fromisoformat("2026-04-16")
        age_years = round((d_ref - d0).days / 365.25, 2)

    # Determine latest version
    latest_version = latest_reg or latest_gh or "NO_RELEASE"

    return {
        "repo_created": repo_created,
        "first_gh": first_gh,
        "first_reg": first_reg,
        "earliest_date": earliest_date,
        "age_years": age_years,
        "latest_gh": latest_gh,
        "latest_reg": latest_reg,
        "latest_version": latest_version
    }

def main():
    with open(CANDIDATES_YAML, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    cands = data["candidates"]

    # Header conforming strictly to Section 3 table specification
    headers = [
        "Record",
        "Phase tags",
        "Tool",
        "Canonical repo / spec URL",
        "Licence class + SPDX",
        "Age / Earliest Release",
        "Version / Latest Release",
        "Stars",
        "Repo flags",
        "Advisories (GH/OSV)",
        "Engines / Python",
        "Publisher / org",
        "Identity check",
        "Evidence prefixes",
        "Fit (CL)",
        "Strongest reason not to use (CL)",
        "Independent pair (CL)",
        "Level (CL)",
        "Mature? (arithmetic)",
        "Arithmetic failure reasons / Notes"
    ]

    lines = []
    lines.append("## R32 sweep: Comprehensive SDLC and Frameworks Qualification Records\n")
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")

    rec_num = 66
    records = []

    for c in cands:
        cid = c["id"]
        # Skip tools already in R9-01..R9-65
        if cid in OVERLAP_TOOLS:
            continue

        rec_id = f"R9-{rec_num}"
        rec_num += 1

        phase_tags = "; ".join(c.get("phase_tags", []))
        tool_name = c.get("display_name", cid)
        repo = c.get("canonical_repo", "UNRESOLVED")

        # Load raw repo JSON
        safe_repo = clean_filename(repo)
        safe_id = clean_filename(cid)

        repo_json = load_json(os.path.join(RAW_SWEEP, f"gh_repo__{safe_repo}.json"))
        if not repo_json:
            repo_json = load_json(os.path.join(RAW_SWEEP, f"gh_repo__{safe_id}.json"))

        lic_txt = load_text(os.path.join(RAW_SWEEP, f"gh_license__{safe_id}.txt"))
        lic_json = load_json(os.path.join(RAW_SWEEP, f"gh_license__{safe_id}.json"))
        adv_json = load_json(os.path.join(RAW_SWEEP, f"gh_advisories__{safe_id}.json"))

        # Stars & Pushed
        stars_str = "NA"
        pushed_str = "NA"
        if repo_json and isinstance(repo_json, dict):
            stars_str = str(repo_json.get("stargazers_count", "NA"))
            pushed_str = repo_json.get("pushed_at", "NA")[:10]

        # Flags: fork, archived, moved
        flags_list = []
        if c.get("archived") or (repo_json and repo_json.get("archived")):
            flags_list.append("archived")
        if c.get("is_fork") or (repo_json and repo_json.get("fork")):
            parent = c.get("parent_repo") or (repo_json.get("parent", {}).get("full_name") if repo_json else "upstream")
            flags_list.append(f"fork_of={parent}")
        if c.get("moved_to"):
            flags_list.append(f"moved_to={c.get('moved_to')}")
        repo_flags = "; ".join(flags_list) if flags_list else "NONE"

        # Publisher / org
        publisher = repo.split("/")[0] if "/" in repo else "NA"

        # License
        gh_spdx = None
        if lic_json and isinstance(lic_json, dict) and lic_json.get("license"):
            gh_spdx = lic_json["license"].get("spdx_id")
        lic_class, lic_spdx, lic_quote = classify_license(lic_txt, gh_spdx)
        lic_str = f"{lic_class} ({lic_spdx})"
        if lic_quote:
            lic_str += f' [Quote: "{lic_quote}"]'

        # Extract dates and versions with rigorous arithmetic
        dv = extract_dates_and_versions(cid, repo)
        
        # Earliest date & Age string
        earliest_date_str = dv["earliest_date"] or "NO_DATE"
        age_years = dv["age_years"]
        if age_years is not None:
            first_rel_str = f"{earliest_date_str} ({age_years}y)"
        else:
            first_rel_str = f"{earliest_date_str} (NA)"

        # Latest version string
        latest_ver_str = dv["latest_version"]
        if dv["latest_gh"] and dv["latest_gh"] != latest_ver_str:
            latest_ver_str = f"{latest_ver_str} / gh={dv['latest_gh']}"

        # Advisories
        gh_adv_count = len(adv_json) if adv_json and isinstance(adv_json, list) else 0
        osv_count = 0
        osv_files = [f for f in RAW_SWEEP_FILES if f.startswith(f"osv_") and f"__{safe_id}.json" in f]
        for of in osv_files:
            odata = load_json(os.path.join(RAW_SWEEP, of))
            if odata and isinstance(odata, dict) and odata.get("vulns"):
                osv_count += len(odata["vulns"])
        advisories_str = f"{gh_adv_count} GH / {osv_count} OSV"

        # Engines / Python
        engines_str = "NA"
        if repo_json and repo_json.get("language"):
            engines_str = repo_json["language"]

        # Identity check
        id_info = c.get("identity_checks", {})
        id_status = id_info.get("status", "NA")
        id_details = id_info.get("details", "")
        
        # If mismatch, output both URLs
        if id_status == "MISMATCH":
            reg_repos = id_info.get("registry_repos", [])
            if reg_repos:
                wrapper_url = f"https://github.com/{reg_repos[0]}"
            else:
                wrapper_url = id_info.get("wrapper_url", c.get("wrapper_url", "https://github.com/RobertCraigie/pyright-python"))
            canonical_url = id_info.get("canonical_url", f"https://github.com/{repo}")
            identity_str = f"MISMATCH: wrapper {wrapper_url} vs canonical {canonical_url}"
        else:
            identity_str = f"{id_status}: {id_details}"

        # Evidence prefixes
        ev_prefixes = f"gh_repo__{safe_repo}; gh_release_latest__{safe_id}; gh_releases__{safe_id}; gh_advisories__{safe_id}; gh_license__{safe_id}"

        # 6 Objective arithmetic flags
        # 1. age >= 2y (first release <= 2024-04-16)
        age_ok = age_years is not None and age_years >= 2.0

        # 2. version >= 1.0.0
        ver_ok = False
        v_match = re.search(r'v?(\d+)\.(\d+)', latest_ver_str)
        if v_match:
            major = int(v_match.group(1))
            ver_ok = major >= 1

        # 3. stars >= 500
        stars_ok = False
        if stars_str.isdigit():
            stars_ok = int(stars_str) >= 500

        # 4. pushed <= 1y ago (>= 2025-04-16)
        pushed_ok = False
        if pushed_str != "NA":
            pushed_ok = pushed_str >= "2025-04-16"

        # 5. licence is permissive or weak-copyleft
        lic_ok = lic_class in ["PERMISSIVE", "WEAK-COPYLEFT"]

        # 6. identity check status OK or MATCH
        id_ok = id_status in ["OK", "MATCH", "VALID"]

        arith_failures = []
        if not age_ok:
            arith_failures.append(f"age <2y (earliest={earliest_date_str})")
        if not ver_ok:
            arith_failures.append(f"version <1.0.0 ({latest_ver_str})")
        if not stars_ok:
            arith_failures.append(f"stars <500 ({stars_str})")
        if not pushed_ok:
            arith_failures.append(f"pushed >1y ago ({pushed_str})")
        if not lic_ok:
            arith_failures.append(f"licence not permissive/weak-copyleft ({lic_str})")
        if not id_ok:
            arith_failures.append(f"identity not verified ({id_status})")

        # Explicit input logging for Age and Version
        inputs_note = f"Inputs: repo_created={dv['repo_created']}, first_gh={dv['first_gh']}, first_reg={dv['first_reg']} -> earliest={earliest_date_str}; gh_ver={dv['latest_gh']}, reg_ver={dv['latest_reg']} -> latest={latest_ver_str}"
        if arith_failures:
            failures_str = "; ".join(arith_failures) + f" | {inputs_note}"
            mature_status = "MATURE_OBJECTIVE_FAIL"
        else:
            failures_str = f"None | {inputs_note}"
            mature_status = "MATURE_OBJECTIVE_PASS"

        # Add record
        record_data = {
            "record": rec_id,
            "phase_tags": phase_tags,
            "tool": tool_name,
            "canonical_repo": repo,
            "license": lic_str,
            "first_release": first_rel_str,
            "latest_version": latest_ver_str,
            "stars": stars_str,
            "flags": repo_flags,
            "advisories": advisories_str,
            "engines": engines_str,
            "publisher": publisher,
            "identity": identity_str,
            "evidence_prefixes": ev_prefixes,
            "fit": "CL",
            "reason_not": "CL",
            "pair": "CL",
            "level": "CL",
            "mature_status": mature_status,
            "arithmetic": failures_str
        }
        records.append(record_data)

    pass_count = sum(1 for r in records if "MATURE_OBJECTIVE_PASS" in r["mature_status"])
    fail_count = len(records) - pass_count

    for r in records:
        row = (
            f"| {r['record']} "
            f"| {r['phase_tags']} "
            f"| {r['tool']} "
            f"| {r['canonical_repo']} "
            f"| {r['license']} "
            f"| {r['first_release']} "
            f"| {r['latest_version']} "
            f"| {r['stars']} "
            f"| {r['flags']} "
            f"| {r['advisories']} "
            f"| {r['engines']} "
            f"| {r['publisher']} "
            f"| {r['identity']} "
            f"| {r['evidence_prefixes']} "
            f"| {r['fit']} "
            f"| {r['reason_not']} "
            f"| {r['pair']} "
            f"| {r['level']} "
            f"| {r['mature_status']} "
            f"| {r['arithmetic']} |"
        )
        lines.append(row)

    lines.append(f"\n\n**R32 Sweep Summary Counts:** Total evaluated: {len(records)}; MATURE_OBJECTIVE_PASS: {pass_count}; MATURE_OBJECTIVE_FAIL: {fail_count}.\n")

    output_content = "\n".join(lines)
    
    with open(STANDALONE_MD, "w", encoding="utf-8", newline="\n") as f:
        f.write(output_content)
    print(f"Standalone table written to {STANDALONE_MD} ({len(records)} rows)")

    # Read pristine original target MD from base commit ba2145c
    try:
        import subprocess
        orig = subprocess.check_output(
            ["git", "show", "ba2145c:product/OSS-QUALIFICATION-RECORDS.md"],
            cwd=REPO_ROOT
        ).decode("utf-8")
    except Exception:
        with open(TARGET_MD, "r", encoding="utf-8") as f:
            orig = f.read()

    # Avoid duplicate append
    if "## R32 sweep:" in orig:
        orig = orig[:orig.index("## R32 sweep:")].rstrip() + "\n\n"
    else:
        orig = orig.rstrip() + "\n\n"

    # Now update the existing R9-01..R9-65 overlap rows with Age inputs, Version inputs, and supersedes notes
    # Let's define the updates for the 8 tools
    updates = {
        "R9-08": {
            "name": "semgrep",
            "age": "2019-12-13 (6.34y)",
            "ver": "1.184.0",
            "notes": "engine only; rules licensed separately; Supersedes R31 evidence with R32 sweep data. [Age inputs: repo_created=2019-12-13, first_gh=2021-02-24, first_reg=2020-05-06 -> earliest=2019-12-13; Version inputs: gh_ver=v1.184.0, reg_ver=1.183.0 -> latest=1.184.0]"
        },
        "R9-25": {
            "name": "ruff",
            "age": "2022-08-09 (3.69y)",
            "ver": "0.17.4",
            "notes": "0.x pre-1.0: stays L1; Supersedes R31 evidence with R32 sweep data. [Age inputs: repo_created=2022-08-09, first_gh=2022-12-04, first_reg=2022-08-27 -> earliest=2022-08-09; Version inputs: gh_ver=0.17.4, reg_ver=0.17.3 -> latest=0.17.4]"
        },
        "R9-43": {
            "name": "pyright",
            "age": "2019-03-12 (7.1y)",
            "ver": "1.1.414",
            "notes": "meets age/version/licence/recency rule; install-hash, security, F10 evidence still required. MISMATCH: wrapper https://github.com/RobertCraigie/pyright-python vs canonical https://github.com/microsoft/pyright. [Age inputs: repo_created=2019-03-12, first_gh=2023-06-21, first_reg=2021-06-20 -> earliest=2019-03-12; Version inputs: gh_ver=1.1.414, reg_ver=1.1.414 -> latest=1.1.414]"
        },
        "R9-44": {
            "name": "pyre-check",
            "age": "2017-11-10 (8.43y)",
            "ver": "0.10.0",
            "notes": "version 0.10.0 <1.0; Supersedes R31 evidence with R32 sweep data. [Age inputs: repo_created=2017-11-10, first_gh=2019-08-07, first_reg=2018-05-14 -> earliest=2017-11-10; Version inputs: gh_ver=v0.9.23, reg_ver=0.10.0 -> latest=0.10.0]"
        },
        "R9-58": {
            "name": "promptfoo",
            "age": "2023-04-28 (2.97y)",
            "ver": "0.125.1",
            "notes": "fast-moving API; testing only; Supersedes R31 evidence with R32 sweep data. [Age inputs: repo_created=2023-04-28, first_gh=2024-07-01, first_reg=2023-04-28 -> earliest=2023-04-28; Version inputs: gh_ver=0.125.1, reg_ver=0.125.1 -> latest=0.125.1]"
        },
        "R9-60": {
            "name": "pyrit",
            "age": "2024-02-21 (2.15y)",
            "ver": "1.1.0",
            "notes": "meets age/version/licence/recency rule; heavy dependency tree; Supersedes R31 evidence with R32 sweep data. [Age inputs: repo_created=2026-03-25, first_gh=None, first_reg=2024-02-21 -> earliest=2024-02-21; Version inputs: gh_ver=None, reg_ver=1.1.0 -> latest=1.1.0]"
        },
        "R9-65": {
            "name": "pr-agent",
            "age": "2023-07-05 (2.78y)",
            "ver": "0.49.0",
            "notes": "version 0.49.0 <1.0; Supersedes R31 evidence with R32 sweep data (moved org: qodo-ai/pr-agent -> The-PR-Agent/pr-agent). [Age inputs: repo_created=2023-07-05, first_gh=2023-09-20, first_reg=2024-03-23 -> earliest=2023-07-05; Version inputs: gh_ver=v0.49.0, reg_ver=0.49.0 -> latest=0.49.0]"
        }
    }

    # Apply updates to orig table lines
    orig_lines = orig.splitlines()
    new_orig_lines = []
    for line in orig_lines:
        matched = False
        for rid, u in updates.items():
            if line.startswith(f"| {rid} |") and u["name"] in line:
                cols = [c.strip() for c in line.split("|")][1:-1]
                # If it's the main summary row (typically 17 columns)
                if len(cols) >= 15:
                    cols[15] = u["notes"]
                    line = "| " + " | ".join(cols[:16]) + " | " + cols[-1] + " |"
                    matched = True
                    break
                elif len(cols) >= 9:
                    cols[-1] = u["notes"]
                    line = "| " + " | ".join(cols) + " |"
                    matched = True
                    break
        new_orig_lines.append(line)

    final_content = "\n".join(new_orig_lines) + "\n\n" + output_content.lstrip()
    with open(TARGET_MD, "w", encoding="utf-8", newline="\n") as f:
        f.write(final_content)

    print(f"Successfully updated {TARGET_MD} with deduplicated sweep records and supersedes notes.")

if __name__ == "__main__":
    main()
