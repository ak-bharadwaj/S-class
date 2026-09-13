# S-Class Trust Model

## 1. Cryptographic Ledger & Hash Chain

S-Class records all state transitions, actions, observations, and verification verdicts in an append-only, tamper-evident local ledger (`LocalLedger`).

### Hash Chain Mechanics
Each event $E_i$ recorded in the ledger computes its event hash as:
$$H_i = \text{SHA256}(H_{i-1} \parallel \text{canonical\_json}(E_i))$$
where $H_0$ is the genesis hash.

If any historical record is modified, inserted, or deleted, the hash chain breaks at that index, and `LocalLedger.verify()` fails.

## 2. Evidence Receipts (`EvidenceReceipt`)

Evidence receipts are issued strictly by `TrustedObservationRuntime` / `ObservationFactory`.
- **Receipt Fields**: `receipt_id`, `task_id`, `claim_id`, `agent`, `action`, `workspace`, `command`, `exit_code`, `stdout_hash`, `stderr_hash`, `execution_kind`, `verifier`, `workspace_fingerprint`, `timestamp`.
- **Sealed Immutability**: Evidence receipts employ `_sealed = True`. Any attempt by an agent or rogue component to mutate fields post-issuance raises an `AttributeError`.
- **Pre-publication Commitment**: Before any receipt is returned to a caller or stored in project state, it is atomically committed to the ledger via `append_atomic()`.

## 3. Trust Anchors & Auditing

`TrustAnchor` persists cryptographic roots across sessions:
- Records checkpoint hash, ledger head hash, and workspace fingerprint.
- `LedgerIntegrityAuditor` validates ledger consistency against trust anchors.
- In case of external tampering, `repair()` classifies status as `CORRUPTED`, `FORKED`, or `RECOVERED_FROM_SNAPSHOT`.
