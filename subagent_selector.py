"""
S-Class v6 Domain-Aware Subagent Selector (subagent_selector.py)

Dynamically selects and composes 6 core roles (architect, builder, qa, security, reviewer, analyst)
rather than blindly spawning 8-24 rigid personas for every task.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
from planner import WorkflowProfile


@dataclass
class SubagentSpec:
    role: str
    name: str
    active_phases: List[str]
    skills: List[str] = field(default_factory=list)
    can_write: bool = False
    can_vote: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "name": self.name,
            "active_phases": self.active_phases,
            "skills": self.skills,
            "can_write": self.can_write,
            "can_vote": self.can_vote,
        }


@dataclass
class SubagentPlan:
    agents: List[SubagentSpec]
    rationale: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_count": len(self.agents),
            "agents": [a.to_dict() for a in self.agents],
            "rationale": self.rationale,
        }


def architect_agent(skills: Optional[List[str]] = None) -> SubagentSpec:
    return SubagentSpec(
        role="architect",
        name="Lead System Architect",
        active_phases=["DESIGN", "DEBATE"],
        skills=skills or ["ux-architecture", "frontend-design"],
        can_write=False,
        can_vote=True
    )


def builder_agent(skills: Optional[List[str]] = None) -> SubagentSpec:
    return SubagentSpec(
        role="builder",
        name="Core Implementation Builder",
        active_phases=["CODING", "INTEGRATION"],
        skills=skills or ["backend-logic", "api-design", "ast-dependency-resolver"],
        can_write=True,
        can_vote=False
    )


def frontend_agent(skills: Optional[List[str]] = None) -> SubagentSpec:
    return SubagentSpec(
        role="frontend",
        name="Frontend UI Specialist",
        active_phases=["CODING", "DESIGN"],
        skills=skills or ["frontend-engineering", "design-system", "emil-apple-design"],
        can_write=True,
        can_vote=False
    )


def db_agent(skills: Optional[List[str]] = None) -> SubagentSpec:
    return SubagentSpec(
        role="database",
        name="Relational Database Architect",
        active_phases=["DESIGN", "CODING"],
        skills=skills or ["schema-design", "zero-infra-db"],
        can_write=True,
        can_vote=False
    )


def qa_agent(skills: Optional[List[str]] = None) -> SubagentSpec:
    return SubagentSpec(
        role="qa",
        name="Quality Assurance Verifier",
        active_phases=["QA", "TASK_VERIFICATION"],
        skills=skills or ["visual-qa", "webapp-testing"],
        can_write=False,
        can_vote=True
    )


def security_agent(skills: Optional[List[str]] = None) -> SubagentSpec:
    return SubagentSpec(
        role="security",
        name="Security & Auth Officer",
        active_phases=["DEBATE", "QA"],
        skills=skills or ["security-shield", "impeccable-harden"],
        can_write=False,
        can_vote=True
    )


def reviewer_agent(skills: Optional[List[str]] = None) -> SubagentSpec:
    return SubagentSpec(
        role="reviewer",
        name="Human Proxy Reviewer",
        active_phases=["QA", "RELEASE"],
        skills=skills or ["responsive-design", "role-based-ux"],
        can_write=False,
        can_vote=True
    )


def analyst_agent(skills: Optional[List[str]] = None) -> SubagentSpec:
    return SubagentSpec(
        role="analyst",
        name="Requirement Analyst",
        active_phases=["TRIAGE", "ANALYSIS", "SPECIFICATION_SYNTHESIS"],
        skills=skills or ["academic-workflows"],
        can_write=False,
        can_vote=False
    )


def select_subagents(
    phase: str,
    profile: Any,
    detected_domains: Optional[List[str]] = None,
    file_types_touched: Optional[List[str]] = None
) -> SubagentPlan:
    """
    Select only the subagents needed for this specific task.
    """
    domains = [d.lower() for d in (detected_domains or [])]
    file_types = [f.lower() for f in (file_types_touched or [])]
    profile_val = profile.value if isinstance(profile, WorkflowProfile) else str(profile).lower()

    # 1. QUESTION, MICRO, SMALL_FIX: 0 subagents — parent executes directly
    if profile_val in ("micro", "small_fix", "question") or profile in (
        WorkflowProfile.MICRO, WorkflowProfile.SMALL_FIX, WorkflowProfile.QUESTION
    ):
        return SubagentPlan(
            agents=[],
            rationale=f"Profile '{profile_val}' requires zero subagents — parent executes directly."
        )

    # 2. HOTFIX: 1 builder + 1 QA
    if profile_val == "hotfix" or profile == WorkflowProfile.HOTFIX:
        return SubagentPlan(
            agents=[builder_agent(), qa_agent()],
            rationale="Emergency hotfix — minimal builder + QA agent set."
        )

    # 3. BUG_FIX: 1 builder + 1 QA (+ security if auth/security related)
    if profile_val == "bug_fix" or profile == WorkflowProfile.BUG_FIX:
        agents = [builder_agent(), qa_agent()]
        if any(d in domains for d in ["security", "auth", "rbac", "permission"]):
            agents.append(security_agent())
        return SubagentPlan(
            agents=agents,
            rationale=f"Bug fix — targeted {len(agents)} agents (builder + QA{' + security' if len(agents) > 2 else ''})."
        )

    # 4. CORE: 1 builder + 1 QA
    if profile_val == "core" or profile == WorkflowProfile.CORE:
        return SubagentPlan(
            agents=[builder_agent(), qa_agent()],
            rationale="Core algorithm/library — minimal builder + QA agent set."
        )

    # 5. FULL / REFACTOR / FAST: Domain-specific composition (3-5 agents)
    agents = [builder_agent()]

    if any(d in domains for d in ["frontend", "ui", "css", "react"]) or any(ext in file_types for ext in [".tsx", ".jsx", ".css", ".html"]):
        agents.append(frontend_agent())

    if any(d in domains for d in ["database", "db", "schema", "migration", "sql"]) or any(ext in file_types for ext in [".sql", ".prisma"]):
        agents.append(db_agent())

    if any(d in domains for d in ["security", "auth", "rbac", "permission"]):
        agents.append(security_agent())

    # QA is always included for thorough verification in FULL
    agents.append(qa_agent())

    # Enforce Lead Writer constraint: only one agent can have can_write=True
    writer_found = False
    for agent in agents:
        if agent.can_write:
            if not writer_found:
                writer_found = True
                agent.name += " (Lead Writer)"
            else:
                agent.can_write = False
                agent.name += " (Reviewer)"

    return SubagentPlan(
        agents=agents,
        rationale=f"Selected {len(agents)} domain-aware subagents for domains: {domains}."
    )
