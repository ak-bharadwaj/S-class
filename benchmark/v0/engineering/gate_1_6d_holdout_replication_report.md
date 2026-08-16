# Gate 1.6D Holdout Task Replication & Statistical Rigor Report

- **Runner Version**: `gate-1.6d-holdout-replication-v1`
- **Holdout Task Set**: `YES - Fresh Holdout`
- **Total Real Tasks**: 12
- **Total Executions**: 48 / 48

## Empirical Oracle Pass Rates & Efficiency

| Baseline | Treatment Description | Max Budget | Tasks Passed | Pass Rate (%) | Cost / Success ($) | Calls / Success | Avg Latency (s) | Total Cost ($) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **B1** | Model-Only (Single-Shot) | 1 call | 5 / 12 | 41.67% | $0.000911 | 2.4 | 4.224s | $0.004556 |
| **B2** | Model + Pytest Repair Loop | 3 calls | 8 / 12 | 66.67% | $0.001343 | 3.0 | 4.159s | $0.010746 |
| **B3** | Model + S-Class Candidate Authority | 3 calls | 4 / 12 | 33.33% | $0.003681 | 7.25 | 4.772s | $0.014725 |
| **B4** | Model + S-Class + Pytest Repair Loop | 3 calls | 9 / 12 | 75.0% | $0.001517 | 2.78 | 4.982s | $0.013653 |

## McNemar Paired Statistical Hypothesis Test (B4 vs B2)

- **Primary Comparison**: `B4 (Model + S-Class + Test Repair) vs B2 (Model + Test Repair)`
- **Contingency Matrix**: $a=7$ (both pass), $b=1$ (B2 pass / B4 fail), $c=2$ (B4 pass / B2 fail), $d=2$ (both fail)
- **McNemar $\chi^2$ Statistic**: `0.0`
- **$p$-value**: `1.0`
- **Statistically Significant ($p < 0.05$)**: `NO`
- **Survives Replication Effect ($B4 \ge B2$)**: `YES`

## Failure Taxonomy Classification Breakdown

| Baseline | Wrong Req | Missing Req | Implementation Bug | Test / API Mismatch | Env Failure |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **B1** | 3 | 2 | 0 | 2 | 0 |
| **B2** | 1 | 1 | 2 | 0 | 0 |
| **B3** | 3 | 1 | 1 | 3 | 0 |
| **B4** | 1 | 1 | 1 | 0 | 0 |

## Independent Human Adjudication Sample
- Sampled **10 failing runs** for human review in `human_adjudication_samples` key.
