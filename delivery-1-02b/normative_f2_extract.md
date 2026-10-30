# Normative Extract: R30 Section F2 Predicate and Invariant Evaluator

## Document Provenance & Verification
- **Source Archive:** `FREEZE-CANDIDATE-v6.0.2-R30.zip`
- **Source File:** `FREEZE-CANDIDATE-v6.0.2/S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md`
- **Expected SHA-256:** `340db97857a7716b1aac2c1b44bc60b32642e3d8074d02720c2333cea278b4ff`
- **Verified SHA-256:** `340db97857a7716b1aac2c1b44bc60b32642e3d8074d02720c2333cea278b4ff`
- **Integrity Status:** `MATCH - VERIFIED`

---

## Section F2 Normative Text

<!-- SECTION F2 | status: ACCEPTED -->
## F2 — Predicate and Invariant Language — decidable fragment

**Status:** ACCEPTED.



**Known defects:** none.

### Context

P3 invariant satisfiability needs a mechanically decidable core, while spec adequacy and weakening control need stronger results than a bare satisfiable/unsatisfiable decision. F2 defines a bounded, typed product-layer fragment and a reference procedure. It introduces no second authority, lifecycle state machine, or canonical constraint store.

### Options considered

| Option | Result |
|---|---|
| Free-form predicates | Rejected: no bounded mechanical semantics. |
| Full programming language | Rejected: unbounded execution and undecidable analysis. |
| Bounded temporal logic in v1 | Rejected: temporal semantics would expand the proof surface before the base fragment is stable. |
| Small typed fragment plus qualified property/stateful tests for temporal cases | **Selected.** |

### Decision

F2 v1 is a quantifier-free, side-effect-free expression over finite scalar, set and list variables. Temporal logic is outside the v1 fragment and routes to qualified property/stateful testing or J.

#### Types, collection domains and missing paths

- `Bool` and finite `Enum` values are allowed.
- `Int` values MUST have a declared finite domain `[min,max]`.
- `String` values are restricted to equality/inequality and finite membership.
- `Set[T]` requires a finite element domain of size `E` and maximum cardinality `K`; its enumeration domain size is `Σ(i=0..K) C(E,i)`.
- Finite `List[T]` requires the same finite element domain and maximum length `K`; its enumeration domain size for variable-length lists is `Σ(i=0..K) E^i`.
- Collection literals MUST use element values from the declared finite element domain.
- Field paths MUST resolve against a declared schema instance. A missing path is a type/binding error, not an implicit false value.

#### Closed EBNF

```text
LETTER          := "A".."Z" | "a".."z"
NONZERO_DIGIT   := "1".."9"
DIGIT           := "0" | NONZERO_DIGIT
IDENT           := LETTER (LETTER | DIGIT | "_")*
escape          := "\\" ("\\" | "\"" | "n" | "r" | "t")
string_char     := LETTER | DIGIT | " " | "_" | "." | "-" | escape
integer         := "0" | NONZERO_DIGIT DIGIT* | "-" NONZERO_DIGIT DIGIT*
path            := IDENT ("." IDENT)*
literal         := boolean | integer | quoted_string | enum_literal
boolean         := TRUE | FALSE
set_literal     := "{" [literal ("," literal)*] "}"
cmp             := EQUALS | NOT_EQUALS | GREATER_THAN | GREATER_OR_EQUAL | LESS_THAN | LESS_OR_EQUAL
cmp_int         := EQUALS | NOT_EQUALS | GREATER_THAN | GREATER_OR_EQUAL | LESS_THAN | LESS_OR_EQUAL
quoted_string   := '"' string_char* '"'
enum_literal    := IDENT
expr            := or_expr
or_expr         := and_expr (OR and_expr)*
and_expr        := unary (AND unary)*
unary           := NOT unary | '(' expr ')' | atom
atom            := path EXISTS
                 | path NOT_EXISTS
                 | path cmp literal
                 | path cmp path
                 | path IN set_literal
                 | path NOT_IN set_literal
                 | CARD(path) cmp_int integer
                 | TRUE
                 | FALSE
```


