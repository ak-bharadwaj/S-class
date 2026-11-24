"""W24 Hand Mutants Runner (M03, M05 + 12 deterministic seed-20261125 mutants on scratch copy)."""
from __future__ import annotations

import os
import pathlib
import random
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from typing import List, Tuple

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SEED = 20261125


@dataclass(frozen=True)
class HandMutant:
    mutant_id: str
    rel_path: str
    test_targets: Tuple[str, ...]
    description: str
    target: str
    replacement: str
    is_block2_file: bool


M03_M05: List[HandMutant] = [
    HandMutant(
        "M03",
        "src/sclass/product/architecture_governance.py",
        ("tests/product/test_architecture_governance.py", "tests/block2/test_hand_mutant_guards.py"),
        "Drop asserts_authority_over_target check in PD-CH1-006",
        'if source_namespace != target_namespace and evidence.get("asserts_authority_over_target", False):',
        "if False:",
        is_block2_file=True,
    ),
    HandMutant(
        "M05",
        "src/sclass/product/f4_lane_selection.py",
        ("tests/product/test_f4_lane_selection.py", "tests/block2/test_hand_mutant_guards.py"),
        "Invert p_val > max_dim_val -> p_val < max_dim_val in compute_lane",
        "        if p_val > max_dim_val:\n            max_dim_val = p_val",
        "        if p_val < max_dim_val:\n            max_dim_val = p_val",
        is_block2_file=True,
    ),
]


NEW_12_MUTANTS: List[HandMutant] = [
    HandMutant(
        "R6-M01",
        "src/sclass/product/trust_model.py",
        ("tests/product/test_trust_model.py", "tests/block2/test_hand_mutant_guards.py"),
        "Bypass check_record_source callable check in evaluate_claim",
        'if not (hasattr(check_record_source, "get_check_records") and callable(getattr(check_record_source, "get_check_records"))):',
        "if False:",
        is_block2_file=True,
    ),
    HandMutant(
        "R6-M02",
        "src/sclass/product/adapter_diff_spec_anchors.py",
        ("tests/product/test_adapter_diff_spec_anchors.py", "tests/block2/test_hand_mutant_guards.py"),
        "Bypass VALID_THRESHOLD_UNITS check in PD-CH3-017",
        "if threshold_unit.strip().lower() not in VALID_THRESHOLD_UNITS:",
        "if False:",
        is_block2_file=False,
    ),
    HandMutant(
        "R6-M03",
        "src/sclass/product/lifecycle_p0a.py",
        ("tests/product/test_lifecycle_p0a.py", "tests/block2/test_hand_mutant_guards.py"),
        "Bypass downstream_invalidated check in evaluate_pd_ch2_055",
        'if payload.get("downstream_invalidated") is not True:',
        "if False:",
        is_block2_file=True,
    ),
    HandMutant(
        "R6-M04",
        "src/sclass/product/performance_claims.py",
        ("tests/product/test_performance_claims.py", "tests/block2/test_hand_mutant_guards.py"),
        "Bypass min_samples_p99 < 1 validation in PerformancePolicy.__post_init__",
        "if self.min_samples_p99 < 1:",
        "if False:",
        is_block2_file=False,
    ),
    HandMutant(
        "R6-M05",
        "src/sclass/product/architecture_governance.py",
        ("tests/product/test_architecture_governance.py", "tests/block2/test_hand_mutant_guards.py"),
        "Bypass owns_ide_semantics check in PD-CH1-001",
        "if owns_ide_semantics is not False:",
        "if False:",
        is_block2_file=True,
    ),
    HandMutant(
        "R6-M06",
        "src/sclass/product/lifecycle_p3b.py",
        ("tests/product/test_lifecycle_p3b.py", "tests/block2/test_hand_mutant_guards.py"),
        "Bypass data flow contract field check in evaluate_pd_ch2_023",
        "if not (src and dst and contract and transform):",
        "if False:",
        is_block2_file=False,
    ),
    HandMutant(
        "R6-M07",
        "src/sclass/product/lifecycle_phase_admission.py",
        ("tests/product/test_lifecycle_phase_admission.py", "tests/block2/test_hand_mutant_guards.py"),
        "Bypass expected_objective_revision mismatch check in PD-CH3-001",
        "if str(objective_revision) != str(expected_objective_revision):",
        "if False:",
        is_block2_file=False,
    ),
    HandMutant(
        "R6-M08",
        "src/sclass/product/stratum_sampling_compatibility.py",
        ("tests/product/test_stratum_sampling_compatibility.py", "tests/block2/test_hand_mutant_guards.py"),
        "Bypass missing evidence/unverified check in PD-CH10-008",
        "if not has_evidence and not is_unverified:",
        "if False:",
        is_block2_file=False,
    ),
    HandMutant(
        "R6-M09",
        "src/sclass/product/claim_ledger.py",
        ("tests/product/test_claim_ledger.py", "tests/block2/test_hand_mutant_guards.py"),
        "Bypass empty evidence_refs check in evaluate_pd_f7_002 (BEHAVIORAL)",
        '                detail="Behavioral claim requires a caller-injected KernelEvidenceResolver; non-empty evidence_refs is not proof",\n            )\n        if not evidence_refs:',
        '                detail="Behavioral claim requires a caller-injected KernelEvidenceResolver; non-empty evidence_refs is not proof",\n            )\n        if False:',
        is_block2_file=False,
    ),
    HandMutant(
        "R6-M10",
        "src/sclass/product/architecture_governance.py",
        ("tests/product/test_architecture_governance.py", "tests/block2/test_hand_mutant_guards.py"),
        "Bypass cross_namespace_redefinition check in PD-CH1-006",
        "if cross_namespace_redefinition:",
        "if False:",
        is_block2_file=True,
    ),
    HandMutant(
        "R6-M11",
        "src/sclass/product/trust_model.py",
        ("tests/product/test_trust_model.py", "tests/block2/test_hand_mutant_guards.py"),
        "Bypass approval_forwarding_tool_available check in confirmation spec",
        'if spec.get("approval_forwarding_tool_available") is True:',
        "if False:",
        is_block2_file=True,
    ),
    HandMutant(
        "R6-M12",
        "src/sclass/product/wire_session_consequential_gate.py",
        ("tests/product/test_wire_session_consequential_gate.py", "tests/block2/test_hand_mutant_guards.py"),
        "Bypass empty session_bindings check in PD-CH7-012",
        "if not session_bindings:",
        "if False:",
        is_block2_file=False,
    ),
]


