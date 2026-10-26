#!/usr/bin/env python3
"""Block 1-02 Predicate Evaluator Mutation Runner.

Applies 7 targeted mutations to src/sclass/product/predicate_evaluator.py,
verifies that each mutant is killed (pytest exit code 1), restores exact original
bytes in a finally block, asserts byte and SHA-256 equality, and verifies baseline passes.
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
LOG_PATH = ROOT / "delivery-1-02" / "mutation_check.log"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


MUTATIONS = [
    (
        "M1_FALSE_UNSAT_DISJUNCTION",
        "Treat OR alternatives as conjunctive (flawed reducer yielding UNSAT on disjunction)",
        "return any(c.evaluate(env) for c in self.children)",
        "return all(c.evaluate(env) for c in self.children)",
    ),
    (
        "M2_BYPASS_UNVERIFIED_OUTCOME",
        "Bypass UNVERIFIED outcome on malformed input (return VERIFIED + SATISFIED)",
        '        return EvaluationResult(\n            outcome=EvaluationOutcome.UNVERIFIED,\n            gate_output=GateOutput(GateState.MISSING, must_id="PD-F2-001"),\n            error=f"Parse failure: {e}",\n        )',
        '        return EvaluationResult(\n            outcome=EvaluationOutcome.VERIFIED,\n            gate_output=GateOutput(GateState.SATISFIED),\n        )',
    ),
    (
        "M3_BYPASS_BUDGET_INCONCLUSIVE",
        "Bypass budget bounding (return SAT instead of INCONCLUSIVE on budget exhaustion)",
        "return BaseEvaluation(\n                    base_result=BaseResult.INCONCLUSIVE,\n                    predicate_digest=cls.compute_digest(node),\n                    domain_estimate=domain_estimate,\n                    evaluated_assignments=evaluated,\n                    budget_exhausted=True,\n                )",
        "return BaseEvaluation(\n                    base_result=BaseResult.SAT,\n                    predicate_digest=cls.compute_digest(node),\n                    domain_estimate=domain_estimate,\n                    evaluated_assignments=evaluated,\n                    budget_exhausted=True,\n                )",
    ),
    (
        "M4_BYPASS_WEAKENING_APPROVAL",
        "Bypass weakening approval check (return SATISFIED without approval)",
        '            elif c == Classification.WEAKENING:\n                if authoritative_approval is not None:\n                    return GateOutput(GateState.SATISFIED)\n                return GateOutput(GateState.BLOCKED_ON_HUMAN, must_id="PD-F1-005")',
        '            elif c == Classification.WEAKENING:\n                return GateOutput(GateState.SATISFIED)',
    ),
    (
        "M5_BYPASS_DOMAIN_WIDENING",
        "Bypass domain widening detection (silently ignore widened domain)",
        "                if set(new_v.domain) - set(old_v.domain):\n                    return ClassificationEvaluation(\n                        classification=Classification.WEAKENING,\n                        reason=f\"Variable '{k}' domain widened\",\n                    )",
        "                if False:\n                    pass",
    ),
    (
        "M6_BYPASS_TEMPORAL_OUT_OF_V1",
        "Bypass temporal routing out of v1 (return SATISFIED instead of BLOCKED_ON_HUMAN[PD-F2-005])",
        '    except NotImplementedError as e:\n        return EvaluationResult(\n            outcome=EvaluationOutcome.UNVERIFIED,\n            gate_output=GateOutput(GateState.BLOCKED_ON_HUMAN, must_id="PD-F2-005"),\n            error=str(e),\n        )',
        '    except NotImplementedError as e:\n        return EvaluationResult(\n            outcome=EvaluationOutcome.VERIFIED,\n            gate_output=GateOutput(GateState.SATISFIED),\n            error=str(e),\n        )',
    ),
    (
        "M7_INVERT_TAUTOLOGY_CLASSIFICATION",
        "Invert tautology classification (report CONTRADICTORY instead of TAUTOLOGY)",
        '            if base_neg.base_result == BaseResult.UNSAT:\n                return ClassificationEvaluation(\n                    classification=Classification.TAUTOLOGY,',
        '            if base_neg.base_result == BaseResult.UNSAT:\n                return ClassificationEvaluation(\n                    classification=Classification.CONTRADICTORY,',
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
        "BLOCK 1-02 PREDICATE EVALUATOR MUTATION BATTERY",
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
        print("ERROR: Baseline tests failed!")
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

    # Write log if NO_OVERWRITE_MUTATION_LOG not set
    if not os.environ.get("NO_OVERWRITE_MUTATION_LOG"):
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        LOG_PATH.write_text(full_log, encoding="utf-8")

    print("\n".join(summary))
    return 0 if (survived == 0 and rc_final == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
