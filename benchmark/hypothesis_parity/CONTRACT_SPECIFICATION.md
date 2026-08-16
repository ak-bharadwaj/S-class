# S-Class EOS — Gate 2: Hypothesis Behavioral Contract Specification

**Status**: FROZEN BEHAVIORAL CONTRACT  
**Reference Version**: `hypothesis==6.165.9`  
**Target Scope**: Property Testing & Invariant Verification Engine

---

## 1. Separation of Guarantees

To ensure rigorous differential verification without over-specifying or confounding external tool nuances with internal engineering standards, specifications are divided into two distinct tiers:

### Tier 1: Reference-Conformance Guarantees (Hypothesis Semantics)
1. **Domain Invariant Adherence**: For every strategy $S(C)$ bounded by constraints $C$, every generated input $x$ MUST strictly satisfy $C$ ($x \in \text{Domain}(S)$).
2. **Falsification Detection**: If a target property $P$ fails on a domain element ($P(x) = \text{False}$), the testing campaign MUST identify a failing input with high probability.
3. **Shrink Failure Preservation**: The shrunk counterexample $x_{\text{shrunk}}$ MUST satisfy $P(x_{\text{shrunk}}) = \text{False}$.
4. **Shrink Reduction Monotonicity**: The shrunk counterexample MUST be no larger than the initial counterexample from which shrinking began:
   $$\text{Size}(x_{\text{shrunk}}) \le \text{Size}(x_{\text{initial}})$$
5. **Filter Exclusion**: For any strategy with a predicate filter $S.\text{filter}(\text{pred})$, NO generated example where $\text{pred}(x) = \text{False}$ shall ever be passed to the test property.
6. **Exception Categorization**: Failures are classified by standard exception categories (`AssertionError`, `TypeError`, `ValueError`, `TimeoutError`, etc.) rather than implementation-specific message strings.

### Tier 2: S-Class Quality & Performance Requirements (Engineering Constraints)
1. **Deterministic Replay**: Under a fixed PRNG seed $s$, an implementation MUST deterministically regenerate its own exact sequence of inputs $[e_1, e_2, \dots, e_N]$. Replaying on the captured counterexample MUST reproduce the failure with zero variance.
2. **Boundary-Biased Exploration**: In campaigns with $N \ge 20$ iterations, the initial segment (first 10% of examples or first 5 iterations) MUST explore domain extrema (e.g., $0, \pm 1, \text{MIN\_INT}, \text{MAX\_INT}, \text{""}, \text{NaN}, \pm\infty$). *(Note: This is an S-Class requirement, not a reference guarantee).*
3. **Shrinking Search Bound**: Shrinking MUST terminate within $\le 500$ property evaluations per failure to prevent unbounded search latencies. *(S-Class acceptance criterion).*
4. **Self-Contained Ephemeral Receipts**: Serialized counterexamples and reproduction metadata MUST be standalone and executable in-memory without requiring on-disk `.hypothesis` cache directories.

---

## 2. Formal Complexity Metric $\text{Size}(x)$

For any generated value $x$, its complexity metric is defined mathematically as:

- **Integers**: $\text{Size}(x) = |x|$
- **Floats**: $\text{Size}(x) = |x|$ if finite, else $\infty$
- **Strings**: $\text{Size}(x) = (\text{len}(x), \sum_{c \in x} \text{ord}(c))$
- **Lists / Tuples**: $\text{Size}(x) = (\text{len}(x), \sum_{item \in x} \text{Size}(item))$
- **Dictionaries**: $\text{Size}(x) = (\text{len}(x), \sum_{(k, v) \in x} (\text{Size}(k) + \text{Size}(v)))$

Comparisons are evaluated lexicographically.

---

## 3. Observation Data Model

The reference adapter and any candidate implementation MUST emit normalized observations conforming to the following immutable schema:

```json
{
  "engine_name": "string",
  "verdict": "PASS | FAIL | ERROR",
  "cases_executed": "int",
  "initial_counterexample": "Optional[dict]",
  "shrunk_counterexample": "Optional[dict]",
  "exception_class": "Optional[str]",
  "exception_message": "Optional[str]",
  "shrink_evaluations": "int",
  "initial_size": "Optional[float | list]",
  "shrunk_size": "Optional[float | list]",
  "execution_time_ns": "int"
}
```

---

## 4. Independent Differential Oracle Contract

The differential oracle MUST NOT trust self-reported verdicts from either implementation.

For every evaluation:
1. **Independent Failure Verification**: When an observation claims `FAIL`, the Oracle directly executes $P(x_{\text{initial}})$ and $P(x_{\text{shrunk}})$ in an isolated harness and asserts that both raise or return `False`.
2. **Independent Pass Verification**: When an observation claims `PASS`, the Oracle asserts that no counterexample was emitted and validates sample inputs against domain constraints.
3. **Independent Shrink Validation**: The Oracle computes $\text{Size}(x_{\text{shrunk}})$ and $\text{Size}(x_{\text{initial}})$ and verifies $\text{Size}(x_{\text{shrunk}}) \le \text{Size}(x_{\text{initial}})$.
4. **Comparative Analysis**: The Oracle compares Reference vs Candidate on:
   - Verdict Agreement: $\text{Verdict}_{\text{ref}} == \text{Verdict}_{\text{cand}}$
   - Semantic Preservation: Both independently falsified $P$
   - Shrink Quality: Relative reduction ratio $\frac{\text{Size}(x_{\text{shrunk}})}{\text{Size}(x_{\text{initial}})}$
   - Shrink Evaluation Count: $\text{Count}_{\text{cand}} \le 500$
