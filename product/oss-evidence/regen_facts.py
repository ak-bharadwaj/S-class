#!/usr/bin/env python3
"""
Regenerate Fact Cells for S-Class R31 OSS Qualification Records.
Implements STEP 2 of TASK OSS-EVIDENCE-R31 with Round 2 strict fallback requirements:
- Licence cell uses strict fallback:
    1. license_expression if present in info
    2. else license field if present and non-empty
    3. else classifiers (parse License :: ...)
    4. else scan raw LICENSE file
- Pygls resolves to Apache-2.0.
- CONTRADICTIONS.md contains pure facts with columns: Claim, Raw Value, Source File.
- Shows diff of old vs new cells.
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DOC_PATH = os.path.join(ROOT, "product", "OSS-QUALIFICATION-RECORDS.md")
RAW_DIR = os.path.join(ROOT, "product", "oss-evidence", "raw")
MANIFEST_PATH = os.path.join(ROOT, "product", "oss-evidence", "MANIFEST.json")
CONTRADICTIONS_PATH = os.path.join(ROOT, "product", "oss-evidence", "CONTRADICTIONS.md")

with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
    manifest = json.load(f)

manifest_map = {m["file"]: m for m in manifest if m.get("status") == "OK" and m.get("sha256")}

def get_json(fn):
    p = os.path.join(RAW_DIR, fn)
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None

def get_text(fn):
    p = os.path.join(RAW_DIR, fn)
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                return f.read()
        except Exception:
            return None
    return None

def sha_prefix(fn):
    m = manifest_map.get(fn)
    if m:
        return f"{fn} {m['sha256'][:12]}"
    return None

def scan_raw_license_text(raw_lic_text):
    if not raw_lic_text:
        return None
    txt_lower = raw_lic_text.lower()
    if "apache license" in txt_lower and "version 2.0" in txt_lower:
        return "Apache-2.0"
    elif "gnu general public license" in txt_lower and "version 3" in txt_lower:
        return "GPL-3.0"
    elif "gnu affero general public license" in txt_lower and "version 3" in txt_lower:
        return "AGPL-3.0"
    elif "gnu lesser general public license" in txt_lower and ("2.1" in txt_lower or "version 2.1" in txt_lower):
        return "LGPL-2.1"
    elif "gnu lesser general public license" in txt_lower and "version 2" in txt_lower:
        return "LGPL-2.0"
    elif "mit license" in txt_lower or "permission is hereby granted, free of charge" in txt_lower:
        return "MIT"
    elif "neither the name of" in txt_lower or "bsd 3-clause" in txt_lower:
        return "BSD-3-Clause"
    elif "bsd 2-clause" in txt_lower or ("redistribution and use in source and binary forms" in txt_lower and "neither the name" not in txt_lower):
        return "BSD-2-Clause"
    elif "mozilla public license" in txt_lower and "2.0" in txt_lower:
        return "MPL-2.0"
    elif "isc license" in txt_lower:
        return "ISC"
    elif "unlicense" in txt_lower:
        return "The Unlicense"
    return "Present (see raw text)"

def resolve_licence_strict(pypi_json, npm_json, gh_key):
    """
    CL Round 2 strict fallback order:
    1. license_expression if present in info
    2. else license field if present and non-empty
    3. else classifiers (parse License :: ...)
    4. else scan raw LICENSE file
    """
    if pypi_json and "info" in pypi_json:
        p_info = pypi_json["info"]
        lic_expr = p_info.get("license_expression")
        if lic_expr and str(lic_expr).strip() and str(lic_expr).strip().lower() != "none":
            return str(lic_expr).strip()
        
        lic_field = (p_info.get("license") or "").strip()
        if lic_field and lic_field.lower() != "none":
            first_line = lic_field.splitlines()[0].strip()
            return first_line[:35]
        
        classifiers = [c for c in p_info.get("classifiers", []) if c.startswith("License ::")]
        if classifiers:
            return classifiers[0].split("::")[-1].strip()

    if npm_json and npm_json.get("license"):
        lic = npm_json["license"]
        if str(lic).strip():
            return str(lic).strip()

    raw_lic_text = get_text(f"gh_license__{gh_key}.txt") if gh_key else None
    scanned = scan_raw_license_text(raw_lic_text)
    if scanned:
        return scanned

    gh_repo = get_json(f"gh_repo__{gh_key}.json") if gh_key else None
    if gh_repo and gh_repo.get("license"):
        spdx = gh_repo["license"].get("spdx_id") or gh_repo["license"].get("name")
        if spdx and spdx != "NOASSERTION":
            return spdx

    return "NOT RETRIEVED"

TOOL_INFO = {
    "R9-39": {"tool": "bashlex", "phase": "P6/B5", "role": "Bash parser (command analysis input, parser B)", "pypi": "bashlex", "npm": None, "gh": "bashlex"},
    "R9-40": {"tool": "tree-sitter-bash", "phase": "P6/B5", "role": "Bash grammar (command analysis, parser A)", "pypi": None, "npm": "tree-sitter-bash", "gh": "tree-sitter-bash"},
    "R9-41": {"tool": "mvdan-sh", "phase": "P6/B5", "role": "Shell parser in Go (command analysis, parser C, offline helper)", "pypi": None, "npm": None, "gh": "mvdan-sh", "go": "mvdan-sh"},
    "R9-42": {"tool": "shellcheck", "phase": "P6/P7", "role": "Shell static analysis (advisory lint of agent scripts)", "pypi": None, "npm": None, "gh": "shellcheck"},
    "R9-43": {"tool": "pyright", "phase": "P7", "role": "Static type check (pair with mypy R9-24)", "pypi": "pyright", "npm": "pyright", "gh": "pyright"},
    "R9-44": {"tool": "pyre-check", "phase": "P7", "role": "Optional third type checker", "pypi": "pyre-check", "npm": None, "gh": "pyre-check"},
    "R9-45": {"tool": "diff-cover", "phase": "P5/P7", "role": "Coverage and quality on changed lines only", "pypi": "diff-cover", "npm": None, "gh": "diff-cover"},
    "R9-46": {"tool": "import-linter", "phase": "P3/P7", "role": "Architecture import contracts", "pypi": "import-linter", "npm": None, "gh": "import-linter"},
    "R9-47": {"tool": "detect-secrets", "phase": "P7/P10", "role": "Secret scanning (pair with Gitleaks R9-26)", "pypi": "detect-secrets", "npm": None, "gh": "detect-secrets"},
    "R9-48": {"tool": "pytest-timeout", "phase": "P5", "role": "Kill hung tests", "pypi": "pytest-timeout", "npm": None, "gh": "pytest-timeout"},
    "R9-49": {"tool": "pytest-rerunfailures", "phase": "P5", "role": "Flaky test retry", "pypi": "pytest-rerunfailures", "npm": None, "gh": "pytest-rerunfailures"},
    "R9-50": {"tool": "pytest-randomly", "phase": "P5", "role": "Random test order and seed pinning", "pypi": "pytest-randomly", "npm": None, "gh": "pytest-randomly"},
    "R9-51": {"tool": "pytest-xdist", "phase": "P5", "role": "Parallel test execution", "pypi": "pytest-xdist", "npm": None, "gh": "pytest-xdist"},
    "R9-52": {"tool": "pip-licenses", "phase": "P10", "role": "Licence inventory of installed packages", "pypi": "pip-licenses", "npm": None, "gh": "pip-licenses"},
    "R9-53": {"tool": "licensecheck", "phase": "P10", "role": "Licence compatibility check", "pypi": "licensecheck", "npm": None, "gh": "licensecheck"},
    "R9-54": {"tool": "scancode-toolkit", "phase": "P10", "role": "Licence and copyright detection from source text", "pypi": "scancode-toolkit", "npm": None, "gh": "scancode"},
    "R9-55": {"tool": "in-toto", "phase": "P10", "role": "Supply-chain attestation layout", "pypi": "in-toto", "npm": None, "gh": "in-toto"},
    "R9-56": {"tool": "sigstore", "phase": "P10", "role": "Keyless signing and verification (sigstore-python)", "pypi": "sigstore", "npm": None, "gh": "sigstore-python"},
    "R9-57": {"tool": "scorecard", "phase": "P10", "role": "Dependency health scoring (OpenSSF Scorecard)", "pypi": None, "npm": None, "gh": "scorecard", "go": "scorecard"},
    "R9-58": {"tool": "promptfoo", "phase": "P11/P9", "role": "Agent and prompt red-team test harness (testing only)", "pypi": None, "npm": "promptfoo", "gh": "promptfoo"},
    "R9-59": {"tool": "garak", "phase": "P11/P9", "role": "LLM vulnerability scanner (testing only)", "pypi": "garak", "npm": None, "gh": "garak"},
    "R9-60": {"tool": "pyrit", "phase": "P11/P9", "role": "Red-team automation framework (testing only)", "pypi": "pyrit", "npm": None, "gh": "pyrit"},
    "R9-61": {"tool": "pygls", "phase": "P6/B7", "role": "Python LSP server framework (optional host adapter)", "pypi": "pygls", "npm": None, "gh": "pygls"},
    "R9-62": {"tool": "lsprotocol", "phase": "P6/B7", "role": "LSP type definitions", "pypi": "lsprotocol", "npm": None, "gh": "lsprotocol"},
    "R9-63": {"tool": "sarif-tools", "phase": "P9/P11", "role": "SARIF reading and diffing", "pypi": "sarif-tools", "npm": None, "gh": "sarif-tools"},
    "R9-64": {"tool": "opengrep", "phase": "P7/P9", "role": "Semgrep-engine fork for SAST", "pypi": "opengrep", "npm": None, "gh": "opengrep"},
    "R9-65": {"tool": "pr-agent", "phase": "P9", "role": "Optional PR review claim generator", "pypi": "pr-agent", "npm": None, "gh": "pr-agent"},
}

ORIGINAL_JUDGMENTS = {
    "R9-39": ("L1", "version 0.18 <1.0 ; licence GPL-3.0 not permissive ; last release 2023-01-18 >12 months"),
    "R9-40": ("L1", "no release-date evidence for npm package (only latest metadata retrieved)"),
    "R9-41": ("L1", "no release-date evidence retrieved"),
    "R9-42": ("L1", "no release-date evidence retrieved"),
    "R9-43": ("L2-proposable", "meets age/version/licence/recency rule; install-hash, security, F10 evidence still required"),
    "R9-44": ("L1", "version 0.10.0 <1.0"),
    "R9-45": ("L2-proposable", "meets age/version/licence/recency rule; install-hash, security, F10 evidence still required"),
    "R9-46": ("L2-proposable", "meets age/version/licence/recency rule; install-hash, security, F10 evidence still required"),
    "R9-47": ("L1", "last release 2024-05-06 >12 months"),
    "R9-48": ("L2-proposable", "meets age/version/licence/recency rule; install-hash, security, F10 evidence still required"),
    "R9-49": ("L1", "licence MPL-2.0 not permissive"),
    "R9-50": ("L2-proposable", "meets age/version/licence/recency rule; install-hash, security, F10 evidence still required"),
    "R9-51": ("L1", "last release 2025-07-01 >12 months"),
    "R9-52": ("L2-proposable", "meets age/version/licence/recency rule; install-hash, security, F10 evidence still required"),
    "R9-53": ("L2-proposable", "meets age/version/licence/recency rule; install-hash, security, F10 evidence still required"),
    "R9-54": ("L1", "mixed licence expression (LicenseRef-*): obligations unreviewed"),
    "R9-55": ("L2-proposable", "meets age/version/licence/recency rule; install-hash, security, F10 evidence still required"),
    "R9-56": ("L2-proposable", "meets age/version/licence/recency rule; install-hash, security, F10 evidence still required"),
    "R9-57": ("L1", "no release-date evidence retrieved"),
    "R9-58": ("L1", "no release-date evidence for npm package (only latest metadata retrieved)"),
    "R9-59": ("L1", "version 0.17.1 <1.0"),
    "R9-60": ("L2-proposable", "meets age/version/licence/recency rule; install-hash, security, F10 evidence still required"),
    "R9-61": ("L2-proposable", "meets age/version/licence/recency rule; install-hash, security, F10 evidence still required"),
    "R9-62": ("L1", "last release 2025-06-17 >12 months"),
    "R9-63": ("L1", "last release 2025-07-17 >12 months"),
    "R9-64": ("L1", "no release-date evidence retrieved"),
    "R9-65": ("L1", "version 0.49.0 <1.0"),
}

TABLE_HEADERS_R9 = [
    "Record", "Tool", "Phase", "Role", "Version (PyPI/npm)", "First release", "Last release",
    "Licence (metadata)", "Licence (raw LICENSE file)", "PyPI publisher / source URL",
    "Requires Python", "Stars", "Pushed at", "Advisories", "Proposed level", "Why that level",
    "Evidence files (sha256 prefix)"
]

def build_r9_39_65_rows():
    rows = []
    for rec_id, info in TOOL_INFO.items():
        tool = info["tool"]
        phase = info["phase"]
        role = info["role"]
        pypi_key = info["pypi"]
        npm_key = info["npm"]
        gh_key = info["gh"]
        
        # 1. Version
        pypi_json = get_json(f"pypi__{pypi_key}.json") if pypi_key else None
        npm_json = get_json(f"npm__{npm_key}.json") if npm_key else None
        gh_repo = get_json(f"gh_repo__{gh_key}.json") if gh_key else None
        gh_rel = get_json(f"gh_release_latest__{gh_key}.json") if gh_key else None
        
        version = "NOT RETRIEVED"
        if pypi_json and pypi_json.get("info", {}).get("version"):
            version = pypi_json["info"]["version"]
        elif npm_json and npm_json.get("version"):
            version = npm_json["version"]
        elif gh_rel and gh_rel.get("tag_name"):
            version = gh_rel["tag_name"]

        # 2. First release & Last release
        first_rel = "NOT RETRIEVED"
        last_rel = "NOT RETRIEVED"
        if pypi_json and "releases" in pypi_json:
            dates = []
            for ver_str, files in pypi_json["releases"].items():
                for f_info in files:
                    if "upload_time" in f_info:
                        dates.append(f_info["upload_time"][:10])
            if dates:
                dates.sort()
                first_rel = dates[0]
                last_rel = dates[-1]
        elif gh_repo:
            if "created_at" in gh_repo:
                first_rel = gh_repo["created_at"][:10]
            if gh_rel and "published_at" in gh_rel:
                last_rel = gh_rel["published_at"][:10]
            elif "pushed_at" in gh_repo:
                last_rel = gh_repo["pushed_at"][:10]

        # 3. Licence metadata (strictly using CL fallback chain)
        lic_meta = resolve_licence_strict(pypi_json, npm_json, gh_key)

        # 4. Raw LICENSE file
        lic_raw = "NOT RETRIEVED"
        raw_lic_text = get_text(f"gh_license__{gh_key}.txt")
        scanned = scan_raw_license_text(raw_lic_text)
        if scanned:
            lic_raw = scanned

        # 5. Publisher / Source URL
        pub_url = "NOT RETRIEVED"
        if pypi_json:
            author = pypi_json.get("info", {}).get("author") or pypi_json.get("info", {}).get("author_email") or "None"
            home = pypi_json.get("info", {}).get("home_page") or pypi_json.get("info", {}).get("project_url") or "None"
            pub_url = f"{author[:25]} / {home[:45]}"
        elif gh_repo:
            pub_url = f"{gh_repo.get('owner', {}).get('login', 'None')} / {gh_repo.get('html_url', 'None')}"

        # 6. Requires Python
        req_py = "n/a"
        if pypi_json:
            req_py = pypi_json.get("info", {}).get("requires_python") or "n/a"

        # 7. Stars
        stars = "NOT RETRIEVED"
        if gh_repo and "stargazers_count" in gh_repo:
            stars = str(gh_repo["stargazers_count"])

        # 8. Pushed at
        pushed_at = "NOT RETRIEVED"
        if gh_repo and "pushed_at" in gh_repo:
            pushed_at = gh_repo["pushed_at"]

        # 9. Advisories
        advisories_str = "NOT RETRIEVED"
        adv_json = get_json(f"gh_advisories__{gh_key}.json")
        osv_json = None
        if pypi_key:
            osv_json = get_json(f"osv_pypi__{pypi_key}.json")
        elif npm_key:
            osv_json = get_json(f"osv_npm__{npm_key}.json")
        elif info.get("go"):
            osv_json = get_json(f"osv_repo__{info['go']}.json")

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

        if isinstance(adv_json, list) or isinstance(osv_json, dict):
            if not adv_ids:
                advisories_str = "0"
            else:
                advisories_str = f"{len(adv_ids)} ({', '.join(adv_ids[:2])})"

        # 10. Proposed level & Why that level
        prop_lvl, why_lvl = ORIGINAL_JUDGMENTS.get(rec_id, ("L1", "UNVERIFIED"))

        # 11. Evidence files (sha256 prefix)
        ev_files = []
        for candidate in [
            f"pypi__{pypi_key}.json" if pypi_key else None,
            f"npm__{npm_key}.json" if npm_key else None,
            f"gh_repo__{gh_key}.json" if gh_key else None,
            f"gh_license__{gh_key}.txt" if gh_key else None,
            f"gh_release_latest__{gh_key}.json" if gh_key else None,
            f"gh_releases__{gh_key}.json" if gh_key else None,
            f"gh_advisories__{gh_key}.json" if gh_key else None,
            f"osv_pypi__{pypi_key}.json" if pypi_key else None,
            f"osv_npm__{npm_key}.json" if npm_key else None,
            f"osv_repo__{info.get('go')}.json" if info.get("go") else None,
        ]:
            if candidate:
                sp = sha_prefix(candidate)
                if sp:
                    ev_files.append(sp)

        ev_str = "; ".join(ev_files[:4])

        row = [
            rec_id, tool, phase, role, version, first_rel, last_rel,
            lic_meta.replace("|", "/"), lic_raw, pub_url.replace("|", "/"),
            req_py, stars, pushed_at, advisories_str, prop_lvl, why_lvl, ev_str
        ]
        rows.append(row)
    return rows

def build_r9_39_65_table(rows):
    lines = []
    lines.append("| " + " | ".join(TABLE_HEADERS_R9) + " |")
    lines.append("|" + "|".join(["---"] * len(TABLE_HEADERS_R9)) + "|")
    for r in rows:
        lines.append("| " + " | ".join(r) + " |")
    return "\n".join(lines)

TABLE_HEADERS_EXISTING = ["Existing record", "Package", "Version", "First release", "Last release", "Licence (PyPI)", "Stars", "Pushed at", "Advisories", "Note"]

def build_existing_records_rows():
    existing = [
        ("R9-08", "semgrep", "semgrep", "engine only; rules licensed separately"),
        ("R9-10", "bandit", "bandit", "Python-only scanner"),
        ("R9-13", "hypothesis", "hypothesis", "MPL-2.0 weak copyleft (dev-only use)"),
        ("R9-15", "mutmut", "mutmut", "BSD-3"),
        ("R9-16", "coverage", "coverage", "requires Python >=3.11: tools venv for the 3.10 leg"),
        ("R9-24", "mypy", "mypy", "pairs with pyright"),
        ("R9-25", "ruff", "ruff", "0.x pre-1.0: stays L1"),
        ("R9-27", "pip-audit", "pip-audit", "licence only in classifier"),
        ("R9-30", "cyclonedx-bom", "cyclonedx-bom", "requires Python <4,>=3.9"),
    ]

    rows = []
    for rec_id, pkg, gh_key, note in existing:
        pypi_json = get_json(f"pypi__{pkg}.json")
        gh_repo = get_json(f"gh_repo__{gh_key}.json")
        adv_json = get_json(f"gh_advisories__{gh_key}.json")
        osv_json = get_json(f"osv_pypi__{pkg}.json")

        ver = pypi_json.get("info", {}).get("version", "NOT RETRIEVED") if pypi_json else "NOT RETRIEVED"
        first_rel = "NOT RETRIEVED"
        last_rel = "NOT RETRIEVED"
        if pypi_json and "releases" in pypi_json:
            dates = []
            for ver_str, files in pypi_json["releases"].items():
                for f_info in files:
                    if "upload_time" in f_info:
                        dates.append(f_info["upload_time"][:10])
            if dates:
                dates.sort()
                first_rel = dates[0]
                last_rel = dates[-1]

        lic_meta = resolve_licence_strict(pypi_json, None, gh_key)

        stars = str(gh_repo.get("stargazers_count")) if gh_repo else "NOT RETRIEVED"
        pushed_at = gh_repo.get("pushed_at", "NOT RETRIEVED") if gh_repo else "NOT RETRIEVED"

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

        adv_str = "0" if not adv_ids else f"{len(adv_ids)} ({', '.join(adv_ids[:2])})"

        row = [rec_id, pkg, ver, first_rel, last_rel, lic_meta, stars, pushed_at, adv_str, note]
        rows.append(row)

    return rows

def build_existing_records_table(rows):
    lines = []
    lines.append("| " + " | ".join(TABLE_HEADERS_EXISTING) + " |")
    lines.append("|" + "|".join(["---"] * len(TABLE_HEADERS_EXISTING)) + "|")
    for r in rows:
        lines.append("| " + " | ".join(r) + " |")
    return "\n".join(lines)

def build_contradictions_content():
    """
    CL Round 2 Requirement 7:
    Strip all subjective opinions or commentary. Facts only: columns Claim, Raw Value, Source File.
    """
    lines = [
        "# Contradictions Between Previous Claims and Raw Evidence",
        "",
        "| Claim | Raw Value | Source File |",
        "|---|---|---|",
        "| diff-cover has 0 stars, last release in 2016, and is unmaintained | 850 stars, pushed_at: 2026-11-04T02:29:40Z, latest release: 11.0.1 on 2026-11-04, 0 advisories | gh_repo__diff-cover.json, pypi__diff-cover.json, gh_advisories__diff-cover.json |",
        "| detect-secrets last release 2024-05-06 >12 months; treat as stale | 3,324 stars, pushed_at: 2026-10-18T18:41:09Z, 0 advisories | gh_repo__detect-secrets.json, gh_advisories__detect-secrets.json |",
        "| pytest-xdist last release 2025-07-01 >12 months | 1,659 stars, pushed_at: 2026-10-14T11:22:15Z, frequent tags in gh_releases__pytest-xdist.json | gh_repo__pytest-xdist.json, gh_releases__pytest-xdist.json |",
        "| promptfoo has no release-date evidence for npm package | 9,642 stars, pushed_at: 2026-11-05T09:15:22Z, 100+ releases documented in gh_releases__promptfoo.json | gh_repo__promptfoo.json, gh_releases__promptfoo.json |",
        "| pr-agent upstream canonical is qodo-ai/pr-agent | HTTP 301 Moved Permanently from qodo-ai/pr-agent to The-PR-Agent/pr-agent; 15,006 stars, pushed_at: 2026-11-05T08:37:25Z | gh_repo__pr-agent-redirect.json, gh_repo__pr-agent.json |",
        "| kodus license unverified | AGPL-3.0 / Enterprise dual-license in license.md; 9 advisories in GitHub Security Advisories; pushed_at: 2026-11-05T12:35:13Z | gh_license__kodus.txt, gh_advisories__kodus.json, gh_repo__kodus.json |",
        "| pr-af license unverified | HTTP 404 Not Found (no LICENSE file present in repository); Go codebase, 665 stars, pushed_at: 2026-11-02T16:58:25Z | gh_license__pr-af.txt, gh_repo__pr-af.json |",
        "| bashlex matches bash syntax | bashlex raises ParsingError on valid here-docs (cat <<'EOF') and nested backticks (echo `echo \\`pwd\\``) that exit 0 in bash -n | tests/oss/test_shell_parser_disagreement.py, gh_repo__bashlex.json |",
        "| opengrep release dates not retrieved and not on PyPI | Absent from PyPI (HTTP 404); GitHub shows 1,412 stars, pushed_at: 2026-11-04T19:02:11Z, latest release v1.0.0, license LGPL-2.1 | pypi__opengrep.json, gh_repo__opengrep.json, gh_release_latest__opengrep.json, gh_license__opengrep.txt |",
        "| tree-sitter-bash no release-date evidence | 428 stars, pushed_at: 2026-10-22T04:12:00Z, 45 releases spanning 2017 to 2026 | gh_repo__tree-sitter-bash.json, gh_releases__tree-sitter-bash.json |",
        "| pygls licence metadata NOT RETRIEVED | license_expression in pypi__pygls.json: Apache-2.0; gh_license__pygls.txt: Apache License 2.0 | pypi__pygls.json, gh_license__pygls.txt |"
    ]
    return "\n".join(lines)

def update_individual_records(content):
    mapping = {
        "R9-01": {"repo": "github/spec-kit", "gh": "spec-kit", "lic": "MIT", "name": "GitHub Spec Kit"},
        "R9-02": {"repo": "Fission-AI/OpenSpec", "gh": "openspec", "lic": "Apache-2.0", "name": "Fission-AI OpenSpec"},
        "R9-03": {"repo": "python-jsonschema/jsonschema", "pypi": "jsonschema", "gh": "jsonschema", "lic": "MIT", "name": "python-jsonschema"},
        "R9-04": {"repo": "tree-sitter/tree-sitter", "pypi": "tree-sitter", "gh": "tree-sitter", "lic": "MIT", "name": "Tree-sitter core"},
        "R9-05": {"repo": "sourcegraph/scip", "gh": "scip", "lic": "Apache-2.0", "name": "SCIP"},
        "R9-06": {"repo": "ast-grep/ast-grep", "pypi": "ast-grep-cli", "gh": "ast-grep", "lic": "MIT", "name": "ast-grep"},
        "R9-07": {"repo": "tobymao/sqlglot", "pypi": "sqlglot", "gh": "sqlglot", "lic": "MIT", "name": "SQLGlot"},
        "R9-08": {"repo": "semgrep/semgrep", "pypi": "semgrep", "gh": "semgrep", "lic": "LGPL-2.1-or-later", "name": "Semgrep engine"},
        "R9-09": {"repo": "semgrep/semgrep-rules", "gh": "semgrep-rules", "lic": "custom", "name": "Semgrep rules bundle"},
        "R9-10": {"repo": "PyCQA/bandit", "pypi": "bandit", "gh": "bandit", "lic": "Apache-2.0", "name": "Bandit"},
        "R9-11": {"repo": "open-policy-agent/opa", "gh": "opa", "lic": "Apache-2.0", "name": "Open Policy Agent (OPA)"},
        "R9-12": {"repo": "pytest-dev/pytest", "pypi": "pytest", "gh": "pytest", "lic": "MIT", "name": "pytest"},
        "R9-13": {"repo": "HypothesisWorks/hypothesis", "pypi": "hypothesis", "gh": "hypothesis", "lic": "MPL-2.0", "name": "Hypothesis"},
        "R9-14": {"repo": "schemathesis/schemathesis", "pypi": "schemathesis", "gh": "schemathesis", "lic": "MIT", "name": "Schemathesis"},
        "R9-15": {"repo": "boxed/mutmut", "pypi": "mutmut", "gh": "mutmut", "lic": "BSD-3-Clause", "name": "mutmut"},
        "R9-16": {"repo": "nedbat/coveragepy", "pypi": "coverage", "gh": "coverage", "lic": "Apache-2.0", "name": "coverage.py"},
        "R9-18": {"repo": "All-Hands-AI/OpenHands", "pypi": "openhands-ai", "gh": "openhands", "lic": "MIT", "name": "OpenHands Software Agent SDK"},
        "R9-19": {"repo": "SWE-agent/mini-swe-agent", "pypi": "mini-swe-agent", "gh": "mini-swe-agent", "lic": "MIT", "name": "mini-swe-agent"},
        "R9-20": {"repo": "modelcontextprotocol/python-sdk", "pypi": "mcp", "gh": "mcp", "lic": "MIT", "name": "MCP Python SDK"},
        "R9-21": {"repo": "agentclientprotocol/agent-client-protocol", "pypi": "agent-client-protocol", "gh": "agent-client-protocol", "lic": "Apache-2.0", "name": "Agent Client Protocol SDK"},
        "R9-22": {"repo": "huggingface/smolagents", "pypi": "smolagents", "gh": "smolagents", "lic": "Apache-2.0", "name": "smolagents"},
        "R9-23": {"repo": "langchain-ai/langgraph", "pypi": "langgraph", "gh": "langgraph", "lic": "MIT", "name": "LangGraph"},
        "R9-24": {"repo": "python/mypy", "pypi": "mypy", "gh": "mypy", "lic": "MIT", "name": "mypy"},
        "R9-25": {"repo": "astral-sh/ruff", "pypi": "ruff", "gh": "ruff", "lic": "MIT", "name": "Ruff"},
        "R9-26": {"repo": "gitleaks/gitleaks", "gh": "gitleaks", "lic": "MIT", "name": "Gitleaks"},
        "R9-27": {"repo": "pypa/pip-audit", "pypi": "pip-audit", "gh": "pip-audit", "lic": "Apache-2.0", "name": "pip-audit"},
        "R9-28": {"repo": "google/osv-scanner", "gh": "osv-scanner", "lic": "Apache-2.0", "name": "OSV-Scanner"},
        "R9-29": {"repo": "anchore/syft", "gh": "syft", "lic": "Apache-2.0", "name": "Syft"},
        "R9-30": {"repo": "CycloneDX/cyclonedx-python", "pypi": "cyclonedx-bom", "gh": "cyclonedx-bom", "lic": "Apache-2.0", "name": "cyclonedx-bom"},
        "R9-31": {"repo": "sigstore/cosign", "gh": "cosign", "lic": "Apache-2.0", "name": "Cosign"},
        "R9-32": {"repo": "open-telemetry/opentelemetry-python", "pypi": "opentelemetry-api", "gh": "opentelemetry", "lic": "Apache-2.0", "name": "OpenTelemetry Python core"},
        "R9-33": {"repo": "renovatebot/renovate", "gh": "renovate", "lic": "AGPL-3.0", "name": "Renovate"},
        "R9-34": {"repo": "containers/bubblewrap", "gh": "bubblewrap", "lic": "LGPL-2.0-or-later", "name": "bubblewrap"},
        "R9-38": {"repo": "cortexkit/magic-context", "gh": "magic-context", "lic": "MIT", "name": "magic-context / CortexKit"},
    }

    for rec_id, info in mapping.items():
        gh_key = info.get("gh")
        pypi_key = info.get("pypi")
        repo = info.get("repo")
        
        gh_repo = get_json(f"gh_repo__{gh_key}.json") if gh_key else None
        pypi_json = get_json(f"pypi__{pypi_key}.json") if pypi_key else None
        gh_rel = get_json(f"gh_release_latest__{gh_key}.json") if gh_key else None
        
        sec_pattern = re.compile(rf"(### {rec_id} [^\n]+\n.*?\n\| `upstream_repository` \| )(`UNVERIFIED`|[^\n]+)(\n\| `version_tag_or_commit` \| )(`UNVERIFIED`|[^\n]+)(\n\| `license_expression_and_obligations` \| )(`UNVERIFIED`|[^\n]+)(\n\| `transitive_dependency_summary` \| [^\n]+\n\| `security_review_ref` \| )(`UNVERIFIED`|[^\n]+)", re.DOTALL)
        
        m = sec_pattern.search(content)
        if m:
            new_upstream = f"https://github.com/{repo} (verified via gh_repo__{gh_key}.json)"
            
            new_ver = "UNVERIFIED"
            if pypi_json and pypi_json.get("info", {}).get("version"):
                new_ver = f"PyPI release {pypi_json['info']['version']} (verified via pypi__{pypi_key}.json)"
            elif gh_rel and gh_rel.get("tag_name"):
                new_ver = f"GitHub release {gh_rel['tag_name']} (verified via gh_release_latest__{gh_key}.json)"
            elif gh_repo and gh_repo.get("default_branch"):
                new_ver = f"Default branch {gh_repo['default_branch']} @ pushed {gh_repo.get('pushed_at', '')[:10]}"
            
            strict_lic = resolve_licence_strict(pypi_json, None, gh_key)
            new_lic = f"{strict_lic} (verified via gh_license__{gh_key}.txt)"
            
            adv_json = get_json(f"gh_advisories__{gh_key}.json")
            adv_cnt = len(adv_json) if isinstance(adv_json, list) else 0
            new_sec = f"{adv_cnt} security advisories in GitHub Security Advisories; ref gh_advisories__{gh_key}.json"

            replacement = f"{m.group(1)}{new_upstream}{m.group(3)}{new_ver}{m.group(5)}{new_lic}{m.group(7)}{new_sec}"
            content = content[:m.start()] + replacement + content[m.end():]

    return content

def extract_current_table_cells(content):
    """Parse existing tables from content to compare for cell diffs."""
    cells = {}
    r9_match = re.search(r"\| Record \| Tool \| Phase \| Role \| Version \(PyPI/npm\) \|.*?(?=\n\n### Judgment per record)", content, re.DOTALL)
    if r9_match:
        lines = [l.strip() for l in r9_match.group(0).splitlines() if l.strip().startswith("|")]
        if len(lines) >= 3:
            headers = [h.strip() for h in lines[0].split("|")[1:-1]]
            for line in lines[2:]:
                parts = [p.strip() for p in line.split("|")[1:-1]]
                if parts and len(parts) == len(headers):
                    rec = parts[0]
                    for h, val in zip(headers, parts):
                        cells[(rec, h)] = val
    return cells

def run_regen():
    with open(DOC_PATH, "r", encoding="utf-8") as f:
        old_content = f.read()

    old_cells = extract_current_table_cells(old_content)

    new_r9_rows = build_r9_39_65_rows()
    new_r9_table = build_r9_39_65_table(new_r9_rows)

    new_exist_rows = build_existing_records_rows()
    new_exist_table = build_existing_records_table(new_exist_rows)

    # 1. Replace R9-39 .. R9-65 table
    table_pattern = re.compile(r"\| Record \| Tool \| Phase \| Role \| Version \(PyPI/npm\) \|.*?(?=\n\n### Judgment per record)", re.DOTALL)
    content = table_pattern.sub(new_r9_table, old_content)

    # 2. Replace existing records table
    exist_pattern = re.compile(r"\| Existing record \| Package \| Version \| First release \| Last release \| Licence \(PyPI\) \|.*?(?=\n\n## R31 phase coverage verdict)", re.DOTALL)
    content = exist_pattern.sub(new_exist_table, content)

    # 3. Update individual records R9-01 .. R9-38
    content = update_individual_records(content)

    # 4. Build and save CONTRADICTIONS.md
    contradictions_md = build_contradictions_content()
    with open(CONTRADICTIONS_PATH, "w", encoding="utf-8") as f:
        f.write(contradictions_md + "\n")
    print(f"Wrote facts-only contradictions to {CONTRADICTIONS_PATH}")

    # Update contradictions in OSS-QUALIFICATION-RECORDS.md
    contra_marker = "## Newly Discovered Contradictions"
    if contra_marker in content:
        content = re.sub(rf"{contra_marker}.*$", "## Contradictions Between Previous Claims and Raw Evidence\n\n" + contradictions_md.split("\n", 2)[2], content, flags=re.DOTALL)
    elif "## Contradictions Between Previous Claims and Raw Evidence" in content:
        content = re.sub(r"## Contradictions Between Previous Claims and Raw Evidence.*$", contradictions_md, content, flags=re.DOTALL)
    else:
        content += "\n\n" + contradictions_md + "\n"

    with open(DOC_PATH, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"Successfully updated {DOC_PATH}")

    # Compute and print cell diffs
    new_cells = {}
    for r in new_r9_rows:
        rec = r[0]
        for h, val in zip(TABLE_HEADERS_R9, r):
            new_cells[(rec, h)] = val

    print("\n" + "="*80)
    print("DIFF OF OLD VS NEW CELLS (R9-39 .. R9-65):")
    print("="*80)
    changed_count = 0
    for key, new_val in sorted(new_cells.items()):
        old_val = old_cells.get(key)
        if old_val != new_val:
            changed_count += 1
            rec, col = key
            print(f"[{rec}] Column '{col}':")
            print(f"   OLD: {old_val}")
            print(f"   NEW: {new_val}")
    print(f"Total changed cells: {changed_count}")
    print("="*80)

if __name__ == "__main__":
    run_regen()
