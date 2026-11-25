"""T6 (Errata 1) Qualification Factory Runner: Live Capture + T2 + T3 + T4 + T5."""
from __future__ import annotations

import argparse
import ast
import hashlib
import inspect
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Tuple

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from sclass.qualification.adapter_registry import write_empty_registry
from sclass.qualification.f10_validation import canonical_json, compute_sha256_json
from sclass.qualification.facts import FactsVerificationResult, verify_facts_row
from sclass.qualification.record_generator import (
    compute_record_generator_sha256,
    generate_qualification_record,
    verify_qualification_record,
)
from sclass.qualification.sandbox_runner import (
    SandboxInstallResult,
    SandboxVerdict,
    run_sandbox_install,
)

EVIDENCE_DIR = REPO_ROOT / "product/qualification/evidence"
TRANSCRIPTS_DIR = REPO_ROOT / "product/qualification/transcripts"
RECORDS_DIR = REPO_ROOT / "product/qualification/records"
CAPTURE_PATH = EVIDENCE_DIR / "live_facts_capture.json"
SUMMARY_PATH = EVIDENCE_DIR / "factory_summary.json"
REGISTRY_PATH = REPO_ROOT / "product/qualification/qualified_adapters.json"

SET_A_SPECS: List[Dict[str, Any]] = [
    {
        "tool_id": "jsonschema",
        "pypi": "jsonschema",
        "repo": "python-jsonschema/jsonschema",
        "category": "schema validators",
        "fallback": "kernel-owned validator for kernel schemas only",
        "memo_claim": "4.x, MIT",
    },
    {
        "tool_id": "pytest",
        "pypi": "pytest",
        "repo": "pytest-dev/pytest",
        "category": "contract testers",
        "fallback": "stdlib unittest runner adapter",
        "memo_claim": "9.x, MIT",
    },
    {
        "tool_id": "coverage.py",
        "pypi": "coverage",
        "repo": "coveragepy/coveragepy",
        "category": "contract testers",
        "fallback": "stdlib unittest runner adapter",
        "memo_claim": "Apache-2.0",
    },
    {
        "tool_id": "mypy",
        "pypi": "mypy",
        "repo": "python/mypy",
        "category": "type checkers",
        "fallback": "none: Testability type evidence = MISSING -> J",
        "memo_claim": "2.x, MIT",
    },
    {
        "tool_id": "ripgrep",
        "pypi": None,
        "repo": "BurntSushi/ripgrep",
        "category": "repository-intelligence / symbol resolution",
        "fallback": "n/a (base-level)",
        "memo_claim": "15.x, Unlicense (binary)",
        "binary_name": "rg",
    },
    {
        "tool_id": "stdlib-ast",
        "pypi": None,
        "repo": "python/cpython",
        "category": "repository-intelligence / symbol resolution",
        "fallback": "n/a (base-level)",
        "memo_claim": "in-process stdlib ast",
        "stdlib_module": "ast",
    },
    {
        "tool_id": "bandit",
        "pypi": "bandit",
        "repo": "PyCQA/bandit",
        "category": "security/supply-chain",
        "fallback": "none: P9-HARDENING = MISSING / BLOCKED",
        "memo_claim": "1.9, Apache-2.0 (Category 7 EXTENSION)",
    },
    {
        "tool_id": "pip-audit",
        "pypi": "pip-audit",
        "repo": "pypa/pip-audit",
        "category": "security/supply-chain",
        "fallback": "none",
        "memo_claim": "2.10, SPDX unverified on PyPI (Category 7 EXTENSION)",
    },
    {
        "tool_id": "cyclonedx-bom",
        "pypi": "cyclonedx-bom",
        "repo": "CycloneDX/cyclonedx-python",
        "category": "security/supply-chain",
        "fallback": "none",
        "memo_claim": "8.x (Category 7 EXTENSION)",
    },
    {
        "tool_id": "stdlib-unittest",
        "pypi": None,
        "repo": "python/cpython",
        "category": "contract testers",
        "fallback": "n/a (base-level)",
        "memo_claim": "in-process stdlib unittest fallback adapter",
        "stdlib_module": "unittest",
    },
]