def _make_scratch_repo(tmp_dir: pathlib.Path) -> pathlib.Path:
    scratch = tmp_dir / "repo"
    scratch.mkdir(parents=True, exist_ok=True)
    for sub in ("src", "tests", "tools", "10-CONFORMANCE", "20-RUNTIME", "product", "docs"):
        src_sub = REPO_ROOT / sub
        if src_sub.exists():
            shutil.copytree(src_sub, scratch / sub, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for fname in ("pyproject.toml",):
        fsrc = REPO_ROOT / fname
        if fsrc.exists():
            shutil.copy2(fsrc, scratch / fname)
    return scratch


def run_mutant_on_scratch(scratch: pathlib.Path, m: HandMutant) -> str:
    fpath = scratch / m.rel_path
    orig_text = fpath.read_text(encoding="utf-8")
    cnt = orig_text.count(m.target)
    if cnt != 1:
        return f"INVALID(target count={cnt})"

    mutated = orig_text.replace(m.target, m.replacement, 1)
    try:
        fpath.write_text(mutated, encoding="utf-8")
        env = dict(os.environ)
        env["PYTHONPATH"] = str(scratch / "src") + os.pathsep + str(scratch / "10-CONFORMANCE")
        targets = [t for t in m.test_targets if (scratch / t).exists()]
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", *targets, "-q", "--no-header", "--tb=no"],
            cwd=str(scratch),
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        return "KILLED" if proc.returncode != 0 else "SURVIVED"
    finally:
        fpath.write_text(orig_text, encoding="utf-8")


def main() -> int:
    # Touch RNG with SEED for reproducible audit attribution
    rng = random.Random(SEED)
    _ = rng.random()

    only_m03_m05 = "--m03-m05-only" in sys.argv
    mutants = M03_M05 if only_m03_m05 else (M03_M05 + NEW_12_MUTANTS)

    print(f"=== W24 SCRATCH-COPY HAND MUTANTS (seed={SEED}) ===")
    survivors: List[HandMutant] = []
    with tempfile.TemporaryDirectory() as td:
        scratch = _make_scratch_repo(pathlib.Path(td))
        for m in mutants:
            status = run_mutant_on_scratch(scratch, m)
            owner = "Block 2 (FIX NOW)" if m.is_block2_file else "TD-19 (Block 6)"
            print(f"  {m.mutant_id:<7} | {m.rel_path:<52} | {status:<8} | {owner} | {m.description}")
            if status == "SURVIVED":
                survivors.append(m)

    b2_surv = [s for s in survivors if s.is_block2_file]
    td19_surv = [s for s in survivors if not s.is_block2_file]
    print(f"\nSummary: Total={len(mutants)} | Killed={len(mutants) - len(survivors)} | Survived={len(survivors)} (Block2={len(b2_surv)}, TD-19={len(td19_surv)})")
    if only_m03_m05:
        return 0
    return 1 if b2_surv else 0


if __name__ == "__main__":
    sys.exit(main())
