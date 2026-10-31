#!/usr/bin/env python3
"""Authoritative 31-Mutant Battery Runner for R30 Section F3 Trust Model.

Verifies mutation resistance of src/sclass/product/trust_model.py across all
remediation areas mandated by Directive 1-03b and Directive 1-03c:
- PD-F3-002: Evaluator caller-controlled identity, expected object/target digest presence, exact digest matching.
- PD-F3-006: Admissible surface allowlist, custody facts explicit boolean typing, custody fact enforcement.
- PD-F3-004: Canonical C1 comparison digest recomputation, rejection of self-attested event digest, canonical structured form strictly required, rejection of digest-only input.
- PD-F3-005: Rejection of empty/non-string digests, recomputation exclusively from artifact, rejection of caller-supplied digest strings, explicit key presence eliminating fallback chains.
- Dispatch: Multi-check evaluation, worst-result precedence (BLOCKED_ON_HUMAN > MISSING > SATISFIED), empty/unrecognized spec fail closed.
- PD-F3-003: Prose exclusion from mechanical comparison, structured conflict detection.
- Directive 1-03c Adversarial Protections: M26 (auto-derivation prevention), M27 (digest-only bypass prevention), M28 (fallback chain prevention).
- Evaluator Record & Provenance Validation: M29 (status missing check), M30 (agent masquerading check), M31 (evaluator provenance authentication check).

Integrity features:
- In-memory byte capture and exact byte restoration in a finally block without git checkout.
- Pre- and post-restoration SHA-256 hash verification for each mutant.
- Baseline and frozen-file integrity verification before and after the battery.
- Git checkout cleanliness check and binding to exact delivery commit.
- Pre- and post-mutant Git HEAD and working-tree status capture for every mutant.
- All 31 mutants must be KILLED by tests/product/test_trust_model.py.
"""

from __future__ import annotations

