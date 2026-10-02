# S-Class: Universal Trust & Control Plane

> **Version**: v6.0.1 Canonical  
> **Status**: Verified Production Line  
> **Normative Contract**: `00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md`

S-Class is the universal trust and control plane between autonomous AI coding agents and developer workspaces. It guarantees that no action request can alter production state without verifiable authority, bounded execution leases, deterministic observation, independent verification, and canonical event reduction.

---

## Architecture Overview

S-Class replaces fragmented legacy heuristics with a mathematically rigorous, fail-closed state machine architecture:

```text
ActionRequest
    ↓
Authority / Policy
    ↓
Admission
    ↓
AuthorizedWorkRequest
    ↓
Execution Gate (Capability Token + Fence)
    ↓
Durable Intent & Quiescence Boundary
    ↓
Runtime Effect
    ↓
Independent Observation
    ↓
Evidence Receipt (Cryptographically Attested)
    ↓
Semantic Verifier
    ↓
Canonical Reducer
    ↓
Engineering / Verified State
    ↓
Causal Frontier
    ↓
Completion / Acceptance
```

---

## Repository Structure

The canonical v6.0.1 repository is organized into strict, decoupled layers:

```text
.
├── 00-SPEC/
│   └── S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md   # Active normative contract and formal specification
├── 10-CONFORMANCE/
│   ├── sclass_semantics_v6_0_1.py            # Canonical semantic kernel (C1, Reducer, State)
│   ├── test_sclass_v6_0_1_conformance.py      # Conformance & 24 adversarial gates
│   ├── test_sclass_v6_0_1_property.py         # Hypothesis property verification matrices
│   ├── c1-vectors.v6.0.1.json                 # C1 canonicalization vectors
│   └── state-machines.v6.0.1.json             # Canonical state transition definitions
├── 20-RUNTIME/
│   ├── sclass_runtime_v6_0_1.py               # ExecutionGate, LinuxExecutionBoundary, ControlPlane
│   └── test_sclass_runtime_v6_0_1.py          # End-to-end runtime & verification lifecycle tests
├── src/sclass/
│   ├── __init__.py                            # Package entry point
│   ├── semantics.py                           # Semantic kernel exports
│   └── runtime.py                             # Runtime & gate exports
├── tools/
│   ├── run_all_s0_partitions.py               # S0 5-partition mutation runner
│   └── run_cr.py                              # Cosmic Ray runner wrapper
├── pyproject.toml                             # Package build definition & test configuration
├── cosmic-ray.toml                            # Cosmic Ray mutation configuration
└── S0_CLOSURE_REPORT.md                       # Executable S0 certification evidence
```

---

## S0 Foundation Baseline Certification

S-Class v6.0.1 has achieved **S0 Baseline Closure** according to §18.2 exit requirements:

- **Vectors**: PASS (`10-CONFORMANCE/c1-vectors.v6.0.1.json`)
- **Adversarial**: PASS (24 explicit security gates against tampering, encoding flaws, integer bounds, and injection)
- **Property**: PASS (6 Hypothesis property matrices verifying determinism, order-independence, and immutability)
- **Mutation**: PASS (**1,085 / 1,085 mutants killed, 0 survived, 0 errors, 100.0% score** across all 5 partitions: S0-M1 C1, S0-M2 Digest, S0-M3 Validation, S0-M4 Identity, S0-M5 Reducer)

Full evidence is published in `S0_CLOSURE_REPORT.md`.

---

## Quickstart & Verification

### 1. Installation
```bash
pip install -e .
```

### 2. Run Conformance & Property Tests
```bash
python -m pytest 10-CONFORMANCE/
```

### 3. Run Runtime Verification Lifecycle Tests
```bash
python -m pytest 20-RUNTIME/
```

### 4. Execute Full S0 Mutation Baseline
```bash
python tools/run_all_s0_partitions.py
```

---

## License
Apache-2.0
