# GAP REPORT: Global MUST Coverage & Implementation Gaps (Task G2)

Machine-generated analysis of MUST requirements across Blocks 0 through 9.

## 1. Summary Statistics

- **Total MUSTs in Master**: 195
- **MUSTs with No Happy Master Fixture**: 96
- **MUSTs with Only Test-Authored Vectors**: 90
- **MUSTs with Human Route Requirements**: 4
- **Duplicate Evaluator Implementations**: 0

## 2. MUSTs with No Happy Master Fixture

| MUST ID | Master Line | Requirement Excerpt |
|---|---|---|
| `PD-F5-001` | Line 106 | | F5 | `PD-F5-001..099` | `001..005` | allocated IDs never reused | |
| `PD-F9-001` | Line 110 | | F9 | `PD-F9-001..099` | `001..004` | allocated IDs never reused | |
| `PD-F10-001` | Line 111 | | F10 | `PD-F10-001..099` | `001..007` | allocated IDs never reused | |
| `PD-CH10-013` | Line 113 | MUST-ID integrity is specified by `PD-CH2-028`; producer self-pass is owned by a |
| `PD-F5-002` | Line 669 | | PD-F5-002 | M | When both missing and blocked checks apply, `MISSING` MUST hav |
| `PD-F5-003` | Line 670 | | PD-F5-003 | E | Evaluator crash, timeout, malformed internal result or budget  |
| `PD-F5-004` | Line 671 | | PD-F5-004 | E | Explain-why and caching MUST be derived from the same canonica |
| `PD-F5-005` | Line 672 | | PD-F5-005 | M | Product phase gates MUST only add blocking conjunctions and MU |
| `PD-F9-002` | Line 923 | | PD-F9-002 | M | Every metric MUST declare numerator, denominator and canonical |
| `PD-F9-003` | Line 924 | | PD-F9-003 | E | Paired metrics MUST be evaluated together so optimization of o |
| `PD-F9-004` | Line 925 | | PD-F9-004 | M | Agent/operator self-reported metrics MUST NOT contribute to ca |
| `PD-F10-004` | Line 992 | **Default adapter resource limits (reviewer clarification, R12; initial policy d |
| `PD-F10-006` | Line 1012 | For CRITICAL-lane obligations that require independent verification, a qualified |
| `PD-F10-002` | Line 1021 | | PD-F10-002 | M/E | A usable adapter MUST bind immutable identity/version/diges |
| `PD-F10-003` | Line 1022 | | PD-F10-003 | M | Only authorized non-agent authority may register/change adapt |
| `PD-F10-005` | Line 1024 | | PD-F10-005 | M/E | Qualification MUST pass all 14 frozen adapter tests, A1 ref |
| `PD-F10-007` | Line 1026 | | PD-F10-007 | E | Differential detection MUST compare canonicalized semantics a |
| `PD-CH1-001` | Line 1068 | | control plane, not IDE/model/worker | `PD-CH1-001` | CH1-T1 | CH1-T8 | |
| `PD-CH6-007` | Line 1069 | | engineering knowledge | `PD-CH6-007` | CH6-T7 | CH6-T8 | |
| `PD-CH5-007` | Line 1071 | | engineering gates | `PD-CH5-007` | CH5-T7 | CH5-T8 | |
| `PD-CH4-014` | Line 1072 | | authorization (scope) | `PD-CH4-014` | CH4-T19 | CH4-T20 | |
| `PD-CH4-005` | Line 1073 | | evidence admissibility | `PD-CH4-005` | CH4-T5 | CH4-T28 | |
| `PD-CH4-016` | Line 1074 | | assessment (independence) | `PD-CH4-016` | CH4-T23 | CH4-T24 | |
| `PD-CH4-006` | Line 1075 | | completion/release authority | `PD-CH4-006` | CH4-T6 | CH4-T29 | |
| `PD-CH1-002` | Line 1105 | | PD-CH1-002 | M | Every v6.0.2 product rule MUST be subordinate to the frozen v |
| `PD-CH1-004` | Line 1185 | | PD-CH1-004 | M | A product-layer concept MUST belong to exactly one declared c |
| `PD-CH1-005` | Line 1209 | | PD-CH1-005 | M | Every new product artifact MUST declare `authority_class` usi |
| `PD-CH1-006` | Line 1242 | | PD-CH1-006 | M | No namespace is permitted to define authority over another na |
| `PD-CH7-011` | Line 1257 | | Enforcement | per cell, the E0/E1/E2 level declared by `PD-CH7-011` for the qu |
| `PD-CH1-007` | Line 1264 | | PD-CH1-007 | M | v1 MUST preserve the full authority floor while limiting ship |
| `PD-CH4-009` | Line 1998 | | PD-CH2-046 | M/E | P5 MUST NOT authorize a red run until the primary test dige |
| `PD-CH4-010` | Line 2003 | Quoted binding text: “Before any red run, bind the complete **TestInputSet** ret |
| `PD-CH3-007` | Line 2442 | **Normative owner:** `PD-CH3-007` is allocated and defined in Chapter 3.8; this  |
| `PD-CH3-009` | Line 2544 | **MUST / class:** reference only; the single defining row is in the chapter MUST |
| `PD-CH3-010` | Line 2606 | **MUST / class:** reference only; the single defining row is in the chapter MUST |
| `PD-CH3-011` | Line 2664 | **Normative owner:** `PD-CH3-011` is allocated and defined in Chapter 3.8; this  |
| `PD-CH3-012` | Line 2737 | **MUST / class:** reference only; the single defining row is in the chapter MUST |
| `PD-CH3-014` | Line 2836 | **Normative owner:** `PD-CH3-014` is allocated and defined in the Chapter 3 MUST |
| `PD-CH3-001` | Line 2892 | **MUST / class:** reference only; the single defining row is in the chapter MUST |
| `PD-CH3-015` | Line 2912 | ### R5 normative closure — PD-CH3-015 |
| ... | ... | (56 additional MUSTs omitted for brevity) |

## 3. MUSTs with Only Test-Authored Vectors

| MUST ID | Test Occurrences | Status |
|---|---|---|
| `PD-F5-001` | 1 tests | Covered by repository tests; zero normative master vectors |
| `PD-F9-001` | 1 tests | Covered by repository tests; zero normative master vectors |
| `PD-F10-001` | 2 tests | Covered by repository tests; zero normative master vectors |
| `PD-CH10-013` | 2 tests | Covered by repository tests; zero normative master vectors |
| `PD-F5-002` | 2 tests | Covered by repository tests; zero normative master vectors |
| `PD-F5-003` | 1 tests | Covered by repository tests; zero normative master vectors |
| `PD-F5-004` | 1 tests | Covered by repository tests; zero normative master vectors |
| `PD-F5-005` | 1 tests | Covered by repository tests; zero normative master vectors |
| `PD-F9-002` | 1 tests | Covered by repository tests; zero normative master vectors |
| `PD-F9-003` | 1 tests | Covered by repository tests; zero normative master vectors |
| `PD-F9-004` | 1 tests | Covered by repository tests; zero normative master vectors |
| `PD-F10-004` | 1 tests | Covered by repository tests; zero normative master vectors |
| `PD-F10-006` | 1 tests | Covered by repository tests; zero normative master vectors |
| `PD-F10-002` | 2 tests | Covered by repository tests; zero normative master vectors |
| `PD-F10-003` | 1 tests | Covered by repository tests; zero normative master vectors |
| `PD-F10-005` | 1 tests | Covered by repository tests; zero normative master vectors |
| `PD-F10-007` | 1 tests | Covered by repository tests; zero normative master vectors |
| `PD-CH6-007` | 2 tests | Covered by repository tests; zero normative master vectors |
| `PD-CH5-007` | 3 tests | Covered by repository tests; zero normative master vectors |
| `PD-CH4-014` | 1 tests | Covered by repository tests; zero normative master vectors |
| `PD-CH4-005` | 2 tests | Covered by repository tests; zero normative master vectors |
| `PD-CH4-016` | 1 tests | Covered by repository tests; zero normative master vectors |
| `PD-CH4-006` | 2 tests | Covered by repository tests; zero normative master vectors |
| `PD-CH7-011` | 1 tests | Covered by repository tests; zero normative master vectors |
| `PD-CH4-009` | 1 tests | Covered by repository tests; zero normative master vectors |
| `PD-CH4-010` | 2 tests | Covered by repository tests; zero normative master vectors |
| `PD-CH3-007` | 1 tests | Covered by repository tests; zero normative master vectors |
| `PD-CH3-009` | 1 tests | Covered by repository tests; zero normative master vectors |
| `PD-CH3-010` | 1 tests | Covered by repository tests; zero normative master vectors |
| `PD-CH3-011` | 1 tests | Covered by repository tests; zero normative master vectors |

## 4. MUSTs with Human Route Requirements in Master Text

| MUST ID | Master Line | Text Requiring Human Route | Evaluator Return Status |
|---|---|---|---|
| `PD-F2-005` | Line 377 | | PD-F2-005 | E/J | Temporal, unbounded or otherwise out-of-fragment predicates  | `BLOCKED_ON_HUMAN` supported in closed vocabulary |
| `PD-CH2-051` | Line 2215 | | PD-CH2-051 | M/E | P8 MUST route failure to the earliest affected phase and st | `BLOCKED_ON_HUMAN` supported in closed vocabulary |
| `PD-CH3-012` | Line 2737 | **MUST / class:** reference only; the single defining row is in the chapter MUST | `BLOCKED_ON_HUMAN` supported in closed vocabulary |
| `PD-CH3-003` | Line 3050 | **MUST / class:** reference only; the single defining row is in the chapter MUST | `BLOCKED_ON_HUMAN` supported in closed vocabulary |

## 5. Duplicate Implementations Across Lanes

- **Zero Duplicate Evaluators**: No duplicate public evaluator definitions exist across different lanes.

