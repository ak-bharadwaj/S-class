# Delivery 1-BASE-b: Integrated Candidate (H1b + Block 1-01 + Block 1-00)

## 1. Metadata & Lineage
- **Integration Branch:** `integration-r30-block-1-00-01-h1b`
- **Pinned Acceptance Candidate HEAD SHA:** `f17d3acb580f5ef57f08f46aa7c77d5913833dd6`
- **Targeted Code Fix Commit:** `b0e0418b5e926f900cff63101550c17ba7ffa2f4`
- **Base Commit (H1b):** `8b012f2dadf8785481b36e48598e34cc8a80c92f`
- **Block 1-01 Cherry-pick Commit:** `54a1f3c62786237d301ad3e258b8a4bebe6f4f52`
- **Block 1-00 Integration Commit:** `9ac8412bac067293965e95b13dbad104b43b2763`
- **Candidate Base Commit:** `50dce8e1fada1a941237291d0f17602dadb0a361`
- **Environment:** Ubuntu 26.04.1 LTS on Linux 6.6.114.1-microsoft-standard-WSL2 (host AK), Python 3.14.4, pip 25.1.1
- **Delivery Date:** 2026-10-25

---

## 2. Separation of Verification Runs
To ensure verifiable audit integrity, two distinct execution runs are tracked:

1. **Prior Developer Local Run (Commit `b0e0418`):**
   - Developer pre-commit verification during RFC 3339 date-time and digest contract fix implementation.
   - Logs: `delivery-1-base-b/1_pip_install.log` through `delivery-1-base-b/6_frozen_hashes.log`.
   - *Scope: Internal developer check only; not independent acceptance evidence.*

2. **Independent CL Acceptance Audit Run (Candidate Commit `f17d3ac`):**
   - Compliance Lead independent audit executed in isolated virtual environment `/home/runner/cl-acceptance-venv`.
   - Verified exact commit `f17d3acb580f5ef57f08f46aa7c77d5913833dd6`.
   - Logs: `delivery-1-base-b/cl_independent_audit/` (Steps 1 through 9, plus `cl_junit.xml`).
   - *Scope: Formal independent acceptance verification evidence.*

---

## 3. Executive Summary
Brief 1-BASE-b requested the production of a single, reproducible integration candidate based on `h1b` (`8b012f2dadf8785481b36e48598e34cc8a80c92f`), incorporating:
1. **Block 1-01:** R30 F1 artifact content model and Appendix A JSON Schemas (48 schemas, validator registry, canonical digests).
2. **Block 1-00:** Two guards (LF-normalized frozen file integrity and kernel state-machine registry checks) and hash-pinned Linux CI.
3. **Block 1-01 Review Defect Resolutions:**
   - Meta-schema validation with `Draft202012Validator.check_schema` across all 48 schemas.
   - Strict RFC 3339 `date-time` format checking with mandatory timezone offset and calendar date validation.
   - Content digest generation strictly reusing frozen kernel `canonical_c1` and verified against all 12 golden vectors.
   - Explicit artifact digest contract test asserting self-referential exclusion, C1 deterministic sorting, and direct `sha256(canonical_c1(data))` encoding differentiated from kernel domain-separated `digest()`.
   - Comprehensive `referencing.Registry` resolving all 48 schema URNs and cross-references.
4. **M5 Cgroup Delegation Hardening:** Explicit capability check (`check_delegated_cgroup_v2_available()`). Dedicated CI job `verify-m5-delegated-cgroup-sandbox` requiring strict zero-skip/zero-failure qualification. Persistent delegation configured via `sclass-cgroup.service`.
5. **Lockfile Reconciliation:** Reconciled `requirements-linux.txt` and `requirements.txt` into identical 1,446-line ASCII hash-pinned lockfiles (45 packages, zero BOM) including `jsonschema==4.26.0`, `jsonschema-specifications==2025.9.1`, `referencing==0.37.0`, and `rpds-py==0.30.0` (with multi-platform Linux wheels supporting Python 3.10 through 3.14).

