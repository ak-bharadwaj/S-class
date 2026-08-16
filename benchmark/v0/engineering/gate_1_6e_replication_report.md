# Gate 1.6E Large-Scale Replication & Statistical Rigor Report (N=40)

- **Runner Version**: `gate-1.6e-large-scale-replication-v1`
- **Replication Scale**: `40 Fresh Engineering Tasks`
- **Total Executions**: `80 Live LLM Runs`

## Empirical Oracle Pass Rates & Efficiency Comparison

| Baseline | Treatment Description | Tasks Passed | Pass Rate (%) | Cost / Success ($) | Calls / Success | Latency / Success (s) | Total Cost ($) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **B2** | Model + Pytest Repair Loop | 39 / 40 | 97.5% | $0.000356 | 2.77 | 5.576s | $0.013883 |
| **B4** | Model + S-Class + Pytest Repair | 38 / 40 | 95.0% | $0.000443 | 2.61 | 5.76s | $0.016843 |

## Exact Binomial McNemar Test & 95% Confidence Interval

- **Comparison**: `B4 (Model + S-Class + Test Repair) vs B2 (Model + Test Repair)`
- **Contingency Matrix**: $a=38$ (both pass), $b=1$ (B2 pass / B4 fail), $c=0$ (B4 pass / B2 fail), $d=1$ (both fail)
- **Exact Binomial Two-Tailed $p$-value**: `1.0`
- **Statistically Significant ($p < 0.05$)**: `NO`
- **95% Confidence Interval for $\Delta = p_{B4} - p_{B2}$**: `[-10.81%, 5.81%]` (Point estimate: `-2.5%`)

## Severity-Weighted Failure Analysis

| Baseline | Wrong Req (3.0) | Missing Req (2.5) | Impl Bug (2.0) | API Mismatch (1.5) | Env Fail (1.0) | Severity Weighted Score |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **B2** | 0 | 1 | 0 | 0 | 0 | `2.5` |
| **B4** | 0 | 1 | 1 | 0 | 0 | `4.5` |

## Blinded Human Adjudication Audit & Inter-Annotator Agreement

- **Sample Size**: 3 failing runs
- **Observed Agreement ($P_o$)**: `100.0%`
- **Cohen's Kappa ($\kappa$)**: `1.0`
- **Reliability Assessment**: `EXCELLENT`
