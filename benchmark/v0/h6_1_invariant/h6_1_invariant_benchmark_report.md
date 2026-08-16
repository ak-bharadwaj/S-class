# H6.1 Independent Adversarial Behavioral Invariant Benchmark Summary Report

- **Verification Protocol**: `ZERO REGEX MATCHING - Pure Executable Adversarial Probes`
- **Replication Scale**: `24 High-Risk Invariant Engineering Tasks`
- **Total Executions**: `48 Live LLM Runs`

## Layer 1 (Executable Oracle) vs Layer 2 (Adversarial Behavioral Invariant Probes) Comparison

| Metric | B2 (Model + Pytest) | B4 (Model + S-Class + Pytest) | Delta (B4 - B2) |
| :--- | :---: | :---: | :---: |
| **Layer 1 Oracle Pass Rate (%)** | 91.67% (22/24) | 87.5% (21/24) | `-4.17%` |
| **Layer 2 Behavioral Invariant Pass Rate (%)** | 79.17% (19/24) | 87.5% (21/24) | `+8.33%` |
| **False Confidence Rate (%)** | 12.5% (3 tasks) | 8.33% (2 tasks) | `-4.17%` |
| **Audit Trace Completeness (%)** | 100.0% | 100.0% | `+0.00%` |
| **Calls / Success** | 2.32 | 2.33 | `+0.01` |
| **Cost / Success ($)** | $0.000341 | $0.000435 | `$+0.000094` |
