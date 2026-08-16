# H6.2 Small Independent Replication Summary Report

- **Replication Scale**: `12 Fresh High-Risk Invariant Tasks`
- **Oracle Pre-Validation**: `CERTIFIED_100_PERCENT_DUAL_SIDED_ACCURACY`
- **Total Executions**: `24 Live LLM Runs`

## Layer 1 (Functional Oracle) vs Layer 2 (Bi-Directional Behavioral Invariant Probes)

| Metric | B2 (Model + Pytest) | B4 (Model + S-Class + Pytest) | Delta (B4 - B2) |
| :--- | :---: | :---: | :---: |
| **Layer 1 Pass Rate (%)** | 75.0% (9/12) | 66.67% (8/12) | `-8.33%` |
| **Layer 2 Pass Rate (%)** | 58.33% (7/12) | 83.33% (10/12) | `+25.00%` |
| **False Confidence Rate (%)** | 33.33% (4 tasks) | 0.0% (0 tasks) | `-33.33%` |
| **Cost / Success ($)** | $0.000502 | $0.000757 | `$+0.000255` |

## Paired Layer 2 Behavioral McNemar Analysis

- **Contingency Matrix**: $a=7, b=0, c=3, d=2$ (**Discordant Pairs = 3**)
- **Exact Binomial McNemar $p$-value**: `p = 0.25000`
- **95% Confidence Interval for $\Delta$**: `-9.97% to +59.97% (Delta = 25.0%)`
