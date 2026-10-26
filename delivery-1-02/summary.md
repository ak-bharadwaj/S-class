# Delivery 1-02: R30 Section F2 Predicate and Invariant Evaluator (Decidable Fragment)

## 1. Metadata
- **Branch:** `block-1-02-predicate-evaluator`
- **Base Commit SHA:** `d146795c73d07258e6a24cfad0b9f2affd32bf92`
- **Timestamp:** 2026-10-26
- **Auditor Environment:** Linux AK 6.6.114.1-microsoft-standard-WSL2 (Ubuntu 26.04.1 LTS, Python 3.14.4, pytest 9.1.1, pip 25.1.1)

---

## 2. Specification Gate Verification
- **R30 Design Text Path:** `FREEZE-CANDIDATE-v6.0.2/S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md` (archive `FREEZE-CANDIDATE-v6.0.2-R30.zip`)
- **Master Design Document SHA-256:** `340db97857a7716b1aac2c1b44bc60b32642e3d8074d02720c2333cea278b4ff`
- **Section Reference:** `<!-- SECTION F2 | status: ACCEPTED -->` lines 249–418 ("F2 — Predicate and Invariant Language — decidable fragment")
- **Authoritative Fixtures:** Section F lines 9100–9312 (`F2-T1` through `F2-T14` / `F2-FT1` through `F2-FT14`)
- **Kernel Enums & States Reused:**
  - Frozen dataclasses in `10-CONFORMANCE/sclass_semantics_v6_0_1.py`: `Requirement`, `Constraint`, `AcceptanceContract`, `VerificationStep`, `Digest`, `ConstraintType`, `RequirementStatus`
  - Gate state vocabulary in `src/sclass/product/schemas/gate_output.json`: `SATISFIED`, `MISSING`, `BLOCKED_ON_HUMAN`
- **Gaps / Ambiguities:** None. All 14 fixtures, grammar, reduction rules, budget bounds, and gate mappings are unambiguously specified.

---

## 3. In-Scope Changed & Created Files
Strict boundary enforcement: Zero changes to `00-SPEC/*`, `10-CONFORMANCE/*`, `20-RUNTIME/*`, lifecycle engine, or kernel authorities.
- **Created:**
  - `src/sclass/product/predicate_evaluator.py`: Complete implementation of R30 Section F2 predicate evaluator, parser, reducer, two-layer evaluator, gate mapper, and UNVERIFIED guard.
  - `tests/product/test_predicate_evaluator.py`: Comprehensive test suite (20 tests) covering all 14 authoritative fixtures (F2-T1..F2-T14), token stream parsing, false-UNSAT guard, budget bounding, and UNVERIFIED outcome enforcement.
  - `delivery-1-02/run_mutations.py`: Self-contained mutation harness targeting evaluator critical logic with in-memory byte restoration and verification.
  - `delivery-1-02/mutation_check.log`: Execution log recording all 7 killed mutants.
  - `delivery-1-02/evidence.txt`: Verification commands, exit codes, and hashes.
  - `delivery-1-02/summary.md`: This delivery report.
- **Modified:**
  - `src/sclass/product/__init__.py`: Package re-exports for predicate evaluator APIs.

---

## 4. Evaluator Design & Feature Coverage

### Closed EBNF Grammar & Token Validation (PD-F2-001)
- Implemented full recursive descent parser enforcing the closed quantifier-free EBNF grammar over scalar, enum, string, set, and list variables.
- Normalizes surface spellings (`&&`, `||`, `!`, `==`, `!=`, `>`, `>=`, `<`, `<=`, `=`, `in`, `not in`, `exists`, `missing`, `true`, `false`) to uppercase canonical vocabulary.
- Canonicalizer emits deterministic AST representation with normalized paths and sorted set literals, yielding deterministic SHA-256 predicate digests.
- Rejects forbidden quantifiers (`FORALL`, `EXISTS(...)`) and malformed tokens with `MISSING[PD-F2-001]`.

### Explicit Finite Domains & Collection Bounding (PD-F2-002)
- Rejects unbounded integer variables without declared finite domain with `MISSING[PD-F2-002]`.
- Implements bounded collection sizing: `Set[T]` with maximum cardinality $K$ and `List[T]` with maximum length $K$.
- Computes total assignment domain estimate as the product of declared variable domain sizes.

