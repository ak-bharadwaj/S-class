# ADR-025: Workspace Preflight Health Auditing

## Status
Accepted

## Context
Running agents in dirty or corrupted workspaces leads to unpredictable results.

## Decision
Before granting execution authorization, S-Class performs preflight checks: git clean status, disk space, and compiler health.
