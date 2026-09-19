# Layer C — Execution Plane

Decouples authorization policy from underlying execution backends:
```text
S-Class Authorizes ──▶ Execution Provider Dispatches ──▶ S-Class Observes
```
Supported providers:
- `NativeProcessProvider`: Direct host process execution.
- `BubblewrapProvider`: Linux unprivileged user namespaces.
- `DaggerProvider`: Reproducible containerized execution pipelines.
