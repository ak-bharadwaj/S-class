# Phase H1b: Real enforcement and secret hygiene (DRAFT for owner review)

**Status**: DESIGNED  
**Author**: Evaluator (committed by builder as `docs/phases/H1b.md` after owner approval)  
**Branch**: `h1b`, created from frozen `h1a` head `9c6e0fc9d21219f48c0235f3dc69687063f84061`  
**Base**: All H1b diffs and grading are against `9c6e0fc9d21219f48c0235f3dc69687063f84061`, not against `main`.  
**Rules**: `00-SPEC` frozen and byte-untouched. Kernel changes only through declared hunks in `docs/KERNEL-CHANGES.md`. Do not touch `main`, `h0`, or `h1a`.

---

## 1. Goal

The boundary that was designed in H1a must actually run, and key material and environment must stop leaking. At the end of H1b a worker can only run inside a real Bubblewrap + cgroup v2 boundary, with a minimal environment, and the control plane trusts only keys loaded from a protected file.

---

## 2. Spec Sections

- §2.2 (trust roots)
- §8.6 (execution boundary)
- §13, §18 (quiescence, attestor)
- ZV10 / CredentialBroker (secrets)

---

## 3. MUSTs and Test Mapping

Every test must fail if the fix is reverted.

| ID | MUST | Required Test | Test Path |
|---|---|---|---|
| **M1** | Preflight compares the attestor's own public key (from its private key) to the pinned public key and rejects a mismatch BEFORE any process spawns. | Right key_id/root + wrong private key -> PermissionError at preflight, sentinel proves no spawn. | `tests/security/test_boundary_hardening.py::test_m1_preflight_rejects_attestor_private_key_mismatch` |
| **M2** | `LocalQuiescenceAttestor.from_environment` is deleted. No key, root or pin is read from `os.environ` anywhere in `20-RUNTIME/` or `src/`. | Gate 6 fails on any new env read in these trees outside an explicit allowlist file; tamper: re-add an env read -> gate fails. The env-read allowlist is a separate committed file, starts with ZERO entries for key, root, pin or private-key names, and every addition is declared in the report. | `tests/security/test_boundary_hardening.py::test_m2_no_env_key_reads_and_tamper_fails_gate6` |
| **M3** | Pins and keys load from a protected file: regular file (no symlink), mode <= 0600, owned by the service user, fail closed on any violation or if missing. | Parametrize so each case is its own reported test: mode 0644, symlink, wrong owner, missing file, malformed JSON: each raises and the control plane is not constructed. | `tests/security/test_boundary_hardening.py::test_m3_protected_pin_file_permissions_and_ownership` |
| **M4** | Workers and verifiers run with a minimal allowlisted environment (fixed PATH, locale, workspace-local HOME/TMPDIR). Nothing from the parent environment passes through. | Parametrize so each case is its own reported test: secret placed in parent env is absent in child for: worker harness, verification engine, and each of the 5 adapters (cosmic_ray, locust, playwright, schemathesis, testcontainers). Zero `os.environ.copy()` remain in `src/`. | `tests/security/test_boundary_hardening.py::test_m4_minimal_allowlisted_env_scrubs_parent_secrets` |
| **M5** | Real Bubblewrap + cgroup v2 execution on Linux CI. Confined process cannot write outside the workspace, has no network, is killed with its whole process tree on timeout, and obeys memory and pids limits. | Replace the single test with five: write outside workspace denied, no network, process-tree kill on timeout, memory limit, pids limit, run on ubuntu-22.04 and ubuntu-24.04. Raw artifact kept. | `tests/security/test_boundary_hardening.py::test_m5_*` (5 tests: write outside workspace denied, no network, timeout process-tree kill, memory limit, pids limit) |
| **M6** | Host without usable user namespaces or cgroup v2 -> BoundaryUnavailable, never an unsandboxed run. | CI job with bwrap unavailable (or blocked) expects BoundaryUnavailable and a sentinel file that proves no worker started. | `tests/security/test_boundary_hardening.py::test_m6_missing_bwrap_or_cgroup_fails_closed_boundary_unavailable` |
| **M7** | The Ubuntu 24.04 prerequisite is documented and applied in CI explicitly: preferred a narrow bwrap AppArmor profile, otherwise a CI-only sysctl, stated in the workflow and in docs/. Not a silent default. | Workflow step visible in CI log; doc states the PRODUCTION requirement honestly. M7 and M11 are graded on CI logs/artifacts (AppArmor step visible, --require-hashes install, pip-audit artifact), not on the pytest alone. | `tests/security/test_boundary_hardening.py::test_m7_ubuntu_24_04_apparmor_prerequisite_and_docs` |
| **M8** | `shell=True` at `src/sclass/workspace/worktrees.py:142` is removed. Remaining `except Exception` in kernel, gate and worker paths are triaged: narrowed or justified in a committed table. | Test that the removed call path rejects shell metacharacters; triage table committed (file and line, decision). | `tests/security/test_boundary_hardening.py::test_m8_worktrees_rejects_shell_metacharacters_and_triage_table` |
| **M9** | The `_*_for_test` methods in `20-RUNTIME/` are either unreachable from production objects (moved under `tests/` via a declared kernel change) or proven non-authoritative. | Test enumerating public and underscore callables of runtime classes finds no budget/limit/consume mutator that bypasses canonical paths, or the methods are gone. | `tests/security/test_boundary_hardening.py::test_m9_no_test_only_mutators_on_runtime_classes` |
| **M10** | `PatchAgentWorker` / `SubprocessToolWorker` with a boundary lacking a gate capability fail closed. | Test with a boundary object lacking `_gate_capability`: PermissionError, no spawn. | `tests/security/test_boundary_hardening.py::test_m10_worker_boundary_without_gate_capability_fails_closed` |
| **M11** | CI installs with hashes (`--require-hashes`) and runs `pip-audit`; results stored as artifacts. | CI step and artifact; a deliberately unpinned requirement fails the job. | `tests/security/test_boundary_hardening.py::test_m11_pip_audit_and_hash_pinned_constraints` |

