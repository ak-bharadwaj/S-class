# Subsystem Evaluation: Verification & Evidence Providers

## 1. Subsystem Scope & Requirements
The Verification Subsystem evaluates claims made by agents or workflows (e.g. "auth tests pass", "no secrets exposed", "CVEs resolved") by coordinating independent verification providers.
Key requirements:
1. **Multi-Verifier Adjudication**: A claim is strengthened when independent verifiers agree. No single tool possesses absolute authority.
2. **Deterministic Evidence Receipts**: Verifiers must output structured `EvidenceReceipt` records containing execution hashes, tool identities, timestamps, and workspace fingerprints.
3. **Pluggable Architecture**: S-Class core verification logic must remain decoupled from specific static analyzers, test runners, or security scanners.

---

## 2. Candidates Evaluated

| Tool | Category | Output Evidence | S-Class Role |
| :--- | :--- | :--- | :--- |
| **pytest / Jest / Vitest** | Unit/Integration Test Runners | Test execution counts, failures, assertion traces, exit codes | **Tier 1 Foundational Verifiers** (`TestVerifier`) |
| **Semgrep** | Multi-language AST Static Analysis | SARIF reports, pattern match locations, security CWE mappings | **Tier 2 Security Provider** (`SemgrepVerifier`) |
| **GitHub CodeQL** | Deep Semantic & Data-Flow Analysis | Taint analysis, inter-procedural call graphs, vulnerability proofs | **Tier 2 Pluggable Security Provider** (`CodeQLVerifier`) |
| **Schemathesis** | Property-Based API Fuzzing | Negative API contracts, schema conformance, 5xx server exceptions | **Tier 2 Contract Verifier** (`APIVerifier`) |
| **Gitleaks** | Secret & Credential Detection | Entropy findings, committed API keys, private key detection | **Tier 2 Secret Verifier** (`SecretVerifier`) |
| **Syft + CycloneDX** | Supply-Chain & SBOM Inspection | Dependency graphs, license deltas, CVE catalogs | **Tier 2 Supply Chain Provider** (`SupplyChainVerifier`) |

---

## 3. Verification Adjudication Model

```
                    Agent / Workflow Claim:
             "Fixed SQL Injection in /api/search"
                              │
                              ▼
                 Verification Orchestrator
                              │
     ┌────────────────────────┼────────────────────────┐
     ▼                        ▼                        ▼
pytest (Unit Tests)   Semgrep (AST Scan)      CodeQL (Taint Flow)
     │                        │                        │
  Receipt                  Receipt                  Receipt
     │                        │                        │
     └────────────────────────┼────────────────────────┘
                              ▼
                 S-Class Verification Engine
                  - Checks receipts against ledger
                  - Verifies workspace fingerprint matches
                  - Evaluates multi-verifier confidence
                              │
                              ▼
                Claim Verdict: ACCEPTED / REJECTED
```

---

## 4. Architectural Decision
- Implement generic `VerificationProvider` protocol in `sclass.verification.providers.base`.
- Plug in native test runners (`pytest`, `jest`), static analyzers (`semgrep`), contract testers (`schemathesis`), and supply chain scanners (`syft`).
- S-Class acts as the adjudicator of all evidence, strictly enforcing Invariant 4 (caller cannot dictate verifier verdict) and Invariant 6 (workspace mutation invalidates dependent evidence).
