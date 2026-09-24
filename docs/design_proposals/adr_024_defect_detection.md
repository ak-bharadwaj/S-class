# ADR-024: Automated Defect Detection and Mutation Analysis

## Status
Accepted

## Context
Standard line coverage metrics give false confidence if tests do not assert actual semantic mutations.

## Decision
S-Class integrates mutation testing (Cosmic Ray, Mutmut) to guarantee test suites detect subtle logic bugs.
