"""
S-Class V12: Dynamic Skill Auto-Loader & Platform Projection Engine
(skill_auto_loader.py)

Ingests Matt Pocock-format SKILL.md playbooks from `.agents/skills/` and dynamically
detects, ranks, and projects them into native host IDE rules:
- Cursor (.cursor/rules/*.mdc)
- Claude Code (.claude/rules/*.md)
- OpenAI Codex CLI (AGENTS.md)
- Google Antigravity / Gemini (GEMINI.md)
Gated by strict token budgets (<1,500 - 2,500 tokens total).
"""

import os
import re
import fnmatch
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Set, Tuple

logger = logging.getLogger("sclass_skill_auto_loader")


@dataclass
class SkillDefinition:
    name: str
    description: str
    triggers: Dict[str, Any]
    token_budget: int
    dependencies: List[str]
    content: str
    file_path: str
    score: float = 0.0


class SkillAutoLoader:
    """
    Dynamic context-aware Skill Auto-Loader.
    Matches workspace state, active FSM phase, and touched files against SKILL.md playbooks,
    resolves dependency DAGs, and projects formatted rules to host agent environments.
    """

    def __init__(self, workspace_dir: Optional[str] = None, skills_dir: Optional[str] = None):
        self.workspace_dir = workspace_dir or os.getcwd()
        if skills_dir:
            self.skills_dir = skills_dir
        else:
            self.skills_dir = os.path.join(self.workspace_dir, ".agents", "skills")

        self.skills: Dict[str, SkillDefinition] = {}
        self.load_available_skills()

    @staticmethod
    def parse_skill_markdown(file_path: str) -> Optional[SkillDefinition]:
        """Parses a SKILL.md file with YAML frontmatter into a SkillDefinition."""
        if not os.path.exists(file_path):
            return None

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
        except Exception as e:
            logger.warning(f"Failed to read {file_path}: {e}")
            return None

        frontmatter_match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.DOTALL)
        if not frontmatter_match:
            return None

        fm_text, content = frontmatter_match.groups()

        # Parse lightweight YAML frontmatter without external YAML dependencies
        name = ""
        description = ""
        token_budget = 1200
        dependencies: List[str] = []
        triggers: Dict[str, Any] = {"file_patterns": [], "fsm_phases": [], "intent_keywords": []}

        active_list_key = None
        for line in fm_text.splitlines():
            line_str = line.strip()
            if not line_str or line_str.startswith("#"):
                continue

            if line_str.startswith("- ") and active_list_key:
                val = line_str[2:].strip().strip('"\'')
                if active_list_key == "dependencies":
                    dependencies.append(val)
                elif active_list_key in triggers:
                    triggers[active_list_key].append(val)
                continue

            if line_str.startswith("name:"):
                active_list_key = None
                name = line_str.split("name:", 1)[1].strip().strip('"\'')
            elif line_str.startswith("description:"):
                active_list_key = None
                description = line_str.split("description:", 1)[1].strip().strip('"\'')
            elif line_str.startswith("token_budget:"):
                active_list_key = None
                try:
                    token_budget = int(line_str.split("token_budget:", 1)[1].strip())
                except ValueError:
                    token_budget = 1200
            elif line_str.startswith("dependencies:"):
                active_list_key = "dependencies"
                raw_dep = line_str.split("dependencies:", 1)[1].strip()
                if raw_dep:
                    dep_items = re.findall(r'["\']([^"\']+)["\']', raw_dep)
                    dependencies.extend(dep_items)
            elif "file_patterns:" in line_str:
                active_list_key = "file_patterns"
                raw_pats = line_str.split("file_patterns:", 1)[1].strip()
                if raw_pats:
                    triggers["file_patterns"].extend(re.findall(r'["\']([^"\']+)["\']', raw_pats))
            elif "fsm_phases:" in line_str:
                active_list_key = "fsm_phases"
                raw_phases = line_str.split("fsm_phases:", 1)[1].strip()
                if raw_phases:
                    triggers["fsm_phases"].extend(re.findall(r'["\']([^"\']+)["\']', raw_phases))
            elif "intent_keywords:" in line_str:
                active_list_key = "intent_keywords"
                raw_kw = line_str.split("intent_keywords:", 1)[1].strip()
                if raw_kw:
                    triggers["intent_keywords"].extend(re.findall(r'["\']([^"\']+)["\']', raw_kw))
            elif not line_str.startswith("-"):
                active_list_key = None

        if not name:
            name = os.path.basename(os.path.dirname(file_path))

        return SkillDefinition(
            name=name,
            description=description,
            triggers=triggers,
            token_budget=token_budget,
            dependencies=dependencies,
            content=content.strip(),
            file_path=file_path,
        )

    def load_available_skills(self) -> Dict[str, SkillDefinition]:
        """Loads all SKILL.md playbooks found in self.skills_dir."""
        self.skills.clear()
        if not os.path.exists(self.skills_dir):
            return self.skills

        for root, _, files in os.walk(self.skills_dir):
            for f in files:
                if f.upper() == "SKILL.MD":
                    fpath = os.path.join(root, f)
                    skill = self.parse_skill_markdown(fpath)
                    if skill:
                        self.skills[skill.name] = skill

        return self.skills

    def detect_active_skills(
        self,
        current_phase: Optional[str] = None,
        touched_files: Optional[List[str]] = None,
        goal_text: Optional[str] = None,
        max_token_budget: int = 2500,
    ) -> List[SkillDefinition]:
        """
        Ranks and returns active skills matching the current phase, touched files,
        and goal keywords, respecting dependency DAGs and token budget limits.
        """
        if not self.skills:
            self.load_available_skills()

        scored: List[Tuple[float, SkillDefinition]] = []
        phase_clean = (current_phase or "").upper()
        files = touched_files or []
        goal_words = set(re.findall(r"\w+", (goal_text or "").lower()))

        for skill in self.skills.values():
            score = 0.0

            # 1. FSM Phase match (+30 points)
            target_phases = [p.upper() for p in skill.triggers.get("fsm_phases", [])]
            if phase_clean and phase_clean in target_phases:
                score += 30.0

            # 2. File Pattern match (+20 points)
            patterns = skill.triggers.get("file_patterns", [])
            for fp in files:
                for pat in patterns:
                    if fnmatch.fnmatch(fp.replace("\\", "/"), pat) or fnmatch.fnmatch(os.path.basename(fp), pat):
                        score += 20.0
                        break

            # 3. Intent Keyword match (+15 points per match)
            keywords = [k.lower() for k in skill.triggers.get("intent_keywords", [])]
            for kw in keywords:
                if kw in goal_words:
                    score += 15.0

            if score > 0:
                skill.score = score
                scored.append((score, skill))

        # Sort highest scoring first
        scored.sort(key=lambda x: x[0], reverse=True)

        # Dependency DAG resolution & Token Budget Gating
        selected_skills: List[SkillDefinition] = []
        selected_names: Set[str] = set()
        accumulated_tokens = 0

        for _, skill in scored:
            # Check dependencies first
            dep_skills = []
            can_add = True
            for dep_name in skill.dependencies:
                if dep_name in self.skills and dep_name not in selected_names:
                    dep_skills.append(self.skills[dep_name])

            needed_tokens = skill.token_budget + sum(d.token_budget for d in dep_skills)
            if accumulated_tokens + needed_tokens <= max_token_budget:
                for dep_skill in dep_skills:
                    if dep_skill.name not in selected_names:
                        selected_skills.append(dep_skill)
                        selected_names.add(dep_skill.name)
                        accumulated_tokens += dep_skill.token_budget

                if skill.name not in selected_names:
                    selected_skills.append(skill)
                    selected_names.add(skill.name)
                    accumulated_tokens += skill.token_budget
            else:
                continue

        return selected_skills

    def project_skills_to_platforms(
        self,
        active_skills: List[SkillDefinition],
        workspace_dir: Optional[str] = None,
    ) -> Dict[str, List[str]]:
        """
        Projects active playbooks into native host IDE configuration files:
        - .cursor/rules/<skill>.mdc
        - .claude/rules/<skill>.md
        - AGENTS.md
        - GEMINI.md
        """
        cwd = workspace_dir or self.workspace_dir
        results: Dict[str, List[str]] = {
            "cursor": [],
            "claude": [],
            "agents_md": [],
            "gemini_md": [],
        }

        if not active_skills:
            return results

        # 1. Project to Cursor (.cursor/rules/<name>.mdc)
        cursor_dir = os.path.join(cwd, ".cursor", "rules")
        os.makedirs(cursor_dir, exist_ok=True)
        for skill in active_skills:
            mdc_path = os.path.join(cursor_dir, f"{skill.name}.mdc")
            globs_str = ",".join(skill.triggers.get("file_patterns", ["*"])) or "*"
            mdc_content = f"""---
description: "{skill.description}"
globs: "{globs_str}"
alwaysApply: false
---

{skill.content}
"""
            with open(mdc_path, "w", encoding="utf-8") as f:
                f.write(mdc_content)
            results["cursor"].append(mdc_path)

        # 2. Project to Claude Code (.claude/rules/<name>.md)
        claude_dir = os.path.join(cwd, ".claude", "rules")
        os.makedirs(claude_dir, exist_ok=True)
        for skill in active_skills:
            claude_path = os.path.join(claude_dir, f"{skill.name}.md")
            with open(claude_path, "w", encoding="utf-8") as f:
                f.write(f"# {skill.name.upper()} PLAYBOOK\n\n{skill.content}\n")
            results["claude"].append(claude_path)

        # 3. Project to AGENTS.md (OpenAI Codex target)
        agents_file = os.path.join(cwd, "AGENTS.md")
        self._update_markdown_section(
            agents_file,
            header="## Active S-Class Playbooks",
            content=self._format_skills_summary(active_skills),
        )
        results["agents_md"].append(agents_file)

        # 4. Project to GEMINI.md (Google Antigravity target)
        gemini_file = os.path.join(cwd, "GEMINI.md")
        self._update_markdown_section(
            gemini_file,
            header="## Active S-Class Playbooks",
            content=self._format_skills_summary(active_skills),
        )
        results["gemini_md"].append(gemini_file)

        return results

    @staticmethod
    def _format_skills_summary(skills: List[SkillDefinition]) -> str:
        blocks = []
        for s in skills:
            blocks.append(f"- **{s.name}**: {s.description}")
        return "\n".join(blocks)

    @staticmethod
    def _update_markdown_section(file_path: str, header: str, content: str) -> None:
        """Injects or replaces a titled section in a markdown file."""
        existing = ""
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                existing = f.read()

        section_pattern = re.compile(rf"{re.escape(header)}.*?(?=\n## |\Z)", re.DOTALL)
        new_section = f"{header}\n\n{content}\n"

        if section_pattern.search(existing):
            updated = section_pattern.sub(new_section, existing)
        else:
            sep = "\n\n" if existing.strip() else ""
            updated = existing.strip() + sep + new_section

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(updated)
