"""
S-Class V12: Live Operator Steering Engine (steering.py)

Ralph Loop pattern: Monitors .agents/STEERING.md for mid-flight human developer directives,
enabling real-time course correction without interrupting active daemon loops.
"""

import os
import re
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("sclass_steering")


class SteeringEngine:
    """
    Monitors and parses live human steering directives from STEERING.md.
    """

    STEERING_FILE_REL = os.path.join(".agents", "STEERING.md")

    @classmethod
    def get_steering_path(cls, workspace_dir: Optional[str] = None) -> str:
        cwd = workspace_dir or os.getcwd()
        # Check .agents/STEERING.md first, then root STEERING.md
        primary = os.path.join(cwd, cls.STEERING_FILE_REL)
        secondary = os.path.join(cwd, "STEERING.md")
        return primary if os.path.exists(primary) or not os.path.exists(secondary) else secondary

    @classmethod
    def read_steering_directive(cls, workspace_dir: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Reads and parses active operator steering instructions."""
        filepath = cls.get_steering_path(workspace_dir)
        if not os.path.exists(filepath):
            return None

        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read().strip()
        except Exception:
            return None

        if not content:
            return None

        # Parse commands from steering text:
        # e.g., COMMAND: PAUSE, COMMAND: ABORT, COMMAND: OVERRIDE_PHASE: DESIGN
        cmd_match = re.search(r"COMMAND:\s*([A-Z_]+(?::[A-Za-z0-9_]+)?)", content)
        command = cmd_match.group(1).strip() if cmd_match else None

        # Check priority
        prio_match = re.search(r"PRIORITY:\s*([A-Z]+)", content)
        priority = prio_match.group(1).strip() if prio_match else "NORMAL"

        return {
            "active": True,
            "filepath": filepath,
            "raw_content": content,
            "command": command,
            "priority": priority,
            "instruction": re.sub(r"(COMMAND|PRIORITY):[^\n]*\n?", "", content).strip(),
        }

    @classmethod
    def write_steering_directive(
        cls,
        instruction: str,
        workspace_dir: Optional[str] = None,
        command: Optional[str] = None,
        priority: str = "HIGH",
    ) -> str:
        """Writes a new human steering directive."""
        cwd = workspace_dir or os.getcwd()
        filepath = os.path.join(cwd, cls.STEERING_FILE_REL)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        lines = [f"# Human Operator Steering Directive (Priority: {priority})", ""]
        if command:
            lines.append(f"COMMAND: {command.upper()}")
        lines.append(f"PRIORITY: {priority.upper()}")
        lines.append("")
        lines.append(instruction.strip())

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

        return filepath

    @classmethod
    def clear_steering_directive(cls, workspace_dir: Optional[str] = None) -> bool:
        """Clears the steering file once consumed."""
        filepath = cls.get_steering_path(workspace_dir)
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
                return True
            except Exception:
                return False
        return True
