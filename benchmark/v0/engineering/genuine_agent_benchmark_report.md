# Gate 1.6B Genuine Agent Benchmark Summary Report

- **Runner Version**: `gate-1.6b-genuine-agent-benchmark-v1`
- **Total Real Tasks**: 16

## Empirical Oracle Pass Rates

| Baseline | Treatment Description | Tasks Passed | Pass Rate (%) | Avg Latency (s) | Total Cost (USD) |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **B1** | Prompt-Only Agent | 0 / 16 | 0.0% | 0.0s | $0.0 |
| **B2** | Agent + Pytest Repair Loop | 0 / 16 | 0.0% | 0.0s | $0.0 |
| **B3** | Agent + S-Class Governance | 0 / 16 | 0.0% | 0.0s | $0.0 |

## Human Evaluator Scoring (Awaiting Rated JSON Run Artifacts)
- Human metrics (defects, review friction, developer interventions, unsupported inventions) are captured directly in each `runs/{task_id}/b{1,2,3}_raw.json` file.
