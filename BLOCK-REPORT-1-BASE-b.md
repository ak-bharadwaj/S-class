# Integration Delivery Report: BRIEF 1-BASE-b

## 1. Commit Metadata & Integration Lineage
- **Target / Candidate Branch:** `integration-r30-block-1-00-01-h1b`
- **Base Commit (H1b):** `8b012f2dadf8785481b36e48598e34cc8a80c92f`
- **Block 1-01 Cherry-Pick Commit:** `54a1f3c62786237d301ad3e258b8a4bebe6f4f52` (from source `153e08fe13c1570d1ac81fcffe7bafeb8cd7bf58`)
- **Integration Candidate HEAD SHA:** `b9182a3b52d9ab9fb7891c80bdfe9e007e51734d`
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

### Full Changed Files List (81 files):
1. **CI & Packaging:**
   - `.github/workflows/ci.yml` (added Block 1-00 guards, switched to `requirements-linux.txt`, added `verify-m5-delegated-cgroup-sandbox` qualification job)
   - `requirements-linux.txt` (1,283-line ASCII hash-pinned lockfile, 41 packages, zero BOM, identical to `requirements.txt`)
2. **Product Artifact Content Model & Schemas (Block 1-01):**
   - `src/sclass/product/__init__.py`
   - `src/sclass/product/artifacts.py`
   - 48 JSON Schema definitions in `src/sclass/product/schemas/`
   - `tests/product/__init__.py`
   - `tests/product/test_artifact_schemas.py`
3. **Guards (Block 1-00):**
   - `tests/guards/test_frozen_integrity_guard.py`
   - `tests/guards/test_kernel_registry_guard.py`
4. **M5 Cgroup Delegation & Boundary Hardening:**
   - `tests/helpers/test_boundary.py` (added `check_delegated_cgroup_v2_available()`)
   - `tests/security/test_boundary_hardening.py` (explicit capability check in 5 M5 tests)
   - `tools/gates/gate_test_results.py` (added `SANDBOX QUALIFICATION STATUS: BLOCKED` diagnostic if skips occur)
   - `tools/verify_all.sh` (added Step 6b for Block 1-00 guard test execution)
5. **Delivery Records & Automation:**
   - `delivery-1-00/` (evidence, logs, summary, `run_mutations.py`)
   - `delivery-1-01/` (evidence, logs, summary)
   - `delivery-1-base-b/` (raw verification battery logs 1 through 6, evidence, summary)
   - `tools/run_delivery_verification.py` (automated reproducible verification runner)

---

## 3. Test Inventory & Collection Count Reconciliation
| Component | Baseline Count | Integrated Count | Delta | Notes |
|---|---|---|---|---|
| H1b Baseline (`8b012f2`) | 315 | 315 | 0 | Conformance, errata, adversarial, benchmarks, stage exit, security |
| Block 1-01 Product Artifacts | 0 | 39 | +39 | `tests/product/test_artifact_schemas.py` (23 functions + parametrizations) |
| Block 1-00 Guards | 0 | 8 | +8 | 5 frozen SHA-256 checks + 3 registry/state machine tests |
| **Total Test Suite** | **315** | **362** | **+47** | **Zero skips, zero xfails, zero failures** |

---

## 4. Frozen Files Byte Integrity Hash Table
All SHA-256 hashes computed on LF-normalized bytes (`sha256(content.replace(b'\r\n', b'\n'))`):
| File Path | Normative Expected Hash | Measured Hash | Verdict |
|---|---|---|---|
| `00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md` | `53c02b13085dc3e1dcf75b9e8c306704d83bf37175b73a6be1a4b6ab7823ebb1` | `53c02b13085dc3e1dcf75b9e8c306704d83bf37175b73a6be1a4b6ab7823ebb1` | PASS |
| `10-CONFORMANCE/sclass_semantics_v6_0_1.py` | `ed2faf251863e1411fe2f33f2848f87e8fa9d4904b7bb1e032a472874e839922` | `ed2faf251863e1411fe2f33f2848f87e8fa9d4904b7bb1e032a472874e839922` | PASS |
| `10-CONFORMANCE/sclass_kernel_v6_0_1.py` | `d0f8f124dd55aab5cfb68d8c7d644eccf2694f52016c2e4a2132e6d6cef5575c` | `d0f8f124dd55aab5cfb68d8c7d644eccf2694f52016c2e4a2132e6d6cef5575c` | PASS |
| `10-CONFORMANCE/c1-vectors.v6.0.1.json` | `db58744d9829f7cac2ec7715a93d30d20a0d9ba6912d01f563504564e85b2da8` | `db58744d9829f7cac2ec7715a93d30d20a0d9ba6912d01f563504564e85b2da8` | PASS |
| `10-CONFORMANCE/state-machines.v6.0.1.json` | `24f159e6f72179ea66365b585f085727f6ef48420a09eae8c6024cb0bb51fdad` | `24f159e6f72179ea66365b585f085727f6ef48420a09eae8c6024cb0bb51fdad` | PASS |

