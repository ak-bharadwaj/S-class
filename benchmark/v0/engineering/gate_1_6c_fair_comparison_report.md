# Gate 1.6C Fair Treatment Benchmark Summary Report

- **Runner Version**: `gate-1.6c-fair-treatment-benchmark-v1`
- **Total Real Tasks**: 16
- **Total Benchmark Executions**: 64 / 64

## Empirical Oracle Pass Rates

| Baseline | Treatment Description | Max Budget | Tasks Passed | Pass Rate (%) | Avg Latency (s) | Total Cost (USD) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **B1** | Model-Only (Single-Shot) | 1 call | 7 / 16 | 43.75% | 3.24s | $0.00408 |
| **B2** | Model + Pytest Repair Loop | 3 calls | 10 / 16 | 62.5% | 3.137s | $0.011805 |
| **B3** | Model + S-Class Candidate Authority | 3 calls | 7 / 16 | 43.75% | 3.554s | $0.013272 |
| **B4** | Model + S-Class + Pytest Repair Loop | 3 calls | 11 / 16 | 68.75% | 3.487s | $0.011708 |

## Failure Taxonomy Classification Breakdown

| Baseline | Wrong Req | Missing Req | Implementation Bug | Test / API Mismatch | Env Failure |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **B1** | 6 | 0 | 3 | 0 | 0 |
| **B2** | 4 | 0 | 2 | 0 | 0 |
| **B3** | 4 | 0 | 5 | 0 | 0 |
| **B4** | 3 | 0 | 2 | 0 | 0 |
