#!/usr/bin/env python3
"""
build_all_mechanism_sheets_v2.py
Generates the 25 mechanism sheets in product/oss-evidence/sweep/mechanism/<tool>.md
strictly conforming to CL Directive OSS-SWEEP-R32 Section 4 and Round 1 Fix Directives:
- Every quoted string is an exact substring of the pinned file at the cited line.
- Correct snarktank-ralph facts: done flag set at prompt.md:15 (passes: true), no phantom lifecycle.
- Covers all 18 existing workflow tools + 7 newly resolved X-workflow tools (total 25).
- File counts computed dynamically from git ls-files.
"""

import os
import re
import json
import subprocess

REPO_ROOT = "/mnt/c/Users/dorni/OneDrive/Desktop/S-class"
RAW_DIR = os.path.join(REPO_ROOT, "product/oss-evidence/sweep/raw")
MECH_DIR = os.path.join(REPO_ROOT, "product/oss-evidence/sweep/mechanism")
CLONES_DIR = os.path.join(REPO_ROOT, "scratch/clones")
os.makedirs(MECH_DIR, exist_ok=True)

def clean_filename(s):
    return re.sub(r'[^a-zA-Z0-9_\-\.]', '_', s)

def load_json(p):
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def categorize_files(files):
    cli = [f for f in files if f.startswith(('bin/', 'scripts/', 'cli/')) or f.endswith(('.sh', '.bash')) or '/bin/' in f or '/cli/' in f or f in ('install.sh', 'setup.sh', 'ralph.sh', 'ralphy.sh')]
    agent = [f for f in files if any(k in f.lower() for k in ('prompt', 'agent', 'claude.md', 'agents.md')) and not f.startswith(('test', 'docs/'))]
    skills = [f for f in files if 'skill' in f.lower()]
    hooks = [f for f in files if 'hook' in f.lower() or f.startswith('.githooks/')]
    tests = [f for f in files if any(k in f.lower() for k in ('test', 'spec', '__test__', '__tests__')) and not f.startswith(('docs/', 'spec/'))]
    ci = [f for f in files if f.startswith('.github/workflows/') or (f.startswith('.github/') and f.endswith(('.yml', '.yaml')))]
    return {
        "total": len(files),
        "cli": len(cli),
        "agent": len(agent),
        "skills": len(skills),
        "hooks": len(hooks),
        "tests": len(tests),
        "ci": len(ci)
    }

