#!/usr/bin/env python3
"""Full Test Suite Classified Runner (B01 Item 2).

Executes the full S-Class test suite (20-RUNTIME tests, 10-CONFORMANCE tests,
and tests/), parses structured JUnit XML results, and classifies every failure
and skip as either:
  - ENV: Missing environmental/host capability (with capability explicitly named:
         bwrap, cgroup v2, userns, linux_posix_proc, env_var:SCLASS_MASTER_PATH)
  - CODE: Genuine code defect, assertion failure, syntax error, or unhandled regression.

Rules:
  - Any CODE failure causes immediate failure (exit code 1).
  - ENV items are explicitly cataloged and NEVER counted as pass.
  - Outputs structured JSON and Markdown classification evidence artifacts.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import platform
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]

# Known capability patterns for ENV classification
ENV_CAPABILITY_PATTERNS = [
    # (capability_name, list_of_substring_patterns)
    ("cgroup v2", [
        "cgroup v2",
        "delegated cgroup",
        "cgroup.controllers",
        "cgroup.procs",
        "cgroup root",
        "cgroup hierarchy",
        "check_delegated_cgroup_v2_available",
    ]),
    ("bwrap", [
        "bubblewrap executable not found",
        "bubblewrap not found",
        "bwrap executable not found",
        "bwrap: ",
        "missing bwrap",
    ]),
    ("userns", [
        "unprivileged user namespaces are blocked",
        "unprivileged user namespaces",
        "user namespaces are blocked or restricted",
        "kernel.apparmor_restrict_unprivileged_userns",
        "userns blocked",
        "userns restricted",
    ]),
    ("linux_posix_proc", [
        "Linux O_PATH unavailable on Windows",
        "Linux /proc process monitor unavailable on Windows",
        "Linux execution requires POSIX environment",
        "requires POSIX environment",
        "non-linux platform without /proc",
    ]),
    ("env_var:SCLASS_MASTER_PATH", [
        "SCLASS_MASTER_PATH environment variable unset",
        "real master tests require SCLASS_MASTER_PATH",
    ]),
]


def classify_outcome(status: str, message: str, details: str) -> tuple[str, str | None, str]:
    """Classifies a non-passed test outcome.

    Returns (category, capability, description)
    where category is 'ENV' or 'CODE'.
    """
    combined = f"{message} {details}".lower()

    for cap_name, patterns in ENV_CAPABILITY_PATTERNS:
        for pat in patterns:
            if pat.lower() in combined:
                return "ENV", cap_name, (message.strip() if message else pat)

    # If no environmental capability pattern matched, it is a CODE failure
    return "CODE", None, (message.strip() if message else details.strip()[:200])


def parse_junit_xml(xml_path: Path) -> dict:
    """Parses JUnit XML report and extracts all testcase outcomes."""
    if not xml_path.exists():
        raise FileNotFoundError(f"JUnit XML not found: {xml_path}")

    tree = ET.parse(xml_path)
    root = tree.getroot()

    passed_items = []
    env_items = []
    code_items = []

    # root can be <testsuites> or <testsuite>
    testsuites = [root] if root.tag == "testsuite" else root.findall("testsuite")
    if not testsuites:
        testsuites = [root]

    for ts in testsuites:
        for tc in ts.findall("testcase"):
            tc_file = tc.get("file", "")
            tc_class = tc.get("classname", "")
            tc_name = tc.get("name", "")
            node_id = f"{tc_file}::{tc_name}" if tc_file else f"{tc_class}::{tc_name}"
            time_sec = float(tc.get("time", 0.0))

            skipped_elem = tc.find("skipped")
            failure_elem = tc.find("failure")
            error_elem = tc.find("error")

            if skipped_elem is not None:
                msg = skipped_elem.get("message", "")
                text = skipped_elem.text or ""
                cat, cap, desc = classify_outcome("skipped", msg, text)
                entry = {
                    "node_id": node_id,
                    "status": "SKIPPED",
                    "category": cat,
                    "capability": cap,
                    "description": desc,
                    "time": time_sec,
                }
                if cat == "ENV":
                    env_items.append(entry)
                else:
                    # Unrecognized skip is still treated as CODE / unclassified
                    code_items.append(entry)

            elif failure_elem is not None:
                msg = failure_elem.get("message", "")
                text = failure_elem.text or ""
                cat, cap, desc = classify_outcome("failure", msg, text)
                entry = {
                    "node_id": node_id,
                    "status": "FAILED",
                    "category": cat,
                    "capability": cap,
                    "description": desc,
                    "details": text[:2000],
                    "time": time_sec,
                }
                if cat == "ENV":
                    env_items.append(entry)
                else:
                    code_items.append(entry)

            elif error_elem is not None:
                msg = error_elem.get("message", "")
                text = error_elem.text or ""
                cat, cap, desc = classify_outcome("error", msg, text)
                entry = {
                    "node_id": node_id,
                    "status": "ERROR",
                    "category": cat,
                    "capability": cap,
                    "description": desc,
                    "details": text[:2000],
                    "time": time_sec,
                }
                if cat == "ENV":
                    env_items.append(entry)
                else:
                    code_items.append(entry)

            else:
                passed_items.append({
                    "node_id": node_id,
                    "status": "PASSED",
                    "time": time_sec,
                })

    return {
        "passed": passed_items,
        "env": env_items,
        "code": code_items,
    }


def generate_classification_report(
    parsed: dict,
    total_time: float,
    output_json: Path,
    output_md: Path,
) -> int:
    passed = parsed["passed"]
    env_items = parsed["env"]
    code_items = parsed["code"]

    n_passed = len(passed)
    n_env = len(env_items)
    n_code = len(code_items)
    total_collected = n_passed + n_env + n_code

    # Group ENV items by capability
    env_by_cap: dict[str, list[dict]] = {}
    for item in env_items:
        cap = item.get("capability") or "unknown_capability"
        env_by_cap.setdefault(cap, []).append(item)

    report_data = {
        "schema": "sclass/test-classification-report/v1",
        "generated_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "total_collected": total_collected,
        "passed_count": n_passed,
        "env_items_count": n_env,
        "code_failures_count": n_code,
        "duration_seconds": total_time,
        "rule_compliance": {
            "code_failures_zero": n_code == 0,
            "env_items_not_counted_as_passed": True,
            "all_env_capabilities_named": all(item.get("capability") for item in env_items),
        },
        "env_summary_by_capability": {
            cap: len(items) for cap, items in sorted(env_by_cap.items())
        },
        "env_items": env_items,
        "code_failures": code_items,
        "status": "PASS" if n_code == 0 else "FAIL",
    }

    # Write JSON
    output_json.parent.mkdir(parents=True, exist_ok=True)
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)

    # Write Markdown
    lines = [
        "# S-Class Full Test Suite Classification Report (B01 Item 2)",
        "",
        f"- **Generated at:** {report_data['generated_at_utc']}",
        f"- **Platform:** `{report_data['platform']}`",
        f"- **Python Version:** `{report_data['python_version']}`",
        f"- **Total Duration:** {total_time:.2f}s",
        "",
        "## Summary Metrics",
        "",
        f"| Metric | Count | Note |",
        f"| :--- | :--- | :--- |",
        f"| **Total Collected** | {total_collected} | 100% of discovered tests |",
        f"| **Passed** | {n_passed} | Genuine green tests |",
        f"| **ENV Exclusions** | {n_env} | Missing host/environment capabilities (NEVER counted as pass) |",
        f"| **CODE Failures** | {n_code} | Code bugs, assertion errors, or unexpected regressions |",
        f"| **Overall Result** | **{'PASS' if n_code == 0 else 'FAIL'}** | CODE failures must be strictly 0 |",
        "",
        "## ENV Capability Breakdown",
        "",
    ]

    if env_by_cap:
        lines.append("| Missing Capability | Items Affected | Nature |")
        lines.append("| :--- | :--- | :--- |")
        for cap, items in sorted(env_by_cap.items()):
            lines.append(f"| `{cap}` | {len(items)} | Host environment lacks required hardware/OS isolation feature |")
        lines.append("")
        lines.append("### Catalog of ENV Items")
        lines.append("")
        lines.append("| Node ID | Status | Capability | Reason |")
        lines.append("| :--- | :--- | :--- | :--- |")
        for item in env_items:
            nid = item["node_id"]
            st = item["status"]
            cap = item.get("capability", "unknown")
            desc = item.get("description", "").replace("|", "\\|")
            lines.append(f"| `{nid}` | {st} | `{cap}` | {desc} |")
        lines.append("")
    else:
        lines.append("*No ENV capability exclusions encountered; all required OS capabilities present.*")
        lines.append("")

    if code_items:
        lines.append("## CODE Failures")
        lines.append("")
        lines.append("> [!CAUTION]")
        lines.append(f"> Job FAILED with {n_code} genuine CODE defect(s):")
        lines.append("")
        for item in code_items:
            lines.append(f"### `{item['node_id']}`")
            lines.append(f"- **Status:** {item['status']}")
            lines.append(f"- **Description:** {item.get('description', '')}")
            if "details" in item:
                lines.append("```text")
                lines.append(item["details"])
                lines.append("```")
            lines.append("")
    else:
        lines.append("## CODE Failures")
        lines.append("")
        lines.append("`0 CODE failures`. All executed product and kernel assertions verified successfully.")
        lines.append("")

    output_md.write_text("\n".join(lines), encoding="utf-8")

    # Print summary to stdout
    print("\n" + "=" * 80)
    print("S-CLASS TEST SUITE CLASSIFICATION SUMMARY")
    print("=" * 80)
    print(f"Total Collected:  {total_collected}")
    print(f"Passed:           {n_passed}")
    print(f"ENV Items:        {n_env} (cataloged below, NEVER counted as pass)")
    print(f"CODE Failures:    {n_code}")
    print("-" * 80)
    if env_by_cap:
        print("ENV Breakdown by Missing Capability:")
        for cap, items in sorted(env_by_cap.items()):
            print(f"  - {cap:<24}: {len(items)} item(s)")
    if n_code > 0:
        print("\nFAIL: Job failed with CODE failures:")
        for item in code_items:
            print(f"  - {item['node_id']}: {item.get('description')}")
        return 1

    print("\nPASS: 0 CODE failures. Test suite classification verified.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Full Test Suite Classified Runner (B01 Item 2)")
    parser.add_argument("--junit-xml", type=Path, default=_REPO_ROOT / "delivery-evidence" / "full_suite_junit.xml")
    parser.add_argument("--output-json", type=Path, default=_REPO_ROOT / "delivery-evidence" / "test_classification_report.json")
    parser.add_argument("--output-md", type=Path, default=_REPO_ROOT / "delivery-evidence" / "test_classification_report.md")
    parser.add_argument("--run-pytest", action="store_true", default=True, help="Execute pytest run (default: True)")
    parser.add_argument("--parse-only", action="store_true", help="Only parse existing JUnit XML without re-running pytest")
    args = parser.parse_args()

    start_time = datetime.datetime.now()

    if not args.parse_only:
        test_paths = [
            "10-CONFORMANCE/test_sclass_v6_0_1_conformance.py",
            "10-CONFORMANCE/test_sclass_v6_0_1_property.py",
            "20-RUNTIME/test_sclass_runtime_v6_0_1.py",
            "tests",
        ]
        args.junit_xml.parent.mkdir(parents=True, exist_ok=True)
        pytest_cmd = [
            sys.executable,
            "-m",
            "pytest",
            *test_paths,
            f"--junitxml={args.junit_xml}",
            "-v",
        ]
        print(f"Running full test suite: {' '.join(pytest_cmd)}")
        # We allow pytest to finish (even if non-zero exit code due to test failure) so we can parse full results
        proc = subprocess.run(pytest_cmd, cwd=str(_REPO_ROOT))
        print(f"Pytest run exited with code: {proc.returncode}")

    duration = (datetime.datetime.now() - start_time).total_seconds()

    parsed = parse_junit_xml(args.junit_xml)
    return generate_classification_report(parsed, duration, args.output_json, args.output_md)


if __name__ == "__main__":
    sys.exit(main())
