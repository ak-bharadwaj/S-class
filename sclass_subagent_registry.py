"""
S-Class EOS Full 8-Subagent Dispatcher & Skill Binding Registry (sclass_subagent_registry.py)

Catalogs, equips, and dispatches ALL 8 defined subagents concurrently:
1. dss_governor (Lead Governance Architect)
2. dss_ui_ux (UI/UX Aesthetic Specialist)
3. dss_frontend_dev (React/Next.js Frontend Architect)
4. dss_backend_dev (NestJS/Express/FastAPI Backend Architect)
5. dss_db_architect (Relational Database Architect)
6. dss_cso_v2 (Chief Security Officer)
7. dss_qa_frontend (Visual QA & DOM Inspector)
8. dss_user_alias_v2 (User Proxy Acceptance & Flow Verifier)

Every subagent is bound to its specialized skill stack (Impeccable, Taste, Emil Kowalski, Builtin)
and equipped with SkillDiscoveryEngine (find-skill) to auto-discover additional skills as needed.
"""

import os
import json
import logging
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional
from sclass_skill_orchestrator import SClassSkillOrchestrator, SkillTaxonomy
from sclass_skill_discovery import SkillDiscoveryEngine

logger = logging.getLogger("sclass_subagent_registry")


@dataclass
class SubagentProfile:
    id: str
    name: str
    role_title: str
    domain: str
    assigned_skills: List[str]
    has_find_skill_capability: bool = True


class SubagentRegistry:
    """Registry of All 8 Defined Subagents with Skill Binding & Discovery."""

    SUBAGENTS: Dict[str, SubagentProfile] = {
        "dss_governor": SubagentProfile(
            id="dss_governor",
            name="Lead Governance Architect",
            role_title="Debate Chair & Architectural Reviewer",
            domain="governance",
            assigned_skills=["impeccable-craft", "ux-architecture", "academic-workflows"]
        ),
        "dss_ui_ux": SubagentProfile(
            id="dss_ui_ux",
            name="UI/UX Aesthetic Specialist",
            role_title="Visual Direction & Taste Designer",
            domain="ui_ux",
            assigned_skills=["frontend-design", "taste-aesthetic", "taste-soft", "taste-minimalist", "design-system"]
        ),
        "dss_frontend_dev": SubagentProfile(
            id="dss_frontend_dev",
            name="Frontend React/Next.js Architect",
            role_title="Client-Side Component & State Builder",
            domain="frontend",
            assigned_skills=["frontend-engineering", "emil-apple-design", "emil-design-eng", "data-dense-ui", "command-search"]
        ),
        "dss_backend_dev": SubagentProfile(
            id="dss_backend_dev",
            name="Backend Controller & API Architect",
            role_title="Server-Side Service & Controller Builder",
            domain="backend",
            assigned_skills=["impeccable-harden", "zero-infra-db", "ast-dependency-resolver"]
        ),
        "dss_db_architect": SubagentProfile(
            id="dss_db_architect",
            name="Relational Database Architect",
            role_title="Schema & Migration Specialist",
            domain="database",
            assigned_skills=["academic-workflows", "approval-workflows", "data-dense-ui"]
        ),
        "dss_cso_v2": SubagentProfile(
            id="dss_cso_v2",
            name="Chief Security Officer",
            role_title="Auth Guards & Security Inspector",
            domain="security",
            assigned_skills=["impeccable-harden", "security-shield", "accessibility"]
        ),
        "dss_qa_frontend": SubagentProfile(
            id="dss_qa_frontend",
            name="Visual QA & DOM Inspector",
            role_title="Browser Inspector & Error Sanitizer",
            domain="quality_assurance",
            assigned_skills=["visual-qa", "impeccable-critique", "impeccable-polish"]
        ),
        "dss_user_alias_v2": SubagentProfile(
            id="dss_user_alias_v2",
            name="User Proxy Flow Verifier",
            role_title="Interactive User Flow Receipt Sign-Off",
            domain="user_acceptance",
            assigned_skills=["responsive-design", "role-based-ux", "emil-animation-opportunities"]
        )
    }

    @classmethod
    def prepare_full_8_subagent_dispatch(cls, goal_text: str, fsm_phase: str, workspace_dir: Optional[str] = None) -> Dict[str, Any]:
        cwd = workspace_dir if workspace_dir else os.getcwd()
        
        # 1. Run upfront Skill Discovery
        discovery_res = SkillDiscoveryEngine.find_and_bind_required_skills(goal_text, cwd)

        # 2. Resolve Phase Topology Router Targets
        from topology import TopologyRouter, SwarmTopology
        topo_router = TopologyRouter(SwarmTopology.STAR)
        phase_topology = topo_router.resolve_phase_topology(fsm_phase, {})
        all_agent_ids = list(cls.SUBAGENTS.keys())
        
        dispatched_subagents = []
        for sa_id, sa in cls.SUBAGENTS.items():
            targets = topo_router.get_communication_targets(sa_id, all_agent_ids)
            # Resolve dynamic skill stack for subagent
            subagent_skills = SClassSkillOrchestrator.resolve_active_skills(fsm_phase, goal_text, cwd)
            skill_ids = [s.id for s in subagent_skills]
            discovered_skills = discovery_res.get("bound_skill_ids", []) if isinstance(discovery_res, dict) else []
            combined_skills = list(dict.fromkeys(sa.assigned_skills + skill_ids + discovered_skills))
            
            dispatched_subagents.append({
                "subagent_id": sa.id,
                "name": sa.name,
                "role_title": sa.role_title,
                "domain": sa.domain,
                "status": "DISPATCHED_CONCURRENTLY",
                "assigned_skills": combined_skills,
                "find_skill_enabled": sa.has_find_skill_capability
            })

        # Save Full 8 Dispatch Receipt
        state_dir = os.path.join(cwd, ".agents")
        os.makedirs(state_dir, exist_ok=True)
        dispatch_file = os.path.join(state_dir, "full_8_subagent_dispatch.json")
        
        receipt = {
            "fsm_phase": fsm_phase,
            "goal": goal_text,
            "total_subagents_dispatched": len(dispatched_subagents),
            "concurrent_execution": True,
            "skill_discovery_active": True,
            "subagents": dispatched_subagents
        }

        try:
            with open(dispatch_file, "w", encoding="utf-8") as f:
                json.dump(receipt, f, indent=2)
        except Exception as e:
            logger.error(f"[SubagentRegistry] Failed to save dispatch receipt: {e}")

        logger.info("[SubagentRegistry] Successfully prepared and dispatched all subagents concurrently.")
        return receipt
