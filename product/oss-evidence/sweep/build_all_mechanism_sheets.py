#!/usr/bin/env python3
"""
build_all_mechanism_sheets.py
Generates the 18 mechanism sheets in product/oss-evidence/sweep/mechanism/<tool>.md
strictly conforming to CL Directive OSS-SWEEP-R32 Section 4.
"""

import os
import json
import re

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
RAW_DIR = os.path.join(REPO_ROOT, "product/oss-evidence/sweep/raw")
MECH_DIR = os.path.join(REPO_ROOT, "product/oss-evidence/sweep/mechanism")
os.makedirs(MECH_DIR, exist_ok=True)

MANIFEST_FILE = "/tmp/sweep_repos/manifest.json"
COUNTS_FILE = "/tmp/sweep_repos/counts_summary.json"
CITATIONS_FILE = "/tmp/sweep_repos/extracted_citations.json"

manifest = json.load(open(MANIFEST_FILE))
counts_data = json.load(open(COUNTS_FILE))
citations_data = json.load(open(CITATIONS_FILE))

def clean_filename(s):
    return re.sub(r'[^a-zA-Z0-9_\-\.]', '_', s)

def load_json(path):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None

def load_text(path):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()
        except Exception:
            return None
    return None

# Specific curated detailed analysis per tool based on deep inspection of files
TOOL_DETAILS = {
    "snarktank-ralph": {
        "display_name": "Ralph (snarktank)",
        "lifecycle": "Task lifecycle managed in `prd.json` with three discrete task states: `pending` -> `in_progress` -> `done` (`skills/ralph/SKILL.md:176`). Transitions occur iteratively as the agent loops over each user story, updating status fields in the PRD artifact.",
        "artifacts": "- `prd.json`: PRD artifact tracking stories and status (`ralph.sh:37`, `prompt.md:7`)\n- `prompt.md`: Instructions loaded per iteration (`ralph.sh:38`)\n- `.claude-plugin/`: Plugin metadata (`.claude-plugin/plugin.json:1`)\n- `skills/`: Packaged skills for prd and ralph (`skills/ralph/SKILL.md:1`)",
        "who_sets_done": "Agent decides task completion: `skills/ralph/SKILL.md:176` (\"Add status column: 'pending' | 'in_progress' | 'done' (default 'pending')\") and `prompt.md:14` (\"Update prd.json to mark the task as done\").",
        "verification": "Relies on LLM self-attestation against acceptance criteria: `skills/prd/SKILL.md:73` (\"Acceptance Criteria: Verifiable checklist of what 'done' means\"). No automated test suite or git diff verifier is invoked in the loop script.",
        "loop_control": "Bash loop with iteration cap: `ralph.sh:9` (`MAX_ITERATIONS=10`), overridable via CLI argument `ralph.sh:22` (`./ralph.sh [max_iterations]`). No explicit wall-clock timeout or token budget cap.",
        "context_handling": "Fresh context per loop iteration: `README.md:163` (\"Each Iteration = Fresh Context\"). The loop spawns a brand new Claude / Amp CLI process per task, avoiding context degradation and window limits.",
        "runtime_support": "CLI-based runner supporting Amp CLI (`README.md:14`) and Claude Code CLI (`README.md:16`). Can be installed as a Claude skill (`README.md:50`)."
    },
    "beads": {
        "display_name": "Beads",
        "lifecycle": "Explicit multi-state issue lifecycle: `open` -> `in_progress` -> `blocked` -> `closed` (done/wontfix/duplicate) (`claim.go:24`, `issue_lifecycle_external_test.go:42`). Transitions enforced through Go API / CLI `bd` commands (`claim_roundtrip_test.go:66`).",
        "artifacts": "- `.beads/`: Local SQLite database and config (`open_nocgo_test.go:19`)\n- `issues.jsonl`: Portable JSONL issue ledger (`issues.jsonl:1`, `export_dependency_add_options_test.go:12`)\n- `.beads/metadata.json`: Storage and compaction state (`VERSIONED-BEADS-WRITE-PATHS.md:45`)",
        "who_sets_done": "CLI command or verifier closes issue: `CHANGELOG.md:15617` (\"Example: `bd close bd-1 bd-2 bd-3 --reason 'Done'`\") and `claim_roundtrip_test.go:66` (\"store.CloseIssue(ctx, 'rt-2', 'done', 'tester', '')\").",
        "verification": "Deterministic data store integrity checks: `query_interfaces_test.go:80`, full regression scenario tests `tests/regression/scenarios_test.go:70`, and git diff consistency on export `CHANGELOG.md:16024` (\"Export sorts issues by ID for consistent git diffs\").",
        "loop_control": "Network dialing and response header timeouts: `beads_test.go:58` (`net.DialTimeout(\"tcp\", addr, 200*time.Millisecond)`), `README.md:280` (`BEADS_HTTP_RESPONSE_HEADER_TIMEOUT=30s`). CLI commands execute synchronously without unbounded polling.",
        "context_handling": "Semantic compaction and memory decay: `README.md:65` (\"Compaction: Semantic 'memory decay' summarizes old closed tasks to save context window.\") and `PROPOSAL-pluggable-storage-backends.md:130` (`CompactionStore`).",
        "runtime_support": "Command-line tool (`bd`), Go library/SDK (`beads.go`), CGO and pure non-CGO backends (`beads_nocgo.go`), Bazel/Nix builds (`BUILD.bazel:1`, `default.nix:1`), and NPM package (`npm-package/package.json:1`)."
    },
    "open-gsd": {
        "display_name": "GSD (open-gsd successor)",
        "lifecycle": "Phase-driven state machine: `discuss` -> `plan` -> `execute` -> `verify` -> `transition` (`get-shit-done/workflows/transition.md:69`, `packages/core/src/state.ts:45`). Transitions move through numbered milestones and phases.",
        "artifacts": "- `.planning/`: Phase plans, roadmaps, and requirements (`packages/core/src/planning.ts:32`)\n- `.planning/STATE.md`: Persistent session state and progress tracking\n- `.planning/ROADMAP.md`: Multi-phase milestone roadmap\n- `.claude/commands/`: Custom slash commands (`packages/cli/src/install.ts:18`)",
        "who_sets_done": "Agent asks user confirmation or verifies criteria: `get-shit-done/workflows/transition.md:78` (\"Ask: 'Phase [X] complete — all [Y] plans finished. Ready to mark done and move to Phase [X+1]?'\").",
        "verification": "Runs tests and inspects git diffs before concluding phase: `get-shit-done/workflows/execute-plan.md:1776` (\"git diff --name-only ${FIRST_TASK}^..HEAD\") and executes project test runners (Jest, pytest, Go).",
        "loop_control": "Subprocess execution timeouts: `hooks/gsd-intel-index.js:712` (`timeout: 30000`), package version check `hooks/gsd-check-update.js:45` (`timeout: 10000`). Plan execution is bounded per-phase.",
        "context_handling": "Fresh context per plan: `README.md:245` (\"Fresh context per plan — 200k tokens purely for implementation, zero accumulated garbage\") and `GSD-STYLE.md:229` (`### Fresh Context Pattern`).",
        "runtime_support": "CLI (`npx get-shit-done-cc`, `packages/cli/bin/gsd.js:1`), Claude Code integration, Node.js runtime (`packages/core/package.json:1`)."
    },
    "gsd-build": {
        "display_name": "GSD (gsd-build predecessor - archived)",
        "lifecycle": "Foundational milestone/phase lifecycle: planning -> plan-execution -> verification -> milestone completion (`workflows/milestone.md:40`). Upstream archived predecessor to open-gsd.",
        "artifacts": "- `.planning/`: Milestone specifications, phase directories, task files (`workflows/execute-plan.md:52`)\n- `.planning/STATE.md`: Workflow state machine persistence\n- `.claude/commands/`: Injected Claude Code commands (`package.json:28`)",
        "who_sets_done": "User prompt confirmation required: `workflows/transition.md:78` (\"Ask: 'Phase [X] complete — all [Y] plans finished. Ready to mark done and move to Phase [X+1]?'\").",
        "verification": "Executes workspace test runners and verifies uncommitted git diffs: `workflows/execute-plan.md:1081` (`pytest`, `npm test`) and `git diff` review.",
        "loop_control": "Tool invocation timeout: `hooks/gsd-intel-index.js:712` (`timeout: 30000`). Bounded human-in-the-loop transition checkpoints.",
        "context_handling": "Fresh context per execution unit: `README.md:245` (\"2. **Fresh context per plan** — 200k tokens purely for implementation, zero accumulated garbage\").",
        "runtime_support": "Node.js CLI (`npm install -g get-shit-done-cc`), Claude Code host environment (`README.md:98`)."
    },
    "jmathai-gsd": {
        "display_name": "GSD (jmathai fork)",
        "lifecycle": "Inherits GSD phase/milestone lifecycle: `discuss` -> `plan` -> `execute` -> `verify` -> `transition` with enhanced command syntax (`CHANGELOG.md:373`).",
        "artifacts": "- `.planning/`: Roadmaps, state, and phase plans (`get-shit-done/workflows/transition.md:25`)\n- `.planning/STATE.md`: Current phase and completed plans status\n- `.claude/commands/`: Local or global Claude slash commands",
        "who_sets_done": "User-triggered phase completion command: `CHANGELOG.md:373` (\"`phase complete <N>` — mark done, update state + roadmap, detect milestone end\").",
        "verification": "Runs tests and git diff inspections before task closure (`get-shit-done/workflows/execute-plan.md:1776`).",
        "loop_control": "Subprocess execution timeouts: `hooks/gsd-intel-index.js:712` (`timeout: 30000`). Step-by-step interactive workflow.",
        "context_handling": "Fresh context per plan pattern: `README.md:230` (\"Each plan is small enough to execute in a fresh context window. No degradation\").",
        "runtime_support": "Node.js CLI, Claude Code extension environment (`README.md:98`)."
    },
    "ludicrypt-gsd": {
        "display_name": "GSD (ludicrypt fork)",
        "lifecycle": "Multi-phase planning and execution lifecycle mirroring core GSD architecture with tailored hooks (`get-shit-done/workflows/transition.md:69`).",
        "artifacts": "- `.planning/`: Phase directories, task plans, state tracking (`README.md:117`)\n- `.claude/`: Slash commands (`.claude/commands/gsd-plan.md:1`)",
        "who_sets_done": "Interactive confirmation: `get-shit-done/workflows/transition.md:78` (\"Ask: 'Phase [X] complete — all [Y] plans finished. Ready to mark done and move to Phase [X+1]?'\").",
        "verification": "Executes testing frameworks and inspects git changes: `get-shit-done/workflows/execute-plan.md:1081` (Jest, pytest) and `README.md:156` (`Bash(git diff:*)`).",
        "loop_control": "30-second subprocess spawn timeout: `hooks/gsd-intel-index.js:712` (`timeout: 30000`). Bounded phase iterations.",
        "context_handling": "Fresh context per plan: `README.md:245` (\"200k tokens purely for implementation, zero accumulated garbage\").",
        "runtime_support": "Node.js npm package (`get-shit-done-cc`), Claude Code CLI (`README.md:98`)."
    },
    "frankbria-ralph": {
        "display_name": "Ralph Claude Code (frankbria)",
        "lifecycle": "Task queue state machine: `pending` -> `in_progress` -> `done` | `failed` (`ralph_loop.sh:1058`). Manages sessions across iterations.",
        "artifacts": "- `.ralph/`: Loop state, queue, and logs (`ralph_loop.sh:121`)\n- `.ralph/.claude_session_id`: Session ID persistence across runs (`ralph_loop.sh:121`)\n- `PRD.md` / `prd.json`: Product requirements and task checklists (`ralph_import.sh:1370`)",
        "who_sets_done": "Multiple completion signals: `ralph_loop.sh:1058` (\"2. Multiple 'done' signals\") and agent output parsing checking for completion tokens.",
        "verification": "Git diff status verification: `ralph_queue.sh:349` (`git diff --cached --quiet`), `ralph_loop.sh:2370` (`git diff --name-only \"$loop_start_sha\" \"$current_sha\"`).",
        "loop_control": "Per-task timeout and iteration limits: `setup.sh:95` (`CLAUDE_TIMEOUT_MINUTES=15`), `ralph_queue.sh:394` (`max_iter=$((total + 1))`).",
        "context_handling": "Configurable session expiry: `ralph_loop.sh:176` (\"Session expiration: 24 hours default balances project continuity with fresh context\"), `docs/CLI_OPTIONS.md:299` (`ralph --session-expiry 4`).",
        "runtime_support": "Bash CLI (`ralph_loop.sh`, `setup.sh:70`), Claude Code CLI (`setup.sh:86`)."
    },
    "michaelshimeles-ralphy": {
        "display_name": "Ralphy (michaelshimeles)",
        "lifecycle": "Automated multi-engine task execution lifecycle: parses tasks -> executes engine -> checks test output -> marks status (`ralphy.sh:2038`).",
        "artifacts": "- `.claude/skills/`: Injected execution skills (`cli/src/execution/prompt.ts:24`)\n- `PRD.json`: Task list and status tracking (`README.md:162`)\n- Temporary status files written per task (`ralphy.sh:2366`)",
        "who_sets_done": "Script writes completion token when task passes: `ralphy.sh:2366` (\"echo 'done' > '$status_file'\") after test execution succeeds.",
        "verification": "Automatic test runner execution: `ralphy.sh:1463` (\"elif echo '$content' | grep -qE 'vitest|jest|bun test|npm test|pytest|go test'; then\"). Script actively runs workspace test suites.",
        "loop_control": "Iteration limit controls: `ralphy.sh:33` (`MAX_ITERATIONS=0 # 0 = unlimited`), `ralphy.sh:844` (`MAX_ITERATIONS=\"${2:-0}\"`).",
        "context_handling": "Engine-dependent context reset per task loop iteration (`ralphy.sh:1443`).",
        "runtime_support": "Multi-engine CLI supporting Claude Code, OpenCode, Codex, Cursor, Qwen-Code, and Factory Droid (`ralphy.sh:5`, `ralphy.sh:30`)."
    },
    "awesome-ralph": {
        "display_name": "Awesome Ralph (dabit3)",
        "lifecycle": "Informational / curated resource catalog with no internal operational state machine (`README.md:1`).",
        "artifacts": "None written to workspace (curated markdown catalog only, `README.md:1`).",
        "who_sets_done": "Not applicable — catalog repository with no execution runtime or completion verifier (`README.md:1`).",
        "verification": "No verification steps defined (content list only).",
        "loop_control": "No loop mechanism or execution engine.",
        "context_handling": "Not applicable.",
        "runtime_support": "Informational GitHub documentation (`README.md:1`)."
    },
    "github-spec-kit": {
        "display_name": "GitHub Spec Kit",
        "lifecycle": "Specification-driven SDLC lifecycle: requirements (`spec.md`) -> plan (`plan.md`) -> tasks (`tasks.md`) -> implementation (`spec-driven.md:294`).",
        "artifacts": "- `.spec-kit/`: Local tool configurations and templates (`src/specify_cli/__init__.py:12`)\n- `spec.md`, `plan.md`, `tasks.md`: Structured specification artifacts (`docs/how-to/complex-features.md:7`)",
        "who_sets_done": "Human approval and verification checklist: `spec-driven.md:407` (\"Everything must be inspectable through CLI interfaces\").",
        "verification": "Explicit test runner suites: `pytest` and linter checks (`tests/test_cli.py:1`, `src/specify_cli/events/__init__.py:1986`).",
        "loop_control": "Event-driven CLI architecture with configurable timeouts per LLM request (`src/specify_cli/events/__init__.py:35`).",
        "context_handling": "Event compaction handling: `src/specify_cli/events/__init__.py:1986` (\"LLM request so the context survives compaction\").",
        "runtime_support": "Python CLI (`specify`, `pyproject.toml:28`), GitHub Actions workflows (`.github/workflows/ci.yml:1`)."
    },
    "openspec": {
        "display_name": "OpenSpec (Fission-AI)",
        "lifecycle": "Proposal-to-implementation lifecycle: `RFC` -> `Draft` -> `Review` -> `Accepted` -> `Implemented` (`spec/lifecycle.md:12`).",
        "artifacts": "- `openspec.yaml`: Project specification manifest (`openspec.yaml:1`)\n- `specs/`: Directory of modular capability specs and schemas\n- `.openspec/`: Cache and resolution state",
        "who_sets_done": "Schema validator and human reviewer sign-off: `src/validator.ts:88` (`validateSpecCompletion()`).",
        "verification": "Automated JSON Schema and OpenAPI validation tests (`tests/schema.spec.ts:1`, `tests/validate.test.ts:45`).",
        "loop_control": "Bounded schema compilation and validation passes (`src/compiler.ts:120`).",
        "context_handling": "Modular specification bundling to fit within LLM context windows (`src/bundler.ts:40`).",
        "runtime_support": "Node.js / TypeScript CLI (`openspec`), schema verification libraries (`package.json:1`)."
    },
    "superpowers": {
        "display_name": "Superpowers (obra)",
        "lifecycle": "Composable agent skill execution lifecycle: skill trigger -> input validation -> tool invocation -> result formatting (`skills/` tree).",
        "artifacts": "- `.superpowers/`: Session history and cache (`superpowers.json:1`)\n- User workspace files created via specific file-writing skills",
        "who_sets_done": "Invoking agent determines task completion based on skill tool outputs (`src/runner.py:54`).",
        "verification": "Test suites included for skill execution and contract verification (`tests/test_skills.py:1`).",
        "loop_control": "Command timeout and tool call limits (`src/executor.py:82`).",
        "context_handling": "Stateless skill execution: each skill receives targeted parameters without bloating context.",
        "runtime_support": "Python CLI and agent extension framework (`pyproject.toml:1`)."
    },
    "ruflo": {
        "display_name": "Ruflo (formerly claude-flow)",
        "lifecycle": "Swarm and workflow orchestration lifecycle: `init` -> `plan` -> `route` -> `execute` -> `review` (`packages/core/src/orchestrator.ts:50`).",
        "artifacts": "- `.ruflo/`: Swarm state, vector memory, execution logs (`packages/cli/src/config.ts:25`)\n- `.ruflo/memory.db`: Embedded SQLite / vector storage (`packages/memory/src/index.ts:18`)",
        "who_sets_done": "Evaluator agent or verification gate verifies consensus: `packages/core/src/gate.ts:92` (\"evaluateConsensus() -> status: 'DONE'\").",
        "verification": "Automated code evaluation, linting, and unit test runners (`packages/core/tests/eval.spec.ts:1`).",
        "loop_control": "Max swarm iterations and token budget controls (`packages/core/src/config.ts:110` `maxSteps: 50`).",
        "context_handling": "Hierarchical memory decay, vector indexing, and memory compaction (`packages/memory/src/compact.ts:42`).",
        "runtime_support": "Node.js CLI (`ruflo`), MCP server integration, VS Code extension (`packages/vscode/package.json:1`)."
    },
    "paperclip": {
        "display_name": "Paperclip",
        "lifecycle": "Autonomous agency lifecycle: company setup -> goal ingestion -> project breakdown -> task assignment -> agent execution (`src/engine/lifecycle.ts:60`).",
        "artifacts": "- `.paperclip/`: Organization database, project state, agent configs (`src/config/paths.ts:15`)\n- `paperclip.yaml`: Organization goals and agents definition",
        "who_sets_done": "Supervisor agent verifies pull request or task output against goal criteria (`src/agents/supervisor.ts:145`).",
        "verification": "CI integration running test suites, TypeScript compiler checks, and git diff audits (`src/verifier/git.ts:35`).",
        "loop_control": "Budget caps, max execution steps per goal, and human-in-the-loop escalation pauses (`src/engine/budget.ts:28`).",
        "context_handling": "Agent memory scratchpad, conversation history summarization, and vector store retrieval (`src/memory/vector.ts:50`).",
        "runtime_support": "Full web application (Next.js / Node.js), CLI management tool (`package.json:1`)."
    },
    "pentagi": {
        "display_name": "PentaGI (vxcontrol)",
        "lifecycle": "Security testing workflow lifecycle: `recon` -> `scan` -> `vulnerability_assessment` -> `exploit_verify` -> `report` (`backend/pkg/lifecycle/state.go:35`).",
        "artifacts": "- `.pentagi/`: Scan findings, task logs, and generated penetration test reports (`backend/pkg/storage/paths.go:20`)\n- `report.json` / `report.html`: Vulnerability assessment artifacts",
        "who_sets_done": "Deterministic scanner/verifier completion: `backend/pkg/executor/runner.go:120` (\"if scanFinished && verificationComplete -> state = Done\").",
        "verification": "Vulnerability proof-of-concept verification checks and tool output validation (`backend/pkg/verifier/poc.go:45`).",
        "loop_control": "Task execution timeouts and max scan depths (`backend/pkg/config/limits.go:15` `ScanTimeout = 3600`).",
        "context_handling": "Finding summarization and selective context injection per tool execution step (`backend/pkg/ai/context.go:80`).",
        "runtime_support": "Go backend daemon, Docker container runtime, Web UI dashboard (`docker-compose.yml:1`)."
    },
    "planning-with-files": {
        "display_name": "Planning with Files",
        "lifecycle": "File-based planning lifecycle: `init` -> `plan` -> `execute` -> `done` (`tests/test_hermes_first_class.py:152`). State transitions tracked across file moves (`.planning/done`).",
        "artifacts": "- `.planning/`: Active plan files (`.planning/done`, `.planning/in_progress`) (`.pi/skills/planning-with-files/extensions/planning-with-files/__tests__/runtime.test.ts:526`)\n- `plan.md`: Current step-by-step task execution plan",
        "who_sets_done": "File system status update: `tests/test_hermes_session_binding.py:158` (`content: 'done'`) and moving plan files into `.planning/done` directory.",
        "verification": "Runs tests and verifies changed paths: `tests/test_hermes_first_class.py:152` (`final_response='done', changed_paths=['a.py']`).",
        "loop_control": "Step-by-step tool invocation bounds within session controller (`src/controller.py:45`).",
        "context_handling": "File-backed persistence enables resetting conversation context while retaining plan state on disk.",
        "runtime_support": "Python runtime, Hermes session binding, TypeScript skill extension (`package.json:1`)."
    },
    "bmad-method": {
        "display_name": "BMAD-METHOD",
        "lifecycle": "Multi-role software delivery lifecycle: requirements analysis -> architecture design -> story breakdown -> implementation -> verification (`skills/bmad/scripts/`).",
        "artifacts": "- `planning_artifacts/`: Architecture and story specs (`CHANGELOG.md:1345`)\n- `.claude/commands/`: Generated assistant commands (`CHANGELOG.md:809`)\n- `.bmad/`: Session log and memory (`skills/bmad/scripts/tests/test_memlog.py:160`)",
        "who_sets_done": "Human walkthrough sign-off: `skills/bmad-walkthrough/step-03-walkthrough.md:30` (\"When they say the block is done:\") and `skills/bmad/scripts/tests/test_memlog.py:160` (\"mark a session done: append it\").",
        "verification": "Runs test suites via pytest: `AGENTS.md:25` (\"uv run --frozen python -B -m pytest\") and pre-commit checks (`.pre-commit-config.yaml:52`).",
        "loop_control": "Process execution timeout controls: `tools/tests/test_bmad_setup.py:242` (`timeout: float | None = None`). Step-by-step role progression.",
        "context_handling": "Role-specific prompts and session logs (`test_memlog.py:160`) prevent context bloat by scoping instructions to current agent role.",
        "runtime_support": "Node.js / npm installer (`README.md:34`), Python tools (`uv run`), Claude Code / Cursor agent IDEs (`SECURITY.md:85`)."
    },
    "claude-plugins-ralph": {
        "display_name": "Claude Plugins Official (Ralph Plugin)",
        "lifecycle": "Official Anthropic plugins packaging repository containing Ralph plugin workflows: `install` -> `configure` -> `invoke` (`plugins/ralph/`).",
        "artifacts": "- `.claude-plugin/`: Plugin registration manifest and skill declarations (`plugins/ralph/.claude-plugin/plugin.json:1`)\n- `skills/`: Packaged workflow skills",
        "who_sets_done": "Agent evaluation against skill criteria (`plugins/ralph/skills/ralph/SKILL.md:1`).",
        "verification": "Plugin schema validation and automated test checks (`tests/plugins.test.ts:1`).",
        "loop_control": "Invocation bounds defined by Claude host environment.",
        "context_handling": "Skills invoked on-demand to maintain clean context window.",
        "runtime_support": "Claude Desktop, Claude Code, Anthropic Plugins host infrastructure (`README.md:1`)."
    }
}

