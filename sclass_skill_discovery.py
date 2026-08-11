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
import subprocess
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
                # Verify if external repo is installed
                if repo_key != "builtin":
                    repo_dir = os.path.join(capability_plugins_dir, repo_key)
                    if not os.path.exists(repo_dir):
                        logger.info(f"[SkillDiscovery] Auto-installing missing skill repository: {repo_key}")
                        success = cls._clone_skill_repo(cls.KNOWN_SKILL_REPOS[repo_key], repo_dir)
                        if success:
                            installed_repos.append(repo_key)

        # 2. Resolve Active Skill Stack
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
    def _clone_skill_repo(cls, repo_url: str, target_dir: str) -> bool:
        """Clones a missing skill repository synchronously."""
        try:
            res = subprocess.run(
                ["git", "clone", "--depth", "1", repo_url, target_dir],
                capture_output=True,
                text=True,
                timeout=30
            )
            return res.returncode == 0
        except Exception as e:
            logger.error(f"[SkillDiscovery] Error cloning skill repo {repo_url}: {e}")
            return False
