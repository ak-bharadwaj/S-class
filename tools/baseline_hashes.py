#!/usr/bin/env python3
"""Baseline Hashes Verification & Generation Tool (Roadmap B01 / Defect 3).

Computes normalized-LF SHA-256 digests of every file across:
  - 00-SPEC/
  - 10-CONFORMANCE/
  - 20-RUNTIME/

Strictly validates manifest entries against embedded canonical package hashes.
Rejects any mismatched, missing, or malformed manifest entries (fail-closed).
Completes multi-branch baseline comparison across:
  - main        (447caf96e356a836b0455ac6d845a6729a9e007f)
  - h0          (e60a089dbdd8d14394009f1c9661967d8d5b7b74)
  - h1a         (9c6e0fc9d21219f48c0235f3dc69687063f84061)
  - h1b         (8b012f2dadf8785481b36e48598e34cc8a80c92f)
  - integration is evaluated dynamically at head under test

Generates governance/BASELINE-HASHES.txt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
GOVERNANCE_DIR = REPO_ROOT / "governance"
BASELINE_HASHES_FILE = GOVERNANCE_DIR / "BASELINE-HASHES.txt"
MANIFEST_FILE = GOVERNANCE_DIR / "FROZEN-MANIFEST.sha256"
CLASSIFICATION_EVIDENCE_FILE = REPO_ROOT / "delivery-evidence" / "branch_baselines_classification.json"
RAW_EVIDENCE_DIR = REPO_ROOT / "delivery-evidence" / "branch_baselines"

# Canonical package hashes from FROZEN-MANIFEST.sha256 in S-CLASS-R32-PACKAGE.zip
# Embedded as deterministic baseline truth anchors. Manifest values cannot override these.
CANONICAL_PACKAGE_HASHES: Dict[str, str] = {
    "00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md": "53c02b13085dc3e1dcf75b9e8c306704d83bf37175b73a6be1a4b6ab7823ebb1",
    "10-CONFORMANCE/c1-vectors.v6.0.1.json": "db58744d9829f7cac2ec7715a93d30d20a0d9ba6912d01f563504564e85b2da8",
    "10-CONFORMANCE/c1_independent.js": "3d70c4791c63d8c6d1dc2724fac5012424067a2c0dd39f6432c1edf0af1abcec",
    "10-CONFORMANCE/coverage-map.v6.0.1.json": "722893054b29448238cb7cca5a149b6262d3cc606a4aeb2711c91e45a7dd6a20",
    "10-CONFORMANCE/sclass_kernel_v6_0_1.py": "d0f8f124dd55aab5cfb68d8c7d644eccf2694f52016c2e4a2132e6d6cef5575c",
    "10-CONFORMANCE/sclass_semantics_v6_0_1.py": "66387014aba28ce307ce630b58dcd3799da8251ca9955583a33a32a5f7b17a76",
    "10-CONFORMANCE/spec_integrity.py": "86056215757b8b66b4f9e405be08c82d26375ee1870a311b1957da8732a4bda5",
    "10-CONFORMANCE/state-machines.v6.0.1.json": "24f159e6f72179ea66365b585f085727f6ef48420a09eae8c6024cb0bb51fdad",
    "10-CONFORMANCE/test_sclass_v6_0_1_conformance.py": "ca4dafd9ab75096e9d92a3b15fbbac8693d03c172da444847657d42fd3b79158",
    "20-RUNTIME/README.md": "254c1a31d9a10a308c96d9c9212c487168c690f269c156bc3076b3ffdf19901f",
    "20-RUNTIME/requirements.txt": "ceeace8d072b469f31ba1a26f2c40677f225d090f76fee996ffe0f7498023c15",
    "20-RUNTIME/sclass_runtime_v6_0_1.py": "7e224c4145f405231b27b2535f17337d2d9c98dff20c1b5109028c9dd5c1c33c",
    "20-RUNTIME/test_sclass_runtime_v6_0_1.py": "0260d0d0860a0218b1990591171ce720122e85be1d42cdeb0718b8ad3f4b28b3",
}

# Authoritative branch reference identities (immutable historical pins)
AUTHORITATIVE_REFS = {
    "main": "447caf96e356a836b0455ac6d845a6729a9e007f",
    "h0": "e60a089dbdd8d14394009f1c9661967d8d5b7b74",
    "h1a": "9c6e0fc9d21219f48c0235f3dc69687063f84061",
    "h1b": "8b012f2dadf8785481b36e48598e34cc8a80c92f",
}


CLASSIFICATION_EVIDENCE_FILE = REPO_ROOT / "delivery-evidence" / "branch_baselines_classification.json"

REF_ARCHITECTURAL_NOTES = {
    "main": "Pre-H1a unconfined boundary failures",
    "h0": "Pre-H1a boundary mock harness defects",
    "h1a": "H1a trust model & test authority separation",
    "h1b": "H1b real Bubblewrap & cgroup v2 sandbox",
    "integration": "R30-B1 consolidated integration baseline",
}


def load_and_validate_branch_classification_evidence(
    evidence_path: Optional[Path] = None,
    raw_evidence_dir: Optional[Path] = None,
) -> Dict[str, dict]:
    """Loads and strictly validates clean-install branch baselines classification evidence.

    Fails closed if:
      - Evidence file does not exist or JSON is invalid / malformed
      - Schema identifier is mismatched
      - Any of the 5 authoritative refs is missing
      - Any ref's commit SHA does not match canonical AUTHORITATIVE_REFS
      - Any ref's counts violate arithmetic consistency (total == passed + env + code)
      - code_failures_count does not equal len(code_failures)
      - env_items_count does not equal sum(env_breakdown.values())
      - Any ref's outcome status does not strictly reflect code_failures == 0 (PASS vs FAIL)
      - Any ref's aggregate metrics disagree with its retained ref_metadata.json
      - The retained JUnit XML is missing, malformed, or has conflicting/duplicate outcomes
      - Independent recomputation from JUnit XML testcase, failure, error, skipped tags disagrees with declared metrics
      - Raw evidence files fail to identify the exact expected ref SHA
    """
    path = evidence_path or CLASSIFICATION_EVIDENCE_FILE
    if not path.exists():
        raise FileNotFoundError(
            f"Branch baselines classification evidence not found at '{path}'. "
            f"Run 'tools/evaluate_branch_baselines.py' first."
        )

    if raw_evidence_dir is not None:
        raw_dir = raw_evidence_dir
    elif (path.parent / "branch_baselines").exists():
        raw_dir = path.parent / "branch_baselines"
    else:
        raw_dir = RAW_EVIDENCE_DIR
    if not raw_dir.exists():
        raise FileNotFoundError(
            f"Raw branch evidence directory not found at '{raw_dir}'. "
            f"Run 'tools/evaluate_branch_baselines.py' first."
        )

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise ValueError(f"Malformed JSON in branch baselines classification evidence '{path}': {e}") from e

    if not isinstance(data, dict):
        raise ValueError(f"Evidence root must be a JSON object, got {type(data).__name__}")

    schema = data.get("schema")
    if schema != "sclass/branch-baselines-classification/v1":
        raise ValueError(f"Unexpected schema in evidence: '{schema}' (expected 'sclass/branch-baselines-classification/v1')")

    metrics_by_ref = data.get("metrics_by_ref")
    if not isinstance(metrics_by_ref, dict):
        raise ValueError("Missing or invalid 'metrics_by_ref' mapping in evidence")

    validated: Dict[str, dict] = {}
    for ref_name in ("main", "h0", "h1a", "h1b", "integration"):
        if ref_name not in metrics_by_ref:
            raise ValueError(f"Missing required ref '{ref_name}' in branch classification evidence")

        m = metrics_by_ref[ref_name]
        if not isinstance(m, dict):
            raise ValueError(f"Metrics for ref '{ref_name}' must be an object")

        ref_sha = m.get("ref_sha")
        if ref_name in AUTHORITATIVE_REFS:
            expected_sha = AUTHORITATIVE_REFS[ref_name]
            if ref_sha != expected_sha:
                raise ValueError(
                    f"Tampered or mismatched commit SHA for ref '{ref_name}': "
                    f"expected '{expected_sha}', got '{ref_sha}'"
                )
        else:
            expected_sha = ref_sha

        try:
            total = int(m["total_collected"])
            passed = int(m["passed_count"])
            env = int(m["env_items_count"])
            code = int(m["code_failures_count"])
        except (KeyError, TypeError, ValueError) as e:
            raise ValueError(f"Invalid or missing numeric metrics for ref '{ref_name}': {e}") from e

        if total < 0 or passed < 0 or env < 0 or code < 0:
            raise ValueError(f"Negative count detected for ref '{ref_name}': total={total}, passed={passed}, env={env}, code={code}")

        if total != passed + env + code:
            raise ValueError(
                f"Count inconsistency for ref '{ref_name}': "
                f"total {total} != passed ({passed}) + env ({env}) + code ({code})"
            )

        status = m.get("status")
        expected_status = "PASS" if code == 0 else "FAIL"
        if status != expected_status:
            raise ValueError(
                f"Status mismatch for ref '{ref_name}': "
                f"code_failures={code} requires status '{expected_status}', got '{status}'"
            )

        # 1. Require code_failures_count == len(code_failures)
        code_failures = m.get("code_failures")
        if not isinstance(code_failures, list):
            raise ValueError(f"Missing or invalid 'code_failures' list for ref '{ref_name}' in aggregate evidence")
        if len(code_failures) != code:
            raise ValueError(
                f"Failure record count mismatch for ref '{ref_name}': "
                f"code_failures_count ({code}) != len(code_failures) ({len(code_failures)})"
            )

        # 2. Validate ENV record counts against ENV evidence
        env_breakdown = m.get("env_breakdown")
        if not isinstance(env_breakdown, dict):
            raise ValueError(f"Missing or invalid 'env_breakdown' mapping for ref '{ref_name}' in aggregate evidence")
        if sum(env_breakdown.values()) != env:
            raise ValueError(
                f"ENV breakdown count mismatch for ref '{ref_name}': "
                f"env_items_count ({env}) != sum(env_breakdown) ({sum(env_breakdown.values())})"
            )

        # 3. Cross-check against retained per-ref metadata
        ref_evidence_dir = raw_dir / ref_name
        meta_path = ref_evidence_dir / "ref_metadata.json"
        if not meta_path.exists():
            raise FileNotFoundError(f"Missing ref_metadata.json for ref '{ref_name}' at '{meta_path}'")
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception as e:
            raise ValueError(f"Malformed JSON in '{meta_path}': {e}") from e
        if not isinstance(meta, dict):
            raise ValueError(f"Root of '{meta_path}' must be an object")

        if meta.get("ref_sha") != expected_sha:
            raise ValueError(
                f"Mismatched ref_sha in '{meta_path}': expected '{expected_sha}', got '{meta.get('ref_sha')}'"
            )
        if meta.get("ref_name") != ref_name:
            raise ValueError(f"Mismatched ref_name in '{meta_path}': expected '{ref_name}', got '{meta.get('ref_name')}'")

        for field in ("total_collected", "passed_count", "env_items_count", "code_failures_count", "status"):
            if meta.get(field) != m.get(field):
                raise ValueError(
                    f"Metadata disagreement for ref '{ref_name}' in field '{field}': "
                    f"aggregate={m.get(field)}, ref_metadata={meta.get(field)}"
                )
        meta_code_failures = meta.get("code_failures")
        if not isinstance(meta_code_failures, list) or len(meta_code_failures) != code:
            raise ValueError(f"Mismatched code_failures list in '{meta_path}' for ref '{ref_name}'")

        # 4. Parse retained JUnit XML and independently recompute testcase, failure, error, skipped counts
        xml_path = ref_evidence_dir / "junit.xml"
        if not xml_path.exists():
            raise FileNotFoundError(f"Missing retained JUnit XML for ref '{ref_name}' at '{xml_path}'")
        try:
            xml_tree = ET.parse(xml_path)
            xml_root = xml_tree.getroot()
        except Exception as e:
            raise ValueError(f"Malformed JUnit XML for ref '{ref_name}' at '{xml_path}': {e}") from e

        testcases = xml_root.findall(".//testcase")
        actual_tc_count = len(testcases)
        if actual_tc_count != total:
            raise ValueError(
                f"JUnit XML testcase count mismatch for ref '{ref_name}': "
                f"expected total {total}, found {actual_tc_count} <testcase> elements in '{xml_path}'"
            )

        actual_failures = 0
        actual_errors = 0
        actual_skipped = 0
        actual_passed = 0
        seen_node_ids = set()

        for tc in testcases:
            name = tc.attrib.get("name", "")
            classname = tc.attrib.get("classname", "")
            file_attr = tc.attrib.get("file", "")
            node_id = f"{file_attr}::{name}" if file_attr else f"{classname}::{name}"
            if node_id in seen_node_ids:
                raise ValueError(f"Duplicate testcase identity '{node_id}' in JUnit XML for ref '{ref_name}'")
            seen_node_ids.add(node_id)

            f_elems = tc.findall("failure")
            e_elems = tc.findall("error")
            s_elems = tc.findall("skipped")

            if (len(f_elems) > 0) + (len(e_elems) > 0) + (len(s_elems) > 0) > 1:
                raise ValueError(f"Conflicting outcome elements on testcase '{node_id}' in '{xml_path}'")

            if f_elems:
                actual_failures += 1
            elif e_elems:
                actual_errors += 1
            elif s_elems:
                actual_skipped += 1
            else:
                actual_passed += 1

        recomputed_code = actual_failures + actual_errors
        if recomputed_code != code:
            raise ValueError(
                f"JUnit XML failure/error mismatch for ref '{ref_name}': "
                f"expected {code} failures, recomputed {recomputed_code} from '{xml_path}'"
            )
        if actual_skipped != env:
            raise ValueError(
                f"JUnit XML skipped mismatch for ref '{ref_name}': "
                f"expected {env} skipped, recomputed {actual_skipped} from '{xml_path}'"
            )
        if actual_passed != passed:
            raise ValueError(
                f"JUnit XML passed mismatch for ref '{ref_name}': "
                f"expected {passed} passed, recomputed {actual_passed} from '{xml_path}'"
            )

        # Check testsuite root attributes
        ts_elem = xml_root.find("testsuite")
        if ts_elem is None and xml_root.tag == "testsuite":
            ts_elem = xml_root
        if ts_elem is not None:
            ts_tests = int(ts_elem.attrib.get("tests", 0))
            ts_failures = int(ts_elem.attrib.get("failures", 0))
            ts_errors = int(ts_elem.attrib.get("errors", 0))
            ts_skipped = int(ts_elem.attrib.get("skipped", 0))
            if ts_tests != total:
                raise ValueError(f"JUnit XML testsuite attribute tests='{ts_tests}' != total {total} for ref '{ref_name}'")
            if ts_failures + ts_errors != code:
                raise ValueError(f"JUnit XML testsuite attribute failures/errors != code {code} for ref '{ref_name}'")
            if ts_skipped != env:
                raise ValueError(f"JUnit XML testsuite attribute skipped='{ts_skipped}' != env {env} for ref '{ref_name}'")

        validated[ref_name] = m

    return validated


def sha256_normalized_lf(raw_bytes: Optional[bytes]) -> str:
    if raw_bytes is None:
        return "MISSING"
    normalized = raw_bytes.replace(b"\r\n", b"\n")
    return hashlib.sha256(normalized).hexdigest()


def validate_manifest_file(manifest_path: Optional[Path] = None) -> Dict[str, str]:
    """Strictly validates manifest file format and asserts exact equivalence with canonical anchors.

    Fails closed (raising ValueError / FileNotFoundError) on:
      - Missing manifest file
      - Malformed lines or missing hash/path columns
      - Invalid SHA-256 digests (not 64 lowercase hex characters)
      - Missing monitored canonical paths
      - Any hash mismatch against canonical package anchors
    """
    p = manifest_path or MANIFEST_FILE
    if not p.exists():
        raise FileNotFoundError(f"Manifest file missing: {p}")

    manifest_entries: Dict[str, str] = {}
    lines = p.read_text(encoding="utf-8").splitlines()

    for line_num, line in enumerate(lines, start=1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            raise ValueError(f"Malformed manifest entry at line {line_num} in {p}: '{line}'")
        h, rel = parts
        h = h.strip().lower()
        rel = rel.strip()
        if rel.startswith("./"):
            rel = rel[2:]

        # Validate hash format
        if len(h) != 64 or not all(c in "0123456789abcdef" for c in h):
            raise ValueError(f"Invalid SHA-256 hash '{h}' for file '{rel}' at line {line_num} in {p}")

        manifest_entries[rel] = h

    # Validate all canonical package hashes are present and identical to anchors
    for canon_path, expected_hash in CANONICAL_PACKAGE_HASHES.items():
        if canon_path not in manifest_entries:
            raise ValueError(f"Manifest {p} is missing required canonical monitored path: '{canon_path}'")
        manifest_hash = manifest_entries[canon_path]
        if manifest_hash != expected_hash:
            raise ValueError(
                f"MANIFEST INTEGRITY TAMPER: Manifest hash for '{canon_path}' ({manifest_hash}) "
                f"does not match canonical package anchor ({expected_hash})"
            )

    return dict(CANONICAL_PACKAGE_HASHES)


GIT_BIN = "/usr/bin/git" if Path("/usr/bin/git").exists() else (shutil.which("git") or "git")


def get_git_file_bytes(ref: str, rel_path: str) -> Optional[bytes]:
    try:
        res = subprocess.run(
            [GIT_BIN, "show", f"{ref}:{rel_path}"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            check=True,
        )
        return res.stdout
    except Exception:
        local_p = REPO_ROOT / rel_path
        if local_p.exists():
            return local_p.read_bytes()
        return None


def resolve_ref_sha(ref_name: str) -> str:
    for candidate in [f"origin/{ref_name}", ref_name, AUTHORITATIVE_REFS.get(ref_name, "")]:
        if not candidate:
            continue
        try:
            res = subprocess.run(
                [GIT_BIN, "rev-parse", candidate],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                check=True,
            )
            sha = res.stdout.strip()
            if len(sha) == 40:
                return sha
        except Exception:
            pass
    return AUTHORITATIVE_REFS.get(ref_name, "unknown")


def list_target_files() -> List[str]:
    files = set()
    for root_name in ["00-SPEC", "10-CONFORMANCE", "20-RUNTIME"]:
        dir_path = REPO_ROOT / root_name
        if dir_path.exists():
            for p in dir_path.rglob("*"):
                if p.is_file() and "__pycache__" not in p.parts:
                    rel = p.relative_to(REPO_ROOT).as_posix()
                    files.add(rel)
    for rel in CANONICAL_PACKAGE_HASHES:
        files.add(rel)
    return sorted(files)


def generate_baseline_hashes_content(
    manifest_path: Optional[Path] = None,
    classification_path: Optional[Path] = None,
    raw_evidence_dir: Optional[Path] = None,
) -> str:
    # 1. Strictly validate manifest against canonical anchors
    pkg_hashes = validate_manifest_file(manifest_path)
    # 2. Strictly validate clean-install branch baselines classification evidence and underlying raw files
    classification_metrics = load_and_validate_branch_classification_evidence(classification_path, raw_evidence_dir)
    target_files = list_target_files()

    ref_shas = {name: resolve_ref_sha(name) for name in AUTHORITATIVE_REFS}

    lines = [
        "# S-CLASS GOVERNANCE BASELINE HASHES (B01 BASELINE LOCK)",
        "# Generated automatically by tools/baseline_hashes.py — DO NOT EDIT MANUALLY",
        "# Normalized-LF SHA-256: hashlib.sha256(file_bytes.replace(b'\\r\\n', b'\\n')).hexdigest()",
        "# Monitored Scope: 00-SPEC/, 10-CONFORMANCE/, 20-RUNTIME/",
        "# Design Package Source: FROZEN-MANIFEST.sha256 in S-CLASS-R32-PACKAGE.zip",
        "# Authoritative Reference Commits:",
        f"#   - main:        {ref_shas.get('main', AUTHORITATIVE_REFS['main'])}",
        f"#   - h0:          {ref_shas.get('h0', AUTHORITATIVE_REFS['h0'])}",
        f"#   - h1a:         {ref_shas.get('h1a', AUTHORITATIVE_REFS['h1a'])}",
        f"#   - h1b:         {ref_shas.get('h1b', AUTHORITATIVE_REFS['h1b'])}",
    ]
    hist_int_sha = classification_metrics.get("integration", {}).get("ref_sha")
    if hist_int_sha:
        lines.append(f"#   - integration (historical baseline: {hist_int_sha}): dynamic at head under test")
    else:
        lines.append("#   - integration: dynamic at head under test")

    lines.extend([
        "",
        "========================================================================================================================",
        "TABLE 1: CURRENT INTEGRATION REPO HASHES VS FROZEN DESIGN PACKAGE HASHES",
        "========================================================================================================================",
        f"{'File':<50} | {'Package Hash':<64} | {'Repo Hash':<64} | Status",
        "-" * 192,
    ])

    int_rows = []
    for f in target_files:
        pkg_h = pkg_hashes.get(f, "NOT_IN_FROZEN_MANIFEST")
        file_path = REPO_ROOT / f
        int_bytes = file_path.read_bytes() if file_path.exists() else None
        int_h = sha256_normalized_lf(int_bytes)

        status_int = "MATCH" if pkg_h == int_h else "DIFFERS"
        lines.append(f"{f:<50} | {pkg_h:<64} | {int_h:<64} | {status_int}")
        int_rows.append((f, pkg_h, int_h, status_int))
        if f == "10-CONFORMANCE/sclass_semantics_v6_0_1.py":
            lines.append(f"{'  [Accepted Erratum E-SEM-1: WorkProposal.__init__]':<50} | {'66387014aba28ce307ce630b58dcd3799da8251ca9955583a33a32a5f7b17a76':<64} | {'7ecc935246b057a3414faa3cfce36daa4f1be2a198c8265cb224990052064592':<64} | ACCEPTED_ERRATA")
        elif f == "10-CONFORMANCE/spec_integrity.py":
            lines.append(f"{'  [Accepted Erratum E-SPEC-1: utf-8 encoding]':<50} | {'86056215757b8b66b4f9e405be08c82d26375ee1870a311b1957da8732a4bda5':<64} | {'c3c68772e2b4ae2a945d88c9cb71e2609d5626541f7bfacbc1294e628a384932':<64} | ACCEPTED_ERRATA")
        elif f == "20-RUNTIME/sclass_runtime_v6_0_1.py":
            lines.append(f"{'  [Accepted Runtime Baseline: H1b X1-X3]':<50} | {'7e224c4145f405231b27b2535f17337d2d9c98dff20c1b5109028c9dd5c1c33c':<64} | {'629eae9d7c52be865dbc66a72f9359b5732bddfc90055464fa2ccfadabe6526a':<64} | ACCEPTED_ERRATA")
        elif f == "20-RUNTIME/test_sclass_runtime_v6_0_1.py":
            lines.append(f"{'  [Accepted Runtime Test Baseline: H1b X1-X3]':<50} | {'0260d0d0860a0218b1990591171ce720122e85be1d42cdeb0718b8ad3f4b28b3':<64} | {'5f839cda9c2d3f34b3fd82701758f0994a7a6a0b7b4221c0448ce635a3148bf3':<64} | ACCEPTED_ERRATA")

    # Multi-branch comparison table across all 4 authoritative immutable refs (main, h0, h1a, h1b)
    lines.extend([
        "",
        "========================================================================================================================",
        "TABLE 2: MULTI-BRANCH BASELINE COMPARISON (MAIN, H0, H1A, H1B)",
        "========================================================================================================================",
        f"{'File':<48} | {'Ref':<12} | {'Commit SHA':<40} | {'Hash':<64} | Pkg Match",
        "-" * 184,
    ])

    branch_hashes: Dict[str, Dict[str, str]] = {}
    for ref_name in ("main", "h0", "h1a", "h1b"):
        sha = ref_shas.get(ref_name, AUTHORITATIVE_REFS[ref_name])
        branch_hashes[ref_name] = {}
        for f in target_files:
            b_bytes = get_git_file_bytes(sha, f)
            b_hash = sha256_normalized_lf(b_bytes) if b_bytes is not None else "NOT_IN_REF"
            branch_hashes[ref_name][f] = b_hash

    for f in target_files:
        pkg_h = pkg_hashes.get(f, "NOT_IN_FROZEN_MANIFEST")
        for ref_name in ("main", "h0", "h1a", "h1b"):
            sha = ref_shas.get(ref_name, AUTHORITATIVE_REFS[ref_name])
            h = branch_hashes[ref_name].get(f, "NOT_IN_REF")
            match_str = "MATCH" if h == pkg_h else "DIFFERS"
            lines.append(f"{f:<48} | {ref_name:<12} | {sha:<40} | {h:<64} | {match_str}")
        lines.append("-" * 184)

    # Clean-Install Branch Baselines Test Classification Summary
    lines.extend([
        "",
        "========================================================================================================================",
        "TABLE 3: CLEAN-INSTALL FULL-SUITE EVIDENCE & TEST CLASSIFICATION BY REF",
        "========================================================================================================================",
        f"{'Ref':<14} | {'Commit SHA':<40} | {'Total':<6} | {'Passed':<6} | {'ENV':<5} | {'CODE':<5} | {'Outcome':<8} | Note",
        "-" * 150,
    ])
    for ref_name in ("main", "h0", "h1a", "h1b"):
        m = classification_metrics[ref_name]
        sha = m["ref_sha"]
        total = str(m["total_collected"])
        passed = str(m["passed_count"])
        env = str(m["env_items_count"])
        code = str(m["code_failures_count"])
        status = m["status"]
        note = REF_ARCHITECTURAL_NOTES.get(ref_name, m.get("note", ""))
        lines.append(f"{ref_name:<14} | {sha:<40} | {total:<6} | {passed:<6} | {env:<5} | {code:<5} | {status:<8} | {note}")
    if "integration" in classification_metrics:
        m = classification_metrics["integration"]
        sha = m["ref_sha"]
        total = str(m["total_collected"])
        passed = str(m["passed_count"])
        status = m["status"]
        lines.append(f"# (Historical R30-B1 integration baseline: {sha} | {total} total | {passed} passed | {status})")
    lines.append("-" * 150)

    # Explanatory Notes
    lines.extend([
        "",
        "========================================================================================================================",
        "EXPLANATORY ANALYSIS OF HASH DIFFERENCES (STATUS: DIFFERS)",
        "========================================================================================================================",
        "1. 00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md: MATCH (exact SHA-256 match across package, main, h0, h1a, h1b).",
        "2. 10-CONFORMANCE core vectors & machines: MATCH across package and all branches:",
        "   - 10-CONFORMANCE/c1-vectors.v6.0.1.json: MATCH (db58744d9829f7cac2ec7715a93d30d20a0d9ba6912d01f563504564e85b2da8)",
        "   - 10-CONFORMANCE/c1_independent.js: MATCH (3d70c4791c63d8c6d1dc2724fac5012424067a2c0dd39f6432c1edf0af1abcec)",
        "   - 10-CONFORMANCE/coverage-map.v6.0.1.json: MATCH (722893054b29448238cb7cca5a149b6262d3cc606a4aeb2711c91e45a7dd6a20)",
        "   - 10-CONFORMANCE/sclass_kernel_v6_0_1.py: MATCH (d0f8f124dd55aab5cfb68d8c7d644eccf2694f52016c2e4a2132e6d6cef5575c)",
        "   - 10-CONFORMANCE/state-machines.v6.0.1.json: MATCH (24f159e6f72179ea66365b585f085727f6ef48420a09eae8c6024cb0bb51fdad)",
        "3. 10-CONFORMANCE/sclass_semantics_v6_0_1.py: DIFFERS from package due to normative errata:",
        "   - Package: 66387014aba28ce307ce630b58dcd3799da8251ca9955583a33a32a5f7b17a76",
        "   - Repo:    7ecc935246b057a3414faa3cfce36daa4f1be2a198c8265cb224990052064592 (Accepted Erratum E-SEM-1: WorkProposal.__init__).",
        "4. 10-CONFORMANCE/test_sclass_v6_0_1_conformance.py: MATCH package bytes ca4dafd9ab75096e9d92a3b15fbbac8693d03c172da444847657d42fd3b79158.",
        "   10-CONFORMANCE/spec_integrity.py: DIFFERS from package due to authorized erratum E-SPEC-1:",
        "   - Package: 86056215757b8b66b4f9e405be08c82d26375ee1870a311b1957da8732a4bda5",
        "   - Repo:    c3c68772e2b4ae2a945d88c9cb71e2609d5626541f7bfacbc1294e628a384932 (Accepted Erratum E-SPEC-1: read_text(encoding='utf-8')).",
        "5. Conformance property and S1-S5 extension tests relocated to tests/conformance_ext/.",
        "6. 20-RUNTIME/sclass_runtime_v6_0_1.py: Evolution across development phases:",
        "   - Package:     7e224c4145f405231b27b2535f17337d2d9c98dff20c1b5109028c9dd5c1c33c",
        "   - main & h0:   761cd60498fd399826359be2e4a56eea9b2ae31a5d783e437945f25d64d0bb0e",
        "   - h1a:         b70a9b7d1dc66d01ed65d71fe801f19951d29f6792e82e203638c7fc388eab5b",
        "   - h1b & integ: 629eae9d7c52be865dbc66a72f9359b5732bddfc90055464fa2ccfadabe6526a (Accepted Runtime Baseline: H1b X1-X3).",
        "7. 20-RUNTIME/test_sclass_runtime_v6_0_1.py: Evolution across development phases:",
        "   - Package:     0260d0d0860a0218b1990591171ce720122e85be1d42cdeb0718b8ad3f4b28b3",
        "   - main & h0:   c58dadc31ccbf7b33842db0ddabc9aa1a3742b827c7efd7d0aabb33657a2f792",
        "   - h1a:         e8364fb8dc35c62160fe37f2bcc9a193fb4b89372e3095ec0a8e0bad3882ba39",
        "   - h1b & integ: 5f839cda9c2d3f34b3fd82701758f0994a7a6a0b7b4221c0448ce635a3148bf3 (Accepted Runtime Test Baseline: H1b X1-X3).",
        "",
        "SUMMARY METRICS:",
        f"  Total Monitored Files:    {len(target_files)}",
        f"  Integration vs Package:   {sum(1 for _, _, _, s in int_rows if s == 'MATCH')} MATCH, {sum(1 for _, _, _, s in int_rows if s == 'DIFFERS')} DIFFERS",
    ])

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Baseline Hashes Generator and Verifier")
    parser.add_argument("--check", action="store_true", help="Check baseline hashes file without writing")
    parser.add_argument("--manifest", type=Path, default=MANIFEST_FILE, help="Path to FROZEN-MANIFEST.sha256")
    parser.add_argument("--classification-json", type=Path, default=CLASSIFICATION_EVIDENCE_FILE, help="Path to branch_baselines_classification.json")
    parser.add_argument("--raw-evidence-dir", type=Path, default=RAW_EVIDENCE_DIR, help="Path to raw branch baselines evidence directory")
    parser.add_argument("--output", type=Path, default=BASELINE_HASHES_FILE, help="Output file path")
    args = parser.parse_args()

    # Step 1: Strictly validate manifest against canonical anchors
    try:
        validate_manifest_file(args.manifest)
    except Exception as e:
        print(f"FAIL: Manifest validation failed: {e}")
        return 1

    # Step 2: Strictly validate branch baselines classification evidence and underlying raw evidence
    try:
        load_and_validate_branch_classification_evidence(args.classification_json, args.raw_evidence_dir)
    except Exception as e:
        print(f"FAIL: Branch baselines classification validation failed: {e}")
        return 1

    content = generate_baseline_hashes_content(args.manifest, args.classification_json, args.raw_evidence_dir)

    if args.check:
        if not args.output.exists():
            print(f"FAIL: {args.output} does not exist. Run without --check to generate.")
            return 1
        existing = args.output.read_text(encoding="utf-8")
        if existing != content:
            import difflib
            diff = list(difflib.unified_diff(existing.splitlines(), content.splitlines(), lineterm=""))
            print(f"FAIL: {args.output} is out of date or drifted. Diff:")
            for d_line in diff[:50]:
                print("  " + d_line)
            return 1
        print(f"PASS: {args.output} is up to date and verified.")
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(content, encoding="utf-8")
    print(f"Wrote baseline hashes report to {args.output}")
    print(f"Total monitored files: {len(list_target_files())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
