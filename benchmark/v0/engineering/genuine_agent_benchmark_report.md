# Gate 1.6B Genuine Agent Benchmark Summary Report

- **Runner Version**: `gate-1.6b-genuine-agent-benchmark-v1`
- **Total Real Tasks**: 16

## Empirical Oracle Pass Rates

| Baseline | Treatment Description | Tasks Passed | Pass Rate (%) | Avg Latency (s) | Total Cost (USD) |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **B1** | Prompt-Only Agent | 4 / 16 | 25.0% | 3.813s | $0.004313 |
| **B2** | Agent + Pytest Repair Loop | 10 / 16 | 62.5% | 3.709s | $0.011704 |
| **B3** | Agent + S-Class Governance | 6 / 16 | 37.5% | 4.216s | $0.005327 |

## Human Evaluator Scoring (Awaiting Rated JSON Run Artifacts)
- Human metrics (defects, review friction, developer interventions, unsupported inventions) are captured directly in each `runs/{task_id}/b{1,2,3}_raw.json` file.
