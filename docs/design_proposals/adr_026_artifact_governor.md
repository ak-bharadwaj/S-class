# ADR-026: Artifact Governor and Tamper-Resistant Storage

## Status
Accepted

## Context
Build artifacts and test logs must be protected against malicious tampering or unintentional overwrite by agents.

## Decision
All generated artifacts are checksummed with SHA-256 and locked with read-only filesystem attributes.