### Single-Variable Polynomial Reduction & Budget Bounding (PD-F2-003)
- Applies polynomial interval/set reduction **only to top-level conjunctive atoms** in the current `AND` chain.
- Solves single-variable subformulas in closed form to identify witnesses without full enumeration.
- Enforces evaluation assignment budget; residual search exceeding budget returns `INCONCLUSIVE` (never `SAT` or `UNSAT`), mapping to `BLOCKED_ON_HUMAN[PD-CH2-020]` or `BLOCKED_ON_HUMAN[PD-F1-004]`.

### False-UNSAT Guard
- Reduction is strictly non-distributive over disjunction; alternatives in `OR` chains are never treated as conjunctive.
- Tested and verified by F2-T6, F2-T11, and F2-T12 (`(x = 2) OR (x = 7)` returns `SAT` over $0..9$; flawed optimizer returning `UNSAT` is blocked).

### Two-Layer Evaluation Architecture & Classification (PD-F2-004)
- **Layer 1 (Base Evaluation):** Returns `{base_result: SAT|UNSAT|INCONCLUSIVE, predicate_digest, domain_estimate}`.
- **Layer 2 (Classification):**
  - Tautology query: $\neg A$ is `UNSAT` $\implies$ `TAUTOLOGY`.
  - Contradiction query: $A$ is `UNSAT` $\implies$ `CONTRADICTORY`.
  - Comparison of old $A$ and new $B$:
    - Added, removed, retyped variables or widened domains classify as `WEAKENING` without issuing queries.
    - $B \land \neg A$ is `SAT` $\implies$ `WEAKENING`.
    - $B \land \neg A$ is `UNSAT` and $A \land \neg B$ is `SAT` $\implies$ `TIGHTENING`.
    - Both queries `UNSAT` $\implies$ `EQUIVALENT`.
    - Inconclusive queries $\implies$ `UNCLASSIFIED`.

### Consumer Gate Mapping
- P3 Invariant Check: `SAT` $\implies$ `SATISFIED`; `UNSAT` $\implies$ `MISSING[PD-CH2-020]`; `INCONCLUSIVE` $\implies$ `BLOCKED_ON_HUMAN[PD-CH2-020]`.
- F1 Adequacy: Tautology or contradiction $\implies$ `MISSING[PD-F1-004]`.
- F1 Weakening Control: `EQUIVALENT` or `TIGHTENING` $\implies$ `SATISFIED`; `WEAKENING` without approval $\implies$ `BLOCKED_ON_HUMAN[PD-F1-005]`; `WEAKENING` with bound authoritative approval $\implies$ `SATISFIED`.

### Out-of-Fragment Temporal Routing (PD-F2-005)
- Temporal operators (`ALWAYS`, `EVENTUALLY`, `UNTIL`, `NEXT`) detected and routed out of v1 decidable fragment, producing `BLOCKED_ON_HUMAN[PD-F2-005]`.

### Protection Against Unverified Inputs
- Missing, unknown, malformed, or unsupported inputs produce `EvaluationOutcome.UNVERIFIED` and appropriate `MISSING[...]` / `BLOCKED_ON_HUMAN[...]` gate outputs. Unverified inputs never produce `SATISFIED`.

---

## 5. Frozen Files Hash Table (LF-Byte Normalized)

| Protected File Path | Expected SHA-256 | Actual Verified SHA-256 | Status |
| :--- | :--- | :--- | :--- |
| `00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md` | `53c02b13085dc3e1dcf75b9e8c306704d83bf37175b73a6be1a4b6ab7823ebb1` | `53c02b13085dc3e1dcf75b9e8c306704d83bf37175b73a6be1a4b6ab7823ebb1` | **MATCH** |
| `10-CONFORMANCE/sclass_semantics_v6_0_1.py` | `ed2faf251863e1411fe2f33f2848f87e8fa9d4904b7bb1e032a472874e839922` | `ed2faf251863e1411fe2f33f2848f87e8fa9d4904b7bb1e032a472874e839922` | **MATCH** |
| `10-CONFORMANCE/sclass_kernel_v6_0_1.py` | `d0f8f124dd55aab5cfb68d8c7d644eccf2694f52016c2e4a2132e6d6cef5575c` | `d0f8f124dd55aab5cfb68d8c7d644eccf2694f52016c2e4a2132e6d6cef5575c` | **MATCH** |
| `10-CONFORMANCE/c1-vectors.v6.0.1.json` | `db58744d9829f7cac2ec7715a93d30d20a0d9ba6912d01f563504564e85b2da8` | `db58744d9829f7cac2ec7715a93d30d20a0d9ba6912d01f563504564e85b2da8` | **MATCH** |
| `10-CONFORMANCE/state-machines.v6.0.1.json` | `24f159e6f72179ea66365b585f085727f6ef48420a09eae8c6024cb0bb51fdad` | `24f159e6f72179ea66365b585f085727f6ef48420a09eae8c6024cb0bb51fdad` | **MATCH** |

