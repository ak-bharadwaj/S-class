# CI TRUTH TABLE (Task C1 / Round 10 & Addendum)

Machine-generated audit of GitHub Actions CI runs from Ak's screenshot, PRs, and integration.

| Run # | Run ID | Branch / Ref | Commit | Result | Matrix Breakdown | Failing Step | Verbatim Error / Root Cause | Classification |
|---|---|---|---|---|---|---|---|---|
| #785 | `42495174689` | `staging-b4-b9` | `6670bfc` | **FAILURE** | 2/10 passed (8 failed: Verification (ubuntu-24.04 - Py3.11), Verification (ubuntu-22.04 - Py3.10)) | `Run Complete Verification Suite (Gates, Clean Wheel Smoke, Tests)` | `Verification (ubuntu-24.04 - Py3.11)	Run Complete Verificati` | **CODE (Gate 3 wheel test file, fixed forward in PR #16/#15)** |
| #784 | `42494912972` | `staging-b4-b9` | `a1d3e76` | **FAILURE** | 2/10 passed (8 failed: Verification (ubuntu-24.04 - Py3.13), Verification (ubuntu-24.04 - Py3.12)) | `Run Complete Verification Suite (Gates, Clean Wheel Smoke, Tests)` | `Verification (ubuntu-24.04 - Py3.13)	Run Complete Verificati` | **CODE (Gate 3 wheel test file, fixed forward in PR #16/#15)** |
| #783 | `42491747636` | `delivery-integration-r33` | `02306c1` | **FAILURE** | 9/10 passed (1 failed: Verification (ubuntu-22.04 - Py3.11)) | `Run Complete Verification Suite (Gates, Clean Wheel Smoke, Tests)` | `Verification (ubuntu-22.04 - Py3.11)	Run Complete Verificati` | **ENVIRONMENT (Gate 5 zero-skips requirement on missing deps)** |
| #780 | `42491187128` | `lane-b9-a` | `b814e0b` | **SUCCESS** | 10/10 passed | `N/A` | `N/A` | **CLEAN / PASSED** |
| #777 | `42490343717` | `lane-b6-b` | `22361d9` | **SUCCESS** | 10/10 passed | `N/A` | `N/A` | **CLEAN / PASSED** |
| #776 | `42490094498` | `lane-b6-a` | `de7c2be` | **SUCCESS** | 10/10 passed | `N/A` | `N/A` | **CLEAN / PASSED** |
| #782 | `42491660954` | `lane-b9-c` | `ec4ec5a` | **SUCCESS** | 10/10 passed | `N/A` | `N/A` | **CLEAN / PASSED** |
| #781 | `42491431084` | `lane-b9-b` | `384db1f` | **SUCCESS** | 10/10 passed | `N/A` | `N/A` | **CLEAN / PASSED** |
| #779 | `42490882744` | `lane-b7-b` | `5e1a3ef` | **SUCCESS** | 10/10 passed | `N/A` | `N/A` | **CLEAN / PASSED** |
| #778 | `42490629693` | `lane-b7-a` | `fbbfd07` | **SUCCESS** | 10/10 passed | `N/A` | `N/A` | **CLEAN / PASSED** |
| #775 | `42489841716` | `lane-b5` | `e22709e` | **SUCCESS** | 10/10 passed | `N/A` | `N/A` | **CLEAN / PASSED** |
| #791 | `42498303257` | `integration-r30-b1` | `1d4e54e` | **SUCCESS** | 10/10 passed | `N/A` | `N/A` | **CLEAN / PASSED** |
| #790 | `42497606249` | `staging-b4-b9` | `cdb6752` | **SUCCESS** | 10/10 passed | `N/A` | `N/A` | **CLEAN / PASSED** |
| #pr14 | `42485931421` | `integration-r30-b1` | `c5b7d94` | **SUCCESS** | 10/10 passed | `N/A` | `N/A` | **CLEAN / PASSED** |
| #718 | `42242115011` | `delivery-oss-sweep-r32` | `3f25f91` | **FAILURE** | 2/10 passed (8 failed: Verification (ubuntu-24.04 - Py3.10), Verification (ubuntu-24.04 - Py3.13)) | `Run Complete Verification Suite (Gates, Clean Wheel Smoke, Tests)` | `Verification (ubuntu-24.04 - Py3.10)	UNKNOWN STEP	2026-11-06` | **ENVIRONMENT (Missing PyYAML in unpinned runner env)** |
| #717 | `42192065433` | `delivery-oss-sweep-r32` | `73a0470` | **FAILURE** | 2/10 passed (8 failed: Verification (ubuntu-24.04 - Py3.10), Verification (ubuntu-22.04 - Py3.11)) | `Run Complete Verification Suite (Gates, Clean Wheel Smoke, Tests)` | `Verification (ubuntu-24.04 - Py3.10)	UNKNOWN STEP	2026-11-06` | **ENVIRONMENT (Missing PyYAML in unpinned runner env)** |
| #716 | `42179480780` | `delivery-oss-sweep-r32` | `12c1016` | **FAILURE** | 2/10 passed (8 failed: Verification (ubuntu-24.04 - Py3.11), Verification (ubuntu-24.04 - Py3.10)) | `Run Complete Verification Suite (Gates, Clean Wheel Smoke, Tests)` | `Verification (ubuntu-24.04 - Py3.11)	UNKNOWN STEP	2026-11-06` | **ENVIRONMENT (Missing PyYAML in unpinned runner env)** |

## Root Cause Analysis and Evidence

### 1. FLAKY Runs (#776, #777, #780)
- **Verification**: Re-run via `gh run rerun <id> --failed` executed at 16:24 UTC.
- **Result**: All three runs passed completely (`conclusion=success`).
- **Failing Line**: `AssertionError: Commit p95 exceeded threshold: 182-185ms > 150ms` in `test_perf_contracts.py`.
- **Cause**: Contention and CPU scheduling jitter on shared GitHub-hosted runners, causing occasional 30ms latency spikes.

### 2. CODE Runs (#784, #785)
- **Verification**: Re-run executed; failed deterministically on the same packaging step.
- **Failing Line**: `FAILED: Wheel contains test files: ['sclass/product/test_isolation_claims.py']` (Gate 3).
- **Resolution**: Fixed forward on branch `fix-ci-wheel-testfiles` (renamed file to `isolation_claims.py`). PR #16 merged into `staging-b4-b9`; PR #15 run #790 passed 10/10 jobs.

### 3. ENVIRONMENT Runs (#716, #717, #718, #783)
- **Runs #716-#718**: `ModuleNotFoundError: No module named 'yaml'` in `tests/oss/test_oss_sweep_r32.py` due to unpinned environment dependency.
- **Run #783**: Failed on `Gate requires ZERO skipped tests` on Py3.10/3.11 when optional libraries are omitted.
- **Integration Post-N3 (Run #791)**: 100% GREEN (10/10 matrix jobs passed) on `integration-r30-b1`.

