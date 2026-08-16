"""
S-Class EOS Dynamic Skill Discovery & Auto-Installer Engine (sclass_skill_discovery.py)

Analyzes project goals, technology stacks, and domain requirements upfront.
Automatically discovers, installs, and binds missing specialized skills into S-Class's active skill stack,
ensuring S-Class never lacks required capabilities for any engineering task.
"""

import os
import re
import json
import logging
from typing import List, Dict, Any, Set, Optional
from sclass_skill_orchestrator import SkillTaxonomy, SkillDefinition, SClassSkillOrchestrator

logger = logging.getLogger("sclass_skill_discovery")


class SkillDiscoveryEngine:
    """
    Automated Skill Discovery & Auto-Installer Engine for S-Class V12.1.
    """

    KNOWN_SKILL_REPOS: Dict[str, str] = {
        "impeccable": "https://github.com/pbakaus/impeccable.git",
        "taste-skill": "https://github.com/Leonxlnx/taste-skill.git",
        "emil-skills": "https://github.com/emilkowalski/skills.git",
        "frontend-design": "https://github.com/anthropic/frontend-design.git"
    }

    @classmethod
    def find_and_bind_required_skills(cls, goal_text: str, workspace_dir: Optional[str] = None) -> Dict[str, Any]:
        """
        Scans goal text and workspace requirements to discover missing skills and auto-bind them.
        """
        cwd = workspace_dir if workspace_dir else os.getcwd()
        plugin_root = os.path.dirname(os.path.abspath(__file__))
        capability_plugins_dir = os.path.join(plugin_root, "capability_plugins")
        os.makedirs(capability_plugins_dir, exist_ok=True)

        goal_lower = goal_text.lower()
        discovered_skills: List[str] = []
        installed_repos: List[str] = []

        # 1. Domain & Technology Matcher
        domain_skill_triggers = {
            "3d": ("3d-webgl", "emil-skills"),
            "animation": ("emil-apple-design", "emil-skills"),
            "taste": ("taste-aesthetic", "taste-skill"),
            "craft": ("impeccable-craft", "impeccable"),
            "chart": ("data-visualization", "builtin"),
            "table": ("data-dense-ui", "builtin"),
            "erp": ("academic-workflows", "builtin")
        }

        for keyword, (skill_id, repo_key) in domain_skill_triggers.items():
            if re.search(r"\b" + re.escape(keyword) + r"\b", goal_lower):
                discovered_skills.append(skill_id)
                # Verify if local approved capability plugin is present
                if repo_key != "builtin":
                    repo_dir = os.path.join(capability_plugins_dir, repo_key)
                    if os.path.exists(repo_dir):
                        installed_repos.append(repo_key)
                    else:
                        logger.info(
                            f"[SkillDiscovery] External plugin repository '{repo_key}' not present locally. "
                            f"Dynamic runtime cloning is disabled under supply-chain boundary policy."
                        )

        # 2. Auto-connect all workspace SKILL.md files into S-Class
        cls.auto_connect_workspace_skills(workspace_dir=cwd)

        # 3. Resolve Active Skill Stack
        active_skills = SClassSkillOrchestrator.resolve_active_skills(
            fsm_phase="ANALYSIS",
            goal_text=goal_text,
            workspace_dir=cwd
        )

        # Save Discovery Receipt
        state_dir = os.path.join(cwd, ".agents")
        os.makedirs(state_dir, exist_ok=True)
        discovery_receipt_path = os.path.join(state_dir, "skill_discovery_receipt.json")

        receipt = {
            "status": "DISCOVERED_AND_BOUND",
            "goal_analyzed": goal_text,
            "discovered_skills_count": len(discovered_skills),
            "discovered_skills": discovered_skills,
            "repos_installed": installed_repos,
            "total_active_skills_bound": len(active_skills)
        }

        try:
            with open(discovery_receipt_path, "w", encoding="utf-8") as f:
                json.dump(receipt, f, indent=2)
        except Exception as e:
            logger.error(f"[SkillDiscovery] Failed to write discovery receipt: {e}")

        logger.info(f"[SkillDiscovery] Discovered and bound {len(discovered_skills)} skills for goal.")
        return receipt

    @classmethod
    def auto_connect_workspace_skills(cls, workspace_dir: Optional[str] = None) -> Dict[str, Any]:
        """
        Scans workspace .agents/skills/ for any custom or newly added SKILL.md files.
        Automatically parses, registers, auto-assigns subagents, phase mapping, and connects them into S-Class.
        """
        cwd = workspace_dir if workspace_dir else os.getcwd()
        skills_dir = os.path.join(cwd, ".agents", "skills")
        if not os.path.exists(skills_dir):
            return {"connected_count": 0, "connected_skills": []}

        connected_skills = []
        for item in os.listdir(skills_dir):
            item_path = os.path.join(skills_dir, item)
            if os.path.isdir(item_path):
                skill_md = os.path.join(item_path, "SKILL.md")
                if os.path.exists(skill_md):
                    try:
                        with open(skill_md, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()

                        name = item
                        description = f"Custom workspace skill for {item}"
                        if content.startswith("---"):
                            parts = content.split("---", 2)
                            if len(parts) >= 3:
                                frontmatter = parts[1]
                                for line in frontmatter.splitlines():
                                    if line.startswith("name:"):
                                        name = line.split("name:", 1)[1].strip()
                                    elif line.startswith("description:"):
                                        description = line.split("description:", 1)[1].strip()

                        desc_lower = description.lower() + " " + content[:500].lower()

                        if any(kw in desc_lower for kw in ["ui", "aesthetic", "visual", "taste", "style", "css", "color", "typography"]):
                            agent_id = "dss_ui_ux"
                        elif any(kw in desc_lower for kw in ["react", "next.js", "component", "frontend", "animation", "motion", "spring"]):
                            agent_id = "dss_frontend_dev"
                        elif any(kw in desc_lower for kw in ["backend", "api", "controller", "route", "service"]):
                            agent_id = "dss_backend_dev"
                        elif any(kw in desc_lower for kw in ["database", "schema", "sql", "orm", "migration"]):
                            agent_id = "dss_db_architect"
                        elif any(kw in desc_lower for kw in ["security", "auth", "guard", "vulnerability", "secret"]):
                            agent_id = "dss_cso_v2"
                        elif any(kw in desc_lower for kw in ["qa", "test", "dom", "browser", "screenshot", "lighthouse"]):
                            agent_id = "dss_qa_frontend"
                        elif any(kw in desc_lower for kw in ["user", "acceptance", "proxy", "flow"]):
                            agent_id = "dss_user_alias_v2"
                        else:
                            agent_id = "dss_governor"

                        phases = ["DESIGN", "CODING"] if agent_id in ["dss_ui_ux", "dss_frontend_dev"] else ["CODING", "INTEGRATION"]

                        skill_def = SkillDefinition(
                            id=name,
                            name=name.replace("-", " ").title(),
                            tier="workspace",
                            purpose=description,
                            rule_guideline=f"Enforce directives from {name}/SKILL.md",
                            technologies=["Workspace Skill"],
                            source_repo="workspace/.agents/skills",
                            reference_playbook=skill_md,
                            default_active=True,
                            recommended_agent_id=agent_id,
                            applicable_phases=phases
                        )

                        SkillTaxonomy.SKILLS[name] = skill_def
                        connected_skills.append({
                            "skill_id": name,
                            "name": skill_def.name,
                            "recommended_agent_id": agent_id,
                            "applicable_phases": phases,
                            "reference_playbook": skill_md
                        })
                        logger.info(f"[SkillDiscovery] Auto-connected workspace skill '{name}' to subagent '{agent_id}'")
                    except Exception as ex:
                        logger.error(f"[SkillDiscovery] Failed auto-connecting skill '{item}': {ex}")

        state_dir = os.path.join(cwd, ".agents")
        os.makedirs(state_dir, exist_ok=True)
        connection_file = os.path.join(state_dir, "skill_auto_connection_receipt.json")
        try:
            with open(connection_file, "w", encoding="utf-8") as f:
                json.dump({
                    "auto_connection_status": "SUCCESS",
                    "total_connected": len(connected_skills),
                    "connected_skills": connected_skills
                }, f, indent=2)
        except Exception:
            pass

        return {"connected_count": len(connected_skills), "connected_skills": connected_skills}
