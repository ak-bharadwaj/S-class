# H6 High-Risk Invariant Benchmark Two-Layer Summary Report

- **Replication Scale**: `24 High-Risk Invariant Engineering Tasks`
- **Total Executions**: `48 Live LLM Runs`

## Layer 1 (Executable Oracle) vs Layer 2 (Invariant Adjudication) Comparison

| Metric | B2 (Model + Pytest) | B4 (Model + S-Class + Pytest) | Delta (B4 - B2) |
| :--- | :---: | :---: | :---: |
| **Layer 1 Oracle Pass Rate (%)** | 37.5% (9/24) | 66.67% (16/24) | `+29.17%` |
| **Layer 2 Invariant Pass Rate (%)** | 12.5% (3/24) | 12.5% (3/24) | `+0.00%` |
| **Critical Invariant Coverage (%)** | 54.17% | 54.17% | `+0.00%` |
| **Unsupported Assumption Rate (%)** | 0.0% | 0.0% | `+0.00%` |
| **Requirement Omissions Count** | 22 | 22 | `+0` |
| **False Confidence Rate (%)** | 33.33% (8 tasks) | 62.5% (15 tasks) | `+29.17%` |
| **Audit Trace Completeness (%)** | 100.0% | 100.0% | `+0.00%` |
| **Calls / Success** | 7.22 | 3.88 | `-3.34` |
| **Cost / Success ($)** | $0.001393 | $0.000905 | `$-0.000488` |
