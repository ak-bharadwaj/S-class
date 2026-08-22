# S-Class Intellectual Property & Provenance Verification Record

## 1. Governance & Licensing Structure
- **Primary Codebase License**: Proprietary & Confidential (Copyright (c) 2026 ak-bharadwaj).
- **Clean-Room Verification Protocol**: All subsystem implementations (D0–D8) have been built from first-principles domain specifications.

## 2. Component Adaptation & Origin Matrix

| Component | Upstream Reference / Standard | License Type | Adaptation Method | Contamination Risk |
| :--- | :--- | :--- | :--- | :--- |
| **`file_lock.py`** | `fcntl.flock` (POSIX) / `msvcrt.locking` (Win32) / `portalocker` | MIT / PSF-2.0 | Clean-room implementation of OS kernel mutual exclusion | 🟢 None (Zero AGPL) |
| **`events/serializer.py`** | RFC 8785 (Canonical JSON) | Open RFC Standard | Pure Python implementation conforming to RFC 8785 | 🟢 None (Zero AGPL) |
| **`policy/` & Cryptography** | Ed25519 (RFC 8032) / `cryptography` package | Apache-2.0 / BSD | Standard library usage for signature verification | 🟢 None (Zero AGPL) |
| **`benchmark/parity/`** | `schemathesis`, `hypothesis`, `pytest` | MIT / MPL-2.0 | Test harness & black-box differential verification | 🟢 None (Zero AGPL) |

## 3. Transitive Dependency Audit

| Dependency | Direct / Transitive | License | Status |
| :--- | :--- | :--- | :--- |
| `cryptography` | Direct | Apache-2.0 / BSD-3-Clause | 🟢 Approved Permissive |
| `portalocker` | Direct (Test / Bench) | PSF-2.0 / MIT | 🟢 Approved Permissive |
| `pytest` | Direct (Development) | MIT | 🟢 Approved Permissive |
| `hypothesis` | Direct (Development) | MPL-2.0 | 🟢 Approved Permissive |
| `schemathesis` | Direct (Development) | MIT | 🟢 Approved Permissive |

## 4. AGPL / Copyleft Contamination Review
- **Audit Date**: August 2026
- **Result**: PASSED (100% Clean)
- **Certification**: No AGPL-3.0, GPL-3.0, or other reciprocal copyleft code exists in any module of the S-Class engine, kernel, controller, planner, or broker layers.
