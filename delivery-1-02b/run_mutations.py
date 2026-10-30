#!/usr/bin/env python3
"""Block 1-02b Predicate Evaluator Mutation Runner.

Applies 14 targeted mutations covering all required safety properties to
src/sclass/product/predicate_evaluator.py, verifies that each mutant is killed
(pytest exit code != 0), restores exact original bytes in a finally block, asserts
byte and SHA-256 equality, and verifies baseline passes.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "src" / "sclass" / "product" / "predicate_evaluator.py"
TEST_TARGET = ROOT / "tests" / "product" / "test_predicate_evaluator.py"
LOG_PATH = ROOT / "delivery-1-02b" / "mutation_check.log"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


MUTATIONS = [
    (
        "M01_RESOLVER_OMITTED",
        "Resolver omitted: bypass check for missing resolver",
        '    if resolver is None:\n        return False, {}, "Missing required frozen binding resolver"',
        '    if resolver is None:\n        return True, {}, None',
    ),
    (
        "M02_UNKNOWN_REFERENCE_ACCEPTED",
        "Unknown reference accepted: bypass check for unresolved reference",
        '        if obj is None:\n            return False, {}, f"Unknown or unresolvable reference \'{ref_val}\' for \'{ref_key}\'"',
        '        if obj is None:\n            continue',
    ),
    (
        "M03_WRONG_TYPE_ACCEPTED",
        "Wrong-type object accepted: bypass check for expected frozen kernel type",
        '        if not isinstance(obj, expected_cls):\n            return False, {}, (\n                f"Reference \'{ref_val}\' resolved to type \'{type(obj).__name__}\', "\n                f"expected frozen kernel type \'{expected_cls.__name__}\'"\n            )',
        '        if False:\n            pass',
    ),
    (
        "M04_FIXTURE_BOOLEAN_TRUSTED",
        "Fixture boolean trusted: trust all_refs_resolve_to_frozen_objects without actual resolution",
        '    has_binding_refs = any(\n        k in spec for k in ("requirement_ref", "constraint_ref", "acceptance_contract_ref", "verification_step_ref")\n    )\n    if has_binding_refs:\n        active_resolver = resolver',
        '    has_binding_refs = any(\n        k in spec for k in ("requirement_ref", "constraint_ref", "acceptance_contract_ref", "verification_step_ref")\n    )\n    if has_binding_refs:\n        if spec.get("all_refs_resolve_to_frozen_objects"):\n            return EvaluationResult(outcome=EvaluationOutcome.VERIFIED, gate_output=GateOutput(GateState.SATISFIED))\n        active_resolver = resolver',
    ),
    (
        "M05_PARTIAL_BINDING_ACCEPTED",
        "Partial binding accepted: do not require all four bindings present",
        '    for ref_key, expected_cls in REQUIRED_FROZEN_BINDING_TYPES.items():\n        if ref_key not in bindings:\n            return False, {}, f"Missing required reference \'{ref_key}\' in bindings"',
        '    for ref_key, expected_cls in REQUIRED_FROZEN_BINDING_TYPES.items():\n        if False:\n            return False, {}, f"Missing required reference \'{ref_key}\' in bindings"',
    ),
    (
        "M06_INCONCLUSIVE_TO_SAT",
        "INCONCLUSIVE converted to SAT: map INCONCLUSIVE base result to SATISFIED",
        '            elif r == BaseResult.INCONCLUSIVE:\n                return GateOutput(GateState.BLOCKED_ON_HUMAN, must_id=must_id_override or "PD-CH2-020")',
        '            elif r == BaseResult.INCONCLUSIVE:\n                return GateOutput(GateState.SATISFIED)',
    ),
    (
        "M07_INCONCLUSIVE_TO_UNSAT",
        "INCONCLUSIVE converted to UNSAT: map INCONCLUSIVE base result to MISSING",
        '            elif r == BaseResult.INCONCLUSIVE:\n                return GateOutput(GateState.BLOCKED_ON_HUMAN, must_id=must_id_override or "PD-CH2-020")',
        '            elif r == BaseResult.INCONCLUSIVE:\n                return GateOutput(GateState.MISSING, must_id=must_id_override or "PD-CH2-020")',
    ),
    (
        "M08_UNSUPPORTED_CONSUMER_SATISFIED",
        "Unsupported consumer mapped to SATISFIED instead of fail-closed MISSING",
        '    if consumer not in ("p3_invariant", "f1_adequacy", "weakening_control"):\n        return GateOutput(GateState.MISSING, must_id=must_id_override or "PD-F2-001", detail=f"Unsupported consumer: \'{consumer}\'")',
        '    if consumer not in ("p3_invariant", "f1_adequacy", "weakening_control"):\n        return GateOutput(GateState.SATISFIED)',
    ),
    (
        "M09_UNCLASSIFIED_TO_FAVORABLE",
        "UNCLASSIFIED mapped to favorable SATISFIED instead of BLOCKED_ON_HUMAN",
        '            elif c == Classification.UNCLASSIFIED:\n                return GateOutput(GateState.BLOCKED_ON_HUMAN, must_id="PD-F1-005")',
        '            elif c == Classification.UNCLASSIFIED:\n                return GateOutput(GateState.SATISFIED)',
    ),
    (
        "M10_WEAKENING_WITHOUT_APPROVAL",
        "Weakening accepted without bound approval: return SATISFIED without checking approval",
        '            elif c == Classification.WEAKENING:\n                if authoritative_approval is not None and str(authoritative_approval).strip():\n                    return GateOutput(GateState.SATISFIED)\n                return GateOutput(GateState.BLOCKED_ON_HUMAN, must_id="PD-F1-005")',
        '            elif c == Classification.WEAKENING:\n                return GateOutput(GateState.SATISFIED)',
    ),
    (
        "M11_OR_MERGED_AS_CONJUNCTIVE",
        "OR alternatives merged as conjunctive: false-UNSAT bug in OrNode evaluation",
        '        return any(c.evaluate(env) for c in self.children)',
        '        return all(c.evaluate(env) for c in self.children)',
    ),
    (
        "M12_INCOMPLETE_RESIDUAL_REPORTED_COMPLETE",
        "Incomplete residual enumeration reported complete: return SAT instead of INCONCLUSIVE on budget overrun",
        '            if evaluated >= budget:\n                return BaseEvaluation(\n                    base_result=BaseResult.INCONCLUSIVE,\n                    predicate_digest=cls.compute_digest(node),\n                    domain_estimate=domain_estimate,\n                    evaluated_assignments=evaluated,\n                    budget_exhausted=True,\n                )',
        '            if evaluated >= budget:\n                return BaseEvaluation(\n                    base_result=BaseResult.SAT,\n                    predicate_digest=cls.compute_digest(node),\n                    domain_estimate=domain_estimate,\n                    evaluated_assignments=evaluated,\n                    budget_exhausted=True,\n                )',
    ),
    (
        "M13_DOMAIN_WIDENING_AS_EQUIVALENCE",
        "Domain widening treated as equivalence: classify widening as EQUIVALENT",
        '                if set(new_v.domain) - set(old_v.domain):\n                    return ClassificationEvaluation(\n                        classification=Classification.WEAKENING,\n                        reason=f"Variable \'{k}\' domain widened",\n                    )',
        '                if set(new_v.domain) - set(old_v.domain):\n                    return ClassificationEvaluation(\n                        classification=Classification.EQUIVALENT,\n                        reason=f"Variable \'{k}\' domain widened",\n                    )',
    ),
    (
        "M14_NON_CANONICAL_DIGEST",
        "Non-canonical digest: substitute raw UTF-8 string encoding for authoritative canonical_c1 mechanism",
        '    c1_bytes = canonical_c1(canonical_str)\n    return hashlib.sha256(c1_bytes).hexdigest()',
        '    return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()',
    ),
]


def run_tests() -> tuple[int, str]:
    cmd = [sys.executable, "-m", "pytest", str(TEST_TARGET), "-q", "-p", "no:cacheprovider"]
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr


def main() -> int:
    orig_bytes = TARGET.read_bytes()
    orig_hash = sha256_bytes(orig_bytes)
    t0 = time.time()
    log_lines = [
        "=" * 80,
        "BLOCK 1-02b PREDICATE EVALUATOR REMEDIATION MUTATION BATTERY",
        f"Target file: {TARGET}",
        f"Original bytes: {len(orig_bytes)}, SHA-256: {orig_hash}",
        f"Python interpreter: {sys.executable}",
        "=" * 80,
        "",
    ]

    print(f"Running baseline clean tests on {TEST_TARGET.name}...")
    rc_clean, out_clean = run_tests()
    log_lines.append(f"--- [BASELINE CLEAN RUN] --- (rc={rc_clean})")
    log_lines.append(out_clean.strip())
    log_lines.append("")
    if rc_clean != 0:
        print(f"ERROR: Baseline tests failed! (rc={rc_clean})")
        print(out_clean)
        return 1

    total_mutants = len(MUTATIONS)
    killed = 0
    survived = 0

    for idx, (m_id, m_desc, target_str, mut_str) in enumerate(MUTATIONS, 1):
        print(f"[{idx}/{total_mutants}] Testing mutant: {m_id} - {m_desc}")
        log_lines.append(f"--- [MUTANT {idx}: {m_id}] ---")
        log_lines.append(f"Description: {m_desc}")

        text = orig_bytes.decode("utf-8")
        if target_str not in text:
            msg = f"ERROR: Target string not found for mutant {m_id}"
            print(msg)
            log_lines.append(msg)
            return 1

        mutated_text = text.replace(target_str, mut_str, 1)
        mutated_bytes = mutated_text.encode("utf-8")

        try:
            TARGET.write_bytes(mutated_bytes)
            rc, out = run_tests()
            log_lines.append(f"Exit code: {rc}")
            log_lines.append(out.strip())
            if rc != 0:
                print(f"  -> KILLED (rc={rc})")
                log_lines.append(f"Result: KILLED (rc={rc})")
                killed += 1
            else:
                print(f"  -> SURVIVED (rc={rc})")
                log_lines.append(f"Result: SURVIVED (rc={rc})")
                survived += 1
        finally:
            # Exact in-memory byte restoration
            TARGET.write_bytes(orig_bytes)
            restored_bytes = TARGET.read_bytes()
            assert restored_bytes == orig_bytes, f"Byte restoration mismatch on mutant {m_id}"
            assert sha256_bytes(restored_bytes) == orig_hash, f"Hash restoration mismatch on mutant {m_id}"
            log_lines.append(f"Restored exact pre-mutation bytes (SHA-256 verified: {orig_hash[:16]}...)")
            log_lines.append("")

    print(f"Running final post-mutation verification clean run...")
    rc_final, out_final = run_tests()
    log_lines.append(f"--- [FINAL CLEAN RUN] --- (rc={rc_final})")
    log_lines.append(out_final.strip())
    log_lines.append("")

    elapsed = time.time() - t0
    summary = [
        "=" * 80,
        f"MUTATION BATTERY COMPLETE: {killed}/{total_mutants} KILLED ({survived} surviving)",
        f"Total duration: {elapsed:.2f}s",
        f"Original bytes restored & verified: True ({orig_hash})",
        "=" * 80,
    ]
    log_lines.extend(summary)
    full_log = "\n".join(log_lines) + "\n"

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text(full_log, encoding="utf-8")

    print("\n".join(summary))
    return 0 if (survived == 0 and rc_final == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
