# ADR-010: Zero-Trust Secret Scanning and In-Memory Redaction

## Status
Accepted

## Context
Agents routinely output API keys, private certificates, and authentication tokens in prompts and command outputs.

## Decision
All stdout/stderr streams and action parameters pass through a high-throughput regex and entropy scanner before persistence.
Identified secrets are redacted with SHA-256 HMAC fingerprints.
