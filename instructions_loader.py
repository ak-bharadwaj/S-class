"""
S-Class v6 Modular Instructions Loader (instructions_loader.py)

Dynamically loads phase-specific instruction modules instead of dumping
monolithic rule files on every agent turn. Saves 80-90% context tokens on simple tasks.
"""

import os
from typing import Optional, Any
from planner import WorkflowProfile


def get_instructions_dir(custom_dir: Optional[str] = None) -> str:
    if custom_dir and os.path.isdir(custom_dir):
        return custom_dir
    base_dir = os.path.dirname(os.path.abspath(__file__))
    instr_dir = os.path.join(base_dir, "instructions")
    if os.path.isdir(instr_dir):
        return instr_dir
    return base_dir


def _load_instruction_file(filename: str, instructions_dir: str) -> str:
    path = os.path.join(instructions_dir, filename)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    return ""


def get_active_instructions(
    current_phase: str,
    profile: Any,
    instructions_dir: Optional[str] = None
) -> str:
    """
    Load ONLY the instructions relevant to the active phase and workflow profile.
    
    - QUESTION profile: returns empty string (no FSM instructions needed).
    - MICRO / SMALL_FIX profiles: returns concise micro execution guidelines.
    - Standard / Full profiles: returns core directives + active phase guidelines.
    """
    instr_dir = get_instructions_dir(instructions_dir)

    # Normalize profile string/enum
    profile_val = profile.value if isinstance(profile, WorkflowProfile) else str(profile).lower()

    # 1. QUESTION profile requires zero FSM instructions
    if profile_val == "question" or profile == WorkflowProfile.QUESTION:
        return ""

    # 2. MICRO & SMALL_FIX profiles get lightweight direct execution rules
    if profile_val in ("micro", "small_fix") or profile in (WorkflowProfile.MICRO, WorkflowProfile.SMALL_FIX):
        micro_rules = _load_instruction_file("micro.md", instr_dir)
        if micro_rules:
            return micro_rules
        # Fallback to core
        return _load_instruction_file("core.md", instr_dir)

    # 3. Phase-specific mapping for standard/full workflows
    phase_map = {
        "TRIAGE": "triage.md",
        "ANALYSIS": "analysis.md",
        "SPECIFICATION_SYNTHESIS": "spec_synthesis.md",
        "DESIGN": "design.md",
        "DEBATE": "debate.md",
        "CODING": "coding.md",
        "TASK_VERIFICATION": "qa.md",
        "QA": "qa.md",
        "RELEASE": "release.md",
    }

    parts = []
    core = _load_instruction_file("core.md", instr_dir)
    if core:
        parts.append(core)

    mapped_file = phase_map.get(current_phase.upper())
    if mapped_file:
        phase_content = _load_instruction_file(mapped_file, instr_dir)
        if phase_content:
            parts.append(phase_content)

    return "\n\n".join(parts)