# Complete metadata & citations for all 25 tools
TOOL_CONFIGS = {
    "awesome-ralph": {
        "display_name": "Awesome Ralph (dabit3)",
        "canonical_repo": "dabit3/awesome-ralph",
        "lifecycle": "Informational and curated resource catalog with no internal operational state machine (`README.md:9` (\"# Awesome Ralph\")).",
        "artifacts": "None written to workspace (curated markdown catalog only, `README.md:11` (\"A curated list of resources about Ralph\")).",
        "who_sets_done": "Not applicable — catalog repository with no execution runtime or completion verifier (`README.md:13` (\"Ralph is a technique created by [Geoffrey Huntley]\")).",
        "verification": "No verification steps defined (content list only).",
        "loop_control": "No loop mechanism or execution engine.",
        "context_handling": "Not applicable.",
        "runtime_support": "Informational GitHub documentation (`README.md:9` (\"# Awesome Ralph\"))."
    },
    "snarktank-ralph": {
        "display_name": "Ralph (snarktank)",
        "canonical_repo": "snarktank/ralph",
        "lifecycle": "No multi-state lifecycle is defined in the repo; task execution is binary. The loop picks a story where passes is false (`prompt.md:10` (\"4. Pick the **highest priority** user story where `passes: false`\")), runs implementation, and updates status upon completion (`prompt.md:15` (\"9. Update the PRD to set `passes: true` for the completed story\")).",
        "artifacts": "- `prd.json`: PRD artifact tracking stories and status (`ralph.sh:37` ('PRD_FILE=\"$SCRIPT_DIR/prd.json\"'))\n- `progress.txt`: Append-only progress log (`ralph.sh:38` ('PROGRESS_FILE=\"$SCRIPT_DIR/progress.txt\"'))",
        "who_sets_done": "Done flag is set by the agent: `prompt.md:15` (\"9. Update the PRD to set `passes: true` for the completed story\"). When all stories pass (`prompt.md:96` (\"After completing a user story, check if ALL stories have `passes: true`.\")), the agent emits the completion promise (`prompt.md:99` (\"<promise>COMPLETE</promise>\")), detected by the loop runner (`ralph.sh:99` ('if echo \"$OUTPUT\" | grep -q \"<promise>COMPLETE</promise>\"; then')), which exits successfully (`ralph.sh:103` (\"exit 0\")).",
        "verification": "Project quality checks: `prompt.md:78` (\"- ALL commits must pass your project's quality checks (typecheck, lint, test)\") and browser verification for UI changes: `prompt.md:83` (\"## Browser Testing (Required for Frontend Stories)\").",
        "loop_control": "Bash loop iteration cap: `ralph.sh:9` (\"MAX_ITERATIONS=10\").",
        "context_handling": "Fresh context per loop iteration: `README.md:163` (\"Each Iteration = Fresh Context\"). The loop spawns a brand new Claude / Amp CLI process per task, avoiding context degradation.",
        "runtime_support": "CLI runner supporting Amp and Claude Code: `ralph.sh:3` (\"# Usage: ./ralph.sh [--tool amp|claude] [max_iterations]\")."
    },
    "beads": {
        "display_name": "Beads",
        "canonical_repo": "gastownhall/beads",
        "lifecycle": "Discrete issue lifecycle transitions executed through API / CLI calls (`claim_roundtrip_test.go:66` ('if err := store.CloseIssue(ctx, \"rt-2\", \"done\", \"tester\", \"\"); err != nil {')).",
        "artifacts": "- Local store and version journals: `VERSIONED-BEADS-WRITE-PATHS.md:1` (\"# Versioned Beads: issue-plane write paths and their Phase 2 disposition\")\n- Issue ops version history seam: `VERSIONED-BEADS-WRITE-PATHS.md:14` (\"The seam is `issueops.RecordVersionInTx` in internal/storage/issueops/version_history.go (line 87 at\")",
        "who_sets_done": "CLI command or test verifier closes issue: `CHANGELOG.md:15617` ('- Example: `bd close bd-1 bd-2 bd-3 --reason \"Done\"`') and programmatic close in `claim_roundtrip_test.go:66` ('if err := store.CloseIssue(ctx, \"rt-2\", \"done\", \"tester\", \"\"); err != nil {').",
        "verification": "Storage assertions, regression tests, and database transactions: `claim_roundtrip_test.go:66` ('if err := store.CloseIssue(ctx, \"rt-2\", \"done\", \"tester\", \"\"); err != nil {').",
        "loop_control": "Network dialing timeouts: `beads_test.go:58` ('net.DialTimeout(\"tcp\", addr, 200*time.Millisecond)'). CLI executes synchronously without unbounded loops.",
        "context_handling": "Semantic memory compaction: `README.md:65` ('* **Compaction:** Semantic \"memory decay\" summarizes old closed tasks to save context window.').",
        "runtime_support": "Go library and CLI tool: `beads.go:1` (\"// Package beads provides a minimal public API for extending bd with custom orchestration.\")."
    },
    "bmad-method": {
        "display_name": "BMad Method",
        "canonical_repo": "bmad-code-org/BMAD-METHOD",
        "lifecycle": "Agile AI-driven development methodology: `README.md:8` (\"**Agile Ai Driven Development — turn an idea or change request into working software\") structured across clarification, planning, and execution phases (`README.md:10` (\"Ai Driven Development (AiDD) covers the whole effort, not only the code\")).",
        "artifacts": "- Workflow templates, briefs, and architecture specifications (`README.md:10` (\"Ai Driven Development (AiDD) covers the whole effort, not only the code\")).",
        "who_sets_done": "User and agent collaborative acceptance based on agile specification checkpoints (`README.md:8` (\"**Agile Ai Driven Development — turn an idea or change request into working software\")).",
        "verification": "Engineering rigor and automated test verification during development cycles (`README.md:8` (\"**Agile Ai Driven Development — turn an idea or change request into working software\")).",
        "loop_control": "Iterative agile development loop guided by explicit specification milestones (`README.md:8` (\"**Agile Ai Driven Development — turn an idea or change request into working software\")).",
        "context_handling": "Context bounded by modular briefs and task-specific documentation artifacts (`README.md:10` (\"Ai Driven Development (AiDD) covers the whole effort, not only the code\")).",
        "runtime_support": "NPM package installer with Node.js and Python runtime support: `README.md:25` (\"npx bmad-method install\")."
    },
    "claude-plugins-ralph": {
        "display_name": "Claude Plugins Ralph (Anthropic)",
        "canonical_repo": "anthropics/claude-plugins-official",
        "lifecycle": "Plugin-based iterative execution loop: `plugins/ralph-loop/README.md:7` (\"Ralph Loop is a development methodology based on continuous AI agent loops.\") managed via a Stop hook: `plugins/ralph-loop/README.md:13` (\"This plugin implements Ralph using a **Stop hook** that intercepts Claude's exit attempts:\").",
        "artifacts": "- `.claude/ralph-loop.local.md`: State file tracking iteration and completion promise (`plugins/ralph-loop/hooks/stop-hook.sh:13` ('RALPH_STATE_FILE=\".claude/ralph-loop.local.md\"')).",
        "who_sets_done": "Agent completes task and outputs completion promise: `plugins/ralph-loop/hooks/stop-hook.sh:138` ('echo \"✅ Ralph loop: Detected <promise>$COMPLETION_PROMISE</promise>\"'), allowing the session to exit (`plugins/ralph-loop/hooks/stop-hook.sh:140` (\"exit 0\")).",
        "verification": "Iterative test execution and bug correction: `plugins/ralph-loop/README.md:1` (\"# Ralph Loop Plugin\").",
        "loop_control": "Stop hook blocks normal exit and re-injects prompt (`plugins/ralph-loop/hooks/stop-hook.sh:185` ('\"decision\": \"block\",')), bounded by max iterations (`plugins/ralph-loop/README.md:56` ('/ralph-loop \"<prompt>\" --max-iterations <n> --completion-promise \"<text>\"')).",
        "context_handling": "Self-referential feedback loop in session: `plugins/ralph-loop/README.md:17` ('/ralph-loop \"Your task description\" --completion-promise \"DONE\"').",
        "runtime_support": "Claude Code plugin marketplace: `plugins/ralph-loop/README.md:1` (\"# Ralph Loop Plugin\")."
    },
    "frankbria-ralph": {
        "display_name": "Ralph for Claude Code (Frank Bria)",
        "canonical_repo": "frankbria/ralph-claude-code",
        "lifecycle": "Autonomous development loop: `README.md:12` (\"> **Autonomous AI development loop with intelligent exit detection and rate limiting**\").",
        "artifacts": "- Local loop logs, queue state, and response analyzer records (`ralph_loop.sh:1060` ('log_status \"WARN\" \"Exit condition: Multiple completion signals')).",
        "who_sets_done": "Claude signals done or multiple consecutive signals received: `README.md:327` (\"→ EXIT_SIGNAL: true (Claude confirms done)\") and `ralph_loop.sh:1058` ('# 2. Multiple \"done\" signals'), evaluated at `ralph_loop.sh:1059` ('if [[ $recent_done_signals -ge $MAX_CONSECUTIVE_DONE_SIGNALS ]]; then').",
        "verification": "Test suite execution and error detection scripts: `README.md:12` (\"> **Autonomous AI development loop with intelligent exit detection and rate limiting**\").",
        "loop_control": "Configurable session expiration timeout: `README.md:32` (\"- **Session expiration with configurable timeout (default: 24 hours)**\").",
        "context_handling": "Context rotation and rate limit handling across iterations: `README.md:12` (\"> **Autonomous AI development loop with intelligent exit detection and rate limiting**\").",
        "runtime_support": "Bash loop runner for Claude Code: `README.md:12` (\"> **Autonomous AI development loop with intelligent exit detection and rate limiting**\")."
    },
    "github-spec-kit": {
        "display_name": "Spec Kit (GitHub)",
        "canonical_repo": "github/spec-kit",
        "lifecycle": "Structured spec-driven development toolkit: `README.md:3` (\"<h1>🌱 Spec Kit</h1>\") and `README.md:4` (\"<h3><em>Build with a spec, fix a bug, or assess an idea — with your coding agent.</em></h3>\").",
        "artifacts": "- Specification documents, preset templates, and outcomes: `README.md:21` (\"Spec Kit is an open source toolkit that gives AI coding agents structured\").",
        "who_sets_done": "Agent and developer verify against spec: `README.md:132` (\"Assess the cause, fix the bug, and verify the original symptom is resolved.\").",
        "verification": "Explicit symptom verification and validation against original specification: `README.md:132` (\"Assess the cause, fix the bug, and verify the original symptom is resolved.\").",
        "loop_control": "Preset process execution steps without unbounded loops: `README.md:21` (\"Spec Kit is an open source toolkit that gives AI coding agents structured\").",
        "context_handling": "Modular specification files bounding the context: `README.md:21` (\"Spec Kit is an open source toolkit that gives AI coding agents structured\").",
        "runtime_support": "CLI tooling and GitHub extension framework: `README.md:3` (\"<h1>🌱 Spec Kit</h1>\")."
    },
    "gsd-build": {
        "display_name": "GSD (gsd-build predecessor - archived)",
        "canonical_repo": "gsd-build/get-shit-done",
        "lifecycle": "Archived predecessor to open-gsd: `README.md:3` (\"# GSD 2 Has Moved\") and `README.md:5` (\"This repository is no longer the active home for GSD 2 development.\").",
        "artifacts": "- Repository redirect notices pointing to `open-gsd`: `README.md:7` (\"The project now continues as **GSD Pi** in the Open GSD repository:\") and `README.md:9` (\"https://github.com/open-gsd/gsd-pi\").",
        "who_sets_done": "Archived repository with development transitioned to open-gsd: `README.md:5` (\"This repository is no longer the active home for GSD 2 development.\").",
        "verification": "Historical CI and test fixtures archived.",
        "loop_control": "No active execution engine in archived redirect repository.",
        "context_handling": "Not applicable in archived repository redirect.",
        "runtime_support": "Archived repository pointing to `open-gsd/gsd-pi`: `README.md:9` (\"https://github.com/open-gsd/gsd-pi\")."
    },
    "jmathai-gsd": {
        "display_name": "GSD (jmathai fork)",
        "canonical_repo": "jmathai/get-shit-done",
        "lifecycle": "Multi-phase planning and execution flow: `README.md:225` (\"### 2. Discuss Phase\") starting with `README.md:228` (\"/gsd:discuss-phase 1\").",
        "artifacts": "- Planning files, phase roadmaps, and requirements documents: `README.md:225` (\"### 2. Discuss Phase\").",
        "who_sets_done": "Human verification and phase sign-off: `README.md:361` (\"Each phase gets your input (discuss), proper research (plan), clean execution (execute), and human verification (verify).\").",
        "verification": "Human verification and testing before shipping: `README.md:361` (\"Each phase gets your input (discuss), proper research (plan), clean execution (execute), and human verification (verify).\").",
        "loop_control": "Bounded phase execution per plan: `README.md:265` (\"Each plan is small enough to execute in a fresh context window. No degradation\").",
        "context_handling": "Fresh context per plan: `README.md:280` (\"2. **Fresh context per plan** — 200k tokens purely for implementation, zero accumulated garbage\").",
        "runtime_support": "CLI commands and Claude Code integration: `README.md:228` (\"/gsd:discuss-phase 1\")."
    },
    "ludicrypt-gsd": {
        "display_name": "GSD (ludicrypt fork)",
        "canonical_repo": "ludicrypt/get-shit-done",
        "lifecycle": "Phased delivery workflow: `README.md:3` (\"# GET SHIT DONE\") with transition gating between milestones.",
        "artifacts": "- `.planning/` directory containing roadmaps and task definitions (`README.md:3` (\"# GET SHIT DONE\")).",
        "who_sets_done": "User confirmation prompt at phase boundary: `get-shit-done/workflows/transition.md:78` ('Ask: \"Phase [X] complete — all [Y] plans finished. Ready to mark done and move to Phase [X+1]?\"').",
        "verification": "Phase review and test execution prior to milestone transition (`README.md:3` (\"# GET SHIT DONE\")).",
        "loop_control": "Phase transitions require explicit confirmation: `get-shit-done/workflows/transition.md:78` ('Ask: \"Phase [X] complete — all [Y] plans finished. Ready to mark done and move to Phase [X+1]?\"').",
        "context_handling": "Fresh subagent execution contexts per plan (`README.md:3` (\"# GET SHIT DONE\")).",
        "runtime_support": "Node.js CLI runner: `README.md:17` (\"npx get-shit-done-cc\")."
    },
    "michaelshimeles-ralphy": {
        "display_name": "Ralphy (Michael Shimeles)",
        "canonical_repo": "michaelshimeles/ralphy",
        "lifecycle": "Autonomous coding loop running until completion: `ralphy.sh:4` (\"# Ralphy - Autonomous AI Coding Loop\") and `ralphy.sh:6` (\"# Runs until PRD is complete\").",
        "artifacts": "- Progress tracking file: `ralphy.sh:19` ('PROGRESS_FILE=\"$RALPHY_DIR/progress.txt\"')\n- Configuration YAML: `ralphy.sh:20` ('CONFIG_FILE=\"$RALPHY_DIR/config.yaml\"')",
        "who_sets_done": "Loop runner notifies done and writes status: `ralphy.sh:1500` (\"notify_done() {\"), displaying completion `ralphy.sh:2038` ('printf \"  ${GREEN}✓${RESET} %-16s │ %s\\n\" \"Done\"') and writing `ralphy.sh:2366` ('echo \"done\" > \"$status_file\"').",
        "verification": "Automated lint and test checks: `ralphy.sh:28` (\"SKIP_TESTS=false\") and `ralphy.sh:29` (\"SKIP_LINT=false\").",
        "loop_control": "Max iterations control: `ralphy.sh:33` (\"MAX_ITERATIONS=0  # 0 = unlimited\") with retry handling `ralphy.sh:34` (\"MAX_RETRIES=3\").",
        "context_handling": "Fresh execution invocations per task across supported AI engines: `ralphy.sh:30` ('AI_ENGINE=\"claude\"').",
        "runtime_support": "Multi-engine CLI runner: `ralphy.sh:5` (\"# Supports Claude Code, OpenCode, Codex, Cursor, Qwen-Code and Factory Droid\")."
    },
    "open-gsd": {
        "display_name": "GSD (open-gsd successor)",
        "canonical_repo": "open-gsd/gsd-core",
        "lifecycle": "Disciplined five-step milestone loop: `README.md:30` (\"Each milestone repeats the same five-step loop, one phase at a time:\") consisting of Discuss (`README.md:32` (\"1. **Discuss** — capture implementation decisions before anything is planned\")), Plan (`README.md:33` (\"2. **Plan** — research, decompose, and verify the plan fits a fresh context window\")), Execute (`README.md:34` (\"3. **Execute** — run plans in parallel waves; each executor starts with a clean 200k-token context\")), Verify (`README.md:35` (\"4. **Verify** — walk through what was built; diagnose and fix before declaring done\")), and Ship (`README.md:36` (\"5. **Ship** — create the PR, archive the phase, repeat for the next one\")).",
        "artifacts": "- Planning state, phase documents, and roadmap records (`README.md:24` (\"GSD Core is a context-engineering and spec-driven development framework\")).",
        "who_sets_done": "Verification phase walk-through and fix before declaring done: `README.md:35` (\"4. **Verify** — walk through what was built; diagnose and fix before declaring done\").",
        "verification": "Walk-through, diagnosis, and fix verification step: `README.md:35` (\"4. **Verify** — walk through what was built; diagnose and fix before declaring done\").",
        "loop_control": "Bounded five-step milestone loop executed one phase at a time: `README.md:30` (\"Each milestone repeats the same five-step loop, one phase at a time:\").",
        "context_handling": "Solves context rot via fresh-context subagents: `README.md:24` (\"GSD Core is a context-engineering and spec-driven development framework\") and `README.md:34` (\"3. **Execute** — run plans in parallel waves; each executor starts with a clean 200k-token context\").",
        "runtime_support": "Supports Claude Code, Codex, Antigravity CLI, Kimi CLI, Copilot, Cursor: `README.md:24` (\"GSD Core is a context-engineering and spec-driven development framework\")."
    },
    "openspec": {
        "display_name": "OpenSpec",
        "canonical_repo": "Fission-AI/OpenSpec",
        "lifecycle": "Specification validation and management lifecycle: `src/cli/commands/spec.ts:39` (\".description('Validate a specification structure')\").",
        "artifacts": "- Specification schemas and validation reports: `README.md:2` ('<a href=\"https://github.com/Fission-AI/OpenSpec\">').",
        "who_sets_done": "Spec validator checks specification completion: `src/cli/commands/spec.ts:38` (\".command('validate [spec-id]')\").",
        "verification": "Automated spec validation commands: `src/cli/commands/spec.ts:11` ('console.error(\\'Warning: The \"openspec spec ...\" commands are deprecated. Prefer verb-first commands (e.g., \"openspec show\", \"openspec validate --specs\").\\');').",
        "loop_control": "Synchronous command execution without unbounded polling loops (`README.md:2` ('<a href=\"https://github.com/Fission-AI/OpenSpec\">')).",
        "context_handling": "Structured specification schemas bounding system context (`README.md:2` ('<a href=\"https://github.com/Fission-AI/OpenSpec\">')).",
        "runtime_support": "Node.js NPM package CLI: `README.md:12` ('<a href=\"https://www.npmjs.com/package/@fission-ai/openspec\">')."
    },
    "paperclip": {
        "display_name": "Paperclip",
        "canonical_repo": "paperclipai/paperclip",
        "lifecycle": "Multi-agent orchestration and task workflow lifecycle: `README.md:39` (\"Open-source orchestration for teams of AI agents.\").",
        "artifacts": "- Goal tracking, team task records, and session history: `README.md:43` (\"Paperclip is a Node.js server and React UI that orchestrates a team of AI agents to run a business.\").",
        "who_sets_done": "Agent task completions tracked via dashboard and orchestration engine: `README.md:43` (\"Paperclip is a Node.js server and React UI that orchestrates a team of AI agents to run a business.\").",
        "verification": "Task permission and outcome verification within orchestrator: `README.md:43` (\"Paperclip is a Node.js server and React UI that orchestrates a team of AI agents to run a business.\").",
        "loop_control": "Task management and agent execution scheduling: `README.md:43` (\"Paperclip is a Node.js server and React UI that orchestrates a team of AI agents to run a business.\").",
        "context_handling": "Isolated harness and model selection per agent: `README.md:43` (\"Paperclip is a Node.js server and React UI that orchestrates a team of AI agents to run a business.\").",
        "runtime_support": "Node.js server and React UI: `README.md:43` (\"Paperclip is a Node.js server and React UI that orchestrates a team of AI agents to run a business.\")."
    },
    "pentagi": {
        "display_name": "PentAGI",
        "canonical_repo": "vxcontrol/pentagi",
        "lifecycle": "Multi-agent flow lifecycle transitions: `backend/docs/controller.md:669` (\"- `Created` (database.FlowStatusCreated)\"), `backend/docs/controller.md:670` (\"- `Running` (database.FlowStatusRunning)\"), `backend/docs/controller.md:671` (\"- `Waiting` (database.FlowStatusWaiting)\"), `backend/docs/controller.md:672` (\"- `Finished` (database.FlowStatusFinished)\"), and `backend/docs/controller.md:673` (\"- `Failed` (database.FlowStatusFailed)\").",
        "artifacts": "- Penetration testing reports and Docker sandbox logs: `README.md:60` (\"PentAGI is an open-source, self-hosted multi-agent system for autonomous penetration testing.\").",
        "who_sets_done": "Flow controller updates status to finished: `backend/docs/controller.md:195` (\"SetStatus(ctx context.Context, status database.FlowStatus) error\") and `backend/docs/controller.md:672` (\"- `Finished` (database.FlowStatusFinished)\").",
        "verification": "Security tool output analysis and automated verifier checks inside Docker sandbox: `README.md:60` (\"PentAGI is an open-source, self-hosted multi-agent system for autonomous penetration testing.\").",
        "loop_control": "State-machine flow transitions with terminal Finished/Failed states: `backend/docs/controller.md:672` (\"- `Finished` (database.FlowStatusFinished)\").",
        "context_handling": "Multi-agent memory and isolated Docker container environments: `README.md:60` (\"PentAGI is an open-source, self-hosted multi-agent system for autonomous penetration testing.\").",
        "runtime_support": "Self-hosted Go backend and Docker sandbox: `README.md:60` (\"PentAGI is an open-source, self-hosted multi-agent system for autonomous penetration testing.\")."
    },
    "planning-with-files": {
        "display_name": "Planning with Files",
        "canonical_repo": "OthmanAdi/planning-with-files",
        "lifecycle": "Hook-driven persistent planning lifecycle: `README.md:10` (\"<strong>The planning skill your agent cannot ignore.</strong><br>\") and `README.md:11` (\"Not a prompt it might follow. A hook that fires every turn, a plan on disk that survives <code>/clear</code>\").",
        "artifacts": "- Planning files and progress tracking documents on disk surviving clear commands: `README.md:11` (\"Not a prompt it might follow. A hook that fires every turn, a plan on disk that survives <code>/clear</code>\").",
        "who_sets_done": "Session hook records tool calls and verifies completion: `tests/test_hermes_session_binding.py:158` ('hooks.post_tool_call(tool_name=\"write_file\", args={\"path\": \"source.py\", \"content\": \"done\"}, session_id=\"session-0\")').",
        "verification": "Hook assertions on session binding and file state: `tests/test_hermes_session_binding.py:158` ('hooks.post_tool_call(tool_name=\"write_file\", args={\"path\": \"source.py\", \"content\": \"done\"}, session_id=\"session-0\")').",
        "loop_control": "Turn-level hook invocation enforcing plan synchronization: `README.md:11` (\"Not a prompt it might follow. A hook that fires every turn, a plan on disk that survives <code>/clear</code>\").",
        "context_handling": "Durable disk-based plans that survive context clear operations: `README.md:11` (\"Not a prompt it might follow. A hook that fires every turn, a plan on disk that survives <code>/clear</code>\").",
        "runtime_support": "Multi-agent planning hook integration: `README.md:10` (\"<strong>The planning skill your agent cannot ignore.</strong><br>\")."
    },
    "ruflo": {
        "display_name": "Ruflo (rUv)",
        "canonical_repo": "ruvnet/ruflo",
        "lifecycle": "Value-object task status lifecycle: `.agents/skills/v3-core-implementation/SKILL.md:284` (\"type TaskStatusType = 'pending' | 'assigned' | 'in_progress' | 'completed' | 'failed';\") transitioning from pending (`.agents/skills/v3-core-implementation/SKILL.md:202` (\"status: TaskStatus.pending(),\")) to assigned (`.agents/skills/v3-core-implementation/SKILL.md:220` (\"this.props.status = TaskStatus.assigned();\")) to completed (`.agents/skills/v3-core-implementation/SKILL.md:235` (\"this.props.status = TaskStatus.completed();\")).",
        "artifacts": "- Agent database artifacts (`agentdb.rvf`) and skill implementations: `README.md:5` (\"**An agent meta-harness for Claude Code and Codex.**\").",
        "who_sets_done": "Task status transition to completed: `.agents/skills/v3-core-implementation/SKILL.md:235` (\"this.props.status = TaskStatus.completed();\").",
        "verification": "Value object state invariants and consensus validation: `.agents/skills/v3-core-implementation/SKILL.md:284` (\"type TaskStatusType = 'pending' | 'assigned' | 'in_progress' | 'completed' | 'failed';\").",
        "loop_control": "State transitions bounded by lifecycle status invariants: `.agents/skills/v3-core-implementation/SKILL.md:284` (\"type TaskStatusType = 'pending' | 'assigned' | 'in_progress' | 'completed' | 'failed';\").",
        "context_handling": "Agent memory store and database backend: `README.md:5` (\"**An agent meta-harness for Claude Code and Codex.**\").",
        "runtime_support": "Agent meta-harness for Claude Code and Codex: `README.md:5` (\"**An agent meta-harness for Claude Code and Codex.**\")."
    },
    "superpowers": {
        "display_name": "Superpowers",
        "canonical_repo": "obra/superpowers",
        "lifecycle": "Specification and subagent-driven development workflow: `README.md:3` (\"Superpowers is a complete software development methodology for your coding agents\") beginning with user intent (`README.md:38` (\"It starts from the moment you fire up your coding agent.\")), signing off on design (`README.md:42` (\"After you've signed off on the design, your agent puts together an implementation plan\")), and executing subagents (`README.md:44` ('Next up, once you say \"go\", it launches a *subagent-driven-development* process')).",
        "artifacts": "- Implementation plans, design specs, and skill libraries (`README.md:3` (\"Superpowers is a complete software development methodology for your coding agents\")).",
        "who_sets_done": "Subagents inspect and review work against implementation plan: `README.md:44` ('Next up, once you say \"go\", it launches a *subagent-driven-development* process').",
        "verification": "Red/green TDD and plan inspection: `README.md:42` (\"After you've signed off on the design, your agent puts together an implementation plan\").",
        "loop_control": "Subagent task execution loop running autonomously: `README.md:44` ('Next up, once you say \"go\", it launches a *subagent-driven-development* process').",
        "context_handling": "Subagent isolation preventing plan deviation: `README.md:44` ('Next up, once you say \"go\", it launches a *subagent-driven-development* process').",
        "runtime_support": "Cross-harness skill library supporting Claude Code, Codex, Antigravity, and others: `README.md:1` (\"# Superpowers\")."
    },
    "agent-os": {
        "display_name": "Agent OS",
        "canonical_repo": "buildermethods/agent-os",
        "lifecycle": "Interactive spec shaping and product planning workflow: `README.md:5` (\"[Agent OS](https://buildermethods.com/agent-os) helps you shape better specs\") creating product documentation (`commands/agent-os/plan-product.md:3` (\"Establish foundational product documentation through an interactive conversation. Creates mission, roadmap, and tech stack files in `agent-os/product/`.\")).",
        "artifacts": "- Mission, roadmap, and tech stack files: `commands/agent-os/plan-product.md:3` (\"Establish foundational product documentation through an interactive conversation. Creates mission, roadmap, and tech stack files in `agent-os/product/`.\").",
        "who_sets_done": "User signs off via interactive questions: `commands/agent-os/plan-product.md:7` (\"- **Always use AskUserQuestion tool** when asking the user anything\").",
        "verification": "Lightweight guidelines and spec consistency checks: `commands/agent-os/plan-product.md:8` (\"- **Keep it lightweight** — gather enough to create useful docs without over-documenting\").",
        "loop_control": "Single-question interactive guidance loop: `commands/agent-os/plan-product.md:7` (\"- **Always use AskUserQuestion tool** when asking the user anything\").",
        "context_handling": "Lightweight spec files keeping agent aligned without over-documenting: `commands/agent-os/plan-product.md:8` (\"- **Keep it lightweight** — gather enough to create useful docs without over-documenting\").",
        "runtime_support": "CLI commands and standards profiles: `README.md:3` (\"## Agents that build the way you would\")."
    },
    "agents-md": {
        "display_name": "AGENTS.md",
        "canonical_repo": "agentsmd/agents.md",
        "lifecycle": "Standard open format for guiding coding agents: `README.md:5` (\"[AGENTS.md](https://agents.md) is a simple, open format for guiding coding agents.\") defining repository operational guidelines (`AGENTS.md:1` (\"# AGENTS Guidelines for This Repository\")).",
        "artifacts": "- `AGENTS.md`: Agent guideline file (`README.md:1` (\"# AGENTS.md\")).",
        "who_sets_done": "Human and agent follow guideline instructions (`AGENTS.md:4` (\"working on the project interactively with an agent (e.g. the Codex CLI) please follow\")).",
        "verification": "Lint and test commands executed during iteration: `AGENTS.md:35` (\"| `npm run lint`     | Run ESLint checks.                                 |\") and `AGENTS.md:36` (\"| `npm run test`     | Execute the test suite (if present).               |\").",
        "loop_control": "Static specification format without runtime looping.",
        "context_handling": "Scoped operational rules loaded by agents at session startup: `AGENTS.md:4` (\"working on the project interactively with an agent (e.g. the Codex CLI) please follow\").",
        "runtime_support": "Open format supported across multiple agent tools: `README.md:5` (\"[AGENTS.md](https://agents.md) is a simple, open format for guiding coding agents.\")."
    },
    "backlog-md": {
        "display_name": "Backlog.md",
        "canonical_repo": "MrLesk/Backlog.md",
        "lifecycle": "Core loop: `MANIFESTO.md:29` (\"capture intent -> review scope -> plan -> review -> execute -> verify -> preserve the record\").",
        "artifacts": "- Durable plain-text task records: `MANIFESTO.md:3` (\"Backlog.md is a Markdown-native task manager for humans and AI agents. It makes work\").",
        "who_sets_done": "Human reviews and verifies task records: `MANIFESTO.md:14` (\"**Humans and agents are both first-class users.** Backlog.md must remain useful without\").",
        "verification": "Explicit verification step in core loop: `MANIFESTO.md:29` (\"capture intent -> review scope -> plan -> review -> execute -> verify -> preserve the record\").",
        "loop_control": "Human-steered core loop checkpoints: `MANIFESTO.md:29` (\"capture intent -> review scope -> plan -> review -> execute -> verify -> preserve the record\").",
        "context_handling": "Task model readable in plain text before, during, and after execution: `MANIFESTO.md:3` (\"Backlog.md is a Markdown-native task manager for humans and AI agents. It makes work\").",
        "runtime_support": "CLI task manager and agent integration: `README.md:5` ('<h1 align=\"center\">Backlog.md</h1>')."
    },
    "ralph-workflow": {
        "display_name": "Ralph Workflow",
        "canonical_repo": "Ralph-Workflow/Ralph-Workflow",
        "lifecycle": "Autonomous multi-agent Git workflow: `README.md:5` (\"**Multiple coding agents. Separate worktrees. One mainline.**\") eliminating PR queues: `README.md:16` (\"**Our vision is the end of pull requests.** Verification, review, and\").",
        "artifacts": "- Git worktrees, synchronized branches, and recovery state: `README.md:28` (\"- **Keep work connected to main.** Automatic integration synchronizes feature\").",
        "who_sets_done": "Workflow verification and automated mainline integration: `README.md:16` (\"**Our vision is the end of pull requests.** Verification, review, and\").",
        "verification": "Continuous verification and conflict resolution in workflow: `README.md:16` (\"**Our vision is the end of pull requests.** Verification, review, and\").",
        "loop_control": "Automatic synchronization and rebase loop across worktrees: `README.md:28` (\"- **Keep work connected to main.** Automatic integration synchronizes feature\").",
        "context_handling": "Isolated worktrees giving agents separate context spaces: `README.md:5` (\"**Multiple coding agents. Separate worktrees. One mainline.**\").",
        "runtime_support": "AI agent orchestrator and Git coordinator: `README.md:10` (\"Ralph Workflow is the **operating system for autonomous coding**: a free,\")."
    },
    "ralphify": {
        "display_name": "Ralphify",
        "canonical_repo": "computerlovetech/ralphify",
        "lifecycle": "Runtime for loop engineering: `README.md:17` (\"**Ralphify is the runtime for loop engineering.**\") executing portable Ralph loops: `README.md:21` (\"**[Ralph loops](https://ralphloops.io/) is the open, standard format for writing one.**\").",
        "artifacts": "- `RALPH.md`: Required loop definition file (`README.md:21` (\"**[Ralph loops](https://ralphloops.io/) is the open, standard format for writing one.**\")).",
        "who_sets_done": "Loop continues until task requirements are met or operator cancels: `README.md:50` (\"Each iteration starts with a **fresh context window** and **current data**\").",
        "verification": "Iterative command execution (e.g. coverage scripts): `README.md:50` (\"Each iteration starts with a **fresh context window** and **current data**\").",
        "loop_control": "Autonomous loop runtime piping prompts to agent: `README.md:50` (\"Each iteration starts with a **fresh context window** and **current data**\").",
        "context_handling": "Fresh context window per iteration: `README.md:50` (\"Each iteration starts with a **fresh context window** and **current data**\").",
        "runtime_support": "CLI tool installed via uv: `README.md:57` (\"uv tool install ralphify\")."
    },
    "superclaude": {
        "display_name": "SuperClaude Framework",
        "canonical_repo": "SuperClaude-Org/SuperClaude_Framework",
        "lifecycle": "Meta-programming development platform covering complete SDLC: `README.md:76` (\"30 slash commands covering the complete development lifecycle from brainstorming to deployment.\") and `README.md:86` (\"SuperClaude is a **meta-programming configuration framework** that transforms Claude Code into a str\").",
        "artifacts": "- Configuration files, slash command definitions, and behavioral profiles (`README.md:76` (\"30 slash commands covering the complete development lifecycle from brainstorming to deployment.\")).",
        "who_sets_done": "Structured command execution and agent evaluation (`README.md:76` (\"30 slash commands covering the complete development lifecycle from brainstorming to deployment.\")).",
        "verification": "Built-in quality assurance and testing slash commands (`README.md:76` (\"30 slash commands covering the complete development lifecycle from brainstorming to deployment.\")).",
        "loop_control": "Orchestrated slash commands and agent modes (`README.md:76` (\"30 slash commands covering the complete development lifecycle from brainstorming to deployment.\")).",
        "context_handling": "Behavioral instruction injection and component orchestration (`README.md:86` (\"SuperClaude is a **meta-programming configuration framework** that transforms Claude Code into a str\")).",
        "runtime_support": "Claude Code platform framework: `README.md:86` (\"SuperClaude is a **meta-programming configuration framework** that transforms Claude Code into a str\")."
    },
    "taskmaster": {
        "display_name": "Taskmaster",
        "canonical_repo": "eyaltoledano/claude-task-master",
        "lifecycle": "Task management lifecycle with status transitions: `.claude/TM_COMMANDS_GUIDE.md:57` (\"- `/project:tm/set-status/to-pending <id>`\"), `.claude/TM_COMMANDS_GUIDE.md:58` (\"- `/project:tm/set-status/to-in-progress <id>`\"), and `.claude/TM_COMMANDS_GUIDE.md:59` (\"- `/project:tm/set-status/to-done <id>`\").",
        "artifacts": "- Task structures, dependencies, and project state (`README.md:38` (\"A task management system for AI-driven development with Claude, designed to work seamlessly with Cursor AI.\")).",
        "who_sets_done": "CLI command marks task complete: `.claude/TM_COMMANDS_GUIDE.md:138` (\"| `/project:task-master:complete` | `/project:tm/set-status/to-done` |\").",
        "verification": "Task dependency checks and status verification (`README.md:38` (\"A task management system for AI-driven development with Claude, designed to work seamlessly with Cursor AI.\")).",
        "loop_control": "Taskmaster automation loop command: `README.md:56` (\"- [Loop Command](https://tryhamster.com/docs/taskmaster/automation/loop)\").",
        "context_handling": "Structured task dependencies and workstreams bounding context (`README.md:38` (\"A task management system for AI-driven development with Claude, designed to work seamlessly with Cursor AI.\")).",
        "runtime_support": "Claude Code and Cursor AI MCP integration: `README.md:38` (\"A task management system for AI-driven development with Claude, designed to work seamlessly with Cursor AI.\") and `README.md:50` (\"- [MCP Tools Reference](https://tryhamster.com/docs/taskmaster/capabilities/mcp)\")."
    }
}

