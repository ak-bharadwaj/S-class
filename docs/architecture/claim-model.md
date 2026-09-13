# S-Class Claim Model

## 1. Claims as Formal Assertions

A `Claim` in S-Class is a typed, scoped proposition submitted by an agent or IDE regarding the state of a task or workspace.
Agent claims are hypotheses, not facts.

### Claim Structure
```python
class Claim:
    claim_id: str
    task_id: str
    statement: str
    claim_type: str  # test_pass, typecheck, lint, security, behavior, feature, docs, git
    scope: Optional[ClaimScope]  # Bound target files, test targets, semantic boundaries
    confidence: float
    metadata: Dict[str, Any]
```

## 2. Claim Scopes (`ClaimScope`)

`ClaimScope` establishes the exact semantic perimeter of a claim:
- `target_files`: Specific source files modified or asserted.
- `test_files`: Specific test files that must be executed.
- `test_identifiers`: Individual test names (e.g., `tests/test_auth.py::test_login`).
- `command_patterns`: Permitted command lines.

If a test runner runs only a subset of tests, or tests completely different files from what the claim asserts, `ClaimScope` detects the mismatch and rejects or flags the evidence as insufficient.

## 3. Claim Lifecycle

1. `PROPOSED`: Agent formulates a claim based on completed work.
2. `EVALUATED`: Claim evaluated against observed receipts using the `ClaimAcceptanceMatrix`.
3. `VERIFIED (ACCEPTED)`: Evidence strictly satisfies requirements.
4. `REJECTED`: Contradicted by observed evidence (e.g. non-zero exit code, test failures, scope mismatch).
5. `INCONCLUSIVE`: Execution was observed, but evidence is insufficient or irrelevant to prove the semantic proposition (`EXECUTION_VERIFIED != CLAIM_VERIFIED`).
