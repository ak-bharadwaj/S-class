# Architecture: Claim / Evidence Lifecycle

## 1. Claim State Machine

Claims follow a deterministic, monotonic lifecycle:

```text
              PROPOSED
                 |
                 v
             SUPPORTED
                 |
                 v
             VERIFIED <----+
                 |         | (Re-verification)
                 v         |
               STALE ------+
                 |
                 v
              FAILED / SUPERSEDED
```

Allowed transitions are strictly validated by `validate_claim_transition()`.

## 2. Dependency Structure

```text
CLAIM
  |
  +-- Technical Obligation Reference
  |
  +-- Evidence Requirements (Mandatory typed evidence)
  |
  +-- Independent Evidence Receipts (Cryptographically signed)
  |
  +-- Independent Verifier (Typed verification domain)
  |
  +-- Dependencies (AST symbols, files, upstream claims)
```

A claim reaches `VERIFIED` status ONLY when all mandatory `EvidenceRequirement`s are satisfied by independently verified `EvidenceReceipt` records.
