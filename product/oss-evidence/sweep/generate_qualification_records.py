#!/usr/bin/env python3
"""
generate_qualification_records.py
Generates the R32 sweep qualification records section starting at R9-66.
Reads committed candidates.yaml and raw evidence files in product/oss-evidence/sweep/raw.
Outputs pure factual evidence, arithmetic objective maturity flags, and 'CL' for judgment fields.
"""

import os
import re
import json
import yaml
from datetime import datetime

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
CANDIDATES_YAML = os.path.join(REPO_ROOT, "product/oss-evidence/sweep/candidates.yaml")
RAW_DIR = os.path.join(REPO_ROOT, "product/oss-evidence/sweep/raw")
TARGET_MD = os.path.join(REPO_ROOT, "product/OSS-QUALIFICATION-RECORDS.md")

def clean_filename(s):
    return re.sub(r'[^a-zA-Z0-9_\-\.]', '_', s)

def load_json(filepath):
    if not os.path.exists(filepath):
        return None
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            return json.load(f)
    except Exception:
        return None

def load_text(filepath):
    if not os.path.exists(filepath):
        return None
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception:
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
        return "NON-OSI / UNKNOWN", gh_spdx or "NO_LICENSE_FOUND", None

    txt = license_text.lower()
    if "mit license" in txt or "permission is hereby granted, free of charge" in txt:
        return "PERMISSIVE", "MIT", None
    if "apache license" in txt and "version 2.0" in txt:
        return "PERMISSIVE", "Apache-2.0", None
    if "redistribution and use in source and binary forms" in txt:
        if "neither the name" in txt or "disclaimer" in txt:
            if "3-clause" in txt or "third" in txt:
                return "PERMISSIVE", "BSD-3-Clause", None
            return "PERMISSIVE", "BSD-2-Clause", None
    if "free and unencumbered software released into the public domain" in txt or "unlicense" in txt:
        return "PERMISSIVE", "Unlicense", None
    if "isc license" in txt or "permission to use, copy, modify, and/or distribute" in txt:
        return "PERMISSIVE", "ISC", None
    if "creative commons zero" in txt or "cc0 1.0" in txt:
        return "PERMISSIVE", "CC0-1.0", None

    if "mozilla public license" in txt and "2.0" in txt:
        return "WEAK-COPYLEFT", "MPL-2.0", None
    if "lesser general public license" in txt or "gnu lgpl" in txt:
        return "WEAK-COPYLEFT", "LGPL-3.0" if "version 3" in txt else "LGPL-2.1", None
    if "eclipse public license" in txt:
        return "WEAK-COPYLEFT", "EPL-2.0", None

    if "gnu general public license" in txt or "gnu gpl" in txt:
        if "version 3" in txt: return "STRONG-COPYLEFT", "GPL-3.0", None
        return "STRONG-COPYLEFT", "GPL-2.0", None
    if "affero general public license" in txt or "gnu agpl" in txt:
        return "STRONG-COPYLEFT", "AGPL-3.0", None

    if "server side public license" in txt or "sspl" in txt:
        return "NON-OSI", "SSPL-1.0", None
    if "business source license" in txt or "bsl" in txt:
        return "NON-OSI", "BSL-1.1", None
    if "functional source license" in txt or "fsl" in txt:
        return "NON-OSI", "FSL-1.1", None
    if "elastic license" in txt:
        return "NON-OSI", "Elastic-2.0", None

    words = license_text.split()
    quote = " ".join(words[:40]) if len(words) >= 40 else " ".join(words)
    return "NON-OSI / UNKNOWN", gh_spdx or "CUSTOM", quote