`IMPLIES(a,b)` is accepted only as canonical sugar and maps to `OR(NOT(a),b)`. Surface spellings map to the canonical comparison/operator vocabulary as follows: `&&` means AND, `||` means OR, `!` means NOT, `==` means equals, `!=` means not-equal, `>` means greater-than, `>=` means greater-than-or-equal, `<` means less-than, `<=` means less-than-or-equal, `in` means IN, `not in` means NOT_IN, `exists` means EXISTS, `missing` means NOT_EXISTS, `true` means TRUE, and `false` means FALSE. Canonical output uses uppercase operator names, normalized paths, sorted set literals and explicit parentheses. `NOT` binds tighter than `AND`, which binds tighter than `OR`; `AND` and `OR` are left-associative; `NOT` is unary. Path-to-path comparison is allowed only when both paths resolve to the same finite scalar, enum or string type. `EXISTS` is true only when the path is present; a missing path is not coerced to a value.

The F1-FT9 and F1-FT10 predicates are expressible as `TRUE` and `x > 1 AND x < 1`.

### Decision procedure

1. Parse, tokenize and schema/type-check the surface form against the EBNF above.
2. Canonicalize the surface syntax to the F2 normal form and emit the canonical predicate digest.
3. Verify finite domains and collection bounds. The total assignment-domain estimate is the product of every variable's scalar domain size, set domain size, or list domain size defined above.
4. Apply a polynomial interval/set reduction **only to top-level conjunctive atoms in the current `AND` chain**. Reduction MUST NEVER treat OR alternatives as conjunctive.
5. For the top-level `AND` of single-variable subformulas, solve each variable independently as a finite union of intervals/member sets. A formula over one variable with arbitrary `AND`/`OR`/`NOT` has its model set computed as a union of intervals/member sets. Everything not solved by that single-variable closed form is residual and is the only portion enumerated. Cross-variable atoms remain residual; never treat OR alternatives as conjunctive.
6. Apply the normative F4 depth-level assignment budget to the residual enumeration. A budget overrun before completion returns `INCONCLUSIVE`, never `SAT` or `UNSAT`, then routes to a qualified property test or J.
7. When complete bounded evaluation is performed, return `SAT` only when at least one bounded assignment satisfies the predicate and `UNSAT` only when all bounded assignments reject it.
8. Emit the canonical predicate digest and procedure result.

#### Worked budget example

An `Int` variable `x` with domain `[0,999999]` has one million possible values, which exceeds both the D0 default assignment budget and the D1 default assignment budget. The conjunctive predicate `x >= 900000 AND x <= 900010` has a closed-form witness `x=900000`; F2 returns `SAT` without exhausting either budget because no enumeration of the solved variable is required. A residual multi-variable case may still consume the applicable F4 budget.

A predicate is a **tautology / accept-all** exactly when its negation is `UNSAT` over the same bounded domain. A predicate is **contradictory** exactly when it is `UNSAT` over that same bounded domain.

For old predicate `A` and new predicate `B` over the same bounded domain:
- `EQUIVALENT` iff `A AND NOT(B)` and `B AND NOT(A)` are both `UNSAT`.
- `TIGHTENING` iff `B AND NOT(A)` is `UNSAT` and `A AND NOT(B)` is `SAT`.
- `WEAKENING` iff `B AND NOT(A)` is `SAT`.
- Anything admitted by the new predicate that the old predicate rejected is `WEAKENING`.
- A widened variable domain is `WEAKENING`.
- Adding, removing or retyping a variable between old and new forms is conservatively `WEAKENING`, even when the predicates otherwise compare as equivalent.

**Two-layer output shape (reviewer clarification, R12).** Layer 1, base evaluation, returns `{base_result: SAT|UNSAT|INCONCLUSIVE, predicate_digest, domain_estimate}` for one predicate over one bounded domain (steps 1-8 above). Layer 2, classification, issues the base queries named above (`NOT(A)` for tautology; `A` for contradiction; `A AND NOT(B)` and `B AND NOT(A)` for old/new comparison) and returns `{classification: TAUTOLOGY|CONTRADICTORY|EQUIVALENT|TIGHTENING|WEAKENING|UNCLASSIFIED, queries:[{query, base_result}]}`. If any required base query is `INCONCLUSIVE`, classification is `UNCLASSIFIED` and routes to a qualified property test or J; it never defaults to a favorable class. An added, removed, retyped or widened variable is `WEAKENING` without issuing queries. F2-T5, F2-T6 and F2-T10 expect the layer-2 `classification`; the layer-1 `base_result` for each is `SAT` or `UNSAT` as the tests list.

### False-UNSAT guard

