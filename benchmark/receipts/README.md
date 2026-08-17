# S-Class EOS V11.2 — Certified Artifact & Receipt Manifest

## Archival & Provenance Convention

Authoritative, full-sized verification JSON artifacts, differential receipts, and execution logs are generated and stored in **GitHub Actions immutable artifact storage** associated with their specific Git commit SHAs and workflow run IDs.

To prevent repository pollution and maintain strict provenance integrity:
- **No historical JSON blobs or uncertified local receipts are checked into the source tree.**
- Certified artifacts are indexed below in [`manifest.json`](file:///C:/Users/dorni/.gemini/config/plugins/sclass-v5/benchmark/receipts/manifest.json) with their immutable SHA, CI run ID, target runtime, and certificate verification verdict.

---

## Index of Certified Gates

| Milestone / Gate | Certified SHA | CI Workflow Name | CI Run ID | Certified Matrix | Status |
| :--- | :--- | :--- | :--- | :--- | :---: |
| **`PARITY-GATE-1`** (POSIX) | `9ecce482076019deacf7aa3285d475e58bea55dc` | `OSS Parity Gate 1 - POSIX / Linux Certification` | [`31994644520`](https://github.com/ak-bharadwaj/S-class/actions/runs/31994644520) | Ubuntu 24.04 (Python 3.10–3.13) | 🟢 Certified |
| **`PARITY-GATE-1`** (Win32) | `c60ee97760ea0353da76bdf7a7b083b6ac252b51` | `OSS Parity Gate 1 - Windows Certification` | [`31994998782`](https://github.com/ak-bharadwaj/S-class/actions/runs/31994998782) | Windows Server 2025 (Python 3.10–3.13) | 🟢 Certified |
| **`PARITY-GATE-2`** (Hypothesis) | `3ad861286aabc56f1aae242d0cedeff173865081` | `OSS Parity Gate 2 - Differential & Performance` | [`32000742914`](https://github.com/ak-bharadwaj/S-class/actions/runs/32000742914) | Ubuntu 24.04 (Python 3.10, 3.11, 3.12, 3.13) | 🟢 Certified |
| **`THESIS-GATE-1A`** (Synthetic Efficacy) | `725fe90daf8b4d20c33e1e466ec8fc6460a10f83` | `S-Class THESIS-GATE-1A - Synthetic Efficacy` | [`32003191497`](https://github.com/ak-bharadwaj/S-class/actions/runs/32003191497) | Ubuntu 24.04 (Python 3.10, 3.11, 3.12, 3.13) | 🟢 Certified |
| **`THESIS-GATE-1B`** (External Validation) | — | Protocol Ready / Awaiting Real Participants | — | 3–5 Developers (3 tasks each) | 🔴 Active |
