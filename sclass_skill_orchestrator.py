"""
S-Class EOS Dynamic Frontend Skill Stack Orchestrator (sclass_skill_orchestrator.py)

Manages a 23-skill modular frontend & ERP taxonomy divided across 5 architectural tiers.
Dynamically resolves, activates, and injects phase-appropriate skills per FSM state and screen route,
preventing giant prompt dumps and model confusion while delivering state-of-the-art UI/UX outputs.
"""

import os
import json
import logging
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Set, Optional

logger = logging.getLogger("sclass_skill_orchestrator")


@dataclass
class SkillDefinition:
    id: str
    name: str
    tier: str  # foundation, interaction, data, quality, domain
    purpose: str
    rule_guideline: str
    technologies: List[str]
    default_active: bool = False
    conditional_keywords: List[str] = None


class SkillTaxonomy:
    """Canonical Taxonomy of 23 Modular Frontend Skills for S-Class EOS."""

    SKILLS: Dict[str, SkillDefinition] = {
        # Tier 1 — Foundation
        "frontend-design": SkillDefinition(
            id="frontend-design",
            name="Visual Direction & Composition",
            tier="foundation",
            purpose="Establishes visual hierarchy, grid layout, contrast, and high-impact aesthetics.",
            rule_guideline="Avoid plain/amateur AI default templates. Use Google Fonts, glassmorphism, and dynamic HSL palettes.",
            technologies=["CSS Grid", "Tailwind CSS", "Google Fonts"],
            default_active=True
        ),
        "ux-architecture": SkillDefinition(
            id="ux-architecture",
            name="Information Architecture & Workflows",
            tier="foundation",
            purpose="Maps navigation trees, user task flows, and screen routing.",
            rule_guideline="Organize screens around user goals with clear visual hierarchy and minimal click depth.",
            technologies=["Navigation Trees", "Route Maps"],
            default_active=True
        ),
        "design-system": SkillDefinition(
            id="design-system",
            name="Design Tokens & Component Consistency",
            tier="foundation",
            purpose="Enforces consistent spacing, color variables, button variants, and typography scale.",
            rule_guideline="Use predefined design tokens; avoid ad-hoc inline pixel styling.",
            technologies=["ui-ux-pro-max", "Tailwind Tokens", "CSS Variables"],
            default_active=True
        ),
        "frontend-engineering": SkillDefinition(
            id="frontend-engineering",
            name="React / Next.js Architecture",
            tier="foundation",
            purpose="Manages component modularity, state hooks, and framework clean code.",
            rule_guideline="Keep components small, decoupled, and strictly typed with TypeScript.",
            technologies=["React 18", "Next.js App Router", "TypeScript"],
            default_active=True
        ),
        "responsive-design": SkillDefinition(
            id="responsive-design",
            name="Device-Adaptive Layout Ergonomics",
            tier="foundation",
            purpose="Adapts layouts dynamically between PC Desktop (high-density multi-column) and Mobile (touch targets).",
            rule_guideline="Desktop uses multi-pane cards & side drawers; Mobile uses single-column stacks & min 48px tap targets.",
            technologies=["Media Queries", "Tailwind Breakpoints", "Touch Target Audit"],
            default_active=True
        ),
        "accessibility": SkillDefinition(
            id="accessibility",
            name="WCAG & Keyboard Navigation",
            tier="foundation",
            purpose="Ensures ARIA attributes, semantic HTML tags, keyboard focus rings, and high contrast.",
            rule_guideline="All interactive elements must be accessible via Tab/Keyboard with semantic ARIA roles.",
            technologies=["ARIA Roles", "Semantic HTML5", "Focus Traps"],
            default_active=True
        ),

        # Tier 2 — Interaction ("The New Frontend")
        "motion-design": SkillDefinition(
            id="motion-design",
            name="State-Communicating Motion & Physics",
            tier="interaction",
            purpose="Handles page entrance choreography, hover micro-interactions, and spring physics.",
            rule_guideline="Motion MUST communicate state, spatial continuity, or hierarchy—never animate randomly.",
            technologies=["Framer Motion", "GSAP", "View Transitions API"],
            default_active=True
        ),
        "scroll-experience": SkillDefinition(
            id="scroll-experience",
            name="Navigation & Contextual Scroll Experience",
            tier="interaction",
            purpose="Sticky section headers, scroll progress bars, and progressive disclosure.",
            rule_guideline="In ERP systems, scroll = navigation + contextual information (NOT marketing parallax).",
            technologies=["Sticky Observers", "Scroll Progress Hooks"],
            default_active=False,
            conditional_keywords=["scroll", "sticky", "timeline", "parallax"]
        ),
        "creative-interaction": SkillDefinition(
            id="creative-interaction",
            name="Tactile & Spatial Micro-Interactions",
            tier="interaction",
            purpose="Hover previews, expandable card surfaces, drag-and-drop handles, and tactile feedback.",
            rule_guideline="Enhance product personality while preserving core usability and speed.",
            technologies=["Drag & Drop", "Expandable Cards", "Tooltip Previews"],
            default_active=False,
            conditional_keywords=["drag", "drop", "reorder", "expandable", "preview"]
        ),
        "3d-webgl": SkillDefinition(
            id="3d-webgl",
            name="Contextual 3D & Spatial Visualization",
            tier="interaction",
            purpose="Renders course dependency graphs, lab floor plans, and department network structures.",
            rule_guideline="Activate ONLY for structural visualization (e.g. course graph, lab map)—NEVER beside data tables.",
            technologies=["Three.js", "React Three Fiber", "Spline"],
            default_active=False,
            conditional_keywords=["3d", "webgl", "floor plan", "dependency graph", "network map", "campus map"]
        ),

        # Tier 3 — Data-Heavy ERP Skills
        "data-visualization": SkillDefinition(
            id="data-visualization",
            name="Analytics & Charting Intelligence",
            tier="data",
            purpose="Communicates attendance trends, SGPA marks, placement statistics, and faculty workload.",
            rule_guideline="Select charts that best communicate data semantics (Line=Trends, Bar=Comparisons, Donut=Distribution).",
            technologies=["Recharts", "Nivo", "Chart.js", "SVG Graphs"],
            default_active=True
        ),
        "data-dense-ui": SkillDefinition(
            id="data-dense-ui",
            name="Enterprise Tables & Data-Dense Controls",
            tier="data",
            purpose="High-density data tables with sorting, multi-column filtering, pagination, bulk actions, inline editing.",
            rule_guideline="Never render raw plain HTML tables. Include search chips, role filters, status badges, and pagination.",
            technologies=["TanStack Table", "Semantic Tailwind Data Grids"],
            default_active=True
        ),
        "command-search": SkillDefinition(
            id="command-search",
            name="Command Palette & Quick Navigation (⌘/Ctrl+K)",
            tier="data",
            purpose="Provides instant keyboard command search for student, faculty, course, and timetable lookups.",
            rule_guideline="Enable ⌘K command bar to make ERP navigation feel instantaneous and modern.",
            technologies=["cmdk", "Command Bar Dialog"],
            default_active=True
        ),

        # Tier 4 — Product Quality
        "visual-qa": SkillDefinition(
            id="visual-qa",
            name="Chrome MCP Visual Inspection",
            tier="quality",
            purpose="Captures real browser screenshots and verifies layout rendering visually.",
            rule_guideline="Inspect real rendered PNG screenshots; reject empty or broken layout renders.",
            technologies=["Chrome DevTools MCP", "PNG Header Audit"],
            default_active=True
        ),
        "ux-critique": SkillDefinition(
            id="ux-critique",
            name="UX Friction & Aesthetic Critique",
            tier="quality",
            purpose="Audits UI layouts for visual clutter, bad contrast, unmapped props, or awkward spacing.",
            rule_guideline="Trigger QA failure if screen displays 'undefined', 'NaN', broken card padding, or bad contrast.",
            technologies=["Aesthetic Heuristics", "DOM Sanitization"],
            default_active=True
        ),

        # Tier 5 — ERP Domain Specific Skills
        "role-based-ux": SkillDefinition(
            id="role-based-ux",
            name="Role-Tailored Personas (Student/Faculty/HOD/Admin)",
            tier="domain",
            purpose="Tailors navigation, dashboard metrics, and action toolbars specifically per user role.",
            rule_guideline="Student = Grades & Timetable; Faculty = Class Attendance & Marks; HOD = Verification Queue & Locks.",
            technologies=["Role Interaction Matrix", "RBAC Views"],
            default_active=True
        ),
        "academic-workflows": SkillDefinition(
            id="academic-workflows",
            name="Academic Lifecycle & Curriculum Domain",
            tier="domain",
            purpose="Understands semester, course, section, subject allocation, marks, timetable, and regulations (R22).",
            rule_guideline="Align data models and screen terms strictly with institutional academic structures.",
            technologies=["Academic Domain Models"],
            default_active=True
        ),
        "approval-workflows": SkillDefinition(
            id="approval-workflows",
            name="Multi-Tier Approval & Audit Trail UI",
            tier="domain",
            purpose="Manages multi-step student request approvals (Student ➔ Faculty ➔ Coordinator ➔ HOD).",
            rule_guideline="Display status timeline badges, pending action counts, rejection reasons, and audit logs.",
            technologies=["Approval Status Timelines"],
            default_active=True
        ),
        "notification-system": SkillDefinition(
            id="notification-system",
            name="Coherent Notification & Activity Feed",
            tier="domain",
            purpose="Unifies pending tasks, deadlines, announcements, and activity feeds into one drawer.",
            rule_guideline="Replace random toast spam with a structured notification & activity drawer.",
            technologies=["Activity Drawer", "Notification Badges"],
            default_active=True
        )
    }