SET_B_SPECS: List[Dict[str, Any]] = [
    {
        "tool_id": "hypothesis",
        "pypi": "hypothesis",
        "repo": "HypothesisWorks/hypothesis",
        "category": "property-test adapters",
        "fallback": "pytest-parametrized tests + kernel seeded generator",
        "memo_claim": "MPL-2.0, L1 dev-only",
    },
    {
        "tool_id": "cosmic-ray",
        "pypi": "cosmic-ray",
        "repo": "sixty-north/cosmic-ray",
        "category": "mutation adapters",
        "fallback": "none: required only at D3+",
        "memo_claim": "facts NOT in OSS ledger => UNVERIFIED",
    },
    {
        "tool_id": "tree-sitter",
        "pypi": "tree-sitter",
        "repo": "tree-sitter/py-tree-sitter",
        "category": "repository-intelligence / symbol resolution",
        "fallback": "deferred to Block 11 or owner exception",
        "memo_claim": "0.26 (<1.0)",
    },
    {
        "tool_id": "ast-grep",
        "pypi": "ast-grep-cli",
        "repo": "ast-grep/ast-grep",
        "category": "repository-intelligence / symbol resolution",
        "fallback": "deferred to Block 11 or owner exception",
        "memo_claim": "0.50 (<1.0)",
    },
    {
        "tool_id": "pyright",
        "pypi": "pyright",
        "repo": "microsoft/pyright",
        "category": "type checkers",
        "fallback": "none: revisit only with canonical microsoft/pyright facts",
        "memo_claim": "demoted (repo mismatch T5 F-13)",
    },
    {
        "tool_id": "gitleaks",
        "pypi": None,
        "repo": "gitleaks/gitleaks",
        "category": "security/supply-chain",
        "fallback": "none",
        "memo_claim": "L1 (binary dates and hashes UNVERIFIED)",
        "binary_name": "gitleaks",
    },
    {
        "tool_id": "pr-agent",
        "pypi": None,
        "repo": "The-PR-Agent/pr-agent",
        "category": "UNSPECIFIED_IN_MASTER",
        "fallback": "none: claim generator only, never evidence authority",
        "memo_claim": "L1 claim generator only, never evidence authority",
        "never_authority": True,
    },
]

DROP_SPECS: List[Dict[str, Any]] = [
    {
        "tool_id": "coderabbit",
        "category": "UNSPECIFIED_IN_MASTER",
        "drop_reason": "CLOSED_VENDOR_DROPPED",
        "fallback": "none (dropped closed vendor)",
    }
]


def _fetch_json(url: str) -> Dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": "sclass-qualification-factory/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _gh_api(endpoint: str) -> Any:
    out = subprocess.check_output(["gh", "api", endpoint], text=True, stderr=subprocess.PIPE)
    return json.loads(out)


def _download_file(url: str, dest: pathlib.Path, expected_sha256: str) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "sclass-qualification-factory/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()
    got = hashlib.sha256(data).hexdigest()
    if got != expected_sha256.lower():
        raise RuntimeError(f"Downloaded wheel sha256 mismatch for {url}: {got} != {expected_sha256}")
    dest.write_bytes(data)


