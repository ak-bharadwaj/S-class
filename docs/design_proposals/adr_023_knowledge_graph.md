# ADR-023: Codebase Knowledge Graph Entity Resolution

## Status
Accepted

## Context
Polyglot repositories require disambiguating identical symbol names across Python, TypeScript, and Rust.

## Decision
S-Class indexes symbols with fully-qualified URI namespaces (`lang://package/module/symbol`).
