# S-Class Execution Model

## 1. Execution Modes

S-Class categorizes execution into four explicit modes defined in `ExecutionMode`:

1. `HOST_ARGV`: Direct execution of target binary with explicit tokenized argument array (`argv`). No shell interpreter is invoked. Shell metacharacters (`;`, `&&`, `||`, `|`, etc.) are prohibited or treated as literal arguments.
2. `HOST_SHELL`: Execution via host shell (`cmd.exe`, `powershell`, `/bin/sh`, `/bin/bash`). Restricted under policy; chained commands and dangerous expansions are scrutinized.
3. `CONTAINER`: Execution inside an isolated container runtime (Docker, Podman).
4. `SANDBOX`: Execution inside an OS-level sandbox (seccomp, pledge, AppContainer).

## 2. ProcessRunner & Execution Identity

`ProcessRunner` manages process lifecycle:
- Launches sub-processes without invoking an intermediate shell whenever possible.
- Captures child process PID directly from OS process handle.
- Inspects real binary executable on disk:
  - Resolves symlinks, hardlinks, and Windows reparse points.
  - Computes SHA-256 hash of the binary file image.
  - Fallback logic protects against zero-byte stub executables (such as WindowsApps reparse points).
- Builds `ExecutionChain`: tracks child PID, parent PID, wrapper binaries (e.g., `cmd.exe -> npx.cmd -> vitest`), and target executable.
- OpenTelemetry semantic conventions are mapped to capture process telemetry with sensitive environment variable redaction.