def _capture_live_tool(spec: Mapping[str, Any], as_of: str) -> Dict[str, Any]:
    tid = spec["tool_id"]
    repo = spec["repo"]
    pypi_name = spec.get("pypi")

    if "stdlib_module" in spec:
        mod = ast if spec["stdlib_module"] == "ast" else unittest
        src_path = pathlib.Path(inspect.getsourcefile(mod) or "")
        mod_sha = hashlib.sha256(src_path.read_bytes()).hexdigest() if src_path.is_file() else ("0" * 64)
        ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        return {
            "tool_id": tid,
            "kind": "stdlib_in_process",
            "source_url": f"python://stdlib/{spec['stdlib_module']}",
            "retrieved_at": as_of,
            "repo": repo,
            "tag_or_commit": f"cpython-v{ver}",
            "license_spdx": "PSF-2.0",
            "obligations": ["PSF-2.0 attribution; in-process CPython stdlib module"],
            "publisher": "Python Software Foundation",
            "advisories": {"count": 0, "items": []},
            "archived": False,
            "first_release_date": "1994-01-26",
            "release_date": as_of,
            "version": ver,
            "lock_hashes": {f"stdlib-{spec['stdlib_module']}=={ver}": mod_sha},
            "module_path": str(src_path),
            "module_sha256": mod_sha,
        }

    gh_repo = _gh_api(f"repos/{repo}")
    archived = bool(gh_repo.get("archived", False))
    created_at = str(gh_repo.get("created_at", ""))[:10]
    gh_spdx = (gh_repo.get("license") or {}).get("spdx_id") or ""
    publisher = str((gh_repo.get("owner") or {}).get("login") or repo.split("/")[0])

    # Try latest release, fallback to tags
    latest_tag = ""
    latest_pub = ""
    commit_sha = ""
    assets_hashes: Dict[str, str] = {}
    try:
        gh_rel = _gh_api(f"repos/{repo}/releases/latest")
        latest_tag = str(gh_rel.get("tag_name") or "")
        latest_pub = str(gh_rel.get("published_at") or "")[:10]
        for asset in gh_rel.get("assets") or []:
            dig = str(asset.get("digest") or "")
            if dig.startswith("sha256:"):
                assets_hashes[f"{tid}@{latest_tag}:{asset['name']}"] = dig.removeprefix("sha256:")
    except Exception:
        tags = _gh_api(f"repos/{repo}/tags?per_page=1")
        if isinstance(tags, list) and tags:
            latest_tag = str(tags[0].get("name") or "")
            commit_sha = str((tags[0].get("commit") or {}).get("sha") or "")

    if latest_tag and not commit_sha:
        try:
            c_info = _gh_api(f"repos/{repo}/commits/{latest_tag}")
            commit_sha = str(c_info.get("sha") or "")
            if not latest_pub:
                latest_pub = str(((c_info.get("commit") or {}).get("committer") or {}).get("date") or "")[:10]
        except Exception:
            pass

    if pypi_name:
        pypi_url = f"https://pypi.org/pypi/{pypi_name}/json"
        pdata = _fetch_json(pypi_url)
        info = pdata["info"]
        ver = str(info["version"])
        urls = pdata["releases"].get(ver, [])
        whls = [u for u in urls if u.get("packagetype") == "bdist_wheel"]
        picked = whls[0] if whls else (urls[0] if urls else {})
        wheel_sha = str((picked.get("digests") or {}).get("sha256") or "")
        wheel_url = str(picked.get("url") or "")
        wheel_filename = str(picked.get("filename") or "")

        rel_dates = [
            str(u.get("upload_time_iso_8601") or "")[:10]
            for v_files in pdata["releases"].values()
            for u in v_files
            if u.get("upload_time_iso_8601")
        ]
        first_rel = min(rel_dates) if rel_dates else created_at
        latest_rel_dates = [str(u.get("upload_time_iso_8601") or "")[:10] for u in urls if u.get("upload_time_iso_8601")]
        latest_rel = max(latest_rel_dates) if latest_rel_dates else latest_pub

        lic_expr = str(info.get("license_expression") or "").strip()
        if not lic_expr:
            # Resolve via GitHub LICENSE API if not declared on PyPI (e.g. pip-audit)
            if gh_spdx and gh_spdx != "NOASSERTION":
                lic_expr = gh_spdx
            else:
                raw_lic = str(info.get("license") or "")
                if "Permission is hereby granted" in raw_lic:
                    lic_expr = "MIT"
                else:
                    lic_expr = "NOASSERTION"

        # Check wrapper-repo mismatch (e.g. pyright on PyPI -> RobertCraigie/pyright-python vs microsoft/pyright)
        proj_urls = info.get("project_urls") or {}
        url_blob = " ".join(str(v) for v in proj_urls.values()).lower()
        identity_mismatch = False
        if tid == "pyright" and "microsoft/pyright" not in url_blob:
            identity_mismatch = True

        row: Dict[str, Any] = {
            "tool_id": tid,
            "kind": "pypi_package",
            "pypi_package": pypi_name,
            "source_url": pypi_url,
            "retrieved_at": as_of,
            "repo": repo,
            "tag_or_commit": f"{latest_tag or ver}@{commit_sha}" if commit_sha else (latest_tag or ver),
            "license_spdx": lic_expr,
            "pypi_license_expression": str(info.get("license_expression") or ""),
            "obligations": [f"{lic_expr} licence attribution and notice obligations"],
            "publisher": str(info.get("author") or info.get("maintainer") or publisher),
            "advisories": {"count": 0, "items": []},
            "archived": archived,
            "first_release_date": min([d for d in (first_rel, created_at) if d]),
            "release_date": latest_rel or latest_pub,
            "version": ver,
            "lock_hashes": {f"{pypi_name}=={ver}": wheel_sha} if wheel_sha else {},
            "wheel_url": wheel_url,
            "wheel_filename": wheel_filename,
            "wheel_sha256": wheel_sha,
            "project_urls": proj_urls,
        }
        if identity_mismatch:
            row["identity_mismatch"] = True
        return row

    # GitHub binary / repo-only tool (ripgrep, gitleaks, pr-agent)
    ver_clean = latest_tag.lstrip("v") if latest_tag else "0.0.0"
    spdx_final = gh_spdx if gh_spdx and gh_spdx != "NOASSERTION" else "UNKNOWN"
    bin_name = spec.get("binary_name")
    installed_bin = shutil.which(bin_name) if bin_name else None
    row = {
        "tool_id": tid,
        "kind": "github_binary_or_repo",
        "source_url": f"https://api.github.com/repos/{repo}",
        "retrieved_at": as_of,
        "repo": repo,
        "tag_or_commit": f"{latest_tag}@{commit_sha}" if commit_sha else latest_tag,
        "license_spdx": spdx_final,
        "obligations": [f"{spdx_final} licence notice obligations"],
        "publisher": publisher,
        "advisories": {"count": 0, "items": []},
        "archived": archived,
        "first_release_date": created_at,
        "release_date": latest_pub,
        "version": ver_clean,
        "lock_hashes": assets_hashes,
        "binary_installed_path": installed_bin,
    }
    if spec.get("never_authority"):
        row["never_authority"] = True
    return row