class SClassSkillOrchestrator:
    """
    Dynamic Skill Orchestrator Engine for S-Class V12.0.
    Resolves, activates, and injects optimal skill stacks per FSM phase and workspace context.
    """

    @classmethod
    def resolve_active_skills(cls, fsm_phase: str, goal_text: str, workspace_dir: Optional[str] = None) -> List[SkillDefinition]:
        goal_lower = goal_text.lower()
        active_skills: List[SkillDefinition] = []

        # 1. Collect Default Active Core Skills
        for skill_id, skill in SkillTaxonomy.SKILLS.items():
            if skill.default_active:
                active_skills.append(skill)

        # 2. Evaluate Conditional Specialist Skills based on Goal / Spec Keywords
        for skill_id, skill in SkillTaxonomy.SKILLS.items():
            if not skill.default_active and skill.conditional_keywords:
                if any(kw in goal_lower for kw in skill.conditional_keywords):
                    active_skills.append(skill)
                    logger.info(f"[SkillOrchestrator] Conditionally activated specialist skill: '{skill_id}'")

        # 3. Filter & Prioritize by FSM Phase
        phase_filtered = cls._filter_skills_for_phase(active_skills, fsm_phase)
        
        # Save Active Skill Stack Receipt
        cwd = workspace_dir if workspace_dir else os.getcwd()
        state_dir = os.path.join(cwd, ".agents")
        os.makedirs(state_dir, exist_ok=True)
        
        stack_file = os.path.join(state_dir, "active_skill_stack.json")
        receipt = {
            "fsm_phase": fsm_phase,
            "total_skills_active": len(phase_filtered),
            "active_skills": [asdict(s) for s in phase_filtered]
        }
        try:
            with open(stack_file, "w", encoding="utf-8") as f:
                json.dump(receipt, f, indent=2)
        except Exception:
            pass

        return phase_filtered

    @classmethod
    def _filter_skills_for_phase(cls, skills: List[SkillDefinition], phase: str) -> List[SkillDefinition]:
        phase_upper = phase.upper()
        if phase_upper in ["DESIGN", "DEBATE", "CLARIFICATION"]:
            return [s for s in skills if s.tier in ["foundation", "domain"]]
        elif phase_upper in ["CODING", "TASK_COMPILATION", "INTEGRATION"]:
            return [s for s in skills if s.tier in ["foundation", "interaction", "data", "domain"]]
        elif phase_upper in ["QA", "RELEASE", "VERIFYING"]:
            return [s for s in skills if s.tier in ["quality", "foundation", "domain"]]
        return skills

    @classmethod
    def generate_skill_prompt_instructions(cls, active_skills: List[SkillDefinition]) -> str:
        lines = [
            "### 🎯 S-Class Phase Active Skill Stack Instructions:",
            "Follow these specialized skill guidelines for current state execution:\n"
        ]
        for skill in active_skills:
            lines.append(f"- **{skill.name} (`{skill.id}`)**: {skill.purpose}")
            lines.append(f"  *Directive*: {skill.rule_guideline}")
            lines.append(f"  *Stack*: {', '.join(skill.technologies)}\n")
        return "\n".join(lines)
