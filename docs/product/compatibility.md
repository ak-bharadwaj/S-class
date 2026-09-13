# S-Class Product Compatibility & Platform Support

## Operating Systems
- **Windows**: Windows 10/11, Windows Server (fully tested with Win32 process query API, path normalization, cmd/powershell execution).
- **Linux**: Ubuntu 20.04+, Debian, Fedora, Arch (`/proc` process inspection, POSIX signal handling).
- **macOS**: macOS 12+ (`proc_pidpath` support).

## Python Runtimes
- Python 3.10, 3.11, 3.12, 3.13, 3.14 (fully verified in WindowsApps and standard virtualenv environments).

## Ecosystem Verifiers
- Python: `pytest`, `unittest`
- JavaScript / TypeScript: `vitest`, `mocha`, `jest`, `playwright`, package scripts (`npm test`, `pnpm test`, `yarn test`, `bun test`)
- Rust: `cargo test`
- Go: `go test`