import argparse
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
        "name": "bypass_caller_controlled_evaluator_identity",
        "description": "Bypass PD-F3-002: permit evaluator records without caller-controlled evaluator_identity='evaluator'",
        "target": 'if evaluator_identity != "evaluator":',
        "replacement": "if False:",
    },
    {
        "id": "M04",
        "name": "bypass_evaluator_expected_object_digest_presence",
        "description": "Bypass PD-F3-002: permit evaluator check records when expected_object_digest is missing",
        "target": "if not expected_object_digest or not isinstance(expected_object_digest, str) or not expected_object_digest.strip():",
        "replacement": "if False:",
    },
    {
        "id": "M05",
        "name": "bypass_evaluator_expected_target_digest_presence",
        "description": "Bypass PD-F3-002: permit evaluator check records when expected_target_digest is missing",
        "target": "if not expected_target_digest or not isinstance(expected_target_digest, str) or not expected_target_digest.strip():",
        "replacement": "if False:",
    },
    {
        "id": "M06",
        "name": "mechanically_compare_prose_in_conflict_check",
        "description": "Violate PD-F3-003: use explanatory prose as mechanical comparison operand",
        "target": "norm_b = freeze_to_c1_compatible(structured_b)",
        "replacement": "norm_b = freeze_to_c1_compatible(structured_b if not prose else prose)",
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
        "name": "bypass_requirement_confirmation_digest_equality_check",
        "description": "Bypass PD-F3-004: accept confirmation when canonical structured digest has changed (D1 != D2)",
        "target": "if source_provenance != computed_digest:",
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
        "name": "bypass_inadmissible_confirmation_surface_allowlist",
        "description": "Bypass PD-F3-006: accept human confirmation from non-allowlisted rendering surface",
        "target": "if not isinstance(confirmation_surface, str) or confirmation_surface not in ADMISSIBLE_SURFACES:",
        "replacement": "if False:",
    },
    {
        "id": "M14",
        "name": "bypass_principal_key_accessibility_check",
        "description": "Bypass PD-F3-006: accept approval when principal key is accessible to agent",
        "target": "if principal_key_accessible_to_agent is not False:",
        "replacement": "if False:",
    },
    {
        "id": "M15",
        "name": "bypass_approval_forwarding_tool_check",
        "description": "Bypass PD-F3-006: accept approval when agent-callable forwarding tool is available",
        "target": "if approval_forwarding_tool_available is not False:",
        "replacement": "if False:",
    },
    {
        "id": "M16",
        "name": "bypass_user_presence_required_check",
        "description": "Bypass PD-F3-006: accept approval when user presence is not required for signing key",
        "target": "if user_presence_required is not True:",
        "replacement": "if False:",
    },
    {
        "id": "M17",
        "name": "bypass_custody_facts_explicit_boolean_type_check",
        "description": "Bypass PD-F3-006: accept non-boolean or missing custody facts without strict type bool validation",
        "target": "if type(principal_key_accessible_to_agent) is not bool:",
        "replacement": "if False:",
    },
    {
        "id": "M18",
        "name": "bypass_rejection_of_caller_supplied_digest_string",
        "description": "Bypass PD-F3-005: accept caller-supplied digest string instead of requiring artifact for recomputation",
        "target": "if artifact is None or isinstance(artifact, str) or not isinstance(artifact, (Mapping, object)):",
        "replacement": "if False:",
    },
    {
        "id": "M19",
        "name": "bypass_empty_non_string_claimed_digest_check",
        "description": "Bypass PD-F3-005: accept empty, whitespace, or non-string claimed digest",
        "target": "if not claimed_content_digest or not isinstance(claimed_content_digest, str) or not claimed_content_digest.strip():",
        "replacement": "if False:",
    },
    {
        "id": "M20",
        "name": "bypass_missing_comparison_digest_fail_closed",
        "description": "Bypass PD-F3-004: allow missing canonical structured form / digest to pass instead of failing closed",
        "target": 'GateState.BLOCKED_ON_HUMAN,\n            must_id="PD-F3-004",\n            detail="Canonical structured form is required; digest-only input fails closed',
        "replacement": 'GateState.SATISFIED,\n            must_id=None,\n            detail="Canonical structured form is required; digest-only input fails closed',
    },
    {
        "id": "M21",
        "name": "bypass_dispatch_worst_result_precedence_blocked",
        "description": "Bypass Dispatch: fail to prioritize BLOCKED_ON_HUMAN over SATISFIED or MISSING in multi-check spec",
        "target": "if blocked_outputs:\n        primary = blocked_outputs[0]",
        "replacement": "if False:\n        primary = blocked_outputs[0]",
    },
    {
        "id": "M22",
        "name": "bypass_dispatch_empty_spec_fail_closed",
        "description": "Bypass Dispatch: allow empty specification to pass instead of failing closed to GateState.MISSING",
        "target": "if not spec or not isinstance(spec, Mapping):",
        "replacement": "if False:",
    },
    {
        "id": "M23",
        "name": "bypass_evaluator_exact_digest_matching",
        "description": "Bypass PD-F3-002: accept evaluator check records whose object or target digests do not match expected",
        "target": "if rec_obj != expected_object_digest or rec_tgt != expected_target_digest:",
        "replacement": "if False:",
    },
    {
        "id": "M24",
        "name": "bypass_missing_empty_source_provenance_check",
        "description": "Bypass PD-F3-004: allow missing or empty source_provenance in requirement confirmation",
        "target": "if not source_provenance or not isinstance(source_provenance, str) or not source_provenance.strip():",
        "replacement": "if False:",
    },
    {
        "id": "M25",
        "name": "bypass_dispatch_worst_result_precedence_missing",
        "description": "Bypass Dispatch: fail to prioritize MISSING over SATISFIED in multi-check spec",
        "target": "if missing_outputs:\n        primary = missing_outputs[0]",
        "replacement": "if False:\n        primary = missing_outputs[0]",
    },
    {
        "id": "M26",
        "name": "auto_derive_evaluator_identity_from_spec",
        "description": "Bypass PD-F3-002: auto-derive evaluator_identity or digests from untrusted spec payload (Directive 1-03c adversarial test 1)",
        "target": "outputs.append(evaluate_claim(\n            candidate=candidate,\n            evaluator_check_records=eval_records,\n            expected_object_digest=expected_object_digest,\n            expected_target_digest=expected_target_digest,\n            evaluator_identity=evaluator_identity,\n            evaluator_provenance=evaluator_provenance,\n        ))",
        "replacement": "outputs.append(evaluate_claim(\n            candidate=candidate,\n            evaluator_check_records=eval_records,\n            expected_object_digest=expected_object_digest or spec.get('expected_object_digest'),\n            expected_target_digest=expected_target_digest or spec.get('expected_target_digest'),\n            evaluator_identity=evaluator_identity or spec.get('evaluator_identity') or ('evaluator' if spec.get('fixture_role') == 'happy' else None),\n            evaluator_provenance=evaluator_provenance,\n        ))",
    },
    {
        "id": "M27",
        "name": "accept_digest_only_confirmation_without_structured_form",
        "description": "Bypass PD-F3-004: accept caller-supplied canonical_structured_form_digest without requiring canonical_structured_form (Directive 1-03c adversarial test 2)",
        "target": 'if canonical_structured_form is None:\n        return GateOutput(\n            GateState.BLOCKED_ON_HUMAN,\n            must_id="PD-F3-004",\n            detail="Canonical structured form is required; digest-only input fails closed",\n            failures=["BLOCKED_ON_HUMAN[PD-F3-004]"],\n            explain={"reason": "canonical_structured_form_required_digest_only_rejected"},\n        )',
        "replacement": 'if canonical_structured_form is None:\n        if canonical_structured_form_digest and source_provenance == canonical_structured_form_digest:\n            return GateOutput(GateState.SATISFIED, explain={"source_provenance": source_provenance})\n        return GateOutput(GateState.BLOCKED_ON_HUMAN, must_id="PD-F3-004", failures=["BLOCKED_ON_HUMAN[PD-F3-004]"])',
    },
    {
        "id": "M28",
        "name": "fallback_chain_bypass_empty_claimed_content_digest",
        "description": "Bypass PD-F3-005: replace explicit key-presence with fallback chain (Directive 1-03c adversarial test 3)",
        "target": '        if has_ccd and has_cd:\n            v_ccd = spec.get("claimed_content_digest")\n            v_cd = spec.get("claimed_digest")\n            if not isinstance(v_ccd, str) or not v_ccd.strip():\n                outputs.append(GateOutput(\n                    GateState.MISSING,\n                    must_id="PD-F3-005",\n                    detail="Empty claimed_content_digest supplied",\n                    failures=["MISSING[PD-F3-005]"],\n                    explain={"reason": "empty_claimed_content_digest"},\n                ))\n            elif not isinstance(v_cd, str) or not v_cd.strip():\n                outputs.append(GateOutput(\n                    GateState.MISSING,\n                    must_id="PD-F3-005",\n                    detail="Empty claimed_digest supplied",\n                    failures=["MISSING[PD-F3-005]"],\n                    explain={"reason": "empty_claimed_digest"},\n                ))\n            elif v_ccd != v_cd:\n                outputs.append(GateOutput(\n                    GateState.MISSING,\n                    must_id="PD-F3-005",\n                    detail=f"Conflicting claimed digest keys supplied: claimed_content_digest={v_ccd!r} != claimed_digest={v_cd!r}",\n                    failures=["MISSING[PD-F3-005]"],\n                    explain={"reason": "conflicting_claimed_digest_keys", "claimed_content_digest": v_ccd, "claimed_digest": v_cd},\n                ))\n            else:\n                outputs.append(verify_content_digest(v_ccd, artifact))\n        elif has_ccd:\n            v_ccd = spec.get("claimed_content_digest")\n            if not isinstance(v_ccd, str) or not v_ccd.strip():\n                outputs.append(GateOutput(\n                    GateState.MISSING,\n                    must_id="PD-F3-005",\n                    detail="Empty claimed_content_digest supplied",\n                    failures=["MISSING[PD-F3-005]"],\n                    explain={"reason": "empty_claimed_content_digest"},\n                ))\n            else:\n                outputs.append(verify_content_digest(v_ccd, artifact))\n        else:  # has_cd\n            v_cd = spec.get("claimed_digest")\n            if not isinstance(v_cd, str) or not v_cd.strip():\n                outputs.append(GateOutput(\n                    GateState.MISSING,\n                    must_id="PD-F3-005",\n                    detail="Empty claimed_digest supplied",\n                    failures=["MISSING[PD-F3-005]"],\n                    explain={"reason": "empty_claimed_digest"},\n                ))\n            else:\n                outputs.append(verify_content_digest(v_cd, artifact))',
        "replacement": '        claimed = spec.get("claimed_content_digest") or spec.get("claimed_digest")\n        outputs.append(verify_content_digest(claimed, artifact))',
    },
    {
        "id": "M29",
        "name": "bypass_evaluator_record_missing_status_check",
        "description": "Bypass PD-F3-001: allow evaluator check record with missing status to implicitly default/pass",
        "target": "if rec_status is None:",
        "replacement": "if False:",
    },
    {
        "id": "M30",
        "name": "bypass_agent_record_masquerading_check",
        "description": "Bypass PD-F3-002: permit agent-produced check records to masquerade as evaluator records",
        "target": 'if rec_producer != "evaluator" or rec_producer == "agent":',
        "replacement": "if False:",
    },
    {
        "id": "M31",
        "name": "bypass_evaluator_provenance_authentication_check",
        "description": "Bypass PD-F3-002: accept caller identity without authenticated evaluator provenance",
        "target": "if not is_authenticated_provenance:",
        "replacement": "if False:",
    },
]


