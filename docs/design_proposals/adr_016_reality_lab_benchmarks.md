# ADR-016: Reality Lab 10-Tier Empirical Benchmark Architecture

## Status
Accepted

## Context
Marketing benchmarks (HumanEval, SWE-bench) test synthetic completion rather than full interactive developer experience.

## Decision
The Reality Lab evaluates 10 complexity tiers (T1 trivial edit to T10 adversarial penetration) measuring wall-clock time, token ratio, and regressions.