Reduction is never distributive over disjunction. For example, `(x EQUALS 1 OR x EQUALS 2) AND x EQUALS 2` is `SAT`; an incorrect reducer that merges the OR alternatives as though they were conjunctive would falsely report `UNSAT`.

### Consumer mapping

The procedure result is distinct from the consumer gate. Every consumer has a deterministic output for the result classes it consumes. For weakening control, `WEAKENING` is `BLOCKED_ON_HUMAN[PD-F1-005]` without a bound authoritative approval and `SATISFIED` only with such approval; this matches F1-T5, F1-T6 and F1-T8.

| Procedure result | P3 invariant check | F1 adequacy | F1 weakening control |
|---|---|---|---|
| `SAT` | `SATISFIED` | `SATISFIED` when adequacy conditions also hold | no weakening decision |
| `UNSAT` | `MISSING[PD-CH2-020]` | `MISSING[PD-F1-004]` | no weakening decision |
| `INCONCLUSIVE` | `BLOCKED_ON_HUMAN[PD-CH2-020]` unless a qualified property/J result closes it | `BLOCKED_ON_HUMAN[PD-F1-004]` until adequacy is decided | `BLOCKED_ON_HUMAN[PD-F1-005]` when weakening classification is required but unresolved |
| `TAUTOLOGY` | `SATISFIED` for bounded satisfiability; non-vacuity remains separate | `MISSING[PD-F1-004]` | no weakening decision |
| `CONTRADICTORY` | `MISSING[PD-CH2-020]` | `MISSING[PD-F1-004]` | no weakening decision |
| `EQUIVALENT` | no consumer decision | no consumer decision | `SATISFIED` |
| `TIGHTENING` | no consumer decision | no consumer decision | `SATISFIED` |
| `WEAKENING` | no consumer decision | no consumer decision | `BLOCKED_ON_HUMAN[PD-F1-005]` without bound authoritative approval; `SATISFIED` with bound authoritative approval |

### MUSTs

| ID | Class | Requirement | Test |
|---|---|---|---|
| PD-F2-001 | M | F2 predicates MUST conform to the closed grammar, finite types, precedence, associativity and canonical surface mapping. | F2-T1 valid canonical input and token stream → `SAT`; F2-T2 malformed token stream / forbidden construct → `MISSING[PD-F2-001]`. |
| PD-F2-002 | M | Every mechanically decided scalar or collection variable MUST have an explicit finite domain; interval/set reduction MUST preserve the bounded model set, apply only to top-level conjunctive atoms, and solve single-variable subformulas using the closed-form rule in step 5 before residual enumeration. | F2-T3 unbounded integer → `MISSING[PD-F2-002]`; F2-T11 false-UNSAT guard → `SAT`. |
| PD-F2-003 | M/E | The reference evaluator MUST return `SAT` only for a satisfying bounded assignment, `UNSAT` only after complete bounded evaluation, and `INCONCLUSIVE` when the evaluation budget expires first. | F2-T4 truncated search → `INCONCLUSIVE`, never `SAT`/`UNSAT`; contradictory fixture in F2-FT5 → correct `UNSAT`. |
| PD-F2-004 | M/E | Tautology, contradiction and old/new classification MUST use the same declared bounded model domain, with `EQUIVALENT`, `TIGHTENING` and `WEAKENING` defined as stated. | F2-T5 tautology → F1 `MISSING[PD-F1-004]`; F2-T6 classification/control fixture. |
| PD-F2-005 | E/J | Temporal, unbounded or otherwise out-of-fragment predicates MUST route to a qualified property/stateful test or J. | F2-T7 temporal predicate without qualified adapter → `BLOCKED_ON_HUMAN[PD-F2-005]`. |
| PD-F2-006 | M/E | Every qualified F2 adapter MUST match the reference evaluator on small conformance fixtures, MUST use the applicable F4 evaluation budget, and MUST return `INCONCLUSIVE` on budget exhaustion. | F2-T8 differential fixture passes only when all reference outputs match. |
| PD-F2-007 | M | F2 canonical bindings MUST resolve to frozen Requirement, Constraint, AcceptanceContract and VerificationStep objects; digest-bound confirmation is governed by F3. | F2-T9 frozen-object bindings resolve; digest-bound confirmation of those objects is tested in F3-T4. |

### Tests

