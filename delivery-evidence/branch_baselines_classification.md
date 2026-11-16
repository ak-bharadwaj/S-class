# S-Class Branch Baselines Clean-Install Evaluation & Test Classification

- **Generated at:** 2026-11-16T13:10:01.211147+00:00
- **Platform:** `Linux-6.6.114.1-microsoft-standard-WSL2-x86_64-with-glibc2.43`
- **Python Version:** `3.12.16`

## Multi-Branch Verification Matrix

| Branch / Ref | Commit SHA | Install Mode | Total Collected | Passed | ENV Exclusions | CODE Failures | Result | Duration | Architectural Note |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `main` | `447caf96` | `unlocked_historical_exemption` | 248 | 240 | 0 | 8 | **FAIL** | 22.61s | Pre-H1a unconfined boundary failures |
| `h0` | `e60a089d` | `unlocked_historical_exemption` | 252 | 250 | 0 | 2 | **FAIL** | 23.28s | Pre-H1a boundary mock harness defects |
| `h1a` | `9c6e0fc9` | `unlocked_historical_exemption` | 270 | 269 | 0 | 1 | **FAIL** | 23.54s | H1a trust model & test authority separation |
| `h1b` | `8b012f2d` | `unlocked_historical_exemption` | 315 | 312 | 0 | 3 | **FAIL** | 28.13s | H1b real Bubblewrap & cgroup v2 sandbox |
| `integration` | `4af5aba9` | `hash_locked_strict` | 2133 | 2130 | 0 | 3 | **FAIL** | 53.80s | R30-B1 consolidated integration baseline |

## Individual CODE Failure Records by Ref

### Ref `main` (447caf96 - FAIL)
*8 CODE failure(s) recorded:*

- **`20-RUNTIME.test_sclass_runtime_v6_0_1::test_fail_closed_os_boundary_without_sandbox`**: PermissionError: cgroup v2 hierarchy is not writable by execution runtime
- **`20-RUNTIME.test_sclass_runtime_v6_0_1::test_process_tree_monitor_records_authorized_same_binary_child`**: assert 1 == 0
[+1 more line; full report in element text]
- **`tests.e2e.test_golden_vertical_slice::test_golden_vertical_slice_end_to_end`**: PermissionError: OS execution is callable only through ExecutionGate
- **`tests.e2e.test_golden_vertical_slice::test_golden_vertical_slice_arbitrary_component`**: PermissionError: OS execution is callable only through ExecutionGate
- **`tests.interfaces.test_mcp_server::test_mcp_server_dispatch_validate_patch_clean`**: json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
- **`tests.interfaces.test_mcp_server::test_mcp_server_dispatch_validate_patch_syntax_error`**: json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
- **`tests.workers.test_worker_harness::test_patch_agent_worker_mutation_and_authorization`**: PermissionError: unauthorized executable/process-tree identity observed
- **`tests.workers.test_worker_harness::test_subprocess_tool_worker_execution`**: PermissionError: running executable identity does not match authorized digest

### Ref `h0` (e60a089d - FAIL)
*2 CODE failure(s) recorded:*

- **`20-RUNTIME.test_sclass_runtime_v6_0_1::test_fail_closed_os_boundary_without_sandbox`**: PermissionError: cgroup v2 hierarchy is not writable by execution runtime
- **`20-RUNTIME.test_sclass_runtime_v6_0_1::test_process_tree_monitor_records_authorized_same_binary_child`**: assert 1 == 0
[+1 more line; full report in element text]

### Ref `h1a` (9c6e0fc9 - FAIL)
*1 CODE failure(s) recorded:*

- **`tests.security.test_boundary_hardening::test_shipped_modules_never_import_from_tests`**: subprocess.CalledProcessError: Command '['/tmp/tmp04s69rtq/h1a/.venv/bin/python', '-m', 'pip', 'wheel', '--no-deps', '-w', '/tmp/tmpi3itk1i_/dist', '/tmp/tmp04s69rtq/h1a']' returned non-zero exit status 1.

