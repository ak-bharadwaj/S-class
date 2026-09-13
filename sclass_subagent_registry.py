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

    UI_SKILL_PATTERNS = {
        "frontend", "react", "design", "aesthetic", "taste", "apple", "visual", "dom",
        "responsive", "animation", "motion", "a11y", "theme", "dark-mode", "toast",
        "dialog", "skeleton", "shimmer", "layout", "css", "tailwind", "ui-library",
        "component", "palette", "typeset", "colorize", "delight", "mobile", "android",
        "ios", "webgl", "3d", "scroll", "creative-interaction", "sonner", "ux", "page-route",
        "form-validation", "field-errors", "data-dense-ui", "accessibility"
    }

    UNREQUESTED_ENTERPRISE_NON_UI = {
        "oauth-sso-saml-auth", "tenant-isolation-multi-tenancy", "elasticsearch-vector-search",
        "db-sharding-read-replicas", "prisma-drizzle-orm", "stripe-payment-checkout",
        "seo-metadata-open-graph", "i18n-localization-engine", "background-pdf-excel-exporter",
        "auth-jwt-rbac", "file-upload-storage", "academic-workflows", "approval-workflows"
    }

    @classmethod
    def _is_skill_excluded_for_non_ui(cls, skill_id: str, goal_text: str = "") -> bool:
        """Determines if a skill is irrelevant for non-UI / algorithmic / library / CLI tasks."""
        s_lower = skill_id.lower()
        goal_lower = goal_text.lower()

        # If explicitly requested in prompt text, do not exclude
        if s_lower in goal_lower:
            return False

        skill_obj = SkillTaxonomy.SKILLS.get(skill_id)
        if skill_obj and skill_obj.conditional_keywords and any(kw in goal_lower for kw in skill_obj.conditional_keywords):
            return False

        # 1. Tier filtering
        if skill_obj:
            if getattr(skill_obj, "tier", "") in ("emil", "taste", "presentation", "interaction"):
                return True
            if getattr(skill_obj, "tier", "") == "impeccable" and s_lower not in ("impeccable-harden", "impeccable-audit"):
                return True

        # 2. Token and substring patterns for UI skills
        tokens = set(s_lower.split("-"))
        if bool(tokens & cls.UI_SKILL_PATTERNS):
            return True
        if any(p in s_lower for p in [
            "dark-mode", "toast", "ui-library", "apple-design", "animation",
            "page-route", "data-dense", "form-validation", "accessibility"
        ]):
            return True

        # 3. Heavy unrequested enterprise/ORM/auth stacks for non-UI tasks
        if s_lower in cls.UNREQUESTED_ENTERPRISE_NON_UI:
            return True

        return False

    @classmethod
    def prepare_full_8_subagent_dispatch(
        cls,
        goal_text: str,
        fsm_phase: str,
        workspace_dir: Optional[str] = None,
        task_domain: Optional[str] = None,
        requires_frontend_ui: Optional[bool] = None,
        complexity_tier: Optional[str] = None
    ) -> Dict[str, Any]:
        cwd = workspace_dir if workspace_dir else os.getcwd()

        # 1. Infer task domain, UI requirements, & complexity tier if not provided
        complexity_tier_val = complexity_tier
        if task_domain is None or requires_frontend_ui is None or complexity_tier_val is None:
            try:
                from task_classifier import TaskClassifier
                tc = TaskClassifier.classify(goal_text, workspace_dir=cwd)
                task_domain = task_domain or tc.domain.value
                requires_frontend_ui = requires_frontend_ui if requires_frontend_ui is not None else tc.requires_frontend_ui
                complexity_tier_val = complexity_tier_val or tc.complexity_tier.value
            except Exception:
                task_domain = task_domain or "fullstack"
                requires_frontend_ui = requires_frontend_ui if requires_frontend_ui is not None else True
                complexity_tier_val = complexity_tier_val or "feature"

        is_non_ui = task_domain in ("algorithm", "library", "cli") or requires_frontend_ui is False
        is_low_complexity = complexity_tier_val in ("trivial", "small")

        # 2. Run upfront Skill Discovery
        discovery_res = SkillDiscoveryEngine.find_and_bind_required_skills(goal_text, cwd)

        # 3. Resolve Phase Topology Router Targets
        from topology import TopologyRouter, SwarmTopology
        topo_router = TopologyRouter(SwarmTopology.STAR)
        phase_topology = topo_router.resolve_phase_topology(fsm_phase, {})
        all_agent_ids = list(cls.SUBAGENTS.keys())

        UI_AGENTS = {"dss_ui_ux", "dss_frontend_dev", "dss_qa_frontend", "dss_user_alias_v2"}
        ARCHITECT_SECURITY_AGENTS = {"dss_governor", "dss_cso_v2"}

        dispatched_subagents = []
        for sa_id, sa in cls.SUBAGENTS.items():
            targets = topo_router.get_communication_targets(sa_id, all_agent_ids)

            # Check if Architect (debate) or Security Officer should be placed on standby for low complexity
            if is_low_complexity and sa_id in ARCHITECT_SECURITY_AGENTS:
                status = "STANDBY_LOW_COMPLEXITY"
                combined_skills = []
            # Check if UI specialist subagent should be placed on standby for pure non-UI tasks
            elif is_non_ui and sa_id in UI_AGENTS:
                status = "STANDBY_NON_UI"
                combined_skills = []
            else:
                status = "DISPATCHED_CONCURRENTLY"
                # Source 1: Resolve dynamic skill stack from SClassSkillOrchestrator
                subagent_skills = SClassSkillOrchestrator.resolve_active_skills(fsm_phase, goal_text, cwd)
                skill_ids = [s.id for s in subagent_skills]

                # Source 2: Discovered skills from SkillDiscoveryEngine
                discovered_skills = []
                if isinstance(discovery_res, dict):
                    discovered_skills = discovery_res.get("discovered_skills", discovery_res.get("bound_skill_ids", []))

                # Source 3: Subagent static base skills
                base_skills = list(sa.assigned_skills)

                # Concatenate all 3 skill sources with deduplication preserving order
                raw_skills = list(dict.fromkeys(base_skills + skill_ids + discovered_skills))

                # If task is non-UI, rigorously filter all 3 concatenated skill sources
                if is_non_ui:
                    combined_skills = [
                        sk for sk in raw_skills
                        if not cls._is_skill_excluded_for_non_ui(sk, goal_text=goal_text)
                    ]
                else:
                    combined_skills = raw_skills

            dispatched_subagents.append({
                "subagent_id": sa.id,
                "name": sa.name,
                "role_title": sa.role_title,
                "domain": sa.domain,
                "status": status,
                "assigned_skills": combined_skills,
                "find_skill_enabled": sa.has_find_skill_capability if status == "DISPATCHED_CONCURRENTLY" else False
            })

        # Save Full 8 Dispatch Receipt
        state_dir = os.path.join(cwd, ".agents")
        os.makedirs(state_dir, exist_ok=True)
        dispatch_file = os.path.join(state_dir, "full_8_subagent_dispatch.json")

        active_count = len([s for s in dispatched_subagents if s["status"] == "DISPATCHED_CONCURRENTLY"])
        receipt = {
            "fsm_phase": fsm_phase,
            "goal": goal_text,
            "task_domain": task_domain,
            "complexity_tier": complexity_tier_val,
            "total_subagents_registered": len(dispatched_subagents),
            "total_subagents_dispatched": len(dispatched_subagents),
            "active_subagents_count": active_count,
            "concurrent_execution": True,
            "skill_discovery_active": True,
            "subagents": dispatched_subagents
        }

        try:
            with open(dispatch_file, "w", encoding="utf-8") as f:
                json.dump(receipt, f, indent=2)
        except Exception as e:
            logger.error(f"[SubagentRegistry] Failed to save dispatch receipt: {e}")

        logger.info(f"[SubagentRegistry] Successfully prepared and dispatched subagents (active={active_count}, domain={task_domain}).")
        return receipt
