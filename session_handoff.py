"""
S-Class V12: Session Continuity & Handoff Engine (session_handoff.py)

Generates authoritative session handoff manifests (.agents/session_handoff.json)
conforming to schema.session-handoff.v1 and repository root entrypoint CONTINUE_HERE.md.
Eliminates context amnesia across heterogeneous AI agents and human developer handoffs.
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List
from codebase_graph_db import CodebaseGraphDB
from staleness_cascade import StalenessCascadeEngine

logger = logging.getLogger("sclass_session_handoff")


class SessionHandoffEngine:
    """
    Serializes project operational state and produces CONTINUE_HERE.md guides.
    """

    SCHEMA_VERSION = "schema.session-handoff.v1"
    DEFAULT_HANDOFF_FILE = os.path.join(".agents", "session_handoff.json")

    def __init__(
        self,
        workspace_dir: Optional[str] = None,
        graph_db: Optional[CodebaseGraphDB] = None,
    ):
        self.workspace_dir = workspace_dir or os.getcwd()
        self.graph_db = graph_db or CodebaseGraphDB(workspace_dir=self.workspace_dir)
        self.cascade = StalenessCascadeEngine(self.workspace_dir, self.graph_db)

    def create_handoff_manifest(self) -> Dict[str, Any]:
        """Collects state and writes .agents/session_handoff.json."""
        state_file = os.path.join(self.workspace_dir, ".agents", "orchestration_state.json")
        fsm_phase = "IDLE"
        goal_text = ""
        active_task = None
        pending_tasks = []

        if os.path.exists(state_file):
            try:
                with open(state_file, "r", encoding="utf-8") as f:
                    sdata = json.load(f)
                fsm_phase = sdata.get("currentPhase", "IDLE")
                goal_text = sdata.get("goal", "")
                tasks = sdata.get("tasks", [])
                for t in tasks:
                    if t.get("status") in ["in_progress", "active"]:
                        active_task = t
                    elif t.get("status") not in ["completed", "verified", "done"]:
                        pending_tasks.append(t)
                if not active_task and pending_tasks:
                    active_task = pending_tasks[0]
            except Exception:
                pass

        # Check stale claims
        claims_data = self.cascade.load_claims()
        stale_claims = [c for c in claims_data.get("claims", {}).values() if c.get("status") == "STALE"]

        # Check ADRs
        adrs = self.graph_db.get_nodes_by_type("ADR")

        # Determine next command
        if stale_claims:
            next_cmd = "python -m pytest tests/"
        elif fsm_phase in ["CODING", "TASK_VERIFICATION"]:
            next_cmd = "python -m pytest tests/ -k test_"
        elif fsm_phase == "DONE":
            next_cmd = "echo Project execution fully completed."
        else:
            next_cmd = "python -m runtime advance"

        manifest = {
            "schema_version": self.SCHEMA_VERSION,
            "fsm_phase": fsm_phase,
            "goal": goal_text,
            "active_task": active_task or {},
            "pending_tasks_count": len(pending_tasks),
            "pending_tasks": pending_tasks[:5],
            "stale_claims_count": len(stale_claims),
            "stale_claims": stale_claims,
            "adrs_count": len(adrs),
            "recent_adrs": adrs[:5],
            "next_resumption_command": next_cmd,
            "handoff_timestamp": CodebaseGraphDB.now_iso(),
        }

        handoff_path = os.path.join(self.workspace_dir, self.DEFAULT_HANDOFF_FILE)
        os.makedirs(os.path.dirname(handoff_path), exist_ok=True)
        with open(handoff_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        # Generate CONTINUE_HERE.md
        self.generate_continue_here_md(manifest)

        return manifest

    def generate_continue_here_md(self, manifest: Dict[str, Any]) -> str:
        """Writes human/agent readable CONTINUE_HERE.md at workspace root."""
        out_path = os.path.join(self.workspace_dir, "CONTINUE_HERE.md")

        active_task = manifest.get("active_task", {})
        if active_task and "id" in active_task:
            task_desc = f"{active_task['id']}: {active_task.get('acceptanceCriteria', '')}".strip(": ")
        else:
            task_desc = "None (Advance phase)"
        stale_block = ""
        if manifest.get("stale_claims_count", 0) > 0:
            stale_items = "\n".join([f"- ⚠️ Claim `{c['claim_id']}`: {c['description']} (Marked STALE)" for c in manifest["stale_claims"][:5]])
            stale_block = f"""
## ⚠️ Stale Verification Obligations
{stale_items}
> Run `{manifest['next_resumption_command']}` to re-verify before proceeding.
"""

        adr_block = ""
        if manifest.get("adrs_count", 0) > 0:
            adr_items = "\n".join([f"- **{a['name']}** (`{a['id']}`): {a.get('docstring', '')[:100]}..." for a in manifest["recent_adrs"][:3]])
            adr_block = f"""
## 🏛️ Active Architecture Decision Records (ADRs)
{adr_items}
"""

        content = f"""# 🚀 CONTINUE_HERE.md — S-Class Session Continuity Guide

> **Notice**: This repository is governed by the S-Class V12 Epistemic Control Plane.
> All incoming agents (Cursor, Claude Code, Codex CLI, Antigravity) must resume from this state.

---

## 📍 Current System Status
- **FSM Phase**: `{manifest['fsm_phase']}`
- **Active Goal**: {manifest['goal'] or 'In Progress'}
- **Active Task**: `{task_desc}`
- **Pending Tasks Remaining**: {manifest['pending_tasks_count']}
- **Handoff Timestamp**: `{manifest['handoff_timestamp']}`

## ⚡ Next Resumption Command
```bash
{manifest['next_resumption_command']}
```
{stale_block}
{adr_block}
## 🛠️ Operating Rules for the Incoming Agent
1. **Never Assume**: Check `.agents/codebase_graph.db` using MCP `graph_query` before inventing symbols.
2. **Test Before Complete**: Verify implementation against real test fixtures.
3. **Promise Handshake**: Terminate completion with `<promise>TASK_ID:DONE</promise>`.
"""
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(content)

        return out_path
