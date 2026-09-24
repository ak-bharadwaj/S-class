"""
S-Class Evolution: Component Vocabulary & Trust Kernel Immutability.
Implements Directive Section 18 & 36:
- Component taxonomy:
    RRSI Core: prompt, control_flow, config, output_plumbing, context_mgmt, client_tool, skill, memory, subagent.
    S-Class Extensions: runtime_adapter, verification, recovery, authorization, observation, evidence, policy, orchestration.
- Critical Security Boundary (Section 36):
    NON_EVOLVABLE_COMPONENTS:
      authorization, evidence, canonical_truth, ledger_integrity.
    The optimizer MUST NOT be allowed to evolve the rules that decide
    whether its own output is trusted.
"""

from __future__ import annotations
from enum import Enum
from typing import Set, Dict, Any


class ComponentCategory(str, Enum):
    # RRSI core structural components
    PROMPT = "prompt"
    CONTROL_FLOW = "control_flow"
    CONFIG = "config"
    OUTPUT_PLUMBING = "output_plumbing"
    CONTEXT_MGMT = "context_mgmt"
    CLIENT_TOOL = "client_tool"
    SKILL = "skill"
    MEMORY = "memory"
    SUBAGENT = "subagent"

    # S-Class specific extensions
    RUNTIME_ADAPTER = "runtime_adapter"
    VERIFICATION = "verification"
    RECOVERY = "recovery"
    AUTHORIZATION = "authorization"
    OBSERVATION = "observation"
    EVIDENCE = "evidence"
    POLICY = "policy"
    ORCHESTRATION = "orchestration"


# Strictly forbidden from RRSI autonomous evolution (Directive Section 18 & 36)
NON_EVOLVABLE_COMPONENTS: Set[str] = {
    ComponentCategory.AUTHORIZATION.value,
    ComponentCategory.EVIDENCE.value,
    "canonical_truth",
    "ledger_integrity",
}

# Permitted evolvable components
EVOLVABLE_COMPONENTS: Set[str] = {
    c.value for c in ComponentCategory if c.value not in NON_EVOLVABLE_COMPONENTS
}


def is_component_evolvable(component_name: str) -> bool:
    """Verifies whether a named component is permitted to be evolved by RRSI."""
    norm = (component_name or "").strip().lower()
    if norm in NON_EVOLVABLE_COMPONENTS:
        return False
    return norm in EVOLVABLE_COMPONENTS
