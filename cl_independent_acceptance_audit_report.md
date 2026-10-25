# CL Independent Acceptance Audit Report: Candidate `f17d3acb580f5ef57f08f46aa7c77d5913833dd6`

**Date:** 2026-10-25  
**Candidate Commit SHA:** `f17d3acb580f5ef57f08f46aa7c77d5913833dd6`  
**Target Branch:** `integration-r30-block-1-00-01-h1b`  
**Base Commit (H1b):** `8b012f2dadf8785481b36e48598e34cc8a80c92f`  
**Auditor Environment:** Ubuntu 26.04.1 LTS on Linux 6.6.114.1-microsoft-standard-WSL2 (host `AK`), Python 3.14.4, pytest 9.1.1, pip 25.1.1  
**Isolated Acceptance Venv:** `/home/runner/cl-acceptance-venv`

---

## 1. Separation of Runs & Audit Context

To maintain complete documentation and audit integrity, the verification history is explicitly partitioned into two distinct runs:

1. **Prior Developer Verification Run (Commit `b0e0418b5e926f900cff63101550c17ba7ffa2f4`):**
   - **Scope:** Developer pre-commit verification conducted locally while resolving the Block 1-01 review defects (RFC 3339 strict date-time parsing and the `compute_content_digest` contract).
   - **Output Paths:** `delivery-1-base-b/1_pip_install.log` through `delivery-1-base-b/6_frozen_hashes.log`, `delivery-1-base-b/evidence.txt`.
   - **Status:** Developer milestone only. **NOT** presented as acceptance verification for the delivered candidate.

2. **Independent CL Acceptance Audit Run (Candidate Commit `f17d3acb580f5ef57f08f46aa7c77d5913833dd6`):**
   - **Scope:** Formal independent verification executed against exact checkout of acceptance candidate `f17d3acb580f5ef57f08f46aa7c77d5913833dd6`.
   - **Output Paths:** `delivery-1-base-b/cl_independent_audit/` (Steps 1 through 9, plus `cl_junit.xml`).
   - **Integrity Requirement:** Every log file explicitly records target commit `f17d3acb580f5ef57f08f46aa7c77d5913833dd6`. `pip freeze` confirms the exact candidate SHA.
   - **Status:** **SOLE ACCEPTANCE AUDIT EVIDENCE**.

---

## 2. Independent Audit Battery Summary

| Stage | Operation / Command | Log File | Exit Code | Elapsed | Status |
|---|---|---|---|---|---|
| **1** | `pip install --require-hashes -r requirements-linux.txt` | `delivery-1-base-b/cl_independent_audit/1_locked_pip_install.log` | **0** | 12.74s | **PASS** (45 packages verified against exact sha256 hashes) |
| **2** | `pip install --no-deps -e .` | `delivery-1-base-b/cl_independent_audit/2_editable_install.log` | **0** | 10.61s | **PASS** (Editable install of `sclass`) |
| **3** | `pip freeze` | `delivery-1-base-b/cl_independent_audit/3_pip_freeze.log` | **0** | 0.65s | **PASS** (Matches `-e git+https://github.com/ak-bharadwaj/S-class.git@f17d3acb580f5ef57f08f46aa7c77d5913833dd6#egg=sclass`) |
| **4** | `pytest tests/guards/ -v` | `delivery-1-base-b/cl_independent_audit/4_guard_tests.log` | **0** | 22.50s | **PASS** (8 passed, 0 skipped, 0 failed) |
| **5** | `pytest -v --junitxml=cl_junit.xml` | `delivery-1-base-b/cl_independent_audit/5_full_suite.log` | **0** | 250.34s | **PASS** (367 passed, 0 skipped, 0 failed in 4m 10s) |
| **6** | `python delivery-1-00/run_mutations.py` | `delivery-1-base-b/cl_independent_audit/6_mutation_checks.log` | **0** | 54.20s | **PASS** (8/8 stages verified with exact byte preservation and finally-block restoration) |
| **7** | `pytest -v tests/security/test_boundary_hardening.py -k test_m5` | `delivery-1-base-b/cl_independent_audit/7_m5_sandbox.log` | **0** | 2.34s | **PASS** (5 passed, 0 skipped, delegated cgroup v2 sandbox qualified) |
| **8** | `python 10-CONFORMANCE/spec_integrity.py` | `delivery-1-base-b/cl_independent_audit/8_spec_integrity.log` | **0** | 17.05s | **PASS** (`SPEC_INTEGRITY_OK registry=260 events=56`) |
| **9** | Frozen SHA-256 byte verification | `delivery-1-base-b/cl_independent_audit/9_frozen_hashes.log` | **0** | 0.05s | **PASS** (5/5 exact matches, 0 mismatches) |

---

## 3. Frozen Files Byte Integrity Hash Table