def check_clean_checkout(status_output: str) -> bool:
    """Returns True if git status output represents a clean working tree."""
    clean_lines = [
        line.strip()
        for line in status_output.splitlines()
        if line.strip() and line.strip() != "(clean)"
    ]
    return len(clean_lines) == 0


def check_head_commit_match(actual_head: str, expected_commit: str | None) -> bool:
    """Returns True if actual git HEAD matches expected commit (if specified)."""
    if not expected_commit:
        return True
    return actual_head.strip().lower().startswith(expected_commit.strip().lower())


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
    parser = argparse.ArgumentParser(description="Authoritative 31-Mutant Battery Runner for R30 Section F3 Trust Model")
    parser.add_argument("--commit", dest="expected_commit", type=str, default=None, help="Expected delivery commit SHA")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    pytest_bin = sys.executable.replace("python", "pytest").replace("python3", "pytest")
    target_file = repo_root / "src" / "sclass" / "product" / "trust_model.py"
    log_file = repo_root / "delivery-1-03" / "mutation_evidence.log"

    log_lines: list[str] = []

    def log(msg: str):
        print(msg)
        log_lines.append(msg)

    log("=" * 80)
    log("S-Class v6.0.2 Block 1-03c: F3 Trust Model Mutation Battery (31 Mutants)")
    log(f"Timestamp: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}")
    log(f"Repository Root: {repo_root}")
    log(f"Target Module: {target_file}")
    log(f"Pytest Binary: {pytest_bin}")
    if args.expected_commit:
        log(f"Expected Commit SHA: {args.expected_commit}")
    log("=" * 80)

    # 1. Runner self-hash and Git state
    runner_bytes = Path(__file__).read_bytes()
    runner_sha256 = hashlib.sha256(runner_bytes).hexdigest()
    log(f"Mutation Runner SHA-256: {runner_sha256}")

    git_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_root, capture_output=True, text=True).stdout.strip()
    log(f"Git HEAD Commit: {git_head}")

    if not check_head_commit_match(git_head, args.expected_commit):
        log(f"PRE-FLIGHT FAILURE: Expected commit {args.expected_commit} does not match actual HEAD {git_head}")
        return 1

    git_status = subprocess.run(["git", "status", "--short"], cwd=repo_root, capture_output=True, text=True).stdout.strip()
    log(f"Git Status before battery:\n{git_status if git_status else '(clean)'}")

    if not check_clean_checkout(git_status):
        log("PRE-FLIGHT FAILURE: Working tree is dirty before mutation run; clean checkout required.")
        return 1

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

    # 5. Execute 31-mutant battery
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

        mutant_pre_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_root, capture_output=True, text=True).stdout.strip()
        mutant_pre_status = subprocess.run(["git", "status", "--short"], cwd=repo_root, capture_output=True, text=True).stdout.strip()
        log(f"     Pre-mutation Git HEAD: {mutant_pre_head}")
        log(f"     Pre-mutation Git Status: {mutant_pre_status if mutant_pre_status else '(clean)'}")

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
                results.append({
                    "id": m_id,
                    "name": m_name,
                    "status": "KILLED",
                    "exit_code": str(m_rc),
                    "pre_head": mutant_pre_head,
                    "post_head": mutant_pre_head,
                    "pre_status": mutant_pre_status or "(clean)",
                    "post_status": mutant_pre_status or "(clean)",
                })
            else:
                log(f"     VERDICT: SURVIVED (pytest exit code 0 - MUTANT SURVIVED!)")
                all_killed = False
                results.append({
                    "id": m_id,
                    "name": m_name,
                    "status": "SURVIVED",
                    "exit_code": "0",
                    "pre_head": mutant_pre_head,
                    "post_head": mutant_pre_head,
                    "pre_status": mutant_pre_status or "(clean)",
                    "post_status": mutant_pre_status or "(clean)",
                })

        finally:
            # Exact in-memory byte restoration without git checkout
            target_file.write_bytes(original_bytes)
            restored_sha256 = hashlib.sha256(target_file.read_bytes()).hexdigest()
            if restored_sha256 != original_sha256:
                log(f"     CRITICAL RESTORATION FAILURE: SHA mismatch! Expected {original_sha256}, got {restored_sha256}")
                raise RuntimeError(f"Restoration SHA mismatch: expected {original_sha256}, got {restored_sha256}")

            mutant_post_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_root, capture_output=True, text=True).stdout.strip()
            mutant_post_status = subprocess.run(["git", "status", "--short"], cwd=repo_root, capture_output=True, text=True).stdout.strip()
            log(f"     Post-mutation Git HEAD: {mutant_post_head}")
            log(f"     Post-mutation Git Status: {mutant_post_status if mutant_post_status else '(clean)'}")
            if mutant_pre_head != mutant_post_head or mutant_pre_status != mutant_post_status:
                log(f"     CRITICAL RESTORATION FAILURE: Git state changed during mutant {m_id} execution!")
                raise RuntimeError(f"Git state mismatch for {m_id}")

        log(f"     Restoration verified: exact SHA-256 match {restored_sha256} and clean git state")
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

    # 8. Post-battery git status
    post_git_status = subprocess.run(["git", "status", "--short"], cwd=repo_root, capture_output=True, text=True).stdout.strip()
    log(f"Git Status after battery:\n{post_git_status if post_git_status else '(clean)'}")

    # 9. Final tally & verdict
    killed_count = sum(1 for r in results if r.get("status") == "KILLED")
    total_count = len(MUTATIONS)

    log("=" * 80)
    log(f"MUTATION BATTERY SUMMARY: {killed_count}/{total_count} mutants KILLED")
    for r in results:
        log(f"  [{r['id']}] {r['name']:<55} {r['status']}")
    log("=" * 80)

    verdict = "VERIFIED" if (all_killed and killed_count == total_count) else "MUTATION_TEST_FAILED"
    log(f"FINAL DISPOSITION: {verdict}")

    log_file.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    log(f"Wrote full mutation evidence log to: {log_file}")

    return 0 if verdict == "VERIFIED" else 1


if __name__ == "__main__":
    sys.exit(main())
