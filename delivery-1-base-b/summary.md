# Delivery 1-BASE-b: Integrated Candidate (H1b + Block 1-01 + Block 1-00)

## 1. Metadata
- **Integration Branch:** `integration-r30-block-1-00-01-h1b`
- **Base Commit (H1b):** `8b012f2dadf8785481b36e48598e34cc8a80c92f`
- **Block 1-01 Cherry-pick Commit:** `54a1f3c62786237d301ad3e258b8a4bebe6f4f52`
- **Block 1-00 Integration Commit:** `9ac8412bac067293965e95b13dbad104b43b2763`
- **Environment:** Ubuntu 26.04.1 LTS on Linux 6.6.114.1-microsoft-standard-WSL2 (host AK), Python 3.14.4, pip 25.1.1
- **Delivery Date:** 2026-10-25

---

## 2. Executive Summary
Brief 1-BASE-b requested the production of a single, reproducible integration candidate based on `h1b` (`8b012f2dadf8785481b36e48598e34cc8a80c92f`), incorporating:
1. **Block 1-01:** R30 F1 artifact content model and Appendix A JSON Schemas (48 schemas, validator registry, canonical digests).
2. **Block 1-00:** Two guards (LF-normalized frozen file integrity and kernel state-machine registry checks) and hash-pinned Linux CI.
3. **Block 1-01 Review Defect Resolutions:**
   - Meta-schema validation with `Draft202012Validator.check_schema` across all 48 schemas.
   - Strict RFC 3339 `date-time` format checking enabled on `Draft202012Validator`.
   - Content digest generation strictly reusing frozen kernel `canonical_c1` and verified against all 12 golden vectors.
   - Comprehensive `referencing.Registry` resolving all 48 schema URNs and cross-references.
4. **M5 Cgroup Delegation Hardening:** Replaced vague platform checks with an explicit capability check (`check_delegated_cgroup_v2_available()`). Added dedicated CI job `verify-m5-delegated-cgroup-sandbox` requiring strict zero-skip/zero-failure qualification. Persistent delegation configured via `sclass-cgroup.service`.
5. **Lockfile Reconciliation:** Reconciled `requirements-linux.txt` and `requirements.txt` into identical 1,446-line ASCII hash-pinned lockfiles (45 packages, zero BOM) including `jsonschema==4.26.0`, `jsonschema-specifications==2025.9.1`, `referencing==0.37.0`, and `rpds-py==0.30.0` (with multi-platform Linux wheels supporting Python 3.10 through 3.14).

All 5 frozen specification/conformance files and the canonical runtime (`20-RUNTIME/*`) have **ZERO** modifications.

---

## 3. Test Inventory & Collection Count Reconciliation
| Suite Component | Tests | Status |
|-----------------|-------|--------|
| H1b Baseline (`8b012f2`) | 315 | PASS |
| Block 1-01 Product Artifacts (`tests/product/`) | 43 | PASS |
| Block 1-00 Kernel & Frozen Guards (`tests/guards/`) | 8 | PASS |
| **Total Test Suite** | **366** | **366 passed, 0 skipped, 0 failed in 305.11s** |

---

## 4. Frozen Files Byte Integrity Hash Table
All hashes computed against normalized LF bytes:
| File Path | Expected SHA-256 | Actual SHA-256 | Match |
|-----------|------------------|----------------|-------|
| `00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md` | `53c02b13085dc3e1dcf75b9e8c306704d83bf37175b73a6be1a4b6ab7823ebb1` | `53c02b13085dc3e1dcf75b9e8c306704d83bf37175b73a6be1a4b6ab7823ebb1` | PASS |
| `10-CONFORMANCE/sclass_semantics_v6_0_1.py` | `ed2faf251863e1411fe2f33f2848f87e8fa9d4904b7bb1e032a472874e839922` | `ed2faf251863e1411fe2f33f2848f87e8fa9d4904b7bb1e032a472874e839922` | PASS |
| `10-CONFORMANCE/sclass_kernel_v6_0_1.py` | `d0f8f124dd55aab5cfb68d8c7d644eccf2694f52016c2e4a2132e6d6cef5575c` | `d0f8f124dd55aab5cfb68d8c7d644eccf2694f52016c2e4a2132e6d6cef5575c` | PASS |
| `10-CONFORMANCE/c1-vectors.v6.0.1.json` | `db58744d9829f7cac2ec7715a93d30d20a0d9ba6912d01f563504564e85b2da8` | `db58744d9829f7cac2ec7715a93d30d20a0d9ba6912d01f563504564e85b2da8` | PASS |
| `10-CONFORMANCE/state-machines.v6.0.1.json` | `24f159e6f72179ea66365b585f085727f6ef48420a09eae8c6024cb0bb51fdad` | `24f159e6f72179ea66365b585f085727f6ef48420a09eae8c6024cb0bb51fdad` | PASS |

---

## 5. Verification Battery Summary
- `1_pip_install.log`: `pip install --require-hashes -r requirements-linux.txt` (exit code 0 in 0.88s)
- `2_guard_tests.log`: `pytest tests/guards/ -v` (8 passed in 22.61s, exit code 0)
- `3_full_suite.log`: `pytest -v --junitxml=verify_junit.xml` (366 passed in 305.11s, 0 skipped, 0 failed, exit code 0)
- `4_mutation_checks.log`: 8-stage negative mutation testing for guards (exit code 0 in 68.81s)
- `5_m5_sandbox_qualification.log`: 5 M5 tests executed with active cgroup v2 delegation (5 passed, 0 skipped, exit code 0 in 3.14s)
- `6_frozen_hashes.log`: Explicit SHA-256 verification (5/5 matches, exit code 0)

---

## 6. Reproducible Rerun Command
```bash
git checkout integration-r30-block-1-00-01-h1b
python -m pip install --require-hashes -r requirements-linux.txt
pip install --no-deps -e .
python tools/run_delivery_verification.py
```