All 5 frozen specification/conformance files and the canonical runtime (`20-RUNTIME/*`) have **ZERO** modifications.

---

## 4. Test Inventory & Collection Count Reconciliation
| Suite Component | Tests | Status |
|-----------------|-------|--------|
| H1b Baseline (`8b012f2`) | 315 | PASS |
| Block 1-01 Product Artifacts (`tests/product/`) | 44 | PASS |
| Block 1-00 Kernel & Frozen Guards (`tests/guards/`) | 8 | PASS |
| **Total Test Suite** | **367** | **367 passed, 0 skipped, 0 failed** |

---

## 5. Frozen Files Byte Integrity Hash Table
All hashes computed against normalized LF bytes:
| File Path | Expected SHA-256 | Actual SHA-256 | Match |
|-----------|------------------|----------------|-------|
| `00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md` | `53c02b13085dc3e1dcf75b9e8c306704d83bf37175b73a6be1a4b6ab7823ebb1` | `53c02b13085dc3e1dcf75b9e8c306704d83bf37175b73a6be1a4b6ab7823ebb1` | PASS |
| `10-CONFORMANCE/sclass_semantics_v6_0_1.py` | `ed2faf251863e1411fe2f33f2848f87e8fa9d4904b7bb1e032a472874e839922` | `ed2faf251863e1411fe2f33f2848f87e8fa9d4904b7bb1e032a472874e839922` | PASS |
| `10-CONFORMANCE/sclass_kernel_v6_0_1.py` | `d0f8f124dd55aab5cfb68d8c7d644eccf2694f52016c2e4a2132e6d6cef5575c` | `d0f8f124dd55aab5cfb68d8c7d644eccf2694f52016c2e4a2132e6d6cef5575c` | PASS |
| `10-CONFORMANCE/c1-vectors.v6.0.1.json` | `db58744d9829f7cac2ec7715a93d30d20a0d9ba6912d01f563504564e85b2da8` | `db58744d9829f7cac2ec7715a93d30d20a0d9ba6912d01f563504564e85b2da8` | PASS |
| `10-CONFORMANCE/state-machines.v6.0.1.json` | `24f159e6f72179ea66365b585f085727f6ef48420a09eae8c6024cb0bb51fdad` | `24f159e6f72179ea66365b585f085727f6ef48420a09eae8c6024cb0bb51fdad` | PASS |

---

## 6. CL Independent Acceptance Audit Summary (Target: `f17d3ac`)
- `cl_independent_audit/1_locked_pip_install.log`: `pip install --require-hashes` (exit code 0)
- `cl_independent_audit/2_editable_install.log`: `pip install --no-deps -e .` (exit code 0)
- `cl_independent_audit/3_pip_freeze.log`: Confirmed `-e ...@f17d3acb580f5ef57f08f46aa7c77d5913833dd6#egg=sclass` (exit code 0)
- `cl_independent_audit/4_guard_tests.log`: `pytest tests/guards/ -v` (8 passed, exit code 0)
- `cl_independent_audit/5_full_suite.log`: `pytest -v --junitxml=cl_junit.xml` (367 passed, 0 skipped, exit code 0)
- `cl_independent_audit/6_mutation_checks.log`: 8-stage negative mutation testing (exit code 0)
- `cl_independent_audit/7_m5_sandbox.log`: 5 M5 tests executed with active cgroup v2 delegation (5 passed, 0 skipped, exit code 0)
- `cl_independent_audit/8_spec_integrity.log`: Spec integrity check (exit code 0)
- `cl_independent_audit/9_frozen_hashes.log`: Explicit SHA-256 verification (5/5 matches, exit code 0)

---

## 7. Reproducible Rerun Instructions for CL
```bash
git checkout f17d3acb580f5ef57f08f46aa7c77d5913833dd6 && \
python -m venv .cl-audit-venv && \
source .cl-audit-venv/bin/activate && \
pip install --require-hashes -r requirements-linux.txt && \
pip install --no-deps -e . && \
python delivery-1-base-b/run_cl_audit.py
```
