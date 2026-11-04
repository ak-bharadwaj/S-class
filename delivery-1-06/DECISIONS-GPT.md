# Section F6 Freshness Remediation — Normative Decisions & Architecture Register (GPT-LPC)

**Branch:** `lane-a-f6-fix`  
**Base Commit (Parent):** `128b96997e44b9d54e7aa5e7e49f7ce0a69860a5` (`origin/integration-r30-b1`)  
**Implementation Commit (C):** `093522cdcc6de64bbc8968b9af90463c26818649`  
**Normative Reference:** R30 Master Product Design (FREEZE-CANDIDATE-v6.0.2), Section F6 Traceability Links & Computed Coverage.  
**Obligations Covered:** PD-F6-001 through PD-F6-006.

---

## 1. Architectural Context & Vulnerability Remediation

Section F6 traceability verification previously contained a fail-open defect in `evaluate_f6_traceability`: when the caller omitted the `freshness_predicate` argument, the evaluator defaulted to `True` for unmapped link endpoints, allowing candidate artifacts to achieve `SATISFIED` coverage without authentic external freshness authority.

CL and GPT Lane Commander governance issued an immediate remediation directive mandating strict fail-closed freshness enforcement with exclusive caller-injected authority.

---

## 2. Normative Decisions Register

### Decision 1: Exclusive Caller-Injected Freshness Authority
- **Normative Rule:** Freshness acceptance requires a caller-injected `freshness_predicate: Callable[[str], bool]`.
- **Enforcement:** If `freshness_predicate is None` or `not callable(freshness_predicate)`, `evaluate_f6_traceability` fails closed immediately with `GateOutput(GateState.MISSING, must_id="PD-F6-005", detail="Freshness predicate must be caller-injected; candidate freshness values confer no authority")`.
- **Anti-Gaming:** Candidate-embedded predicates in the payload (`spec["freshness_predicate"]`) are completely ignored and confer zero authority.

### Decision 2: Endpoint-Level Freshness Enforcement
- **Normative Rule:** Every endpoint in every declared link (`link.source` and `link.destination`) must be validated against `check_endpoint_freshness`.
- **Enforcement:** No endpoint can inherit freshness from a payload field, omission, or missing mapping entry. Every endpoint is explicitly submitted to the caller-injected predicate.

### Decision 3: Strict Boolean Return Validation & Exception Handling
- **Normative Rule:** An injected predicate return value must be strictly `type(res) is bool and res is True`.
- **Enforcement:** Return values of `False`, `None`, integers `0`/`1`, strings `"true"`/`"False"`, or collections `[]`/`{}` fail closed with `MISSING[PD-F6-005]`.
- **Exception Safety:** Any exception raised by `freshness_predicate` is caught via `try...except Exception` and fails closed with `MISSING[PD-F6-005]`, preventing unhandled crashes and guaranteeing no candidate can bypass evaluation via an exception.

### Decision 4: Asymmetric Candidate Restrictions
- **Normative Rule:** Candidate payload freshness fields can make evaluation stricter, never grant freshness.
- **Enforcement:**
  - If candidate specifies `source_fresh is False` for `source_digest`, `destination_fresh is False` for `destination_digest`, or `freshness_map.get(nid) is False`, the endpoint is marked stale, even if the injected predicate returns `True`.
  - Conversely, candidate claims of `True` (e.g., `freshness_map = {nid: True}`, `source_fresh = True`) confer zero authority and cannot satisfy freshness without confirmation from the injected predicate.

### Decision 5: Consumption in Coverage Traversal
- **Normative Rule:** Coverage computation (`compute_chain_coverage`) must strictly consume the validated `is_fresh` checker with zero default-to-True fallback.
- **Defense in Depth:** All chain nodes (Requirements, Acceptance Criteria, Verification Steps, Tests, Evidence, Obligations) undergo freshness checking. Any stale node encountered triggers fail-closed rejection under `PD-F6-005`.

---

## 3. Normative MUST Mapping Summary

| MUST ID | Description | Remediation Status |
| :--- | :--- | :--- |
| **PD-F6-001** | Structured traceability spec, non-empty mapping, caller-injected `SourceRefResolver` required, explicit typed links required, heuristic name matching strictly forbidden. | Preserved & enforced fail-closed. |
| **PD-F6-002** | Orphan node detection (unlinked requirements, orphan verification steps, unlinked evidence). | Preserved & verified under injected predicate. |
| **PD-F6-003** | RFC 8785 C1 canonical SHA-256 stable link identity across revisions. | Preserved (deterministic golden hash verified). |
| **PD-F6-004** | Agent-asserted coverage anti-gaming; broken chains reject asserted coverage. | Preserved & verified fail-closed. |
| **PD-F6-005** | Caller-injected freshness predicate required; strict boolean validation; payload fields confer no freshness; exception handling fails closed; candidate stale flags make checks stricter. | Remediated & verified (10/10 probes, 10/10 mutants killed). |
| **PD-F6-006** | Realized vs planned coverage computation consumes verified freshness with zero default-to-True paths. | Remediated & verified. |