### Ref `h1b` (8b012f2d - FAIL)
*3 CODE failure(s) recorded:*

- **`tests.security.test_boundary_hardening::test_shipped_modules_never_import_from_tests`**: subprocess.CalledProcessError: Command '['/tmp/tmp04s69rtq/h1b/.venv/bin/python', '-m', 'pip', 'wheel', '--no-deps', '-w', '/tmp/tmpjuua3ey0/dist', '/tmp/tmp04s69rtq/h1b']' returned non-zero exit status 1.
- **`tests.security.test_boundary_hardening::test_m2_no_env_key_reads_and_tamper_fails_gate6`**: AssertionError: Gate 6 failed unexpectedly on clean repo: 
  === Gate 6: Environment Variable Security Gate (BLOCKING) ===
  
  [1] os.environ / os.getenv accesses in src/ (0 found):
  
  [2] os.environ / os.getenv accesses in shipped kernel files (1 found):
[+12 more lines; full report in element text]
- **`tests.security.test_boundary_hardening::test_m11_pip_audit_and_hash_pinned_constraints`**: AssertionError: Expected hash enforcement error, got: /tmp/tmp04s69rtq/h1b/.venv/bin/python: No module named pip
  
[+7 more lines; full report in element text]

### Ref `integration` (4af5aba9 - FAIL)
*3 CODE failure(s) recorded:*

- **`tests.security.test_boundary_hardening::test_shipped_modules_never_import_from_tests`**: subprocess.CalledProcessError: Command '['/tmp/tmp04s69rtq/integration/.venv/bin/python', '-m', 'pip', 'wheel', '--no-deps', '-w', '/tmp/tmpf7n98877/dist', '/tmp/tmp04s69rtq/integration']' returned non-zero exit status 1.
- **`tests.security.test_boundary_hardening::test_m2_no_env_key_reads_and_tamper_fails_gate6`**: AssertionError: Gate 6 failed unexpectedly on clean repo: 
  === Gate 6: Environment Variable Security Gate (BLOCKING) ===
  
  [1] os.environ / os.getenv accesses in src/ (0 found):
  
  [2] os.environ / os.getenv accesses in shipped kernel files (1 found):
    20-RUNTIME/sclass_runtime_v6_0_1.py:2094 [environ] -> env=EnvironmentFingerprint(os.uname().sysname,os.uname().machine,digest("sclass/toolchain/v1",(sys.executable,sys.version.split()[0])),digest("sclass/env-names/v1",tuple(sorted(os.environ.keys()))),None) [ALLOWLISTED]
  
  [3] os.environ / os.getenv accesses in built wheel package (1 found):
    wheel_build_failure:0 [error] -> /tmp/tmp04s69rtq/integration/.venv/bin/python: No module named pip [UNAUTHORIZED]
  
  FAILED: 1 unauthorized environment variable reads outside allowlist detected:
    ! wheel_build_failure:0 -> /tmp/tmp04s69rtq/integration/.venv/bin/python: No module named pip
  
  === Gate 6 Result: FAIL ===
  
assert 1 == 0
 +  where 1 = CompletedProcess(args=['/tmp/tmp04s69rtq/integration/.venv/bin/python', '/tmp/tmp04s69rtq/integration/tools/gates/gate_env_vars.py'], returncode=1, stdout='=== Gate 6: Environment Variable Security Gate (BLOCKING) ===\n\n[1] os.environ / os.getenv accesses in src/ (0 found):\n\n[2] os.environ / os.getenv accesses in shipped kernel files (1 found):\n  20-RUNTIME/sclass_runtime_v6_0_1.py:2094 [environ] -> env=EnvironmentFingerprint(os.uname().sysname,os.uname().machine,digest("sclass/toolchain/v1",(sys.executable,sys.version.split()[0])),digest("sclass/env-names/v1",tuple(sorted(os.environ.keys()))),None) [ALLOWLISTED]\n\n[3] os.environ / os.getenv accesses in built wheel package (1 found):\n  wheel_build_failure:0 [error] -> /tmp/tmp04s69rtq/integration/.venv/bin/python: No module named pip [UNAUTHORIZED]\n\nFAILED: 1 unauthorized environment variable reads outside allowlist detected:\n  ! wheel_build_failure:0 -> /tmp/tmp04s69rtq/integration/.venv/bin/python: No module named pip\n\n=== Gate 6 Result: FAIL ===\n', stderr='').returncode
