# Ubuntu 24.04 AppArmor & Unprivileged User Namespaces Prerequisite

## 1. Background

Starting with Ubuntu 24.04 LTS (Noble Numbat), the Linux kernel defaults to restricting unprivileged user namespace creation:
```ini
kernel.apparmor_restrict_unprivileged_userns = 1
```
Because S-Class enforces strict unprivileged sandboxing via Bubblewrap (`bwrap`) without requiring root execution privileges, unconfined user namespace creation is restricted by default on unconfigured Ubuntu 24.04 installations.

When unprivileged user namespaces are restricted, S-Class strictly fails closed: `LinuxExecutionBoundary` detects that user namespaces are inoperative and raises `BoundaryUnavailable`. **Under no circumstances does S-Class fall back to unsandboxed execution.**

---

## 2. PRODUCTION Requirement (Mandatory)

In **PRODUCTION**, host administrators must maintain AppArmor enforcement and deploy the committed narrow AppArmor profile for Bubblewrap.

Do **NOT** disable kernel unprivileged user namespace restrictions globally.

### Production Setup Instructions:
1. Ensure `apparmor-utils` and `bubblewrap` are installed on the host:
   ```bash
   sudo apt-get update && sudo apt-get install -y apparmor-utils bubblewrap
   ```
2. Load and enforce the narrow S-Class Bubblewrap AppArmor profile:
   ```bash
   sudo apparmor_parser -r docs/security/bwrap-apparmor-profile
   ```
3. Verify that the profile is active:
   ```bash
   sudo aa-status | grep bwrap
   ```
   Expected output:
   ```text
   bwrap (/usr/bin/bwrap)
   ```

This profile permits `/usr/bin/bwrap` to request `userns` capabilities while executing unconfined within its own process boundary, allowing Bubblewrap to construct its sandboxed mount and network namespaces.

---

## 3. CI-Only / Development Alternative (Strictly Non-Production)

For automated continuous integration testing where ephemeral runner instances lack persistent AppArmor profile loading, the restriction may be relaxed at runner boot:

```bash
# CI-ONLY / DEVELOPMENT ONLY - DO NOT USE IN PRODUCTION
sudo sysctl -w kernel.apparmor_restrict_unprivileged_userns=0
```

> [!CAUTION]
> The `sysctl` method disables user namespace AppArmor mediation system-wide. It is strictly designated as **CI-only** and must **NEVER** be applied to multi-tenant, production, or customer-facing environments. Production hosts must always utilize the narrow AppArmor profile via `apparmor_parser`.
