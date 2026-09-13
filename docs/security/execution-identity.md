# Execution Identity Verification

## 1. Ground Truth Process Capture
`ExecutionIdentity` establishes ground truth by querying OS kernel interfaces:
- **Windows**: Uses `ctypes.windll.kernel32.QueryFullProcessImageNameW` to obtain the exact executable image backing the running process PID. Handles WindowsApps reparse points and execution aliases.
- **Linux**: Resolves `/proc/{pid}/exe` symlink to find the underlying ELF binary image.
- **macOS**: Queries `proc_pidpath`.

## 2. Binary Image Integrity
For every executed command:
- Resolves executable binary path.
- Computes SHA-256 hash of the binary file image on disk.
- Captures true child process PID.
- Captures parent PID and wrapper execution chains.

This prevents agents from executing malicious binaries disguised with common names (such as a local script named `pytest`).
