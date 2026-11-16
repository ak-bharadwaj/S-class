# S-Class Branch Baselines Clean-Install Evaluation & Test Classification

- **Generated at:** 2026-11-14T11:48:48.381489+00:00
- **Platform:** `Linux-6.6.114.1-microsoft-standard-WSL2-x86_64-with-glibc2.43`
- **Python Version:** `3.12.16`

## Multi-Branch Verification Matrix

| Branch / Ref | Commit SHA | Total Collected | Passed | ENV Exclusions | CODE Failures | Result | Duration | Architectural Note |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `main` | `447caf96` | 248 | 240 | 0 | 8 | **FAIL** | 20.71s | Pre-H1a unconfined boundary failures |
| `h0` | `e60a089d` | 252 | 250 | 0 | 2 | **FAIL** | 21.84s | Pre-H1a boundary mock harness defects |
| `h1a` | `9c6e0fc9` | 270 | 270 | 0 | 0 | **PASS** | 25.70s | H1a trust model & test authority separation |
| `h1b` | `8b012f2d` | 315 | 315 | 0 | 0 | **PASS** | 49.32s | H1b real Bubblewrap & cgroup v2 sandbox |
| `integration` | `4af5aba9` | 2133 | 2133 | 0 | 0 | **PASS** | 79.16s | R30-B1 consolidated integration baseline |

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

### Ref `h1a` (9c6e0fc9 - PASS)
*0 CODE failures. Clean pass.*

### Ref `h1b` (8b012f2d - PASS)
*0 CODE failures. Clean pass.*

### Ref `integration` (4af5aba9 - PASS)
*0 CODE failures. Clean pass.*