| Test | Procedure result | Consumer gate mapping |
|---|---|---|
| F2-T1 | `SAT` | P3 `SATISFIED`; F1 adequacy `SATISFIED` |
| F2-T2 | parser/type failure | `MISSING[PD-F2-001]` |
| F2-T3 | type/bound error | `MISSING[PD-F2-002]` |
| F2-T4 | `INCONCLUSIVE` | P3 `BLOCKED_ON_HUMAN[PD-CH2-020]`; F1 adequacy `BLOCKED_ON_HUMAN[PD-F1-004]` when unresolved |
| F2-T5 | `TAUTOLOGY`; contradiction subcase = `UNSAT` | F1 adequacy `MISSING[PD-F1-004]`; contradictory subcase P3 `MISSING[PD-CH2-020]` |
| F2-T6 | `EQUIVALENT`, `TIGHTENING`, `WEAKENING` | weakening: `BLOCKED_ON_HUMAN[PD-F1-005]` without approval; `SATISFIED` with bound approval |
| F2-T7 | out of v1 temporal fragment | `BLOCKED_ON_HUMAN[PD-F2-005]` |
| F2-T8 | complete reference/differential match | `SATISFIED` only on complete match |
| F2-T9 | frozen binding resolution | `SATISFIED` |
| F2-T10 | F2-FT10 token-level cases (`IDENT`, `DIGIT`, `string_char`, quoted-string, set-literal) and large-domain compound formulas over `x: Int[0,999999]` | `SATISFIED` for valid tokens; `MISSING[PD-F2-001]` for invalid token; `(x < 500000 OR NOT(x < 500000))` classifies `TAUTOLOGY` (F1 adequacy `MISSING[PD-F1-004]`); old `x < 900000` to new `(x < 900000 OR NOT(x < 900000))` classifies `WEAKENING` (`BLOCKED_ON_HUMAN[PD-F1-005]` without approval) |
| F2-T11 | F2-FT11 false-UNSAT guard: `(x >= 0) AND (x <= 4)` over x in 0..4 | optimized and reference both `SAT`; `SATISFIED` |
| F2-T12 | F2-FT12 compound OR `(x = 2) OR (x = 7)`: optimized `UNSAT`, reference `SAT` | `MISSING[PD-F2-002]` |
| F2-T13 | F2-FT13 residual cross-variable atom `x < y` with residual enumeration not completed | base `INCONCLUSIVE` (PD-F2-003); P3 `BLOCKED_ON_HUMAN[PD-CH2-020]`; an optimized `SAT` is not accepted |
| F2-T14 | F2-FT14 domain widening with no structural diff and agent claim `equivalent` | classification `WEAKENING` (PD-F2-004); without approval `BLOCKED_ON_HUMAN[PD-F1-005]` |

### Kernel binding

F2 binds to the frozen `Requirement` definition `00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md` §3 L1273-L1280 "@dataclass(frozen=True)", `Constraint` §3 L1288-L1295 "@dataclass(frozen=True)", `AcceptanceContract` §5.2 L2021-L2028 "@dataclass(frozen=True)", and `VerificationStep` §5.2 L2039-L2047 "@dataclass(frozen=True)". The cited frozen objects remain authority structures; F2 adds only product-layer predicate semantics.

F2 also consumes the frozen evidence/acceptance pipeline: `05-VERIFICATION/S-CLASS-VERIFICATION-AND-EVIDENCE-SPEC.md` §4 L60-L78 "## 4. Evidence identity" and §5 L80-L93 "## 5. Evidence is not acceptance". Digest-bound confirmation is a forward dependency on F3 and is not defined by F2.

**Who may write:** the parser/evaluator writes procedure results; agents may submit candidate predicates; only the normal S-Class authority path may bind a predicate to a canonical obligation.

### NEVER

F2 MUST NEVER interpret prose as a predicate, treat OR alternatives as conjunctive, silently widen a domain, treat `INCONCLUSIVE` as `SAT` or `UNSAT`, substitute an unqualified temporal evaluator, persist a second canonical constraint store, or treat agent-authored syntax as authority.

### Cost bound

Parsing/canonicalization is linear in input length. Top-level single-variable interval/set reduction is polynomial in atom count. Closed-form witness search avoids enumeration for solved variables. Residual enumeration is bounded by the product of declared scalar/set/list domain sizes and the applicable F4 assignment budget. Adapter comparison is bounded to the declared small conformance fixtures; budget overflow is a hard stop.

**State:** DESIGNED; not VERIFIED.



---

## Authoritative F2 Test Fixtures (F2-T1 through F2-T14)

