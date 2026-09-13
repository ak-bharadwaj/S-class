# S-Class Task & Verification Lifecycle

## 1. End-to-End Operation Flow

```text
+-------------------+
|    Agent / IDE    |
+-------------------+
          |
          | 1. ActionRequest (e.g. edit, run command)
          v
+-------------------+
|   Authorization   | ---> PolicyEngine enforces boundaries & capabilities
+-------------------+
          |
          | 2. Approved Action
          v
+-------------------+
|  Actual Execution | ---> ProcessRunner invokes process, captures child PID & binary hash
+-------------------+
          |
          | 3. OS Observation
          v
+-------------------+
| Observation Runtime| ---> Records exit code, stdout/stderr, file hashes
+-------------------+
          |
          | 4. Atomic Commit
          v
+-------------------+
| Cryptographic     | ---> Ledger appends event into hash chain
| Ledger            |
+-------------------+
          |
          | 5. Sealed EvidenceReceipt
          v
+-------------------+
| Verification      | ---> Identifies real verifier plugin, parses structured results
| Engine            |
+-------------------+
          |
          | 6. Claim Assessment
          v
+-------------------+
| Verified Project  | ---> Updates checkpoint, project state, task status
| State             |
+-------------------+
          |
          | 7. Cross-Agent Handoff
          v
+-------------------+
| Successor Agent   | ---> Receives tamper-evident state, cryptographic proof
+-------------------+
```

## 2. Staleness Cascades

If an agent or external actor mutates any file within the workspace after a verification has completed:
- S-Class computes the workspace fingerprint (hash of tracked workspace files).
- If the fingerprint changes, previously verified claims referencing those files or tasks enter `STALE` status.
- Next actions require re-verification or explicit invalidation handling.
