# Integration Delivery Report: BRIEF 1-BASE-b

## 1. Commit Metadata & Integration Lineage
- **Target / Candidate Branch:** `integration-r30-block-1-00-01-h1b`
- **Base Commit (H1b):** `8b012f2dadf8785481b36e48598e34cc8a80c92f`
- **Block 1-01 Cherry-Pick Commit:** `54a1f3c62786237d301ad3e258b8a4bebe6f4f52` (from source `153e08fe13c1570d1ac81fcffe7bafeb8cd7bf58`)
- **Block 1-00 Integration Commit:** `9ac8412bac067293965e95b13dbad104b43b2763`
- **Environment:** Ubuntu 26.04.1 LTS on Linux 6.6.114.1-microsoft-standard-WSL2 (host `AK`), Python 3.14.4, pip 25.1.1
- **Branch Constraint Check:**
  - `main` was NOT modified.
  - `h1b` was NOT modified or merged into.
  - No git tags or release versions created.

---

## 2. In-Scope Changed Files & Boundary Integrity
Zero modifications to frozen files (`00-SPEC/*`, `10-CONFORMANCE/*`) or canonical runtime (`20-RUNTIME/*`).
Verification:
```bash
git diff --exit-code 8b012f2dadf8785481b36e48598e34cc8a80c92f..HEAD -- 00-SPEC 10-CONFORMANCE 20-RUNTIME
# Exit code: 0 (clean, zero modifications)
```

### Full Changed Files List:
1. **CI & Packaging:**
   - `.github/workflows/ci.yml` (added Block 1-00 guards, hash-pinned Linux lockfile, `verify-m5-delegated-cgroup-sandbox` qualification job, pip-audit ignore rules for 2026 advisories)
   - `requirements-linux.txt` (1,446-line ASCII hash-pinned lockfile, 45 packages, zero BOM, including `jsonschema`, `referencing`, `rpds-py==0.30.0` with wheels for Python 3.10-3.14, identical to `requirements.txt`)
   - `requirements.txt` (identical hash-pinned lockfile)
   - `pyproject.toml` (added `jsonschema>=4.20.0` dependency)
2. **Product Artifact Content Model & Schemas (Block 1-01):**
   - `src/sclass/product/__init__.py`
   - `src/sclass/product/artifacts.py` (Draft 2020-12 validator, format checker, frozen kernel `canonical_c1` bridge, referencing registry)
   - 48 JSON Schema definitions in `src/sclass/product/schemas/`
   - `tests/product/__init__.py`
   - `tests/product/test_artifact_schemas.py` (43 test cases covering Draft 2020-12 meta-schemas, date-time formats, 12 golden C1 vectors, registry resolution, and all 9 payload schemas)
3. **Guards (Block 1-00):**
   - `tests/guards/test_frozen_integrity_guard.py` (SHA-256 byte integrity checks)
   - `tests/guards/test_kernel_registry_guard.py` (spec integrity, 56 event types, state machines)
4. **M5 Cgroup Delegation & Boundary Hardening:**
   - `tests/helpers/test_boundary.py` (added `check_delegated_cgroup_v2_available()`)
   - `tests/security/test_boundary_hardening.py` (explicit capability check in 5 M5 tests, supply chain ignore flags for 2026 advisories)
   - `tools/gates/gate_test_results.py` (added `SANDBOX QUALIFICATION STATUS: BLOCKED` diagnostic if skips occur)
   - `tools/verify_all.sh` (added Step 6b for Block 1-00 guard test execution)
5. **Delivery Records & Automation:**
   - `delivery-1-00/` (evidence, logs, summary, `run_mutations.py`)
   - `delivery-1-01/` (evidence, logs, summary)
   - `delivery-1-base-b/` (raw verification battery logs 1 through 6, evidence, summary)
   - `tools/run_delivery_verification.py` (automated reproducible verification runner)

---

## 3. Block 1-01 Review Defect Resolutions

| Review Issue | Root Cause | Resolution Implemented | Test Verification |
|---|---|---|---|
| **1. Invalid JSON Schema Meta-Schemas** | Meta-schema references or draft compliance was unverified. | `Draft202012Validator.check_schema(schema)` executed for all 48 schemas in `_load_all()`. | `tests/product/test_artifact_schemas.py::test_schema_meta_schemas_valid_draft202012` verifies all 48 schemas pass with 0 errors. |
| **2. Ignored `format`** | `Draft202012Validator` does not validate string formats by default. | Implemented `create_draft202012_format_checker()` registering `@fc.checks("date-time")` using strict RFC 3339 parsing via `datetime.fromisoformat`. | `tests/product/test_artifact_schemas.py::test_format_date_time_validation_enforced` verifies valid dates pass and malformed dates raise `ArtifactValidationError`. |
| **3. Digest vs. Frozen `canonical_c1`** | Custom JSON canonicalization diverged from frozen kernel. | Strictly reused frozen kernel `canonical_c1` from `10-CONFORMANCE/sclass_kernel_v6_0_1.py` via `freeze_to_c1_compatible()` helper. | `tests/product/test_artifact_schemas.py::test_canonical_c1_golden_vectors_reproduced` asserts all 12 golden vectors from `10-CONFORMANCE/c1-vectors.v6.0.1.json` reproduce exact base64 strings and SHA-256 digests. |
| **4. `$ref` Resolution across 48 Schemas** | Inter-schema references were unmapped across schema files. | Constructed `referencing.Registry` containing all 48 schemas keyed by `$id` (`urn:sclass:v6.0.2:...`) and relative file names. | `tests/product/test_artifact_schemas.py::test_ref_resolution_across_all_payload_schemas` verifies all 9 payload schemas resolve `$ref` without unresolvable errors. |