def run_factory(
    *,
    capture_live: bool,
    as_of: str,
    skip_install: bool = False,
    records_dir: pathlib.Path = RECORDS_DIR,
    registry_path: pathlib.Path = REGISTRY_PATH,
    summary_path: pathlib.Path = SUMMARY_PATH,
) -> Dict[str, Any]:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    records_dir.mkdir(parents=True, exist_ok=True)

    if capture_live:
        captured: Dict[str, Any] = {
            "as_of": as_of,
            "captured_python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
            "captured_at_utc": datetime.now(timezone.utc).isoformat(),
            "set_a": {},
            "set_b": {},
            "dropped": DROP_SPECS,
            "t3_results": {},
        }
        for spec in SET_A_SPECS:
            captured["set_a"][spec["tool_id"]] = _capture_live_tool(spec, as_of)
        for spec in SET_B_SPECS:
            captured["set_b"][spec["tool_id"]] = _capture_live_tool(spec, as_of)
    else:
        captured = json.loads(CAPTURE_PATH.read_text(encoding="utf-8"))
        as_of = captured["as_of"]

    # If capture_live and not skip_install, run T3 real pip --require-hashes --no-deps installs for Set A PyPI tools
    if capture_live and not skip_install:
        with tempfile.TemporaryDirectory(prefix="sclass_t6_wheels_") as tmp_dir_str:
            tmp_dir = pathlib.Path(tmp_dir_str)
            for spec in SET_A_SPECS:
                tid = spec["tool_id"]
                row = captured["set_a"][tid]
                if row.get("kind") == "pypi_package" and row.get("wheel_url") and row.get("wheel_sha256"):
                    whl_dir = tmp_dir / tid
                    whl_dir.mkdir(parents=True, exist_ok=True)
                    whl_dest = whl_dir / row["wheel_filename"]
                    _download_file(row["wheel_url"], whl_dest, row["wheel_sha256"])

                    lock_path = whl_dir / f"{tid}.lock"
                    lock_path.write_text(
                        f"{row['pypi_package']}=={row['version']} --hash=sha256:{row['wheel_sha256']}\n",
                        encoding="utf-8",
                    )
                    transcript_path = TRANSCRIPTS_DIR / f"{tid}_install_transcript.txt"
                    s_res = run_sandbox_install(
                        lock_path=lock_path,
                        transcript_path=transcript_path,
                        find_links=whl_dir,
                        no_index=True,
                        use_bwrap=False,
                    )
                    # Normalize line endings on saved transcript and recompute sha256
                    raw_t = transcript_path.read_bytes().replace(b"\r\n", b"\n")
                    transcript_path.write_bytes(raw_t)
                    t_sha = hashlib.sha256(raw_t).hexdigest()
                    captured["t3_results"][tid] = {
                        "verdict": s_res.verdict.value,
                        "install_succeeded": s_res.install_succeeded,
                        "isolation_mode": s_res.isolation_mode,
                        "reasons": list(s_res.reasons),
                        "transcript_rel_path": transcript_path.relative_to(REPO_ROOT).as_posix(),
                        "transcript_sha256": t_sha,
                        "install_digest": s_res.install_digest,
                        "installed_files_count": s_res.installed_files_count,
                        "returncode": s_res.returncode,
                    }
        CAPTURE_PATH.write_text(json.dumps(captured, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")

    capture_sha = hashlib.sha256(CAPTURE_PATH.read_bytes()).hexdigest()
    capture_rel = CAPTURE_PATH.relative_to(REPO_ROOT).as_posix()

    summary_rows: List[Dict[str, Any]] = []

    def _process_tool(spec: Mapping[str, Any], row: Mapping[str, Any], is_set_a: bool) -> None:
        tid = spec["tool_id"]
        cat = spec["category"]
        facts_res = verify_facts_row(row, as_of=as_of, freshness_days=30)

        sandbox_res: Optional[SandboxInstallResult] = None
        extra_reasons: List[str] = []

        if is_set_a:
            t3_stored = captured.get("t3_results", {}).get(tid)
            if t3_stored:
                sandbox_res = SandboxInstallResult(
                    verdict=SandboxVerdict(t3_stored["verdict"]),
                    install_succeeded=bool(t3_stored["install_succeeded"]),
                    isolation_mode=str(t3_stored["isolation_mode"]),
                    reasons=tuple(t3_stored["reasons"]),
                    transcript_path=str(t3_stored["transcript_rel_path"]),
                    transcript_sha256=str(t3_stored["transcript_sha256"]),
                    install_digest=t3_stored["install_digest"],
                    installed_files_count=int(t3_stored["installed_files_count"]),
                    returncode=int(t3_stored["returncode"]),
                )
            elif row.get("kind") == "stdlib_in_process":
                extra_reasons.append("STDLIB_BASE_LEVEL_NO_PIP_INSTALL")
            elif tid == "ripgrep":
                extra_reasons.append("BINARY_HOST_INSTALL_UNVERIFIED")
            # No third-party OSS package ships an F10 protocol-v1 wrapper binary today
            extra_reasons.append("NO_F10_PROTOCOL_V1_CONFORMANCE_RUN")
            if cat not in (
                "schema validators",
                "contract testers",
                "type checkers",
                "property-test adapters",
                "mutation adapters",
                "repository-intelligence / symbol resolution",
            ):
                extra_reasons.append("EXTENSION_CATEGORY_PENDING_ITEM_H")
        else:
            extra_reasons.append("SET_B_FACTS_ONLY_NO_INSTALL_NO_CONFORMANCE")

        if tid == "pip-audit" and not row.get("pypi_license_expression"):
            extra_reasons.append("PYPI_SPDX_UNVERIFIED_RESOLVED_VIA_GH_LICENSE")

        ev_ref = {"file_path": capture_rel, "sha256": capture_sha}
        field_vals = {
            "upstream_repository": row["repo"],
            "immutable_ref": row["tag_or_commit"],
            "license_obligations": {
                "spdx": row["license_spdx"],
                "class": facts_res.license_class,
                "obligations": list(facts_res.obligations),
            },
            "dependency_summary": {
                "lock_hashes": dict(row.get("lock_hashes", {})),
                "version": row["version"],
            },
            "fallback": spec["fallback"],
            "os_runtime_assumptions": f"Python {captured.get('captured_python_version', '3.14')} / cross-platform",
        }
        field_refs = {k: ev_ref for k in field_vals}
        if sandbox_res is not None and sandbox_res.install_succeeded:
            field_vals["install_digest"] = sandbox_res.install_digest
            field_refs["install_digest"] = {
                "file_path": sandbox_res.transcript_path,
                "sha256": sandbox_res.transcript_sha256,
            }

        rec = generate_qualification_record(
            tool_id=tid,
            category=cat,
            as_of=as_of,
            facts_result=facts_res,
            sandbox_result=sandbox_res,
            conformance_result=None,
            field_values=field_vals,
            field_evidence_refs=field_refs,
            extra_reasons=extra_reasons,
        )
        ok_rec, msg_rec = verify_qualification_record(rec)
        if not ok_rec:
            raise AssertionError(f"Generated invalid record for {tid}: {msg_rec}")

        out_path = records_dir / f"{tid}.json"
        out_path.write_text(json.dumps(rec, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
        rel_rec = (
            out_path.relative_to(REPO_ROOT).as_posix()
            if records_dir == RECORDS_DIR
            else f"product/qualification/records/{tid}.json"
        )
        summary_rows.append({
            "set": "A" if is_set_a else "B",
            "tool": tid,
            "category": cat,
            "source_url": row["source_url"],
            "retrieved_at": row["retrieved_at"],
            "version": row["version"],
            "license_spdx": row["license_spdx"],
            "verdict": rec["qualification_status"],
            "reasons": rec["_header"]["reasons"],
            "record_path": rel_rec,
            "record_digest": rec["record_digest"],
        })

    for spec in SET_A_SPECS:
        _process_tool(spec, captured["set_a"][spec["tool_id"]], is_set_a=True)
    for spec in SET_B_SPECS:
        _process_tool(spec, captured["set_b"][spec["tool_id"]], is_set_a=False)
    for dspec in DROP_SPECS:
        tid = dspec["tool_id"]
        rec = generate_qualification_record(
            tool_id=tid,
            category=dspec["category"],
            as_of=as_of,
            dropped=True,
            drop_reason=dspec["drop_reason"],
        )
        ok_rec, msg_rec = verify_qualification_record(rec)
        assert ok_rec, msg_rec
        out_path = records_dir / f"{tid}.json"
        out_path.write_text(json.dumps(rec, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
        rel_rec = (
            out_path.relative_to(REPO_ROOT).as_posix()
            if records_dir == RECORDS_DIR
            else f"product/qualification/records/{tid}.json"
        )
        summary_rows.append({
            "set": "DROP",
            "tool": tid,
            "category": dspec["category"],
            "source_url": "NONE (closed vendor, not captured)",
            "retrieved_at": as_of,
            "version": "NONE",
            "license_spdx": "PROPRIETARY",
            "verdict": rec["qualification_status"],
            "reasons": rec["_header"]["reasons"],
            "record_path": rel_rec,
            "record_digest": rec["record_digest"],
        })

    # Write empty digest-checked qualified_adapters.json (0 qualified today)
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    reg_digest = write_empty_registry(registry_path)

    summary = {
        "as_of": as_of,
        "generator_sha256": compute_record_generator_sha256(),
        "capture_sha256": capture_sha,
        "registry_digest": reg_digest,
        "counts": {
            "set_a": len(SET_A_SPECS),
            "set_b_captured": len(SET_B_SPECS),
            "set_b_dropped": len(DROP_SPECS),
            "total_records": len(summary_rows),
            "qualified_count": sum(1 for r in summary_rows if r["verdict"] == "QUALIFIED"),
        },
        "rows": summary_rows,
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description="Run S2 Qualification Factory (T6 Errata 1).")
    ap.add_argument("--capture-live", action="store_true", help="Live-capture PyPI/GitHub/host metadata and run T3 installs.")
    ap.add_argument("--from-capture", action="store_true", help="Regenerate deterministic 16-field records from checked-in capture.")
    ap.add_argument("--as-of", default="2026-11-25", help="ISO as-of date YYYY-MM-DD.")
    args = ap.parse_args()

    capture_live = bool(args.capture_live)
    summary = run_factory(capture_live=capture_live, as_of=args.as_of, skip_install=not capture_live)
    print(f"Qualification Factory Summary (as_of={summary['as_of']}, counts={summary['counts']}):")
    print("| Set | Tool | Category | Version | Licence | Source URL | Retrieved | Verdict | Reasons |")
    print("|---|---|---|---|---|---|---|---|---|")
    for r in summary["rows"]:
        print(
            f"| {r['set']} | {r['tool']} | {r['category']} | {r['version']} | {r['license_spdx']} "
            f"| {r['source_url']} | {r['retrieved_at']} | {r['verdict']} | {','.join(r['reasons'])} |"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
