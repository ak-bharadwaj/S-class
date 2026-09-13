# OSS Candidate Evaluation: Dagger

## 1. Candidate Overview
- **Project**: Dagger (`dagger/dagger`) — https://github.com/dagger/dagger
- **Purpose**: Programmable CI/CD and containerized execution engine. Delivers hermetic, cached, repeatable, observable pipelines defined as code in Python, TypeScript, or Go.
- **License**: Apache License 2.0 (SPDX: `Apache-2.0`). Compatible.
- **Primary Language / Ecosystem**: Go (core engine built on BuildKit), multi-language SDKs (Python, TypeScript, Go).

## 2. Maturity & Governance
- **Maturity**: Created by the founders of Docker in 2020. High production adoption for automated testing and containerized verification workloads.
- **Maintainer Health**: Full-time engineering team backed by Dagger Inc. with vibrant community support.
- **Release Cadence**: Rapid bi-weekly release cycle with stable GraphQL-based core engine API.

## 3. Engineering Rigor & Trustworthiness
- **Security**: Strict container isolation, build sandbox guarantees inherited from BuildKit, credential masking, secret scoping.
- **Testing**: Massive integration test suites testing multi-platform container builds, caching validity, and execution determinism.
- **Production Evidence**: Broad production use in enterprise CI/CD across Fortune 500 engineering teams.
- **Platform Coverage**: Linux, macOS (via container engine), Windows (via WSL2 or Docker desktop).
- **Protocol Compliance**: GraphQL API, OpenTelemetry trace export for every pipeline operation.
- **Performance**: High performance through multi-stage caching and parallel container execution graph.

## 4. Architectural Fit & S-Class Boundaries
- **Integration Cost**: Moderate. Requires local container runtime (Docker/Podman/Dagger Engine).
- **Failure Modes**: Docker daemon downtime, disk exhaustion from container layer cache, high cold-start latency compared to bare-metal host processes.
- **What We Adopt**: Dagger as an optional containerized `ExecutionBackend` for running hermetic verification workloads in isolated environments.
- **What We DON'T Adopt**: Dagger does NOT replace the S-Class execution engine for lightweight local developer loops. Direct host execution and lightweight sandboxes (bubblewrap) are required for low-latency feedback.
- **S-Class Wrapper**: `sclass.execution.backends.dagger_backend.DaggerExecutionBackend` implementing `ExecutionBackend`.
- **Escape Plan**: `ExecutionBackend` interface cleanly abstracts Dagger. S-Class can dispatch to Host, Bubblewrap, gVisor, or Dagger interchangeably.

## 5. Architectural Decision
- **Decision**: `EXTEND`
- **Architectural Tier**: Tier 2 (Pluggable Execution Backend)
- **Rationale Summary**: Dagger provides rock-solid hermetic execution and reproducible pipeline caching, making it an ideal backend for heavy verification or CI reproduction, without forcing local developers to pay a container startup penalty for every command.