### F2-T1 / F2-FT1 — valid token stream and bounded predicate
```yaml
input_tokens: [IDENT(x), GREATER_OR_EQUAL, INTEGER(1), AND, IDENT(x), LESS_THAN, INTEGER(5)]
string_tokens: [IDENT(name), EQUALS, QUOTED_STRING("abc"), IN, SET_OPEN, IDENT(A), COMMA, IDENT(B), SET_CLOSE]
identifier_tokens: [IDENT(alpha_1), IDENT(B2)]
string_char_tokens: [ESCAPED_QUOTE, ESCAPED_BACKSLASH]
schema:
  x: {type: Int, domain: [0, 1, 2, 3, 4, 5]}
predicate: "x GREATER_OR_EQUAL 1 AND x LESS_THAN 5"
expected_parse: valid
expected_procedure_result: SAT
expected_gate_output: SATISFIED
```

### F2-T2 / F2-FT2 — malformed token / forbidden construct
```yaml
case_1:
  input_tokens: [IDENT(x), AND, AND, INTEGER(1)]
  expected_parse: invalid
case_2:
  input_tokens: [FORALL, LPAREN, IDENT(x), COMMA, INTEGER(1), RPAREN]
  expected_parse: invalid
expected_gate_output: MISSING[PD-F2-001]
```

### F2-T3 / F2-FT3 — unbounded integer
```yaml
schema:
  x: {type: Int}
predicate: "x EQUALS 1"
expected_gate_output: MISSING[PD-F2-002]
```

### F2-T4 / F2-FT4 — truncated residual search
```yaml
schema:
  x: {type: Int, domain: [0, 1, 2, 3]}
  y: {type: Int, domain: [0, 1, 2, 3]}
predicate: "x NOT_EQUALS y"
evaluation_budget_assignments: 1
expected_procedure_result: INCONCLUSIVE
expected_gate_output: BLOCKED_ON_HUMAN[PD-CH2-020]
```

### F2-T5 / F2-FT5 — tautology and contradiction
```yaml
tautology:
  schema: {x: {type: Int, domain: [0, 1]}}
  predicate: "TRUE"
  negation: "FALSE"
  negation_result: UNSAT
  expected_procedure_result: TAUTOLOGY
  expected_gate_output: MISSING[PD-F1-004]
contradiction:
  schema: {x: {type: Int, domain: [0, 1]}}
  predicate: "x GREATER_THAN 1 AND x LESS_THAN 1"
  expected_procedure_result: UNSAT
  expected_gate_output: MISSING[PD-CH2-020]
```

### F2-T6 / F2-FT6 — weakening classifications, approval control, variable changes, false-UNSAT guard
```yaml
same_domain_cases:
  equivalent:
    old: "x LESS_OR_EQUAL 10"
    new: "x LESS_OR_EQUAL 10"
    domain: {x: [0, 20]}
    expected: EQUIVALENT
  tightening:
    old: "x LESS_OR_EQUAL 10"
    new: "x LESS_OR_EQUAL 5"
    domain: {x: [0, 20]}
    expected: TIGHTENING
  weakening_without_approval:
    old: "x LESS_OR_EQUAL 10"
    new: "x LESS_OR_EQUAL 20"
    domain: {x: [0, 20]}
    authoritative_approval: null
    expected_classification: WEAKENING
    expected_gate_output: BLOCKED_ON_HUMAN[PD-F1-005]
  weakening_with_bound_approval:
    old: "x LESS_OR_EQUAL 10"
    new: "x LESS_OR_EQUAL 20"
    domain: {x: [0, 20]}
    authoritative_approval: DECISION-42
    expected_classification: WEAKENING
    expected_gate_output: SATISFIED
  structural_diff_unavailable:
    old: "x LESS_OR_EQUAL 10"
    new: "x LESS_OR_EQUAL 20"
    domain: {x: [0, 20]}
    structural_diff_procedure: null
    authoritative_approval: null
    expected_classification: WEAKENING
    expected_gate_output: BLOCKED_ON_HUMAN[PD-F1-005]
  widened_domain:
    old: "x LESS_OR_EQUAL 10"
    new: "x LESS_OR_EQUAL 10"
    old_domain: {x: [0, 20]}
    new_domain: {x: [0, 30]}
    expected: WEAKENING
variable_change_cases:
  added_variable:
    old_schema: {x: {type: Int, domain: [0, 1]}}
    new_schema: {x: {type: Int, domain: [0, 1]}, y: {type: Int, domain: [0, 1]}}
    expected: WEAKENING
  removed_variable:
    old_schema: {x: {type: Int, domain: [0, 1]}, y: {type: Int, domain: [0, 1]}}
    new_schema: {x: {type: Int, domain: [0, 1]}}
    expected: WEAKENING
  retyped_variable:
    old_schema: {x: {type: Int, domain: [0, 1]}}
    new_schema: {x: {type: Enum, values: [A, B]}}
    expected: WEAKENING
false_unsat_guard:
  schema: {x: {type: Int, domain: [1, 2]}}
  predicate: "(x EQUALS 1 OR x EQUALS 2) AND x EQUALS 2"
  correct_result: SAT
  incorrect_cross_or_merge_result: UNSAT
```