---

## 6. Test & Mutation Verification Summary

### Focused Predicate Evaluator Suite (`tests/product/test_predicate_evaluator.py`)
- **Total Tests:** 20 collected
- **Passed:** 20 (100%)
- **Failed:** 0
- **Duration:** 2.27s
- **Exit Code:** 0

### Combined Product Suite (`tests/product/`)
- **Total Tests:** 64 collected (44 artifact schema tests + 20 predicate evaluator tests)
- **Passed:** 64 (100%)
- **Duration:** 3.11s
- **Exit Code:** 0

### Mutation Battery Results (`delivery-1-02/run_mutations.py`)
- **Runner SHA-256:** `ca3b204b0cb369eee63c9c0c16318487c8a712d00baf2fc171acb064f334fdf3`
- **Mutations Tested:** 7
- **Mutants Killed:** 7 (100%)
- **Mutants Surviving:** 0
- **Byte Restoration Verification:** In-memory pre-mutation bytes restored and verified bit-for-bit after each mutation test (SHA-256: `224af69456a21421...`).
- **Mutation Breakdown:**
  1. `M1_FALSE_UNSAT_DISJUNCTION`: KILLED (rc=1, failed 3 tests)
  2. `M2_BYPASS_UNVERIFIED_OUTCOME`: KILLED (rc=1, failed 2 tests)
  3. `M3_BYPASS_BUDGET_INCONCLUSIVE`: KILLED (rc=1, failed 2 tests)
  4. `M4_BYPASS_WEAKENING_APPROVAL`: KILLED (rc=1, failed 1 test)
  5. `M5_BYPASS_DOMAIN_WIDENING`: KILLED (rc=1, failed 2 tests)
  6. `M6_BYPASS_TEMPORAL_OUT_OF_V1`: KILLED (rc=1, failed 1 test)
  7. `M7_INVERT_TAUTOLOGY_CLASSIFICATION`: KILLED (rc=1, failed 1 test)
- **Duration:** 24.80s
- **Exit Code:** 0

### Full Test Suite Run (`python -m pytest -q`)
- **Total Tests:** 393 collected
- **Passed:** 393 (100%)
- **Failed:** 0
- **Skipped:** 0
- **Duration:** 335.64s (5m 35s)
- **Exit Code:** 0

---

## 7. Acceptance Checklist
- [x] All 14 authoritative design fixtures F2-T1..F2-T14 implemented and passing.
- [x] Closed EBNF grammar, precedence, associativity, and canonical token validation strictly enforced.
- [x] Finite domain bounding enforced for all scalar, collection, and list variables.
- [x] Single-variable polynomial reduction does not flatten disjunctions (false-UNSAT guard verified).
- [x] Evaluation budget expiration produces `INCONCLUSIVE` (never silent `SAT` or `UNSAT`).
- [x] Tautology, contradiction, equivalence, tightening, and weakening classification matching design.
- [x] Temporal operators route out of v1 to `BLOCKED_ON_HUMAN[PD-F2-005]`.
- [x] Unknown, missing, malformed, or unsupported inputs produce `UNVERIFIED` and cannot satisfy gates.
- [x] Zero changes to `00-SPEC/`, `10-CONFORMANCE/`, or `20-RUNTIME/`.
- [x] 100% mutants killed (7/7) with byte-level in-memory restoration.
- [x] Full test suite (393 tests) clean pass in locked environment.

---

## 8. Reproducible Rerun Instructions

```bash
# Focused predicate evaluator suite
python -m pytest tests/product/test_predicate_evaluator.py -v

# Combined product suite
python -m pytest tests/product/ -v

# Evaluator mutation battery
python delivery-1-02/run_mutations.py

# Frozen integrity guard
python -m pytest tests/guards/test_frozen_integrity_guard.py -v
```