All hashes computed against normalized LF bytes:

| File Path | Expected SHA-256 | Actual SHA-256 | Result |
|---|---|---|---|
| `00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md` | `53c02b13085dc3e1dcf75b9e8c306704d83bf37175b73a6be1a4b6ab7823ebb1` | `53c02b13085dc3e1dcf75b9e8c306704d83bf37175b73a6be1a4b6ab7823ebb1` | **MATCH** |
| `10-CONFORMANCE/sclass_semantics_v6_0_1.py` | `ed2faf251863e1411fe2f33f2848f87e8fa9d4904b7bb1e032a472874e839922` | `ed2faf251863e1411fe2f33f2848f87e8fa9d4904b7bb1e032a472874e839922` | **MATCH** |
| `10-CONFORMANCE/sclass_kernel_v6_0_1.py` | `d0f8f124dd55aab5cfb68d8c7d644eccf2694f52016c2e4a2132e6d6cef5575c` | `d0f8f124dd55aab5cfb68d8c7d644eccf2694f52016c2e4a2132e6d6cef5575c` | **MATCH** |
| `10-CONFORMANCE/c1-vectors.v6.0.1.json` | `db58744d9829f7cac2ec7715a93d30d20a0d9ba6912d01f563504564e85b2da8` | `db58744d9829f7cac2ec7715a93d30d20a0d9ba6912d01f563504564e85b2da8` | **MATCH** |
| `10-CONFORMANCE/state-machines.v6.0.1.json` | `24f159e6f72179ea66365b585f085727f6ef48420a09eae8c6024cb0bb51fdad` | `24f159e6f72179ea66365b585f085727f6ef48420a09eae8c6024cb0bb51fdad` | **MATCH** |

---

## 4. Delegated Cgroup v2 Sandbox Qualification

- **Host cgroup path:** `/sys/fs/cgroup/sclass`
- **Enabled controllers:** `memory`, `pids`, `cpu`
- **Ownership:** `runner:runner` (uid 1000)
- **Qualification tests:**
  - `test_m5_write_outside_workspace_denied`: PASSED
  - `test_m5_no_network`: PASSED
  - `test_m5_process_tree_kill_on_timeout`: PASSED
  - `test_m5_memory_limit_enforced`: PASSED
  - `test_m5_pids_limit_enforced`: PASSED
- **Zero Skips:** 5 passed, 0 skipped. Sandbox qualification status: **QUALIFIED**.

---

## 5. Mutation Harness Isolation & Byte Restoration Guarantee

The mutation test suite [`delivery-1-00/run_mutations.py`](delivery-1-00/run_mutations.py) verifies the guard suite with strict byte-level isolation:
1. Exact original pre-mutation bytes and SHA-256 hashes are captured in memory prior to each mutation.
2. Mutations are executed and confirmed to trigger expected guard failures (exit code 1).
3. Exact pre-mutation bytes are restored directly within a `finally` block (`target.write_bytes(orig_bytes)`).
4. Direct byte-for-byte and SHA-256 equality checks confirm complete restoration without calling `git checkout`.
5. Guard regression checks verify that the restored file passes with exit code 0.
6. A post-battery hash sweep confirms all 5 frozen files match their expected SHA-256 hashes, with `git diff --exit-code -- 00-SPEC 10-CONFORMANCE` confirming zero working tree modifications.

---

## 6. Remote GitHub Actions CI Run Confirmation

- **CI Workflow Run:** [Run 40203654279](https://github.com/ak-bharadwaj/S-class/actions/runs/40203654279)
- **Target Remote HEAD:** `f17d3acb580f5ef57f08f46aa7c77d5913833dd6`
- **All 10 Jobs Succeeded:**
  - `verify-m5-delegated-cgroup-sandbox`: 5 passed, 0 skipped
  - `verify-m6-boundary-hardening-unavailable`: passed
  - 8 verification matrix jobs across Ubuntu 22.04 & 24.04 (Python 3.10-3.13): 367 passed, 0 skipped

---

## 7. Reproducible Rerun Instructions

To reproduce the exact audit results:

```bash
git checkout f17d3acb580f5ef57f08f46aa7c77d5913833dd6 && \
python -m venv .cl-audit-venv && \
source .cl-audit-venv/bin/activate && \
pip install --require-hashes -r requirements-linux.txt && \
pip install --no-deps -e . && \
python delivery-1-base-b/run_cl_audit.py
```

All generated log files in `delivery-1-base-b/cl_independent_audit/` record `TARGET_COMMIT: f17d3acb580f5ef57f08f46aa7c77d5913833dd6` in their headers.

---

## 8. Audit Verdict

**FIX / HOLD — the reported code fixes appear credible, but the block is not yet independently accepted. Do not merge or tag based solely on this delivery report.**