- **`tests.security.test_boundary_hardening::test_m11_pip_audit_and_hash_pinned_constraints`**: AssertionError: Expected hash enforcement error, got: /tmp/tmp04s69rtq/integration/.venv/bin/python: No module named pip
  
assert ('must have their versions pinned with ==' in '/tmp/tmp04s69rtq/integration/.venv/bin/python: No module named pip\n' or 'must have their versions pinned with ==' in '' or 'is not pinned with a hash' in '/tmp/tmp04s69rtq/integration/.venv/bin/python: No module named pip\n' or 'is not pinned with a hash' in '' or 'require-hashes' in '/tmp/tmp04s69rtq/integration/.venv/bin/python: No module named pip\n' or 'require-hashes' in '')
 +  where '/tmp/tmp04s69rtq/integration/.venv/bin/python: No module named pip\n' = CompletedProcess(args=['/tmp/tmp04s69rtq/integration/.venv/bin/python', '-m', 'pip', 'install', '--dry-run', '--require-hashes', '-r', '/tmp/tmplp1uq8an.txt'], returncode=1, stdout='', stderr='/tmp/tmp04s69rtq/integration/.venv/bin/python: No module named pip\n').stderr
 +  and   '' = CompletedProcess(args=['/tmp/tmp04s69rtq/integration/.venv/bin/python', '-m', 'pip', 'install', '--dry-run', '--require-hashes', '-r', '/tmp/tmplp1uq8an.txt'], returncode=1, stdout='', stderr='/tmp/tmp04s69rtq/integration/.venv/bin/python: No module named pip\n').stdout
 +  and   '/tmp/tmp04s69rtq/integration/.venv/bin/python: No module named pip\n' = CompletedProcess(args=['/tmp/tmp04s69rtq/integration/.venv/bin/python', '-m', 'pip', 'install', '--dry-run', '--require-hashes', '-r', '/tmp/tmplp1uq8an.txt'], returncode=1, stdout='', stderr='/tmp/tmp04s69rtq/integration/.venv/bin/python: No module named pip\n').stderr
 +  and   '' = CompletedProcess(args=['/tmp/tmp04s69rtq/integration/.venv/bin/python', '-m', 'pip', 'install', '--dry-run', '--require-hashes', '-r', '/tmp/tmplp1uq8an.txt'], returncode=1, stdout='', stderr='/tmp/tmp04s69rtq/integration/.venv/bin/python: No module named pip\n').stdout
 +  and   '/tmp/tmp04s69rtq/integration/.venv/bin/python: No module named pip\n' = CompletedProcess(args=['/tmp/tmp04s69rtq/integration/.venv/bin/python', '-m', 'pip', 'install', '--dry-run', '--require-hashes', '-r', '/tmp/tmplp1uq8an.txt'], returncode=1, stdout='', stderr='/tmp/tmp04s69rtq/integration/.venv/bin/python: No module named pip\n').stderr
 +  and   '' = CompletedProcess(args=['/tmp/tmp04s69rtq/integration/.venv/bin/python', '-m', 'pip', 'install', '--dry-run', '--require-hashes', '-r', '/tmp/tmplp1uq8an.txt'], returncode=1, stdout='', stderr='/tmp/tmp04s69rtq/integration/.venv/bin/python: No module named pip\n').stdout
