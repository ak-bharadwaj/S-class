# SYNTHETIC MASTER PRODUCT DESIGN DOCUMENT (FOR UNIT TESTS)
<!-- Version: synthetic-1.0.0 -->

## 1. Scope and Synthetic Requirements
| ID | Class | Requirement | Test |
|---|---|---|---|
| PD-SYN-001 | M | Synthetic test requirement for unit testing | SYN-T1 |
| PD-F5-001 | M | Deterministic gate evaluator replay | F5-T1 |

## 2. Normative Test Fixtures

### F5-T1 / F5-FT1 — deterministic replay input
```yaml
phase: P2
expected_gate_output: SATISFIED
```

## Appendix F — Synthetic Fixtures

#### SYN-T1 — gaming fixture for PD-SYN-001
```yaml
must_id: PD-SYN-001
fixture_role: gaming
expected_gate_output: MISSING[PD-SYN-001]
```

#### SYN-T2 — happy fixture for PD-SYN-001
```yaml
must_id: PD-SYN-001
fixture_role: happy
expected_gate_output: SATISFIED
```
