# ADR-001: Separation of Epistemic Observation from Agent Claims

## Status
Accepted

## Context
Autonomous coding agents frequently make claims regarding test success, syntax correctness, and security invariants.
Treating agent assertions as ground truth introduces severe hallucination and sycophancy vulnerabilities.

## Decision
We decouple epistemic observation from agent claims. Agent assertions are classified as untrusted claims (V0).
Durable state mutations require independent physical observation by S-Class observers (V1-V7).

## Consequences
- Verifiers must independently inspect exit codes, file diffs, and process trees.
- Agent narrative memory cannot overwrite verified project state.
