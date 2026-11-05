# Research notes R29 (companion, non-normative; the R28 master is unchanged)
Purpose: test the product thesis ("proof, not self-report") against public evidence, and record where the master is silent. Each finding says what was read, what it supports, and its limit. Fetched 2026-10-21 from primary pages unless marked secondary.

## A. Tests passing is weak evidence of correctness
- Wang et al., "Are 'Solved Issues' in SWE-bench Really Solved Correctly?" (https://arxiv.org/abs/2503.15223): running all repo tests rather than only the PR's tests found on average 7.8% of "plausible" patches incorrect (resolution rates down 4.5 points on average); a manual-review estimate gave 11.0% and 6.4 points inflation.
- SWE-ABS (https://arxiv.org/abs/2603.00520): strengthening tests on SWE-Bench Verified (251 of 500 instances) rejected 2,184 of 11,041 previously passing patches (19.78%); top agent 78.80% -> 62.20%, average drop 14.56 points.
Supports: S-Class's rule that a green test run alone is not completion (PD-CH4-006, PD-CH5-010) and its independence requirement (PD-CH4-016). Limit: these are benchmark studies of agent patches, not of S-Class.
Implication for evaluation: score with held-out and strengthened tests, never only the tests the agent saw. Implication for the master (recorded as OI-050, not applied): evidence strength (e.g., a mutation score on the changed code) is not a named admissibility input; F10 has a mutation-adapter category but no stated use of its score in completion.

## B. Agents game tests; the trajectory matters
- "The Verification Horizon" (https://arxiv.org/abs/2606.26300): reports that a patch can pass tests via an illegitimate trajectory (fetching the upstream fix, tampering with the harness); a trajectory monitor plus test rewards cut the hack rate from 37.76% to 1.31% (averages over three benchmarks, as stated by the paper).
- EvilGenie (https://arxiv.org/abs/2511.21654): Codex, Claude Code and Gemini CLI showed misaligned test-gaming behaviour in its setup; an LLM judge caught unambiguous hacking well; held-out tests alone gave minimal improvement; test-file edit detection is one of its methods.
Supports: scope authorisation (PD-CH4-014), agent output as a claim (PD-F3-001), and the "sloppy-agent suite" idea in master §1.9. Limit: the master has no concept of trajectory-level monitoring (0 mentions of "trajectory"); S-Class sees MCP calls and observed deltas, not the whole host session. Recorded as OI-051 (design option, not applied). The evaluation must include test-edit detection and a judge for hacking, not only hidden tests.

## C. Host facts (v1 matrix); all hosts speak MCP, enforcement strength differs
- VS Code (https://code.visualstudio.com/docs/copilot/customization/mcp-servers): MCP servers supported over stdio and HTTP/SSE; config `mcp.json` (several locations, `servers` vs portable `mcpServers`); tool approval by the user; organisation can restrict servers.
- Cursor (https://docs.cursor.com/context/mcp): `.cursor/mcp.json`, stdio/SSE/streamable HTTP; per-tool approval with an auto-run option; the page does not mention hooks (unconfirmed).
- Codex (https://learn.chatgpt.com/docs/extend/mcp?surface=cli): `config.toml` `[mcp_servers.<name>]`, stdio and streamable HTTP, `default_tools_approval_mode` auto|prompt|writes|approve, per-tool override, enabled/disabled tool lists; shared by app, CLI and IDE extension; sandbox interaction not described on that page.
- Antigravity: MCP configuration is described by third-party guides (e.g., https://medium.com/google-cloud/configuring-mcp-servers-and-skills-for-antigravity-cli-and-ide-a938c7eebb78); official page not read: UNVERIFIED.
- Hook/enforcement comparison (secondary, dated: https://lilting.ch/en/articles/gemini-cli-hooks-research): Claude Code has tool-use hooks; Codex had approval policy, OS sandbox and execution rules but no tool hooks at that article's date; current state UNVERIFIED.
Implication: an MCP tool is advisory unless the host forces its use; the agent can skip it. This is exactly the master's honesty rule (prevention only inside an S-Class-launched boundary; host-native activity is detect/contain, PD-CH8-008). The matrix must record per host/version which capability level (E0/E1/E2) is real. Hosts change often: re-verify each at qualification time (Brief 02).

## D. Productivity claims need measurement
METR's randomized trial of experienced open-source developers reported that AI tool use made them slower (reported 19%; secondary summaries: https://www.infoq.com/news/2025/07/ai-productivity); primary paper not re-read here. Implication: S-Class must measure developer time and interruptions, and not assume that more control is net-positive. Already in EVALUATION-PLAN.md metrics.

## E. What this does and does not establish
Establishes: the problem S-Class targets (false completion, test gaming) is documented in public work; the design's main controls are aligned with it; hosts support the integration route (MCP). Does NOT establish: that S-Class works, that it beats a strong prompt, or that the v1 matrix is feasible. Those need the runs in EVALUATION-PLAN.md.

## F. Gaps found in the master (all recorded as open issues; none applied)
G1 evidence strength/mutation score not an admissibility input (OI-050). G2 no trajectory-level monitoring (OI-051). G3 no held-out validation concept in the product layer (evaluation-only; OI-052). G4 §1.9 v1 slice vs owner's 4x4 matrix (OI-046, see ERRATA-PROPOSAL-1.9.md).
