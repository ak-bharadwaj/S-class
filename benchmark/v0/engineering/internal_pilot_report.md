# Internal Real-Workflow Pilot Decision Report

**Task Target**: `INTERNAL_PILOT_CONFIG_GC` (`config_gc.py` Artifact Lifecycle & Integrity)  
**Starting Base**: SHA [`75ae7cf`](https://github.com/ak-bharadwaj/S-class/commit/75ae7cf)  
**Developer Decision**: 🟢 **KEEP S-CLASS**

---

## 1. Live Empirical Execution Record

| Metric | Condition A (Agent + Pytest) | Condition B (Agent + S-Class + Pytest) | Empirical Finding |
| :--- | :---: | :---: | :--- |
| **Layer 1 Oracle Result** | ❌ **FAIL** (0 / 2) | 🟢 **PASS** (2 / 2) | B4 passed on Iteration 2; B2 failed all 3 retries |
| **Model Calls** | 3 calls (exhausted budget) | **2 calls** | B4 resolved test feedback faster |
| **Total Latency** | 12.57s | **11.09s** | B4 was ~1.5s faster total |
| **Cost ($)** | $0.001518 | **$0.001421** | B4 cost slightly less due to 1 fewer call |

---

## 2. Qualitative Developer Audit

- **Condition A (B2) Invariant Misses**:
  1. Failed to establish persistent SHA-256 hash manifest tracking (`.artifact_hashes.json`).
  2. Attempted to auto-generate `.sha256` files during verification when missing, which masked tampering errors on `test_pilot_gc_tamper`.
  3. Exhausted max retries (3 calls) without achieving green tests.
- **Condition B (B4) S-Class Catches**:
  1. Built an explicit `register_baseline_artifacts()` manifest store (`.artifact_hashes.json`) driven by S-Class requirement governance.
  2. Enforced SHA-256 digest hashing and correctly raised `ArtifactTamperError` on file modification.
  3. Protected `master_ledger.md` and `*.json` files from purge during garbage collection.
- **Catch Correctness**: `100% Correct`
- **False Alarms**: `None`

---

## 3. Developer Judgment & Final Decision

> **Final Decision**: **KEEP S-CLASS**  
> On this real internal repository task, S-Class requirement governance provided necessary structural invariants (manifest hash store and report preservation) that enabled the agent to reach 100% green tests in 2 calls, whereas plain test repair (B2) failed across 3 iterations.
