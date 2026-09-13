"""
S-Class V13: Cross-Platform Context Projection & Handoff Engine (rule_generator.py)

Dynamically generates ecosystem-specific configuration directives for all 6 supported platforms:
- Cursor (.cursor/rules/sclass-governance.mdc)
- Claude Code (CLAUDE.md)
- OpenAI Codex CLI (AGENTS.md)
- Google Antigravity / Gemini (GEMINI.md)
- GitHub Copilot (.github/copilot-instructions.md)
- Windsurf (.windsurfrules)

Integrates with adapters.detect_platforms to allow selective projection or full projection.
Supports --no-rules flag for hook-only governance.
"""

from __future__ import annotations
import os
import json
import sqlite3
from typing import Dict, Any, Optional, List


class PlatformRuleGenerator:
    """Projects central S-Class cognitive state into native IDE rule files."""

    def __init__(self, workspace_dir: Optional[str] = None, graph_db: Optional[Any] = None):
        self.workspace_dir = os.path.abspath(workspace_dir or os.getcwd())
        self.graph_db = graph_db
        self.state_dir = os.path.join(self.workspace_dir, ".agents")
        self.state_file = os.path.join(self.state_dir, "orchestration_state.json")
        self.db_file = os.path.join(self.state_dir, "codebase_graph.db")

    def _get_project_context(self) -> Dict[str, Any]:
        """Gathers latest FSM phase, active goals, graph stats, and pending tasks."""
        fsm_phase = "UNKNOWN"
        goal_text = ""
        active_tasks = []

        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    fsm_phase = data.get("currentPhase", "UNKNOWN")
                    goal_text = data.get("goal", "")
                    active_tasks = [t for t in data.get("tasks", []) if t.get("status") != "completed"]
            except Exception:
                pass

        stats = {"total_nodes": 0, "total_edges": 0, "nodes_by_type": {}}
        if self.graph_db is not None and hasattr(self.graph_db, "get_stats"):
            try:
                stats = self.graph_db.get_stats()
            except Exception:
                pass
        elif os.path.exists(self.db_file):
            try:
                conn = sqlite3.connect(self.db_file)
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM codebase_nodes")
                stats["total_nodes"] = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM codebase_edges")
                stats["total_edges"] = cur.fetchone()[0]
                cur.execute("SELECT node_type, COUNT(*) FROM codebase_nodes GROUP BY node_type")
                stats["nodes_by_type"] = dict(cur.fetchall())
                conn.close()
            except Exception:
                pass

        # Load ADR records if present
        adrs = []
        if self.graph_db is not None and hasattr(self.graph_db, "get_nodes_by_type"):
            try:
                adrs = self.graph_db.get_nodes_by_type("ADR")
            except Exception:
                pass
        else:
            adr_file = os.path.join(self.state_dir, "adr_records.json")
            if os.path.exists(adr_file):
                try:
                    with open(adr_file, "r", encoding="utf-8") as f:
                        adrs = json.load(f)
                except Exception:
                    pass

        return {
            "fsm_phase": fsm_phase,
            "goal": goal_text,
            "active_tasks": active_tasks,
            "stats": stats,
            "adrs": adrs,
        }

    def generate_all_projections(self, platforms: Optional[List[str]] = None, no_rules: bool = False) -> Dict[str, str]:
        """
        Generates configuration rules.
        When platforms is None:
          Defaults to generating the core 4 ecosystems (cursor, claude, codex, gemini)
          plus any extra detected platforms (copilot, windsurf).
        If platforms is explicitly passed:
          Only generates projections for requested platforms.
        If no_rules=True:
          Skips generating rules entirely.
        """
        if no_rules:
            return {"status": "skipped", "reason": "--no-rules flag active"}

        ctx = self._get_project_context()
        generated = {}

        if platforms is None:
            # Default to all 4 core platforms for 100% backward compatibility
            target_platforms = ["cursor", "claude", "codex", "gemini"]
            try:
                from adapters import detect_platforms
                detected = detect_platforms(self.workspace_dir)
                if "copilot" in detected:
                    target_platforms.append("copilot")
                if "windsurf" in detected:
                    target_platforms.append("windsurf")
            except Exception:
                pass
        else:
            target_platforms = platforms

        norm_targets = [p.lower() for p in target_platforms]

        if any("cursor" in p for p in norm_targets):
            generated["cursor"] = self.generate_cursor_rule(ctx)
        if any("claude" in p for p in norm_targets):
            generated["claude"] = self.generate_claude_rule(ctx)
        if any("codex" in p for p in norm_targets):
            generated["codex"] = self.generate_agents_md(ctx)
        if any(p in ("antigravity", "gemini") for p in norm_targets):
            generated["gemini"] = self.generate_gemini_md(ctx)
        if any("copilot" in p for p in norm_targets):
            generated["copilot"] = self.generate_copilot_instructions(ctx)
        if any("windsurf" in p for p in norm_targets):
            generated["windsurf"] = self.generate_windsurfrules(ctx)

        return generated

    def generate_cursor_rule(self, ctx: Optional[Dict[str, Any]] = None) -> str:
        ctx = ctx or self._get_project_context()
        cursor_dir = os.path.join(self.workspace_dir, ".cursor", "rules")
        os.makedirs(cursor_dir, exist_ok=True)
        rule_path = os.path.join(cursor_dir, "sclass-governance.mdc")

        content = f"""---
description: "S-Class Authoritative Microkernel & Codebase Governance"
globs: "*"
alwaysApply: true
---

# S-Class V12 Epistemic Governance (Cursor Target)

## Active Session Context
- **FSM Phase**: `{ctx['fsm_phase']}`
- **Active Goal**: {ctx['goal'] or 'Under Development'}
- **Pending Tasks**: {len(ctx['active_tasks'])} active
- **Knowledge Graph**: {ctx['stats']['total_nodes']} nodes, {ctx['stats']['total_edges']} edges

## Non-Negotiable Engineering Directives
1. **Zero Hallucinated APIs**: Always verify existing symbols in `.agents/codebase_graph.db` or via MCP `graph_query` before inventing method names or endpoints.
2. **Blast Radius Discipline**: Running changes must consider downstream callers. Do not alter public signatures without an accepted ADR.
3. **Strict Verification**: Never claim a task is completed without running targeted unit tests (`pytest` or `npm test`).
4. **Completion Handshake**: Terminate completed task chunks with `<promise>TASK-ID:DONE</promise>`.
"""
        with open(rule_path, "w", encoding="utf-8") as f:
            f.write(content)
        return rule_path

    def generate_claude_rule(self, ctx: Optional[Dict[str, Any]] = None) -> str:
        ctx = ctx or self._get_project_context()
        claude_path = os.path.join(self.workspace_dir, "CLAUDE.md")

        content = f"""# CLAUDE.md - S-Class V12 Control Plane Directives

## Active Operational State
- **Current FSM Phase**: `{ctx['fsm_phase']}`
- **Active Goal**: {ctx['goal'] or 'Standard Maintenance'}
- **Knowledge Graph Scale**: {ctx['stats']['total_nodes']} symbols indexed across {ctx['stats']['nodes_by_type'].get('FILE', 0)} files.

## Primary Verification Commands
- **Run Pytest Regression**: `python -m pytest tests/`
- **Knowledge Graph Query**: Use MCP tool `graph_query` or `impact_analysis`
- **FSM State Advance**: `python -m runtime advance`

## Negative Invariants (NEVER DO THIS)
- NEVER suppress exceptions with bare `except: pass`.
- NEVER bypass visual verification gates with mock or zero-variance images.
- NEVER invent dependencies not registered in public package registries.
"""
        with open(claude_path, "w", encoding="utf-8") as f:
            f.write(content)

        # Rule Parity: Also generate .claude/rules/sclass-governance.md
        claude_rules_dir = os.path.join(self.workspace_dir, ".claude", "rules")
        os.makedirs(claude_rules_dir, exist_ok=True)
        claude_rule_path = os.path.join(claude_rules_dir, "sclass-governance.md")
        claude_rule_content = f"""# S-Class Epistemic Governance (Claude Code Target)

## Active Session Context
- **FSM Phase**: `{ctx['fsm_phase']}`
- **Active Goal**: {ctx['goal'] or 'Under Development'}
- **Pending Tasks**: {len(ctx['active_tasks'])} active
- **Knowledge Graph**: {ctx['stats']['total_nodes']} nodes, {ctx['stats']['total_edges']} edges

## Non-Negotiable Engineering Directives
1. **Zero Hallucinated APIs**: Always verify existing symbols in `.agents/codebase_graph.db` or via MCP `graph_query` before inventing method names or endpoints.
2. **Blast Radius Discipline**: Running changes must consider downstream callers. Do not alter public signatures without an accepted ADR.
3. **Strict Verification**: Never claim a task is completed without running targeted unit tests (`pytest` or `npm test`).
4. **Completion Handshake**: Terminate completed task chunks with `<promise>TASK-ID:DONE</promise>`.
"""
        with open(claude_rule_path, "w", encoding="utf-8") as f:
            f.write(claude_rule_content)

        return claude_path

    def generate_agents_md(self, ctx: Optional[Dict[str, Any]] = None) -> str:
        ctx = ctx or self._get_project_context()
        agents_path = os.path.join(self.workspace_dir, "AGENTS.md")

        content = f"""# AGENTS.md - OpenAI Codex CLI & Subagent Operational Contract

## Execution Environment & Sandboxing Limits
- **Workspace Root**: `{self.workspace_dir}`
- **FSM Phase**: `{ctx['fsm_phase']}`
- **State Database**: `.agents/codebase_graph.db` (SQLite WAL mode)

## Behavioral Constraints
1. **Atomic Conventional Commits**: All modifications must use format `feat(scope): ...` or `fix(scope): ...`.
2. **Subagent Scoping**: Limit edits strictly to files mapped to your assigned task targets.
3. **ADR Alignment**: Respect all active Architecture Decision Records ({len(ctx['adrs'])} recorded).
"""
        with open(agents_path, "w", encoding="utf-8") as f:
            f.write(content)
        return agents_path

    def generate_gemini_md(self, ctx: Optional[Dict[str, Any]] = None) -> str:
        ctx = ctx or self._get_project_context()
        gemini_path = os.path.join(self.workspace_dir, "GEMINI.md")

        content = f"""# GEMINI.md - Google Antigravity & Reactive Agent Protocols

## System Context
- **FSM Phase**: `{ctx['fsm_phase']}`
- **Goal**: {ctx['goal'] or 'Active Development'}
- **Graph Nodes**: {ctx['stats']['total_nodes']}

## Coordination Protocol
- **Reactive Wakeups**: Background tasks notify automatically upon exit. Do not poll in busy loops.
- **Brain Artifacts**: All task plans and architectural decisions must be stored in `.agents/` or designated brain directories.
- **Quality Fortress**: Maintain 100% green tests across all verification tiers ($V_0 \to V_4$).
"""
        with open(gemini_path, "w", encoding="utf-8") as f:
            f.write(content)
        return gemini_path

    def generate_copilot_instructions(self, ctx: Optional[Dict[str, Any]] = None) -> str:
        ctx = ctx or self._get_project_context()
        github_dir = os.path.join(self.workspace_dir, ".github")
        os.makedirs(github_dir, exist_ok=True)
        copilot_path = os.path.join(github_dir, "copilot-instructions.md")

        content = f"""# GitHub Copilot Custom Instructions

## System Status
- **Governed by S-Class Microkernel**: Phase `{ctx['fsm_phase']}`
- **Active Goal**: {ctx['goal'] or 'Active Development'}

## Guidelines
- Do not add hardcoded API keys or credentials.
- Ensure all created functions include docstrings and comprehensive type hints.
- Keep dependencies strictly limited to packages declared in requirements.txt.
"""
        with open(copilot_path, "w", encoding="utf-8") as f:
            f.write(content)
        return copilot_path

    def generate_windsurfrules(self, ctx: Optional[Dict[str, Any]] = None) -> str:
        ctx = ctx or self._get_project_context()
        rules_path = os.path.join(self.workspace_dir, ".windsurfrules")

        content = f"""# S-Class Governance: Windsurf Rules

## Workspace Context
- **FSM Phase**: `{ctx['fsm_phase']}`
- **Active Goals**: {ctx['goal'] or 'System Integrity'}

## Rules
- Verify all code changes against local test suites before completing tasks.
- Avoid introducing circular imports or high-blast-radius API breaks.
- Respect all registered ADR architecture contracts.
"""
        with open(rules_path, "w", encoding="utf-8") as f:
            f.write(content)
        return rules_path
