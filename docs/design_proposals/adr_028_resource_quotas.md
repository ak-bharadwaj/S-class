# ADR-028: Resource Quota Scheduling and Rate Limiting

## Status
Accepted

## Context
Runaway recursive agent loops can exhaust API rate limits, disk space, and cloud compute budgets.

## Decision
S-Class enforces hard resource caps per agent session, halting execution when quotas are exceeded.
