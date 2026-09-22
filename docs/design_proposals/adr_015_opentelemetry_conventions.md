# ADR-015: OpenTelemetry Distributed Tracing Conventions

## Status
Accepted

## Context
Tracing agent actions requires standardized span naming and semantic conventions.

## Decision
All spans adopt the `sclass.*` prefix. Spans record physical exit codes, stdout hashes, and token costs.