---

## 5. Raw Verification Battery Outputs & Exit Codes

### Battery 1: Hash-Pinned Dependency Installation
```text
$ /home/runner/delivery-env/bin/pip install --require-hashes -r requirements-linux.txt --find-links /home/runner/pip-cache
[EXIT CODE: 0] [ELAPSED: 1.24s]
Looking in links: /home/runner/pip-cache
Requirement already satisfied: cryptography==50.0.2 in ...
Requirement already satisfied: pytest==9.1.1 in ...
... (all 41 hash-pinned dependencies satisfied)
```

### Battery 2: Guard Test Execution
```text
$ /home/runner/delivery-env/bin/python -m pytest tests/guards/ -v
[EXIT CODE: 0] [ELAPSED: 22.12s]
tests/guards/test_frozen_integrity_guard.py::test_frozen_file_sha256_exact[...] PASSED [ 12%]
tests/guards/test_frozen_integrity_guard.py::test_frozen_file_sha256_exact[...] PASSED [ 25%]
tests/guards/test_frozen_integrity_guard.py::test_frozen_file_sha256_exact[...] PASSED [ 37%]
tests/guards/test_frozen_integrity_guard.py::test_frozen_file_sha256_exact[...] PASSED [ 50%]
tests/guards/test_frozen_integrity_guard.py::test_frozen_file_sha256_exact[...] PASSED [ 62%]
tests/guards/test_kernel_registry_guard.py::test_spec_integrity_script_passes PASSED   [ 75%]
tests/guards/test_kernel_registry_guard.py::test_state_machines_json_structure_and_counts PASSED [ 87%]
tests/guards/test_kernel_registry_guard.py::test_event_type_enum_in_semantics PASSED  [100%]
============================== 8 passed in 21.38s ==============================
```

### Battery 3: Full Integrated Test Suite
```text
$ /home/runner/delivery-env/bin/python -m pytest -v --junitxml=verify_junit.xml
[EXIT CODE: 0] [ELAPSED: 324.98s]
...
======================= 362 passed in 324.12s (0:05:24) ========================
```

### Battery 4: Guard Mutation Checks (8 Stages)
```text
$ /home/runner/delivery-env/bin/python delivery-1-00/run_mutations.py
[EXIT CODE: 0] [ELAPSED: 84.54s]
--- [STAGE 0] Clean Baseline Guards Run --- Exit code: 0 (8 passed)
--- [STAGE 1] Mutate 00-SPEC/...md --- Exit code: 1 (FAILED as expected) -> Restored clean
--- [STAGE 2] Mutate 10-CONFORMANCE/sclass_semantics_v6_0_1.py --- Exit code: 1 (FAILED as expected) -> Restored clean
--- [STAGE 3] Mutate 10-CONFORMANCE/sclass_kernel_v6_0_1.py --- Exit code: 1 (FAILED as expected) -> Restored clean
--- [STAGE 4] Mutate 10-CONFORMANCE/c1-vectors.v6.0.1.json --- Exit code: 1 (FAILED as expected) -> Restored clean
--- [STAGE 5] Mutate 10-CONFORMANCE/state-machines.v6.0.1.json --- Exit code: 1 (FAILED as expected) -> Restored clean
--- [STAGE 6] Mutate state-machines JSON structure --- Exit code: 1 (FAILED as expected) -> Restored clean
--- [STAGE 7] Mutate EventType enum in semantics --- Exit code: 1 (FAILED as expected) -> Restored clean
--- [STAGE 8] Final Clean Guards Run Across All Guards --- Exit code: 0 (8 passed)
Git diff on 00-SPEC and 10-CONFORMANCE exit code: 0 (all 5 files verified untouched)
ALL 8 MUTATION STAGES PASSED VERIFICATION.
```

