# Guide: Writing Custom Verifiers in S-Class

Custom verifiers extend S-Class's verification hierarchy to support new testing frameworks, linters, or formal provers.

## 1. Implement Verifier Interface
Each verifier must implement the `execute_and_observe()` lifecycle:
1. Verify executable hash against trusted registry.
2. Execute target tool in isolated sandbox.
3. Parse structured machine output (JUnit XML, TAP, JSON).
4. Return an immutable `IndependentAssessment`.
