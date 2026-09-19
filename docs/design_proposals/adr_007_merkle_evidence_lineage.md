# ADR-007: Cryptographic Merkle Root Evidence Lineage

## Status
Accepted

## Context
Audit trails must provide non-repudiation and proof that past evidence receipts were not altered after the fact.

## Decision
Every evidence receipt includes the SHA-256 digest of its immediate parent receipt, forming an append-only Merkle chain.
Periodic checkpoints publish root hashes to durable project metadata.
