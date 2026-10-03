# Architecture Decision Record (ADR-3): Ambient Security Switches and Boundary Authority Material

## Status
Accepted (Phase H1a Report & Investigation)

## Context & The "No Ambient Switch" Architectural Principle

A foundational requirement of the S-Class v6.0.1 Trust and Control Plane is that **execution authority, sandboxing enforcement, and cryptographic trust decisions must never depend on ambient, unauthenticated state**.

In Phases H0 and earlier prototypes, the codebase contained ambient security switches:
- `SCLASS_TEST_MODE`: An ambient environment variable that permitted bypassing Bubblewrap namespace isolation, allowed raw boundary execution, permitted unprovisioned quiescence attestors, and relaxed `ExecutionGate` preflight checks.
- Ad-hoc environment variable reads for cryptographic keys: `SCLASS_BOUNDARY_TRUST_ROOT`, `SCLASS_BOUNDARY_KEY_ID`, and `SCLASS_BOUNDARY_PRIVATE_KEY_B64`.

Under Phase H1a, all ambient security bypass switches (`SCLASS_TEST_MODE`, `TEST_MODE`, `SCLASS_UNSANDBOXED`, `INSECURE`) have been eliminated from shipped runtime code. Gate 6 has been converted to a blocking security gate that fails build/release if any such switch is detected.

This ADR documents the investigation of the remaining ambient environment reads in `20-RUNTIME/sclass_runtime_v6_0_1.py` lines 1865–1867 and defines their replacement architecture.

---

## Investigation: Ambient Boundary Authority Material (Lines 1865–1867)

### 1. Code Site & Inspection
In `20-RUNTIME/sclass_runtime_v6_0_1.py` (lines 1863–1875):
```python
@classmethod
def from_environment(cls, keys: SQLiteKeyDirectory):
    root = os.environ.get("SCLASS_BOUNDARY_TRUST_ROOT")
    key_id = os.environ.get("SCLASS_BOUNDARY_KEY_ID")
    raw = os.environ.get("SCLASS_BOUNDARY_PRIVATE_KEY_B64")
    if not root or not key_id or not raw:
        return None
    try:
        private = Ed25519PrivateKey.from_private_bytes(base64.b64decode(raw, validate=True))
    except Exception as exc:
        raise PermissionError("invalid provisioned boundary private key") from exc
    return cls(keys, root, key_id, private, _provisioning_token=_BOUNDARY_PROVISIONING_TOKEN)
```

### 2. Who Reads Them?
The method `LocalQuiescenceAttestor.from_environment(keys)` is invoked exclusively during control plane bootstrap:
- In `SClassControlPlane.__init__()` (line 924):
  ```python
  self.boundary_attestor = (
      LocalQuiescenceAttestor.from_environment(self.keys)
      or UnprovisionedQuiescenceAuthority()
  )
  ```
If any of the three environment variables is missing, `from_environment()` returns `None`, falling back to `UnprovisionedQuiescenceAuthority()`.

### 3. What Trust Decision Do They Control?
These variables control the **cryptographic attestation of OS process boundary quiescence**:
1. `LocalQuiescenceAttestor.attest()` uses `private` (an Ed25519 private key) to sign `QuiescenceProof` structures over the domain `"sclass/quiescence-attestation/v3"`.
2. A `QuiescenceProof` certifies that:
   - A specific OS process ID and start time (`process_id`, `process_start_time_ns`) ran under the boundary.
   - The executed binary matches the authorized `ExecutionIdentity` digest.
   - All descendant child processes in the process tree have completed and quiescence has been achieved.
3. The `ExecutionGate` requires an authentic, cryptographically validated `QuiescenceProof` before committing state mutations (`MutationObserved`, `ExecutionCompleted`) and before settling resource budgets.
4. If an actor possesses or can inject this private key, they can forge valid quiescence proofs for unconfined, hostile, or arbitrarily modified processes, bypassing all OS boundary verification.

### 4. How Could a Hostile Process Read or Set Them?
Because process environment variables are ambient and shared across process hierarchies in Unix/Linux systems:
1. **Shared Process Environment**: Any child process spawned without explicit `clearenv()` or environment filtering can read parent environment variables via `/proc/self/environ` or `os.environ`.
2. **Same-UID Process Inspection**: On Linux systems where `ptrace_scope` allows it or within the same container, any process running under the same user UID can read `/proc/<control_plane_pid>/environ`, disclosing the base64-encoded private key.
3. **Parent Shell / CI / Orchestrator Injection**: If an attacker gains code execution in a build pipeline, container orchestrator, or preflight hook, they can inject malicious `SCLASS_BOUNDARY_*` values into the environment before the control plane boots.
4. **Log & Crash Dump Exposure**: Ambient environment variables are frequently dumped into crash reports, CI debug logs, monitoring traces, or `ps -ef e` listings.

---

## Proposed Replacement Architecture

To adhere to the "No Ambient Switch" principle, ambient environment variable reads must be replaced with **explicit dependency injection and protected key stores**:

### 1. Injected KeyDirectory
Instead of parsing base64 blobs from `os.environ`, the control plane and attestor will receive their signing keys via an explicit `KeyDirectory` instance:
```python
# Proposed: Explicit Key Directory Injection
class LocalQuiescenceAttestor:
    def __init__(
        self,
        keys: SQLiteKeyDirectory,
        key_id: str,
        private: Ed25519PrivateKey,
    ):
        ...
```

### 2. Protected Local Key File (Option B)
For standalone CLI and daemon services requiring persistent local boundary identity:
- Store the private key in a filesystem path protected by OS access controls:
  - Default path: `/etc/sclass/boundary_key.pem` (or `/run/sclass/boundary.key`)
  - Permissions: strictly `0400` or `0600`, owned by the dedicated `sclass` service UID / root.
  - The attestor validates `stat().st_mode` and file ownership before reading. If permissions are too permissive, it fails closed.
- The path is passed explicitly via constructor or configuration file, never implicitly picked up from untrusted environment variables.

### 3. Mutual Ephemeral Attestation (Option C)
For distributed or containerized workers:
- The control plane generates an ephemeral Ed25519 keypair in memory during startup, registers the public key into the canonical `runtime_keys` table within the event store, and retains the private key in protected process memory only.
- Zero disk persistence and zero ambient exposure.

---

## Hard Invariants
1. Shipped runtime code shall contain zero ambient environment switches (`SCLASS_TEST_MODE`, `*TEST_MODE*`, `*UNSANDBOX*`, `*INSECURE*`).
2. Test-only execution adapters (`TestOnlyUnsandboxedBoundary`) must reside strictly under `tests/` and be passed via explicit constructor arguments.
3. Gate 6 strictly enforces the denylist across `src/`, kernel authority files, and the built wheel package.
