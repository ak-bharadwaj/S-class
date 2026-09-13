# OSS Candidate Evaluation: Bubblewrap (`bwrap`)

## 1. Candidate Overview
- **Project**: Bubblewrap (`containers/bubblewrap`) — https://github.com/containers/bubblewrap
- **Purpose**: Low-level, unprivileged sandboxing tool for Linux based on user, mount, network, PID, and IPC namespaces. Allows running untrusted code with restricted access to the filesystem and operating system resources.
- **License**: GNU Lesser General Public License v2.1 or later (SPDX: `LGPL-2.1-or-later`). Permissive for execution wrappers and external CLI invocations.
- **Primary Language / Ecosystem**: C. Standard binary available in all major Linux distributions (used by Flatpak).

## 2. Maturity & Governance
- **Maturity**: Developed by Project Atomic / Red Hat in 2016 to power Flatpak desktop application sandboxing. Over a decade of hardening in Linux distributions.
- **Maintainer Health**: Maintained by the Red Hat / GNOME / containers team. Conservative, high-discipline codebase focused solely on namespace isolation.
- **Release Cadence**: Conservative release cadence; stable command-line interface.

## 3. Engineering Rigor & Trustworthiness
- **Security**: Designed specifically to run without `setuid` root privileges (unprivileged user namespaces). Extensively audited by Red Hat and GNOME security teams.
- **Testing**: Regression suites covering namespace separation, bind mounts, pivot-root attacks, seccomp filters, and file descriptor leaks.
- **Production Evidence**: Core isolation mechanism protecting millions of Linux desktops running Flatpak applications daily.
- **Platform Coverage**: Linux only (requires Linux user/mount namespaces). Not available natively on macOS or Windows.
- **Protocol Compliance**: POSIX command-line execution and standard Unix file descriptors.
- **Performance**: Near-native process execution speed with negligible startup overhead (<5ms).

## 4. Architectural Fit & S-Class Boundaries
- **Integration Cost**: Low on Linux. Invoked via subprocess argv compilation.
- **Failure Modes**: Missing user namespace support in host kernel, misconfigured mount table leaking host paths.
- **What We Adopt**: Linux process sandboxing mechanism: filesystem read-only masking, workspace-only write bind mounts, network isolation (`--unshare-net`), process table isolation (`--unshare-pid`).
- **What We DON'T Adopt**: Bubblewrap is an isolation primitive, NOT a security policy. S-Class compiles declarative security policies into Bubblewrap arguments; Bubblewrap does not make policy decisions.
- **S-Class Wrapper**: `sclass.execution.backends.bubblewrap_backend.BubblewrapExecutionBackend` implementing `ExecutionBackend`.
- **Escape Plan**: `ExecutionBackend` protocol interface allows switching between Host, Bubblewrap, gVisor, or platform-native isolation mechanisms (such as macOS sandbox-exec or Windows Job Objects / AppContainers).

## 5. Architectural Decision
- **Decision**: `WRAP`
- **Architectural Tier**: Tier 2 (Pluggable Linux Execution Backend)
- **Rationale Summary**: Writing custom Linux container namespaces or seccomp filters is dangerous and unnecessary. Bubblewrap provides battle-tested, unprivileged Linux process sandboxing that S-Class policy compilers can target directly.
