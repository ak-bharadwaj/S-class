# Ralph Workflow

## The end of pull requests.

**Multiple coding agents. Separate worktrees. One mainline.**

Coding agents can write code in parallel. Getting their changes together
should be just as autonomous.

Ralph Workflow is the **operating system for autonomous coding**: a free,
open-source AI agent orchestrator that plans, builds, verifies, and integrates
work with the coding agents you already use. Its standout capability is Git
synchronization across worktrees: agents work separately while Ralph Workflow
brings their committed changes back to a shared mainline.

**Our vision is the end of pull requests.** Verification, review, and
integration belong inside the development loop, so work can flow from task to
main without a human carrying every branch through a PR queue. You define the
outcome and the checks. Ralph Workflow runs the workflow. You judge the software.

[**Start your first run →**](START_HERE.md)

## Build in parallel. Integrate continuously.

Separate worktrees give agents room to work. Ralph Workflow handles the Git coordination
that makes their work converge.

- **Keep work connected to main.** Automatic integration synchronizes feature
  branches with the configured mainline at startup, after commits, and at phase
  boundaries. Other worktrees can pick up those integrated changes at their
  next synchronization.
- **Resolve conflicts in the workflow.** Ralph Workflow rebases onto the target and
  routes conflicts to coding agents for resolution, with an endpoint merge
  fallback when rebase resolution cannot finish.
- **Land changes automatically.** Ralph Workflow fast-forwards the local target to the
  integrated feature tip and can synchronize it with the configured remote.
  Local integration is enabled by default; the default target is `main`.
- **Recover interrupted integration.** Durable recovery state lets Ralph Workflow
  continue an unfinished Git operation before ordinary development resumes.

This is the foundation for a workflow without pull requests: agent worktrees
converging on the same codebase as development happens. Your repository's
branch protections and required checks still determine what it permits;
Ralph Workflow does not bypass them.

Automatic integration can advance local main and publish to `origin` when
available. The worktree holding main is treated as integration infrastructure:
by default, blocking uncommitted content there can be snapshotted and reset.
Keep active edits in feature worktrees. Read the
[auto-integration guide](ralph-workflow/docs/sphinx/configuration.md#auto-integration)
for synchronization, recovery, snapshot restoration, and settings for local-only
or manual Git operation.

## Give it a task. Let the loop work.

Ralph Workflow builds on the **Ralph loop**, the underlying iterative coding
pattern: **plan → build → verify → fix**. The product adds a strong default
workflow for writing software, with agent review, retries, fallback agents,
checkpoint recovery, and Git integration around that simple core.

Start with a bounded feature, a refactor with tests, or a mechanical migration.
Write what done means in `PROMPT.md`, include the checks you trust, and let
Ralph Workflow carry the task through the workflow. When it returns, inspect the summary
and exercise the changed software yourself.

Adopt the defaults first. As your needs grow, compose larger workflows by
changing the agents, phases, tools, and output contracts in configuration.

## Get started

You need **Python 3.12+**, **Git**, **pipx**, and at least one supported coding
agent CLI installed and authenticated. Ralph Workflow runs locally; the agent
you choose determines model access and usage costs. The executable is named
`ralph`.

Run these commands in your own terminal, inside the project you want to work on:

```bash
pipx install ralph-workflow
ralph --version
cd /path/to/your/project
ralph --init
ralph --list-agents
ralph --diagnose
```

Confirm your agent appears and fix any diagnostic problems before continuing.
Then edit the generated `PROMPT.md`: replace the starter with your task,
acceptance criteria, and verification commands. Remove the
`<!-- ralph:starter-prompt ... -->` marker at the top; Ralph Workflow refuses to run
while it remains. Keep any existing task specification you still need.

For example, in a Python project with pytest, a focused first task might be:

```markdown
# Goal
Reject an empty email address in the signup validator with a clear error.

## Acceptance criteria
- An empty email is rejected before a user record is created.
- Valid signup behavior and public interfaces stay unchanged.
- Tests cover both the rejected input and a valid signup.

## Verification
- Run python -m pytest and fix any failures.
```

Start the run:

```bash
ralph
```

When it finishes, read what changed and which checks ran, then try the result.
The [first-run walkthrough](START_HERE.md) covers each step; the
[getting-started tutorial](ralph-workflow/docs/sphinx/getting-started.md)
helps you choose a task and write its specification.

No pipx? Use `pip install ralph-workflow` in a Python 3.12+ virtual environment.
Working from this checkout? See the
[source installation guide](ralph-workflow/CONTRIBUTING.md#dev-build-vs-stable-build)
for `make install` / `make dev` and the separate `rdev` launcher.

## Bring your coding agent

Ralph Workflow ships nine built-in backends: **Claude Code**, **Claude Code headless**,
**Codex**, **OpenCode**, **Nanocoder**, **AGY (Google Anti Gravity)**, **Pi**,
**Cursor**, and **Kimi Code**.

Authenticate your agent on your machine and Ralph Workflow uses it. Configure agent
chains to choose which agents handle each kind of work and which take over
when an attempt fails. See the
[agent guide](ralph-workflow/docs/sphinx/agents.md) for setup and the
[compatibility reference](ralph-workflow/docs/sphinx/agent-compatibility.md)
for CLI and model details.

## Is Ralph Workflow for you?

Ralph Workflow fits developers and teams who want to run autonomous coding work across
Git worktrees, keep main moving, and spend less time coordinating agents and
merges. It works best with clear tasks and tests or other checks that can
establish whether the software works.

If your task is still open-ended exploration, define its finish line first.
If your repository has no reliable checks, build that foundation before
entrusting it with unattended changes.

## Make it yours

| You want to… | Go here |
|---|---|
| Complete your first run | [Start here](START_HERE.md) |
| Choose agents, configure Git sync, or change `ralph-workflow.toml` | [Configuration](ralph-workflow/docs/sphinx/configuration.md) |
| Customize workflow phases in `pipeline.toml` | [Pipeline configuration](ralph-workflow/docs/sphinx/advanced-pipeline-configuration.md) |
| Configure tools in `mcp.toml` or outputs in `artifacts.toml` | [MCP configuration](ralph-workflow/docs/sphinx/advanced-mcp-configuration.md) · [Artifact configuration](ralph-workflow/docs/sphinx/advanced-artifact-configuration.md) |
| Find an answer or troubleshoot a run | [Docs map](docs/README.md) · [Operator manual](ralph-workflow/docs/sphinx/index.rst) |

## Open source

Ralph Workflow is licensed under **AGPL-3.0-or-later**.

[PyPI](https://pypi.org/project/ralph-workflow/) ·
[Report an issue](https://github.com/Ralph-Workflow/Ralph-Workflow/issues/new) ·
[Contribute](CONTRIBUTING.md)

The Ralph Loop pattern is attributed to
[Geoffrey Huntley](https://ghuntley.com/ralph). Ralph Workflow is an independent
implementation that builds on that core.