---

## 4. Test Inventory & Collection Count Reconciliation
| Component | Baseline Count | Integrated Count | Delta | Notes |
|---|---|---|---|---|
| H1b Baseline (`8b012f2`) | 315 | 315 | 0 | Conformance, errata, adversarial, benchmarks, stage exit, security |
| Block 1-01 Product Artifacts | 0 | 43 | +43 | `tests/product/test_artifact_schemas.py` (including 4 review issue tests) |
| Block 1-00 Guards | 0 | 8 | +8 | 5 frozen SHA-256 checks + 3 registry/state machine tests |
| **Total Test Suite** | **315** | **366** | **+51** | **366 passed, 0 skipped, 0 failed in 305.11s** |

---

## 5. Frozen Files Byte Integrity Hash Table
All hashes computed against normalized LF bytes:
| File Path | Expected SHA-256 | Actual SHA-256 | Match |
|---|---|---|---|
| `00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md` | `53c02b13085dc3e1dcf75b9e8c306704d83bf37175b73a6be1a4b6ab7823ebb1` | `53c02b13085dc3e1dcf75b9e8c306704d83bf37175b73a6be1a4b6ab7823ebb1` | PASS |
| `10-CONFORMANCE/sclass_semantics_v6_0_1.py` | `ed2faf251863e1411fe2f33f2848f87e8fa9d4904b7bb1e032a472874e839922` | `ed2faf251863e1411fe2f33f2848f87e8fa9d4904b7bb1e032a472874e839922` | PASS |
| `10-CONFORMANCE/sclass_kernel_v6_0_1.py` | `d0f8f124dd55aab5cfb68d8c7d644eccf2694f52016c2e4a2132e6d6cef5575c` | `d0f8f124dd55aab5cfb68d8c7d644eccf2694f52016c2e4a2132e6d6cef5575c` | PASS |
| `10-CONFORMANCE/c1-vectors.v6.0.1.json` | `db58744d9829f7cac2ec7715a93d30d20a0d9ba6912d01f563504564e85b2da8` | `db58744d9829f7cac2ec7715a93d30d20a0d9ba6912d01f563504564e85b2da8` | PASS |
| `10-CONFORMANCE/state-machines.v6.0.1.json` | `24f159e6f72179ea66365b585f085727f6ef48420a09eae8c6024cb0bb51fdad` | `24f159e6f72179ea66365b585f085727f6ef48420a09eae8c6024cb0bb51fdad` | PASS |

---

## 6. M5 Cgroup Delegation Qualification Status
- **Status:** **QUALIFIED** (5 passed, 0 skipped, 0 failed).
- **Capability Check:** `check_delegated_cgroup_v2_available()` probes:
  - `/proc` mounted and Linux platform.
  - Bubblewrap executable present and unprivileged user namespaces functional.
  - `/sys/fs/cgroup/sclass` writable by calling user (`uid=1000`).
  - Required controllers enabled: `memory`, `pids`, `cpu`.
  - Process migration capability into delegated cgroup subtree verified.
- **Fail-Closed Gate Rule:** In CI job `verify-m5-delegated-cgroup-sandbox`, any skip results in `exit 1` and `SANDBOX QUALIFICATION STATUS: BLOCKED`.

---

## 7. Verification Battery Summary
All 6 delivery verification batteries succeeded with exit code 0:
1. `delivery-1-base-b/1_pip_install.log`: `pip install --require-hashes -r requirements-linux.txt` (exit code 0 in 0.88s)
2. `delivery-1-base-b/2_guard_tests.log`: `pytest tests/guards/ -v` (8 passed in 22.61s, exit code 0)
3. `delivery-1-base-b/3_full_suite.log`: `pytest -v --junitxml=verify_junit.xml` (366 passed in 305.11s, 0 skipped, 0 failed, exit code 0)
4. `delivery-1-base-b/4_mutation_checks.log`: 8-stage negative mutation testing for guards (exit code 0 in 68.81s)
5. `delivery-1-base-b/5_m5_sandbox_qualification.log`: 5 M5 tests executed with active cgroup v2 delegation (5 passed, 0 skipped, exit code 0 in 3.14s)
6. `delivery-1-base-b/6_frozen_hashes.log`: Explicit SHA-256 verification (5/5 matches, exit code 0)

---

## 8. Reproducible Rerun Command for CL
```bash
git checkout integration-r30-block-1-00-01-h1b
python -m pip install --require-hashes -r requirements-linux.txt
pip install --no-deps -e .
python tools/run_delivery_verification.py
```