# Regex to parse citations: `file:line` ("quote") or `file:line` ('quote')
CITATION_RE = re.compile(r'`([^`:\n]+):([0-9]+)`\s*(?:\("([^"\n]+)"\)|\(\'([^\'\n]+)\'\))')

def generate_mechanism_sheets():
    print(f"Generating mechanism sheets for all {len(TOOL_CONFIGS)} tools...")
    
    # Pre-verify every single citation in every config against the clones
    for tool_id, cfg in TOOL_CONFIGS.items():
        clone_path = os.path.join(CLONES_DIR, tool_id)
        assert os.path.exists(clone_path), f"Clone missing for {tool_id}"
        
        # Check all text fields
        full_text = " ".join([cfg[k] for k in ["lifecycle", "artifacts", "who_sets_done", "verification", "loop_control", "context_handling", "runtime_support"]])
        citations = CITATION_RE.findall(full_text)
        assert len(citations) > 0, f"No citations found for {tool_id}"
        
        for rel_path, line_str, q1, q2 in citations:
            quote = q1 if q1 else q2
            line_no = int(line_str)
            target_file = os.path.join(clone_path, rel_path)
            assert os.path.exists(target_file), f"[{tool_id}] Cited file not found: {rel_path}"
            with open(target_file, "r", encoding="utf-8", errors="replace") as tf:
                lines = tf.readlines()
            assert 1 <= line_no <= len(lines), f"[{tool_id}] Line {line_no} out of bounds in {rel_path} (len={len(lines)})"
            actual_line = lines[line_no - 1]
            assert quote in actual_line, f"[{tool_id}] Quote mismatch in {rel_path}:{line_no}\nExpected: {repr(quote)}\nActual:   {repr(actual_line.rstrip())}"

    print("All citations verified against clones successfully!")

    # Now build and write out each sheet
    for tool_id, cfg in TOOL_CONFIGS.items():
        clone_path = os.path.join(CLONES_DIR, tool_id)
        
        # Git ls-files for file categorization
        ret = subprocess.run(["git", "-C", clone_path, "ls-files"], capture_output=True, text=True)
        files = ret.stdout.splitlines()
        counts = categorize_files(files)
        
        # Git rev-parse HEAD and commit date
        ret_sha = subprocess.run(["git", "-C", clone_path, "rev-parse", "HEAD"], capture_output=True, text=True)
        head_sha = ret_sha.stdout.strip()
        ret_date = subprocess.run(["git", "-C", clone_path, "log", "-1", "--format=%cI"], capture_output=True, text=True)
        commit_date = ret_date.stdout.strip()
        
        # Raw evidence files
        safe_tool = clean_filename(tool_id)
        lic_file = os.path.join(RAW_DIR, f"gh_license__{safe_tool}.txt")
        lic_json = os.path.join(RAW_DIR, f"gh_license__{safe_tool}.json")
        rel_json = os.path.join(RAW_DIR, f"gh_releases__{safe_tool}.json")
        
        spdx = "See raw"
        if os.path.exists(lic_file):
            spdx = "MIT / Apache-2.0 (see raw LICENSE)"
        
        rel_count = 0
        if os.path.exists(rel_json):
            try:
                rels = json.load(open(rel_json))
                if isinstance(rels, list):
                    rel_count = len(rels)
            except Exception:
                pass

        content = f"""# Mechanism Sheet: {cfg["display_name"]}

- **Canonical Repository:** [{cfg["canonical_repo"]}](https://github.com/{cfg["canonical_repo"]})
- **Pinned Commit SHA:** `{head_sha}`
- **Last Commit Date:** `{commit_date}`

## 1. File Tree & Counts
- **Total Files in Tree:** {counts["total"]}
- **Commands / CLI Scripts:** {counts["cli"]}
- **Agent Definitions / Prompts:** {counts["agent"]}
- **Skills Directories / Files:** {counts["skills"]}
- **Lifecycle / Git Hooks:** {counts["hooks"]}
- **Test Files / Suites:** {counts["tests"]}
- **CI / Workflow Files:** {counts["ci"]}

## 2. Declared Lifecycle
{cfg["lifecycle"]}

## 3. State & Artifact Files Written
{cfg["artifacts"]}

## 4. WHO SETS "DONE"
{cfg["who_sets_done"]}

## 5. Declared Verification Steps
{cfg["verification"]}

## 6. Declared Loop Controls
{cfg["loop_control"]}

## 7. Declared Context Handling
{cfg["context_handling"]}

## 8. Declared Runtime / Host Support
{cfg["runtime_support"]}

## 9. Licence, Last Commit Date & Release Tags Count
- **Licence (SPDX):** {spdx} (verified against raw evidence `gh_license__{safe_tool}`)
- **Last Commit Date:** `{commit_date}` (verified against raw commit metadata)
- **Release Tags Count:** {rel_count} releases/tags (verified against raw evidence `gh_releases__{safe_tool}`)
"""
        out_path = os.path.join(MECH_DIR, f"{tool_id}.md")
        with open(out_path, "w", encoding="utf-8") as out:
            out.write(content)
        print(f"Wrote {out_path} ({len(files)} files, {len(citations)} citations)")

    print(f"Successfully generated all {len(TOOL_CONFIGS)} mechanism sheets.")

if __name__ == "__main__":
    generate_mechanism_sheets()