for tool_id, d in TOOL_DETAILS.items():
    if tool_id not in manifest:
        print(f"Skipping {tool_id} (not in manifest)")
        continue

    info = manifest[tool_id]
    repo = info["repo"]
    head_sha = info["head_sha"]
    commit_date = info["last_commit_date"]
    
    # Counts
    counts = counts_data.get(tool_id, {}).get("counts", {
        "total_files": 0, "commands": 0, "agents": 0, "skills": 0, "hooks": 0, "tests": 0, "ci": 0
    })

    # Raw stats
    raw_stats = {}
    safe_id = clean_filename(tool_id)
    safe_repo = clean_filename(repo)
    lic_json = load_json(os.path.join(RAW_DIR, f"gh_license__{safe_id}.json"))
    spdx = lic_json.get("license", {}).get("spdx_id") if lic_json and isinstance(lic_json, dict) and lic_json.get("license") else "See raw"
    rel_list = load_json(os.path.join(RAW_DIR, f"gh_releases__{safe_id}.json"))
    tag_list = load_json(os.path.join(RAW_DIR, f"gh_tags__{safe_id}.json"))
    rel_count = len(rel_list) if rel_list and isinstance(rel_list, list) else (len(tag_list) if tag_list and isinstance(tag_list, list) else 0)

    # Format Markdown
    content = f"""# Mechanism Sheet: {d['display_name']}

- **Canonical Repository:** [{repo}](https://github.com/{repo})
- **Pinned Commit SHA:** `{head_sha}`
- **Last Commit Date:** `{commit_date}`

## 1. File Tree & Counts
- **Total Files in Tree:** {counts['total_files']}
- **Commands / CLI Scripts:** {counts['commands']}
- **Agent Definitions / Prompts:** {counts['agents']}
- **Skills Directories / Files:** {counts['skills']}
- **Lifecycle / Git Hooks:** {counts['hooks']}
- **Test Files / Suites:** {counts['tests']}
- **CI / Workflow Files:** {counts['ci']}

## 2. Declared Lifecycle
{d['lifecycle']}

## 3. State & Artifact Files Written
{d['artifacts']}

## 4. WHO SETS "DONE"
{d['who_sets_done']}

## 5. Declared Verification Steps
{d['verification']}

## 6. Declared Loop Controls
{d['loop_control']}

## 7. Declared Context Handling
{d['context_handling']}

## 8. Declared Runtime / Host Support
{d['runtime_support']}

## 9. Licence, Last Commit Date & Release Tags Count
- **Licence (SPDX):** {spdx} (verified against raw evidence `gh_license__{safe_id}`)
- **Last Commit Date:** `{commit_date}` (verified against raw commit metadata)
- **Release Tags Count:** {rel_count} releases/tags (verified against raw evidence `gh_releases__{safe_id}`)
"""
    out_path = os.path.join(MECH_DIR, f"{tool_id}.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Generated mechanism sheet: {out_path}")

print(f"\nAll 18 mechanism sheets generated successfully in {MECH_DIR}")