def parse_candidate_record(rec_num, c):
    cid = c["id"]
    safe_id = clean_filename(cid)
    display_name = c.get("display_name", cid)
    phase_tags = ", ".join(c.get("phase_tags", []))
    repo = c.get("canonical_repo")

    # Defaults for non-repos
    if not repo or repo == "UNRESOLVED" or repo.startswith(("closed/", "spec/")):
        is_unresolved = repo == "UNRESOLVED"
        is_closed = repo and repo.startswith("closed/")
        is_spec = repo and repo.startswith("spec/")
        status_label = "UNRESOLVED" if is_unresolved else ("CLOSED_SOURCE" if is_closed else "SPEC_ONLY")
        
        return {
            "record": f"R9-{rec_num}",
            "phase_tags": phase_tags,
            "tool": display_name,
            "canonical_repo": repo or "UNRESOLVED",
            "license": "NO_REPO",
            "first_release": "NO_RELEASE",
            "latest_version": "NO_RELEASE",
            "stars": "NA",
            "flags": "NONE",
            "advisories": "NA",
            "engines": "NA",
            "publisher": "NA",
            "identity": f"{c.get('identity_checks', {}).get('status', 'NA')}: {c.get('identity_checks', {}).get('details', 'no_repo')}",
            "evidence_prefixes": f"candidates.yaml, unresolved.md" if is_unresolved else "candidates.yaml",
            "fit": "CL",
            "reason_not": "CL",
            "pair": "CL",
            "level": "CL",
            "mature_status": f"MATURE_OBJECTIVE_FAIL (no repo: {status_label})",
            "arithmetic": f"age=NA, ver=NA, rel=NA, lic=NO_REPO, flags=NA, id={c.get('identity_checks', {}).get('status', 'NA')}"
        }

    safe_repo = clean_filename(repo)
    repo_json = load_json(os.path.join(RAW_DIR, f"gh_repo__{safe_repo}.json"))
    rel_latest_json = load_json(os.path.join(RAW_DIR, f"gh_release_latest__{safe_id}.json"))
    rel_list_json = load_json(os.path.join(RAW_DIR, f"gh_releases__{safe_id}.json"))
    tags_json = load_json(os.path.join(RAW_DIR, f"gh_tags__{safe_id}.json"))
    adv_json = load_json(os.path.join(RAW_DIR, f"gh_advisories__{safe_id}.json"))
    lic_txt = load_text(os.path.join(RAW_DIR, f"gh_license__{safe_id}.txt"))
    lic_json = load_json(os.path.join(RAW_DIR, f"gh_license__{safe_id}.json"))

    # Stars
    stars = repo_json.get("stargazers_count", "NA") if repo_json else "NA"

    # Repo flags
    flags_list = []
    if c.get("archived") or (repo_json and repo_json.get("archived")):
        flags_list.append("archived=true")
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

    # Releases
    # Latest version & date
    latest_ver = "NO_RELEASE"
    latest_date_str = None
    if rel_latest_json and isinstance(rel_latest_json, dict) and rel_latest_json.get("tag_name"):
        latest_ver = f"{rel_latest_json.get('tag_name')} ({rel_latest_json.get('published_at', '')[:10]})"
        latest_date_str = rel_latest_json.get("published_at", "")[:10]
    elif rel_list_json and isinstance(rel_list_json, list) and len(rel_list_json) > 0:
        r0 = rel_list_json[0]
        latest_ver = f"{r0.get('tag_name')} ({r0.get('published_at', '')[:10]})"
        latest_date_str = r0.get("published_at", "")[:10]
    elif tags_json and isinstance(tags_json, list) and len(tags_json) > 0:
        latest_ver = f"{tags_json[0].get('name')} (tag)"

    # First release
    first_rel = "NO_RELEASE"
    first_date_str = None
    if rel_list_json and isinstance(rel_list_json, list) and len(rel_list_json) > 0:
        r_last = rel_list_json[-1]
        first_rel = f"{r_last.get('tag_name')} ({r_last.get('published_at', '')[:10]})"
        first_date_str = r_last.get("published_at", "")[:10]
    elif tags_json and isinstance(tags_json, list) and len(tags_json) > 0:
        t_last = tags_json[-1]
        first_rel = f"{t_last.get('name')} (tag)"
    
    # Fallback first release to repo created_at if no releases list
    if not first_date_str and repo_json and repo_json.get("created_at"):
        first_date_str = repo_json.get("created_at")[:10]
        if first_rel == "NO_RELEASE":
            first_rel = f"repo_created ({first_date_str})"

    # Advisories
    gh_adv_count = len(adv_json) if adv_json and isinstance(adv_json, list) else 0
    # Check OSV files
    osv_count = 0
    osv_files = [f for f in os.listdir(RAW_DIR) if f.startswith(f"osv_") and f"__{safe_id}.json" in f]
    for of in osv_files:
        odata = load_json(os.path.join(RAW_DIR, of))
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
    identity_str = f"{id_status}: {id_details}"

    # Evidence prefixes
    ev_prefixes = [f"gh_repo__{safe_repo}", f"gh_release_latest__{safe_id}", f"gh_releases__{safe_id}", f"gh_advisories__{safe_id}", f"gh_license__{safe_id}"]

    # 6 Objective arithmetic flags
    # 1. age >= 2y (first release <= 2024-04-16)
    age_ok = False
    if first_date_str:
        try:
            age_ok = first_date_str <= "2024-04-16"
        except Exception:
            pass

    # 2. version >= 1.0 (latest tag not 0.x)
    ver_ok = False
    tag_clean = latest_ver.split()[0].lstrip("vV")
    if tag_clean and tag_clean != "NO_RELEASE":
        parts = tag_clean.split(".")
        try:
            major = int(parts[0])
            ver_ok = major >= 1
        except Exception:
            pass

    # 3. release <= 12m (latest release >= 2025-04-16)
    recency_ok = False
    if latest_date_str:
        try:
            recency_ok = latest_date_str >= "2025-04-16"
        except Exception:
            pass
    elif repo_json and repo_json.get("pushed_at"):
        pushed = repo_json.get("pushed_at")[:10]
        recency_ok = pushed >= "2025-04-16"

    # 4. permissive licence
    lic_ok = (lic_class == "PERMISSIVE")

    # 5. not archived, not fork, not moved
    flags_ok = (repo_flags == "NONE")

    # 6. identity ok (MATCH or NA)
    identity_ok = (id_status in ["MATCH", "NA"])

    failed_flags = []
    if not age_ok: failed_flags.append(f"age<2y ({first_date_str})")
    if not ver_ok: failed_flags.append(f"ver<1.0 ({tag_clean})")
    if not recency_ok: failed_flags.append(f"stale>12m ({latest_date_str or 'none'})")
    if not lic_ok: failed_flags.append(f"licence={lic_class}")
    if not flags_ok: failed_flags.append(f"flags={repo_flags}")
    if not identity_ok: failed_flags.append(f"identity={id_status}")

    all_pass = (age_ok and ver_ok and recency_ok and lic_ok and flags_ok and identity_ok)
    mature_status = "MATURE_OBJECTIVE_PASS" if all_pass else f"MATURE_OBJECTIVE_FAIL ({', '.join(failed_flags)})"
    arithmetic_str = f"age={first_date_str or 'NA'}, ver={tag_clean or 'NA'}, rel={latest_date_str or 'NA'}, lic={lic_class}, flags={repo_flags}, id={id_status}"

    return {
        "record": f"R9-{rec_num}",
        "phase_tags": phase_tags,
        "tool": display_name,
        "canonical_repo": repo,
        "license": lic_str,
        "first_release": first_rel,
        "latest_version": latest_ver,
        "stars": str(stars),
        "flags": repo_flags,
        "advisories": advisories_str,
        "engines": engines_str,
        "publisher": publisher,
        "identity": identity_str,
        "evidence_prefixes": ", ".join(ev_prefixes),
        "fit": "CL",
        "reason_not": "CL",
        "pair": "CL",
        "level": "CL",
        "mature_status": mature_status,
        "arithmetic": arithmetic_str
    }

