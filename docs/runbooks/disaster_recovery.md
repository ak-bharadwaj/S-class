# Disaster Recovery & State Reconstruction Runbook

## 1. Principles
S-Class maintains durable truth in immutable JSONL ledgers.
Derived SQLite indexes and caches are secondary projections that can be rebuilt from scratch.

## 2. State Reconstruction Procedure
```bash
# 1. Stop active agent processes
sclass stop --all

# 2. Rebuild SQLite projection from canonical JSONL log
sclass repair --source artifacts/events.jsonl

# 3. Validate Merkle tree integrity
sclass verify --deep
```