### F2-T7 / F2-FT7 — temporal property routed out of v1
```yaml
schema:
  state: {type: Enum, values: [OPEN, CLOSED]}
predicate: "ALWAYS[2](state EQUALS OPEN)"
qualified_stateful_adapter: null
expected_gate_output: BLOCKED_ON_HUMAN[PD-F2-005]
```

### F2-T8 / F2-FT8 — reference enumerator differential
```yaml
schema:
  x: {type: Int, domain: [0, 1]}
inputs:
  - predicate: "x EQUALS 0"
    reference_result: SAT
    adapter_result: SAT
  - predicate: "x EQUALS 0 AND x EQUALS 1"
    reference_result: UNSAT
    adapter_result: UNSAT
all_small_fixtures_match: true
expected_gate_output: SATISFIED
```

### F2-T9 / F2-FT9 — frozen bindings
```yaml
requirement_ref: REQ-1
constraint_ref: CON-1
acceptance_contract_ref: AC-1
verification_step_ref: VS-1
all_refs_resolve_to_frozen_objects: true
expected_gate_output: SATISFIED
```

### F2-T10 / F2-FT10 — token-level parser and large-domain compound formula
```yaml
token_cases:
  ident: [IDENT(alpha_1), IDENT(B2)]
  digit: [DIGIT(0), DIGIT(9)]
  string_char: [ESCAPED_QUOTE, ESCAPED_BACKSLASH, LETTER(a)]
  quoted_string: QUOTED_STRING("abc")
  set_literal: [SET_OPEN, IDENT(A), COMMA, IDENT(B), SET_CLOSE]
  invalid: [IDENT(x), AND, AND, INTEGER(1)]
large_domain:
  schema: {x: {type: Int, domain: [0, 999999]}}
  tautology: "x LESS_THAN 500000 OR NOT(x LESS_THAN 500000)"
  old_predicate: "x LESS_THAN 900000"
  new_predicate: "x LESS_THAN 900000 OR NOT(x LESS_THAN 900000)"
  tautology_result: TAUTOLOGY
  weakening_result: WEAKENING
  without_approval_gate: BLOCKED_ON_HUMAN[PD-F1-005]
```

### F2-T11 / F2-FT11 — false-UNSAT guard
```yaml
bounded_domain: {x: [0,1,2,3,4]}
predicate: '(x >= 0) AND (x <= 4)'
reference_enumerator_satisfying_assignments: 5
optimized_evaluator_result: SAT
expected_gate_output: SATISFIED
```

### F2-T12 / F2-FT12 — compound OR alternatives are not conjunctive
```yaml
bounded_domain: {x: [0,1,2,3,4,5,6,7,8,9]}
predicate: '(x = 2) OR (x = 7)'
optimized_result: UNSAT
reference_result: SAT
expected_gate_output: MISSING[PD-F2-002]
```

### F2-T13 / F2-FT13 — residual cross-variable atom
```yaml
bounded_domain: {x: [0,1,2], y: [0,1,2]}
predicate: 'x < y'
residual_enumerator_completed: false
optimized_result: SAT
expected_base_result: INCONCLUSIVE
expected_gate_output: BLOCKED_ON_HUMAN[PD-CH2-020]
```

### F2-T14 / F2-FT14 — widening requires weakening classification
```yaml
old_domain: {x: [0,1,2]}
new_domain: {x: [0,1,2,3]}
structural_diff: absent
agent_claim: equivalent
expected_classification: WEAKENING
expected_gate_output: BLOCKED_ON_HUMAN[PD-F1-005]
```


