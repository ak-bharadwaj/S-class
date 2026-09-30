# Fleet Intelligence — Assumption Graphs & Symbol Leases

## 1. Symbol Leases
When multiple autonomous agents edit a repository concurrently:
- Each agent must acquire an exclusive lease on code symbols or file paths.
- Leases are indexed with microsecond precision in SQLite.
- Overlapping lease attempts fail closed with `LeaseConflictError`.

## 2. Assumption Graphs
- If Agent B relies on an assumption published by Agent A:
  `AssumptionNode(source='Agent A', statement='API auth token conforms to RFC 6750')`
- If Agent A subsequently invalidates this statement or changes the signature:
  The assumption graph triggers an automatic cascading invalidation across Agent B's tasks.
