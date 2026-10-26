#!/usr/bin/env python3
"""Execute mutation audit provenance closure and produce single reproducible evidence log."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RUNNER_REL = "delivery-1-00/run_mutations.py"
RUNNER_PATH = REPO / RUNNER_REL
OUT_LOG = REPO / "delivery-1-base-b" / "cl_independent_audit" / "mutation_audit_provenance.log"
PYTHON = sys.executable

FROZEN_FILES = {
    "00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md": "53c02b13085dc3e1dcf75b9e8c306704d83bf37175b73a6be1a4b6ab7823ebb1",
    "10-CONFORMANCE/sclass_semantics_v6_0_1.py": "ed2faf251863e1411fe2f33f2848f87e8fa9d4904b7bb1e032a472874e839922",
    "10-CONFORMANCE/sclass_kernel_v6_0_1.py": "d0f8f124dd55aab5cfb68d8c7d644eccf2694f52016c2e4a2132e6d6cef5575c",
    "10-CONFORMANCE/c1-vectors.v6.0.1.json": "db58744d9829f7cac2ec7715a93d30d20a0d9ba6912d01f563504564e85b2da8",
    "10-CONFORMANCE/state-machines.v6.0.1.json": "24f159e6f72179ea66365b585f085727f6ef48420a09eae8c6024cb0bb51fdad",
}


def git_cmd(args: list[str]) -> str:
    res = subprocess.run(["git"] + args, cwd=str(REPO), capture_output=True, text=True)
    return res.stdout.strip()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_lf(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    lines: list[str] = []

    def log(msg: str = ""):
        print(msg)
        lines.append(msg)

    timestamp_start = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    pre_head = git_cmd(["rev-parse", "HEAD"])
    pre_status = git_cmd(["status", "--short"])
    pre_runner_sha = sha256_file(RUNNER_PATH)

    log("=" * 80)
    log("MUTATION AUDIT PROVENANCE EVIDENCE RECORD")
    log("=" * 80)
    log(f"START_TIMESTAMP:        {timestamp_start}")
    log(f"WORKING_DIRECTORY:      {REPO}")
    log(f"PYTHON_INTERPRETER:     {PYTHON}")
    log(f"TARGET_COMMIT_SHA:      {pre_head}")
    log(f"RUNNER_SCRIPT:          {RUNNER_REL}")
    log(f"PRE_RUNNER_SHA256:      {pre_runner_sha}")
    log(f"PRE_GIT_STATUS_SHORT:   {'(clean)' if not pre_status else pre_status}")
    log(f"PRE_GIT_REV_PARSE_HEAD: {pre_head}")
    log("=" * 80)

    # 1. Execute mutation runner
    log("\n--- [EXECUTION] Running delivery-1-00/run_mutations.py ---")
    t0 = time.time()
    env = os.environ.copy()
    env["NO_OVERWRITE_MUTATION_LOG"] = "1"
    proc = subprocess.run([PYTHON, str(RUNNER_PATH)], cwd=str(REPO), capture_output=True, text=True, env=env)
    elapsed = time.time() - t0
    runner_rc = proc.returncode

    log(f"EXIT_CODE: {runner_rc}")
    log(f"ELAPSED:   {elapsed:.2f}s\n")
    log("--- [RAW RUNNER OUTPUT] ---")
    log(proc.stdout.strip())
    if proc.stderr:
        log("\n--- [RAW RUNNER STDERR] ---")
        log(proc.stderr.strip())
    log("--- [END RAW RUNNER OUTPUT] ---\n")

    # 2. Frozen file verification
    log("=" * 80)
    log("FROZEN FILES POST-EXECUTION SHA-256 CHECK")
    log("=" * 80)
    mismatches = 0
    for rel_path, expected in FROZEN_FILES.items():
        actual = sha256_lf(REPO / rel_path)
        if actual == expected:
            log(f"OK     {actual}  {rel_path}")
        else:
            log(f"FAILED {actual} != {expected}  {rel_path}")
            mismatches += 1
    frozen_status = "PASS (0 mismatches)" if mismatches == 0 else f"FAIL ({mismatches} mismatches)"
    log(f"FROZEN_FILES_RESULT: {frozen_status}\n")

    # 3. Post-execution Git state and runner integrity verification
    post_head = git_cmd(["rev-parse", "HEAD"])
    post_status = git_cmd(["status", "--short"])
    post_runner_sha = sha256_file(RUNNER_PATH)
    timestamp_end = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    log("=" * 80)
    log("POST-EXECUTION PROVENANCE & INTEGRITY VERIFICATION")
    log("=" * 80)
    log(f"END_TIMESTAMP:           {timestamp_end}")
    log(f"POST_GIT_REV_PARSE_HEAD: {post_head}")
    head_unchanged = post_head == pre_head
    log(f"HEAD_UNCHANGED:          {head_unchanged} ({post_head})")

    # Filter out our own log if needed
    status_lines = [l for l in post_status.splitlines() if not l.endswith("mutation_audit_provenance.log")]
    is_clean = len(status_lines) == 0
    log(f"POST_GIT_STATUS_SHORT:   {'(clean)' if is_clean else post_status}")
    log(f"CHECKOUT_REMAINS_CLEAN:  {is_clean}")

    runner_unchanged = post_runner_sha == pre_runner_sha
    log(f"POST_RUNNER_SHA256:      {post_runner_sha}")
    log(f"RUNNER_SHA_UNCHANGED:    {runner_unchanged}")

    passed = (
        runner_rc == 0
        and mismatches == 0
        and head_unchanged
        and is_clean
        and runner_unchanged
    )
    verdict = "VERIFIED" if passed else "RERUN FAILED"
    log(f"\nPROVENANCE_AUDIT_VERDICT: {verdict}")
    log("=" * 80)

    # Write log
    OUT_LOG.parent.mkdir(parents=True, exist_ok=True)
    OUT_LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nWrote provenance evidence log to: {OUT_LOG}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
