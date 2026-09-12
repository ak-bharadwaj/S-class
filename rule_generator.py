"""
S-Class V12: Cross-Platform Rule Generator & Context Projection Engine
(rule_generator.py)

Compiles the Single Source of Truth (SSOT) from the Codebase Knowledge Graph,
active FSM phase, and task contracts into native platform directives:
- Cursor (.cursor/rules/sclass-governance.mdc)
- Claude Code (CLAUDE.md)
- OpenAI Codex CLI (AGENTS.md)
- Google Antigravity / Gemini (GEMINI.md)
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List
from codebase_graph_db import CodebaseGraphDB

logger = logging.getLogger("sclass_rule_generator")


class PlatformRuleGenerator:
    """
    Projects S-Class epistemic governance and CKG context into native platform configurations.
    """

    def __init__(self, workspace_dir: Optional[str] = None, graph_db: Optional[CodebaseGraphDB] = None):
        self.workspace_dir = workspace_dir or os.getcwd()
        self.graph_db = graph_db or CodebaseGraphDB(workspace_dir=self.workspace_dir)

    def _get_project_context(self) -> Dict[str, Any]:
        """Gathers active FSM state, stats, and active tasks."""
        state_file = os.path.join(self.workspace_dir, ".agents", "orchestration_state.json")
        fsm_phase = "IDLE"
        goal_text = ""
        active_tasks = []

        if os.path.exists(state_file):
            try:
                with open(state_file, "r", encoding="utf-8") as f:
                    sdata = json.load(f)
                fsm_phase = sdata.get("currentPhase", "IDLE")
                goal_text = sdata.get("goal", "")
                active_tasks = [t for t in sdata.get("tasks", []) if t.get("status") != "completed"]
            except Exception:
                pass

        stats = self.graph_db.get_stats()
        adrs = self.graph_db.get_nodes_by_type("ADR")

        return {
            "fsm_phase": fsm_phase,
            "goal": goal_text,
            "active_tasks": active_tasks,
            "stats": stats,
            "adrs": adrs,
        }

    def generate_all_projections(self) -> Dict[str, str]:
        """Generates configuration rules for all 4 major AI agent ecosystems."""
        ctx = self._get_project_context()
        generated = {}

        generated["cursor"] = self.generate_cursor_rule(ctx)
        generated["claude"] = self.generate_claude_rule(ctx)
        generated["codex"] = self.generate_agents_md(ctx)
        generated["gemini"] = self.generate_gemini_md(ctx)

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
