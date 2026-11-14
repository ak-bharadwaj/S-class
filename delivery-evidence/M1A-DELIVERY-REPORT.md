# S-CLASS M1-A DELIVERY REPORT — BASELINE TRUTH (ROADMAP B01 + B04)

- **Date / Timestamp:** 2026-11-14T12:00:00+00:00
- **Target Milestones:** Roadmap B01 (Baseline Lock & Full Suite Classification) + B04 (Kernel Enum Guard & Replay)
- **Product Pull Request:** [#25 — feat(m1a): baseline truth lock, kernel enum guard, replay digest equality, and classified test suite (B01+B04)](https://github.com/ak-bharadwaj/S-class/pull/25)
- **PR Status:** **OPEN / UNMERGED / DO NOT MERGE** (Awaiting formal audit/approval)
- **Branch:** `m1a-baseline`
- **Integration Base:** `integration-r30-b1` (`4af5aba9d9898bb10dd2e859cc6d8a4572fac157`)
- **PR Head Commit:** `ed20653dca5905606b22ef4c1a73badcefb2a540`
- **Evidence Branch:** `evidence-m1a-baseline`

---

## 1. CI Execution & Verification Matrix

- **Push Workflow Run:** [Run 43587415031 (Conclusion: SUCCESS)](https://github.com/ak-bharadwaj/S-class/actions/runs/43587415031)
- **Pull Request Workflow Run:** [Run 43587419782 (Conclusion: SUCCESS)](https://github.com/ak-bharadwaj/S-class/actions/runs/43587419782)

### Complete 12-Job CI Status (12/12 Green)

| Job Name | Platform / Python | Status | Conclusion | Description |
| :--- | :--- | :--- | :--- | :--- |
| **Baseline Truth Verification** | Ubuntu 24.04 (Py3.10 + Py3.12) | completed | **success** | Dedicated B01+B04 Linux job: cross-python replay equality, baseline hash check, full classified runner |
| **M5 Delegated cgroup v2 Sandbox Qualification** | Ubuntu 24.04 (Py3.12) | completed | **success** | Strict 0-skip / 0-fail qualification of delegated cgroup v2 & bubblewrap sandbox |
| **M6 BoundaryUnavailable** | Ubuntu 24.04 (Py3.12) | completed | **success** | Fail-closed verification without AppArmor profile (zero unconfined execution) |
| **E4 Mutation Battery** | Ubuntu 24.04 (Py3.12) | completed | **success** | 50/50 mutants evaluated with exact JUnit AssertionError identity mapping |
| **Verification (ubuntu-22.04 - Py3.10)** | Ubuntu 22.04 / Python 3.10 | completed | **success** | Matrix verifier, stress test, clean wheel smoke, gate checks |
| **Verification (ubuntu-22.04 - Py3.11)** | Ubuntu 22.04 / Python 3.11 | completed | **success** | Matrix verifier, stress test, clean wheel smoke, gate checks |
| **Verification (ubuntu-22.04 - Py3.12)** | Ubuntu 22.04 / Python 3.12 | completed | **success** | Matrix verifier, stress test, clean wheel smoke, gate checks |
| **Verification (ubuntu-22.04 - Py3.13)** | Ubuntu 22.04 / Python 3.13 | completed | **success** | Matrix verifier, stress test, clean wheel smoke, gate checks |
| **Verification (ubuntu-24.04 - Py3.10)** | Ubuntu 24.04 / Python 3.10 | completed | **success** | Matrix verifier, stress test, clean wheel smoke, gate checks |
| **Verification (ubuntu-24.04 - Py3.11)** | Ubuntu 24.04 / Python 3.11 | completed | **success** | Matrix verifier, stress test, clean wheel smoke, gate checks |
| **Verification (ubuntu-24.04 - Py3.12)** | Ubuntu 24.04 / Python 3.12 | completed | **success** | Matrix verifier, stress test, clean wheel smoke, gate checks |
| **Verification (ubuntu-24.04 - Py3.13)** | Ubuntu 24.04 / Python 3.13 | completed | **success** | Matrix verifier, stress test, clean wheel smoke, gate checks |

---

## 2. GPT Audit Corrections (Task Package #4)

### Defect 1: Kernel Enum Guard False-PASS Path (`tests/guards/test_kernel_enum_guard.py`)
- **Root Cause:** Extraction previously filtered classes against known machines, potentially omitting unmapped enum/state/status/machine classes. Negative tests did not exercise the actual source extraction path.
- **Correction:**
  - Implemented full AST extraction (`validate_semantics_file`) and runtime reflection (`validate_runtime_reflection_classes`).
  - Added strict canonical 77-enum whitelist (`CANONICAL_SEMANTICS_ENUM_WHITELIST`), canonical state classes, and canonical machine names.
  - Rejects any unauthorized Enum, State, Status, or Machine class discovered in AST or runtime scanning.
  - Added 6 negative adversarial tests modifying temporary copies of `sclass_semantics_v6_0_1.py` and proving immediate fail-closed rejection.

### Defect 2: Full-Suite Classifier False ENV (`tools/run_full_suite_classified.py`)
- **Root Cause:** Failed/error tests mentioning capability substrings (`cgroup v2`, `bwrap`, `userns`) could potentially be classified as `ENV`.
- **Correction:**
  - In `classify_outcome()`, any test outcome with `status in ("failure", "error", "failed")` is strictly classified as `CODE`. Capability keywords never mask test failures.
  - Only explicit `skipped` outcomes with matching capability keywords are classified as `ENV`.
  - Empty JUnit reports (0 testcases) or reports with counter inconsistencies fail closed with exit code 2.
  - Pytest non-zero exit codes unrepresented in JUnit are synthesized as `CODE` failures.
  - Added 6 guard tests in `tests/guards/test_full_suite_classifier.py`.

### Defect 3: Baseline Lock Manifest Integrity & Branch Baselines (`tools/baseline_hashes.py`)
- **Root Cause:** Manifest entries previously overrode canonical anchors; multi-branch comparison across all 5 branches (`main`, `h0`, `h1a`, `h1b`, `integration`) needed formal codification and clean-install evidence.
- **Correction:**
  - `validate_manifest_file()` validates `FROZEN-MANIFEST.sha256` against embedded canonical anchors; raises `ValueError` on any mismatch, corruption, missing entries, or bad hex format. Anchors cannot be overridden.
  - Generated Table 1 (Integration vs Package), Table 2 (Multi-Branch Baseline Comparison across all 5 refs), and Table 3 (Clean-Install Full-Suite Evidence by Ref) in `governance/BASELINE-HASHES.txt`.
  - Added `tests/guards/test_baseline_hashes_guard.py` (8 tests) proving manifest tampering fails closed.
  - Evaluated clean git archive trees across all 5 refs, verifying exact test classifications.

### Defect 4: Replay Comparator Flag Enforcement (`tools/replay_genesis_digest.py`)
- **Root Cause:** `compare_reports()` did not validate report schema, allowed identical Python versions, and did not assert cross-run flag consistency.
- **Correction:**
  - Added `validate_report_schema()`: enforces presence and truth of `expected_golden_digest_match`, `sqlite_store_replay_digest_match`, `dual_replay_digest_match`, and verifies mutual identity `run1 == run2 == sqlite == expected_golden`.
  - `compare_reports()` enforces `r1.python_version != r2.python_version`, assert identical digests and head hashes.
  - Added 8 negative tampering tests in `tests/guards/test_replay_genesis_digest.py`.

---

## 3. GPT Audit Task Package #5 Corrections (Consolidated Iteration)

### Defect 1: Kernel Machine Guard Structural Detection (`tests/guards/test_kernel_enum_guard.py`)
- **Root Cause:** Detection previously checked `"Machine" in name`, creating a bypass for classes named with alternative conventions (e.g. `RogueLifecycle`, `ProtocolRunner`).
- **Correction:**
  - Implemented `is_machine_style_class_def()` checking structural attributes (`transitions`, `initial_state`, `allowed_transitions`), transition methods (`transition`, `can_transition`), and lifecycle keywords.
  - Enforced full AST and runtime reflection whitelisting against all 270 canonical classes in `CANONICAL_SEMANTICS_ALL_CLASSES`.
  - Added adversarial tests: `test_negative_added_rogue_lifecycle_machine_fails_guard` (reproduction) and `test_negative_added_machine_different_naming_convention_fails_guard`.
  - Verified 11/11 tests pass.

### Defect 2: JUnit Outcome Parsing Conflict Rejection (`tools/run_full_suite_classified.py`)
- **Root Cause:** In JUnit parsing, skipped check preceded failure check. Conflicting XML elements could mask test failures as ENV skips.
- **Correction:**
  - `parse_junit_xml()` inspects all outcome elements (`skipped`, `failure`, `error`). If multiple conflicting outcome elements exist on a single testcase, it raises `ValueError("MALFORMED JUNIT CONFLICT: ...")` fail-closed.
  - Failure/error elements strictly take precedence over skipped elements.
  - Added 4 guard tests in `tests/guards/test_full_suite_classifier.py` verifying conflicting XML fails closed and never produces PASS.

### Defect 3: Historical Clean-Install Multi-Branch Baselines (`tools/evaluate_branch_baselines.py`)
- **Root Cause:** Historical branch evaluations were previously un-isolated and inherited caller environment variables.
- **Correction:**
  - Implemented automated multi-branch clean installer:
    - Dedicated clean git archive extraction into isolated tempdirs per ref.
    - Dedicated `uv venv` per ref installing each ref's declared dependencies (`requirements-linux.txt` / `20-RUNTIME/requirements.txt` + `pytest`, `hypothesis`, `pyyaml`, `ruff`, `pip`, `wheel`, `setuptools`).
    - Sanitized execution environment; sets `SCLASS_MASTER_PATH` only if the master design document physically exists in that ref.
    - Preserves raw logs, JUnit XML, install logs, and metadata under `delivery-evidence/branch_baselines/<ref>/`.
    - Generates `delivery-evidence/branch_baselines_classification.json` and `delivery-evidence/branch_baselines_classification.md`.
  - Exact historical counts reproduced:
    - `main` (`447caf96`): 248 total, 240 passed, 0 env, 8 code failures (FAIL)
    - `h0` (`e60a089d`): 252 total, 250 passed, 0 env, 2 code failures (FAIL)
    - `h1a` (`9c6e0fc9`): 270 total, 270 passed, 0 env, 0 code failures (PASS)
    - `h1b` (`8b012f2d`): 315 total, 315 passed, 0 env, 0 code failures (PASS)
    - `integration` (`4af5aba9`): 2133 total, 2133 passed, 0 env, 0 code failures (PASS)

### Defect 4: Baseline Table 3 Dynamic Evidence Verification (`tools/baseline_hashes.py`)
- **Root Cause:** Table 3 embedded literal strings rather than reading and validating actual evidence.
- **Correction:**
  - Added `load_and_validate_branch_classification_evidence()`: loads `delivery-evidence/branch_baselines_classification.json`, validates schema, checks all 5 refs, verifies exact commit SHAs, validates count arithmetic (`total == passed + env + code`), and verifies status. Fails closed if missing, malformed, or tampered.
  - Table 3 is generated dynamically from the validated evidence metrics.
  - Added 7 tampering guard tests in `tests/guards/test_baseline_hashes_guard.py` verifying that missing, malformed, mismatched SHA, count inconsistency, or status mismatch fails closed and causes `baseline_hashes.py --check` to exit with code 1.
  - Verified 67/67 guard tests pass.

---

## 4. GPT Audit Task Package #6 Corrections (Iteration 3/3 — Final Permitted Iteration)

### Defect 1: AST Class Scope Hierarchy & Rejection of Nested Classes (`tests/guards/test_kernel_enum_guard.py`)
- **Root Cause:** `extract_ast_class_definitions()` previously stored classes in a flat dictionary keyed only by `node.name` using `ast.walk()`. A nested class with the same name as a top-level canonical class (e.g. `AcceptanceContract.WorkProposal`) overwrote the top-level class, evading detection. Furthermore, runtime reflection did not scan inner class definitions.
- **Correction:**
  - Implemented `ClassDefScopeVisitor(ast.NodeVisitor)`:
    - Tracks nested scopes across classes and functions (`scope_stack`).
    - Assigns fully qualified class names (`qualified_name`).
    - Detects duplicate simple names via `self.duplicate_simple_names`.
    - Detects nested class definitions via `self.nested_classes`.
    - Implements dict mapping protocol (`__iter__`, `__getitem__`, `__len__`, `__contains__`, `get`, `keys`, `items`, `values`) for full compatibility.
  - In `validate_semantics_file()`:
    - Fails closed immediately if `visitor.nested_classes` is non-empty (`KERNEL CLASS GUARD VIOLATION: Unauthorized nested class definition(s)...`).
    - Fails closed if `visitor.duplicate_simple_names` is non-empty (`KERNEL CLASS GUARD VIOLATION: Duplicate class name definition(s)...`).
  - In `validate_runtime_reflection_classes()`:
    - Rejects any class whose `__qualname__` contains a `.` (`Unauthorized nested class qualname`).
    - Inspects `cls.__dict__` for nested `type` objects belonging to the module (`Unauthorized inner/nested class discovered`).
  - Added 4 adversarial test cases in `tests/guards/test_kernel_enum_guard.py`:
    - `test_negative_added_nested_class_with_canonical_name_fails_guard` (reproduction with `AcceptanceContract.WorkProposal`).
    - `test_negative_added_nested_class_with_unauthorized_name_fails_guard` (`AcceptanceContract.RogueNested`).
    - `test_negative_duplicate_class_name_fails_guard` (duplicate top-level `WorkProposal`).
    - `test_negative_runtime_reflection_detects_nested_class` (monkeypatched inner class in `cls.__dict__`).
  - Verified 15/15 tests in `test_kernel_enum_guard.py` pass.

### Defect 2: Classification Evidence Cross-Verification & Raw JUnit Recomputation (`tools/baseline_hashes.py`)
- **Root Cause:** `load_and_validate_branch_classification_evidence()` previously validated only count arithmetic and status strings, but did not cross-verify failure counts against `code_failures`, did not verify ENV counts against `env_breakdown`, did not cross-check aggregate metrics against per-ref `ref_metadata.json`, and did not independently parse retained `junit.xml`.
- **Correction:**
  - Rewrote `load_and_validate_branch_classification_evidence(evidence_path, raw_evidence_dir)`:
    1. Validates `code_failures_count == len(code_failures)` (catches fabricated PASS immediately).
    2. Validates `env_items_count == sum(env_breakdown.values())`.
    3. Cross-checks all fields (`ref_sha`, `ref_name`, `total_collected`, `passed_count`, `env_items_count`, `code_failures_count`, `status`, and `code_failures` list) against `delivery-evidence/branch_baselines/<ref>/ref_metadata.json`.
    4. Parses retained `junit.xml` per ref using `xml.etree.ElementTree`:
       - Counts `<testcase>` tags; asserts `len(testcases) == total_collected`.
       - Enforces uniqueness of testcase node identities (`seen_node_ids`).
       - Rejects conflicting outcome elements (`skipped` + `failure`/`error`) on individual testcases.
       - Independently counts `<failure>`, `<error>`, and `<skipped>` tags, recomputing `recomputed_code = actual_failures + actual_errors` and `recomputed_passed = total - (code + skipped)`.
       - Asserts recomputed values strictly match declared metrics.
       - Validates `<testsuite>` root attributes (`tests`, `failures`, `errors`, `skipped`).
  - Added 6 new adversarial guard tests in `tests/guards/test_baseline_hashes_guard.py`:
    - `test_load_and_validate_branch_classification_rejects_fabricated_pass` (fabricated `main` PASS metric with 8 failure records rejected).
    - `test_load_and_validate_branch_classification_rejects_env_breakdown_mismatch`.
    - `test_load_and_validate_branch_classification_rejects_tampered_metadata_count`.
    - `test_load_and_validate_branch_classification_rejects_tampered_junit_xml`.
    - `test_load_and_validate_branch_classification_rejects_missing_raw_evidence_file`.
    - `test_baseline_hashes_check_fails_on_tampered_raw_junit` (proves `tools/baseline_hashes.py --check` exits with code 1 when raw evidence is tampered).
  - Verified 21/21 tests in `test_baseline_hashes_guard.py` pass; verified all 77/77 guard tests pass.

---

## 5. Multi-Branch Baseline Evaluation & Test Classification

Evaluated via clean-install test runner on exact commit SHAs:

| Branch Ref | Exact Commit SHA | Total | Passed | Skipped (ENV) | Failed (CODE) | Suite Status | Architectural Notes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`main`** | `447caf96e356a836b0455ac6d845a6729a9e007f` | 248 | 240 | 0 | 8 | FAIL | Pre-H1a unconfined boundary failures |
| **`h0`** | `e60a089dbdd8d14394009f1c9661967d8d5b7b74` | 252 | 250 | 0 | 2 | FAIL | Pre-H1a boundary mock harness defects |
| **`h1a`** | `9c6e0fc9d21219f48c0235f3dc69687063f84061` | 270 | 270 | 0 | 0 | PASS | H1a trust model & test authority separation |
| **`h1b`** | `8b012f2dadf8785481b36e48598e34cc8a80c92f` | 315 | 315 | 0 | 0 | PASS | H1b real Bubblewrap & cgroup v2 sandbox |
| **`integration`** | `4af5aba9d9898bb10dd2e859cc6d8a4572fac157` | 2133 | 2133 | 0 | 0 | PASS | R30-B1 consolidated integration baseline |

---

## 6. Cross-Version Replay-from-Genesis Equality (B04)

- **Genesis State Digest:** `sha256:cb417280b6d7fa6c7ab1224f0c5d52ef63b2fd906fd0b1ac59edf22e6603afef`
- **Python 3.10 Final State Digest:** `sha256:41441988483b72e847838d077c635482396b0db35184ebb2cdf655a2759da674`
- **Python 3.12 Final State Digest:** `sha256:41441988483b72e847838d077c635482396b0db35184ebb2cdf655a2759da674`
- **Python 3.10 Final Head Hash:**    `sha256:8e2e52f13ee17addf9b60bc8e2850f7c911e4a894e507b842db614854599be3d`
- **Python 3.12 Final Head Hash:**    `sha256:8e2e52f13ee17addf9b60bc8e2850f7c911e4a894e507b842db614854599be3d`
- **Digest Equality Across Python 3.10 & 3.12:** **IDENTICAL (BIT-FOR-BIT MATCH)**
- **SQLite Store Replay Equivalence:** Verified identical to in-memory reducer replay.

---

## 7. Hard Invariant Compliance Verification

- [x] **No push to main:** All commits pushed strictly to branch `m1a-baseline` and `evidence-m1a-baseline`.
- [x] **No merge of M1-A PR:** PR #25 remains strictly OPEN and UNMERGED.
- [x] **No force-push, deletion, squash, or tags:** Linear clean commit history preserved.
- [x] **Protected files completely untouched:**
  - `00-SPEC/` — untouched (0 bytes modified)
  - `10-CONFORMANCE/` — untouched (0 bytes modified)
  - `20-RUNTIME/` — untouched (0 bytes modified)
  - `gate.py` — untouched
  - `Appendix A` — untouched
  - Master design file — untouched
  - MUST statuses — untouched
- [x] **Separation of Evidence:** Evidence files and delivery report maintained on `evidence-m1a-baseline`; product PR strictly limited to 9 files.
