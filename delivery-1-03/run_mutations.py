#!/usr/bin/env python3
"""Authoritative 16-Mutant Battery Runner for R30 Section F3 Trust Model.

Verifies mutation resistance of src/sclass/product/trust_model.py:
- In-memory byte capture and exact byte restoration in a finally block without git checkout.
- Pre- and post-restoration SHA-256 hash verification for each mutant.
- Baseline and frozen-file integrity verification before and after the battery.
- All 16 mutants must be KILLED by tests/product/test_trust_model.py.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
import sys
import time


FROZEN_FILES = {
    "00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md": "53c02b13085dc3e1dcf75b9e8c306704d83bf37175b73a6be1a4b6ab7823ebb1",
    "10-CONFORMANCE/sclass_semantics_v6_0_1.py": "ed2faf251863e1411fe2f33f2848f87e8fa9d4904b7bb1e032a472874e839922",
    "10-CONFORMANCE/sclass_kernel_v6_0_1.py": "d0f8f124dd55aab5cfb68d8c7d644eccf2694f52016c2e4a2132e6d6cef5575c",
    "10-CONFORMANCE/c1-vectors.v6.0.1.json": "db58744d9829f7cac2ec7715a93d30d20a0d9ba6912d01f563504564e85b2da8",
    "10-CONFORMANCE/state-machines.v6.0.1.json": "24f159e6f72179ea66365b585f085727f6ef48420a09eae8c6024cb0bb51fdad",
}

MUTATIONS = [
    {
        "id": "M01",
        "name": "bypass_agent_check_records_rejection",
        "description": "Bypass PD-F3-002: accept agent-authored check records claiming PASS without evaluator records",
        "target": "if has_agent_check_records:",
        "replacement": "if False:",
    },
    {
        "id": "M02",
        "name": "bypass_evaluator_records_required_check",
        "description": "Bypass PD-F3-001: allow candidate to self-authenticate when evaluator check records are empty",
        "target": "if not valid_evaluator_records:",
        "replacement": "if False:",
    },
    {
        "id": "M03",
        "name": "allow_agent_to_author_evaluator_records",
        "description": "Bypass PD-F3-002: permit agent-authored records in evaluator_check_records",
        "target": 'if rec_producer == "evaluator" and rec_status == "PASS":',
        "replacement": 'if rec_status == "PASS":',
    },
    {
        "id": "M04",
        "name": "bypass_evaluator_object_digest_binding",
        "description": "Bypass PD-F3-002: ignore object digest mismatch in evaluator check records",
        "target": "if expected_object_digest is not None and rec_obj != expected_object_digest:",
        "replacement": "if False:",
    },
    {
        "id": "M05",
        "name": "bypass_evaluator_target_digest_binding",
        "description": "Bypass PD-F3-002: ignore target digest mismatch in evaluator check records",
        "target": "if expected_target_digest is not None and rec_tgt != expected_target_digest:",
        "replacement": "if False:",
    },
    {
        "id": "M06",
        "name": "mechanically_compare_prose_in_conflict_check",
        "description": "Violate PD-F3-003: use explanatory prose as mechanical comparison operand",
        "target": "if norm_a != norm_b:",
        "replacement": "if norm_a != norm_b or prose:",
    },
    {
        "id": "M07",
        "name": "bypass_structured_conflict_detection",
        "description": "Bypass PD-F3-003: report SATISFIED despite conflicting structured representations",
        "target": "if norm_a != norm_b:",
        "replacement": "if False:",
    },
    {
        "id": "M08",
        "name": "allow_approval_record_for_requirement_confirmation",
        "description": "Violate PD-F3-004: allow ApprovalRecord to confirm requirements instead of governance only",
        "target": "if isinstance(confirmation_event, ApprovalRecord) or (",
        "replacement": "if False and (",
    },
    {
        "id": "M09",
        "name": "bypass_requirement_confirmation_event_type_check",
        "description": "Bypass PD-F3-004: accept non-REQUIREMENT_CONFIRMED event types for requirement confirmation",
        "target": 'if event_type not in valid_event_types and getattr(event_type, "value", None) not in valid_event_types:',
        "replacement": "if False:",
    },
    {
        "id": "M10",
        "name": "bypass_requirement_confirmation_authority_check",
        "description": "Bypass PD-F3-004: allow AGENT or unauthorized authority to confirm requirements",
        "target": "if auth_str not in valid_authorities:",
        "replacement": "if False:",
    },
    {
        "id": "M11",
        "name": "bypass_requirement_confirmation_digest_check",
        "description": "Bypass PD-F3-004: accept confirmation when canonical structured digest has changed (D1 != D2)",
        "target": "if target_digest is not None and source_provenance != target_digest:",
        "replacement": "if False:",
    },
    {
        "id": "M12",
        "name": "bypass_content_digest_mismatch_check",
        "description": "Bypass PD-F3-005: accept claimed content digest differing from recomputed digest",
        "target": "if claimed_content_digest != recomputed_digest:",
        "replacement": "if False:",
    },
    {
        "id": "M13",
        "name": "bypass_inadmissible_confirmation_surface_check",
        "description": "Bypass PD-F3-006: accept human confirmation from agent_facing_tool or untrusted surface",
        "target": "if confirmation_surface in inadmissible_surfaces:",
        "replacement": "if False:",
    },
    {
        "id": "M14",
        "name": "bypass_principal_key_accessibility_check",
        "description": "Bypass PD-F3-006: accept approval when principal key is accessible to agent",
        "target": "if principal_key_accessible_to_agent:",
        "replacement": "if False:",
    },
    {
        "id": "M15",
        "name": "bypass_approval_forwarding_tool_check",
        "description": "Bypass PD-F3-006: accept approval when agent-callable forwarding tool is available",
        "target": "if approval_forwarding_tool_available:",
        "replacement": "if False:",
    },
    {
        "id": "M16",
        "name": "bypass_user_presence_required_check",
        "description": "Bypass PD-F3-006: accept approval when user presence is not required for signing key",
        "target": "if not user_presence_required:",
        "replacement": "if False:",
    },
]


def verify_frozen_hashes(repo_root: Path) -> tuple[bool, list[str]]:
    """Verifies that all frozen specification and conformance files match pinned SHA-256."""
    errors = []
    for rel_path, expected_hash in FROZEN_FILES.items():
        full_path = repo_root / rel_path
        if not full_path.is_file():
            errors.append(f"MISSING: {rel_path}")
            continue
        actual_hash = hashlib.sha256(full_path.read_bytes()).hexdigest()
        if actual_hash != expected_hash:
            errors.append(f"TAMPER: {rel_path} expected {expected_hash} got {actual_hash}")
    return len(errors) == 0, errors


def run_test(repo_root: Path, pytest_bin: str) -> tuple[int, str]:
    """Runs pytest on the test suite and captures output and exit code."""
    cmd = [pytest_bin, "tests/product/test_trust_model.py", "-q"]
    proc = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True)
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    pytest_bin = sys.executable.replace("python", "pytest").replace("python3", "pytest")
    target_file = repo_root / "src" / "sclass" / "product" / "trust_model.py"
    log_file = repo_root / "delivery-1-03" / "mutation_evidence.log"

    log_lines: list[str] = []

    def log(msg: str):
        print(msg)
        log_lines.append(msg)

    log("=" * 80)
    log("S-Class v6.0.2 Block 1-03: F3 Trust Model Mutation Battery (16 Mutants)")
    log(f"Timestamp: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}")
    log(f"Repository Root: {repo_root}")
    log(f"Target Module: {target_file}")
    log(f"Pytest Binary: {pytest_bin}")
    log("=" * 80)

    # 1. Runner self-hash and Git state
    runner_bytes = Path(__file__).read_bytes()
    runner_sha256 = hashlib.sha256(runner_bytes).hexdigest()
    log(f"Mutation Runner SHA-256: {runner_sha256}")

    git_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_root, capture_output=True, text=True).stdout.strip()
    log(f"Git HEAD Commit: {git_head}")

    # 2. Frozen integrity verification before run
    frozen_ok, frozen_errs = verify_frozen_hashes(repo_root)
    if not frozen_ok:
        log("PRE-FLIGHT FAILURE: Frozen file integrity violation:")
        for err in frozen_errs:
            log(f"  {err}")
        return 1
    log("Frozen file hashes verified: 5/5 MATCH.")

    # 3. Clean baseline test run
    base_rc, base_out = run_test(repo_root, pytest_bin)
    if base_rc != 0:
        log(f"BASELINE FAILURE: Unmutated code failed tests (rc={base_rc}):")
        log(base_out)
        return 1
    log(f"Baseline test run passed clean: {base_out.splitlines()[-1] if base_out else 'OK'}")

    # 4. Read original target file bytes
    original_bytes = target_file.read_bytes()
    original_sha256 = hashlib.sha256(original_bytes).hexdigest()
    original_text = original_bytes.decode("utf-8")
    log(f"Target file original SHA-256: {original_sha256} ({len(original_bytes)} bytes)")
    log("-" * 80)

    results: list[dict[str, str]] = []
    all_killed = True

    # 5. Execute 16-mutant battery
    for mutant in MUTATIONS:
        m_id = mutant["id"]
        m_name = mutant["name"]
        m_desc = mutant["description"]
        target = mutant["target"]
        replacement = mutant["replacement"]

        log(f"[{m_id}] Testing mutant: {m_name}")
        log(f"     Description: {m_desc}")

        if target not in original_text:
            log(f"     ERROR: Target string not found in {target_file.name}: {target}")
            all_killed = False
            results.append({"id": m_id, "name": m_name, "status": "ERROR_TARGET_NOT_FOUND"})
            continue

        occurrences = original_text.count(target)
        if occurrences > 1:
            log(f"     ERROR: Target string ambiguous (found {occurrences} times): {target}")
            all_killed = False
            results.append({"id": m_id, "name": m_name, "status": "ERROR_AMBIGUOUS_TARGET"})
            continue

        mutated_text = original_text.replace(target, replacement, 1)
        mutated_bytes = mutated_text.encode("utf-8")
        mutated_sha256 = hashlib.sha256(mutated_bytes).hexdigest()

        try:
            # Apply mutation in working tree
            target_file.write_bytes(mutated_bytes)
            assert target_file.read_bytes() == mutated_bytes, "Write verification failed"

            # Run test against mutant
            m_rc, m_out = run_test(repo_root, pytest_bin)

            if m_rc != 0:
                summary_line = m_out.splitlines()[-1] if m_out else "FAILED"
                log(f"     VERDICT: KILLED (pytest exit code {m_rc}: {summary_line})")
                results.append({"id": m_id, "name": m_name, "status": "KILLED", "exit_code": str(m_rc)})
            else:
                log(f"     VERDICT: SURVIVED (pytest exit code 0 - MUTANT SURVIVED!)")
                all_killed = False
                results.append({"id": m_id, "name": m_name, "status": "SURVIVED", "exit_code": "0"})

        finally:
            # Exact in-memory byte restoration without git checkout
            target_file.write_bytes(original_bytes)
            restored_sha256 = hashlib.sha256(target_file.read_bytes()).hexdigest()
            if restored_sha256 != original_sha256:
                log(f"     CRITICAL RESTORATION FAILURE: SHA mismatch! Expected {original_sha256}, got {restored_sha256}")
                raise RuntimeError(f"Restoration SHA mismatch: expected {original_sha256}, got {restored_sha256}")

        log(f"     Restoration verified: exact SHA-256 match {restored_sha256}")
        log("-" * 80)

    # 6. Post-battery frozen file verification
    post_frozen_ok, post_frozen_errs = verify_frozen_hashes(repo_root)
    if not post_frozen_ok:
        log("POST-RUN FAILURE: Frozen file integrity violation after mutations:")
        for err in post_frozen_errs:
            log(f"  {err}")
        return 1
    log("Post-battery frozen file integrity: 5/5 MATCH.")

    # 7. Post-battery baseline test run
    post_rc, post_out = run_test(repo_root, pytest_bin)
    if post_rc != 0:
        log(f"POST-RUN FAILURE: Post-restoration test run failed (rc={post_rc}): {post_out}")
        return 1
    log(f"Post-restoration baseline test run passed clean: {post_out.splitlines()[-1] if post_out else 'OK'}")

    # 8. Final tally & verdict
    killed_count = sum(1 for r in results if r.get("status") == "KILLED")
    total_count = len(MUTATIONS)

    log("=" * 80)
    log(f"MUTATION BATTERY SUMMARY: {killed_count}/{total_count} mutants KILLED")
    for r in results:
        log(f"  [{r['id']}] {r['name']:<50} {r['status']}")
    log("=" * 80)

    verdict = "VERIFIED" if (all_killed and killed_count == total_count) else "MUTATION_TEST_FAILED"
    log(f"FINAL DISPOSITION: {verdict}")

    log_file.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    log(f"Wrote full mutation evidence log to: {log_file}")

    return 0 if verdict == "VERIFIED" else 1


if __name__ == "__main__":
    sys.exit(main())