### Battery 5: M5 Sandbox Qualification with Active Cgroup Delegation
```text
$ /home/runner/delivery-env/bin/python -m pytest -v tests/security/test_boundary_hardening.py -k test_m5
[EXIT CODE: 0] [ELAPSED: 3.30s]
tests/security/test_boundary_hardening.py::test_m5_write_outside_workspace_denied PASSED [ 20%]
tests/security/test_boundary_hardening.py::test_m5_no_network PASSED                     [ 40%]
tests/security/test_boundary_hardening.py::test_m5_process_tree_kill_on_timeout PASSED  [ 60%]
tests/security/test_boundary_hardening.py::test_m5_memory_limit_enforced PASSED         [ 80%]
tests/security/test_boundary_hardening.py::test_m5_pids_limit_enforced PASSED           [100%]
======================= 5 passed, 58 deselected in 2.51s =======================
```

### Battery 6: Frozen Byte Hashes Verification
```text
OK     53c02b13085dc3e1dcf75b9e8c306704d83bf37175b73a6be1a4b6ab7823ebb1  00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md
OK     ed2faf251863e1411fe2f33f2848f87e8fa9d4904b7bb1e032a472874e839922  10-CONFORMANCE/sclass_semantics_v6_0_1.py
OK     d0f8f124dd55aab5cfb68d8c7d644eccf2694f52016c2e4a2132e6d6cef5575c  10-CONFORMANCE/sclass_kernel_v6_0_1.py
OK     db58744d9829f7cac2ec7715a93d30d20a0d9ba6912d01f563504564e85b2da8  10-CONFORMANCE/c1-vectors.v6.0.1.json
OK     24f159e6f72179ea66365b585f085727f6ef48420a09eae8c6024cb0bb51fdad  10-CONFORMANCE/state-machines.v6.0.1.json
Result: PASS (0 mismatches)
```

---

## 6. M5 / Cgroup v2 Qualification Analysis
- **Capability Check:** `check_delegated_cgroup_v2_available()` probes:
  1. Linux platform presence.
  2. Functional `bwrap` unprivileged namespace support.
  3. Writable delegated cgroup v2 subtree (`/sys/fs/cgroup/sclass` or root).
  4. Required controllers enabled (`memory`, `pids`, `cpu`).
  5. Process migration capability (`cgroup.procs` write access).
- **Execution & CI Hardening:**
  - If capability is missing in an unconfigured test environment, tests skip with explicit diagnostic reasons (e.g. `M5 sandboxed execution requires delegated cgroup v2: cgroup root /sys/fs/cgroup is not writable by current user (uid=1000)`).
  - Gate 2 (`tools/gates/gate_test_results.py`) treats skips as a failure condition and logs `SANDBOX QUALIFICATION STATUS: BLOCKED`. Skips are NOT treated as qualification.
  - CI adds a dedicated runner job `verify-m5-delegated-cgroup-sandbox` on `ubuntu-24.04` which configures the delegated cgroup subtree and strictly asserts zero skips and zero failures across the M5 suite.

---

## 7. Unresolved Issues
- **None.** All 7 gates in `tools/verify_all.sh` pass cleanly. All 362 tests pass. All 8 mutation checks pass. All 5 frozen file hashes match normative vectors. Zero modifications exist in frozen or canonical runtime files.

---

## 8. Exact CL Rerun Instructions
From a clean clone on a Linux or WSL2 runner:
```bash
# 1. Checkout integration branch
git checkout integration-r30-block-1-00-01-h1b

# 2. Verify HEAD commit SHA
git rev-parse HEAD
# Expected: b9182a3b52d9ab9fb7891c80bdfe9e007e51734d

# 3. Create clean virtualenv and install hash-pinned dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install --require-hashes -r requirements-linux.txt
pip install --no-deps -e .

# 4. Run automated delivery verification battery
python tools/run_delivery_verification.py

# 5. Run full gate verification script
bash tools/verify_all.sh
```
