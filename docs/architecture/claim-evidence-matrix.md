# S-Class Claim-to-Evidence Acceptance Matrix

The following matrix governs the minimum required evidence kind and default verdict when evidence is missing, mismatched, or insufficient.

| Claim Type | Minimum Required Evidence | Default Missing / Mismatch Verdict | Policy Description |
|---|---|---|---|
| `test_pass` | `STRUCTURED_TEST_RESULTS` | `REJECT` | Test execution claims require authorized test runner execution with 0 failures. |
| `typecheck` | `OBSERVED_EXECUTION` | `REJECT` | Typecheck claims require verified execution of mypy, tsc, or pyright. |
| `lint` | `OBSERVED_EXECUTION` | `REJECT` | Linting claims require verified execution of ruff, eslint, or flake8. |
| `security` | `SECURITY_VERIFIER` | `INCONCLUSIVE` | Security claims require security verifiers (bandit, snyk, pip-audit); generic commands are inconclusive. |
| `behavior` | `BEHAVIOR_EVIDENCE` | `INCONCLUSIVE` | Semantic behavior claims require behavioral contract tests; generic execution is inconclusive. |
| `feature` | `BEHAVIOR_EVIDENCE` | `INCONCLUSIVE` | Feature claims require behavioral test coverage; generic exit-code 0 commands are inconclusive. |
| `correctness`| `BEHAVIOR_EVIDENCE` | `INCONCLUSIVE` | Correctness claims require semantic verification; generic execution is inconclusive. |
| `docs` | `TARGET_FILE_EVIDENCE` | `REJECT` | Documentation claims require verified diffs in documentation files. |
| `deployment` | `OBSERVED_EXECUTION` | `REJECT` | Deployment claims require observed deployment pipeline execution. |
| `git` | `OBSERVED_EXECUTION` | `REJECT` | VCS / Git claims require observed git command execution. |

### Core Principle
**`EXECUTION_VERIFIED != CLAIM_VERIFIED`**
A command returning exit code 0 (e.g. `echo success` or `ls`) proves only that the process ran, not that an authentication module works, security flaws were fixed, or features are functional.