---

## 4. Recommended Split

Move the Gitleaks adapter and seeded-secret corpus test (consolidated report item C6) to H2. M1-M11 is already a full phase, and wide phases hide defects. Owner decides.

---

## 5. Out of Scope

- Real workers (OpenHands / ACP)
- MCP
- New features
- Non-Linux platforms
- Firecracker / gVisor / Landlock
- Mutation reproduction (H2)
- Egress proxy

---

## 6. Builder Rules (Unchanged)

- No weakened, skipped or xfail tests.
- No env-var switch may change security behavior.
- Numbers come from machine-captured logs.
- Linux CI evidence.
- No force-push.
- Labels allowed: `DESIGNED`, `SCAFFOLDED (UNVERIFIED)`, `IMPLEMENTED (UNVERIFIED)`; only the external evaluator writes `VERIFIED` or `Qualified`.
- Think like the attacker first: for every MUST, write the bypass as a failing test before the fix.

---

## 7. Grading (Evaluator, Clean Clone)

1. `bash tools/verify_all.sh` on a machine WITHOUT bwrap: `BoundaryUnavailable` tests pass, 0 skipped.
2. CI artifact digests copied from the run page; real-bwrap tests present in the 22.04 and 24.04 logs.
3. Reintroduce each bypass (env read, bare Popen, weak file mode, wrong-key attestor, `os.environ.copy()`): a test or gate must fail each time.
4. Own attack scripts against the new API; kernel diff only in declared hunks (`git diff 9c6e0fc..HEAD`); spec and conformance byte-identical.

---

## 8. Unverified Items to Declare

- Anything not executed on real hardware (cgroup limits on non-CI hosts)
- Mutation result (until H2)
