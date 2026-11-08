# Block 2 Delivery Packet Specification (Skeleton)

**Status:** SKELETON ONLY. Draft preparation packet.
**MUST Ownership:** None (evidence-only lane covering all 19 Block 2 MUSTs).

> **IMPORTANT:** In accordance with CL Block 2 Full Run instructions (Sections E & F), no runtime Block 2 pass evidence set is claimed at this stage. The real evidence execution occurs post-merge after AK merges Wave 1, GATE-B, FIXTURE, and B1 Fixes into `integration-r30-b1`.

---

## 1. Required Raw Logs Inventory

The verification tool `tools/verify_block2.sh` audits the presence and integrity of the following mandatory logs:

| Required File | Purpose | Verification Source |
|---|---|---|
| `python_3_12_full_suite.log` | Complete test suite execution under Python 3.12 (no new failures vs baseline) | `/home/runner/venv-3.12/bin/pytest` |
| `python_3_13_full_suite.log` | Complete test suite execution under Python 3.13 (no new failures vs baseline) | `/home/runner/venv-3.13/bin/pytest` |
| `fixture_manifest.json` | Deterministic canonical JSON result manifest for 66 PAIR fixtures and 17 SINGLE rows | `tools/run_block2_fixtures.py` |
| `fixture_summary.txt` | Human-readable fixture execution counts (RAN-MATCH, RAN-MISMATCH, NOT_RUN, ERROR, MOCK) | `tools/run_block2_fixtures.py` |
| `frozen_integrity.log` | Exact SHA-256 validation for all 5 frozen files + R2-9 note | `tests/guards/test_frozen_integrity_guard.py` |
| `import_guard.log` | AST import direction audit proving zero forbidden cross-layer imports | `tests/guards/test_import_direction_guard.py` |

---

## 2. Fail-Closed Verification Audit

The verification script `tools/verify_block2.sh` strictly enforces that if any log above is missing or invalid, execution **fails closed with non-zero exit code (exit 1)**.

### Dry-run Fail-Closed Demonstration:
```bash
$ ./tools/verify_block2.sh
============================================================
S-CLASS BLOCK 2 DELIVERY VERIFICATION
============================================================
Auditing required delivery logs in .../delivery-2-block2...
  [FAIL] Missing required log: python_3_12_full_suite.log
  [FAIL] Missing required log: python_3_13_full_suite.log
  [FAIL] Missing required log: fixture_manifest.json
  [FAIL] Missing required log: fixture_summary.txt
  [FAIL] Missing required log: frozen_integrity.log
  [FAIL] Missing required log: import_guard.log
============================================================
FAILED CLOSED: 6 required log(s) missing from delivery packet!
Delivery cannot advance until all raw logs are collected post-merge.
============================================================
(exit code 1)
```

---

## 3. Post-Merge Collection Plan

When AK has merged all prerequisite branches into integration and CL issues the instruction `RUN DELIVERY`:
1. `tools/run_block2_fixtures.py` will be invoked against the merged repository.
2. Full pytest suites for Python 3.10–3.13 will be saved into their respective log files.
3. Frozen integrity guards and import guards will be executed and captured.
4. `tools/verify_block2.sh` will verify the complete set and exit 0.