def main():
    with open(CANDIDATES_YAML, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    candidates = data["candidates"]
    records = []
    rec_num = 66

    for c in candidates:
        r = parse_candidate_record(rec_num, c)
        records.append(r)
        rec_num += 1

    print(f"Parsed {len(records)} qualification records (R9-66 to R9-{rec_num-1}).")

    # Generate Markdown Table
    lines = [
        "\n\n## R32 sweep: Comprehensive SDLC and Agent-Workflow Qualifications\n",
        "This section documents the OSS qualification records for the OSS-SWEEP-R32 candidate set across SDLC phases (P0–P11), cross-cutting disciplines, and agent workflows. All values derive strictly from committed raw evidence files in `product/oss-evidence/sweep/raw/` and `candidates.yaml`. All judgment columns (`fit`, `strongest reason not to use`, `independent pair`, `level`) are reserved strictly for CL.\n",
        "### Objective Maturity Assessment Arithmetic\n",
        "A candidate is evaluated against 6 objective factual criteria:",
        "1. **Age >= 2y:** First release or repo creation <= 2024-04-16",
        "2. **Version >= 1.0:** Latest release tag >= 1.0 (not 0.x pre-release)",
        "3. **Release <= 12m:** Latest release or push >= 2025-04-16",
        "4. **Permissive License:** Permissive OSI-compliant license (MIT, Apache-2.0, BSD, ISC, etc.)",
        "5. **Clean Repository:** Not archived, not an unmaintained fork, not redirected/moved",
        "6. **Identity Verified:** Ecosystem package identity check evaluates to `MATCH` or `NA`\n",
        "Candidates meeting all 6 criteria receive `MATURE_OBJECTIVE_PASS`. Candidates failing one or more receive `MATURE_OBJECTIVE_FAIL (<failed flags>)`.\n\n",
        "| Record | Phase Tags | Tool | Canonical Repo | Licence Class + SPDX | First Release | Latest Version + Date | Stars | Repo Flags | Advisories (GH/OSV) | Engines / Language | Publisher / Org | Identity Check | Evidence Prefixes | Fit | Reason Not To Use | Independent Pair | Level | Objective Maturity Status | Arithmetic Inputs |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"
    ]

    pass_count = 0
    fail_count = 0

    for r in records:
        if "MATURE_OBJECTIVE_PASS" in r["mature_status"]:
            pass_count += 1
        else:
            fail_count += 1
            
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
    
    # Save standalone copy for verification
    sweep_table_path = os.path.join(REPO_ROOT, "product/oss-evidence/sweep/qualification_records_r32.md")
    with open(sweep_table_path, "w", encoding="utf-8") as f:
        f.write(output_content)
    print(f"Standalone table written to {sweep_table_path}")

    # Append to target OSS-QUALIFICATION-RECORDS.md
    with open(TARGET_MD, "r", encoding="utf-8") as f:
        orig = f.read()

    # Avoid duplicate append
    if "## R32 sweep:" in orig:
        orig = orig[:orig.index("## R32 sweep:")].rstrip() + "\n\n"
    else:
        orig = orig.rstrip() + "\n\n"

    with open(TARGET_MD, "w", encoding="utf-8") as f:
        f.write(orig + output_content.lstrip())

    print(f"Successfully appended R32 sweep records to {TARGET_MD}")

if __name__ == "__main__":
    main()
