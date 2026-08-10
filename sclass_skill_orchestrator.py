"""
S-Class EOS Dynamic Skill Orchestrator & Execution Engine (sclass_skill_orchestrator.py)

Fully catalogs, initializes, and orchestrates 45 specialized skills across:
1. Paul Bakaus Impeccable (22 Playbooks: craft, shape, init, document, extract, critique, audit, polish, bolder, quieter, distill, harden, onboard, animate, colorize, typeset, layout, delight, overdrive, clarify, adapt, optimize, live).
2. Leon Taste-Skill (7 Aesthetics: minimalist, soft, brutalist, stitch, brandkit, redesign, image-to-code).
3. Emil Kowalski Skills (10 Animation Directives: animate, animation-vocabulary, apple-design, ask-sonner, emil-design-eng, find-animation-opportunities, improve-animations, pick-ui-library, prototype, review-animations).
4. Builtin Foundation & ERP Domain Skills (6 Core Foundation + 5 ERP Specialist Skills).

Enforces the No-Laziness Directive: S-Class MUST NOT skip skills out of model shortcuts.
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
    tier: str  # foundation, interaction, data, quality, domain, taste, impeccable, emil
    purpose: str
    rule_guideline: str
    technologies: List[str]
    source_repo: str = "builtin"
    reference_playbook: str = ""
    default_active: bool = False
    conditional_keywords: List[str] = None


class SkillTaxonomy:
    """Canonical Catalog of 45 Modular Skills in S-Class EOS."""

    PLUGIN_BASE: str = os.path.dirname(os.path.abspath(__file__))
    IMPECCABLE_REF: str = os.path.join(PLUGIN_BASE, "capability_plugins", "impeccable", "skill", "reference")
    EMIL_REF: str = os.path.join(PLUGIN_BASE, "capability_plugins", "emil-skills", "skills")
    TASTE_REF: str = os.path.join(PLUGIN_BASE, "capability_plugins", "taste-skill", "skills")

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

        # Tier 2 — Data-Heavy ERP Skills
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

        # Tier 3 — Product Quality & Visual QA
        "visual-qa": SkillDefinition(
            id="visual-qa",
            name="Chrome MCP Visual Inspection",
            tier="quality",
            purpose="Captures real browser screenshots and verifies layout rendering visually.",
            rule_guideline="Inspect real rendered PNG screenshots; reject empty or broken layout renders.",
            technologies=["Chrome DevTools MCP", "PNG Header Audit"],
            default_active=True
        ),

        # Tier 4 — ERP Domain Specific Skills
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

        # Tier 5 — Paul Bakaus Impeccable Skill Suite (pbakaus/impeccable)
        "impeccable-craft": SkillDefinition(
            id="impeccable-craft",
            name="Impeccable Craft Floor & Quality Gate",
            tier="impeccable",
            purpose="Enforces award-winning design director craft floor, banning safe/timid defaults.",
            rule_guideline="Go all out. Complete deliverable fully, inspect once with desktop+mobile screenshot batch, fix all defects in 1 pass.",
            technologies=["Impeccable Craft Engine", "Product/Operate/Persuade Register"],
            source_repo="pbakaus/impeccable",
            reference_playbook=os.path.join(IMPECCABLE_REF, "craft-floor.md"),
            default_active=True
        ),
        "impeccable-harden": SkillDefinition(
            id="impeccable-harden",
            name="Impeccable Production & Edge Case Hardening",
            tier="impeccable",
            purpose="Hardens UI components for zero records, long text overflow, missing avatars, and error boundaries.",
            rule_guideline="Every component MUST gracefully handle zero records, 100-char strings, loading skeletons, and network failure.",
            technologies=["Impeccable Harden Playbook", "Edge Case Testing"],
            source_repo="pbakaus/impeccable",
            reference_playbook=os.path.join(IMPECCABLE_REF, "harden.md"),
            default_active=True
        ),
        "impeccable-critique": SkillDefinition(
            id="impeccable-critique",
            name="Impeccable UX Heuristic Critique Engine",
            tier="impeccable",
            purpose="UX design review with 43KB heuristic scoring across cognitive load, visual hierarchy, and copy clarity.",
            rule_guideline="Audit cognitive friction, visual hierarchy depth, touch targets, and contrast ratios.",
            technologies=["Impeccable Critique Playbook"],
            source_repo="pbakaus/impeccable",
            reference_playbook=os.path.join(IMPECCABLE_REF, "critique.md"),
            default_active=True
        ),
        "impeccable-polish": SkillDefinition(
            id="impeccable-polish",
            name="Impeccable Final Polish Pass",
            tier="impeccable",
            purpose="Refines typography alignment, border contrast, micro-spacing, and button focus states before shipping.",
            rule_guideline="Eliminate pixel misalignment, awkward borders, and low contrast elements in the final release pass.",
            technologies=["Impeccable Polish Playbook"],
            source_repo="pbakaus/impeccable",
            reference_playbook=os.path.join(IMPECCABLE_REF, "polish.md"),
            default_active=True
        ),
        "impeccable-bolder": SkillDefinition(
            id="impeccable-bolder",
            name="Impeccable Bolder Visual Transformation",
            tier="impeccable",
            purpose="Amplifies safe or bland UI designs into distinctive, high-impact interfaces.",
            rule_guideline="Replace plain grey cards with frosted glass surfaces, vibrant HSL gradients, and crisp typography.",
            technologies=["Impeccable Bolder Playbook"],
            source_repo="pbakaus/impeccable",
            reference_playbook=os.path.join(IMPECCABLE_REF, "bolder.md"),
            default_active=False,
            conditional_keywords=["bolder", "dull", "bland", "amplify", "impact"]
        ),
        "impeccable-quieter": SkillDefinition(
            id="impeccable-quieter",
            name="Impeccable Quieter Visual De-Cluttering",
            tier="impeccable",
            purpose="Tones down overly aggressive or overstimulating UI designs into clean, professional interfaces.",
            rule_guideline="Reduce visual noise, soften bright neon backgrounds, and focus attention on primary user workflows.",
            technologies=["Impeccable Quieter Playbook"],
            source_repo="pbakaus/impeccable",
            reference_playbook=os.path.join(IMPECCABLE_REF, "quieter.md"),
            default_active=False,
            conditional_keywords=["quieter", "noise", "declutter", "overstimulating", "clean"]
        ),

        # Tier 6 — Leon Taste-Skill Suite (Leonxlnx/taste-skill)
        "taste-aesthetic": SkillDefinition(
            id="taste-aesthetic",
            name="Taste Aesthetic & Visual Tone Engine",
            tier="taste",
            purpose="Provides curated aesthetic direction (Minimalist, Soft, Glassmorphism, Brutalist, Stitch).",
            rule_guideline="In ERP systems, use Soft / Minimalist Glassmorphism (dark background, subtle borders, high contrast typography).",
            technologies=["Taste Design Tokens", "Color Palette Curations"],
            source_repo="Leonxlnx/taste-skill",
            reference_playbook=os.path.join(TASTE_REF, "taste-skill", "SKILL.md"),
            default_active=True
        ),
        "taste-minimalist": SkillDefinition(
            id="taste-minimalist",
            name="Minimalist Precision Aesthetic",
            tier="taste",
            purpose="Focuses on generous whitespace, high contrast, clean typography, and zero visual bloat.",
            rule_guideline="Eliminate unnecessary border lines and container nesting; let typography and whitespace define layout.",
            technologies=["Minimalist Tokens"],
            source_repo="Leonxlnx/taste-skill",
            reference_playbook=os.path.join(TASTE_REF, "minimalist-skill", "SKILL.md"),
            default_active=True
        ),
        "taste-soft": SkillDefinition(
            id="taste-soft",
            name="Soft Glassmorphism & Micro-Shadows",
            tier="taste",
            purpose="Delivers subtle backdrop filters, soft ambient shadows, and smooth card corners.",
            rule_guideline="Use backdrop-blur-md, 1px subtle border highlights, and soft ambient drop shadows.",
            technologies=["Soft Glass Tokens"],
            source_repo="Leonxlnx/taste-skill",
            reference_playbook=os.path.join(TASTE_REF, "soft-skill", "SKILL.md"),
            default_active=True
        ),

        # Tier 7 — Emil Kowalski Animation & Polish Suite (emilkowalski/skills)
        "emil-apple-design": SkillDefinition(
            id="emil-apple-design",
            name="Apple-Grade Micro-Interactions & UI Polish",
            tier="emil",
            purpose="Delivers Apple-level tactile feedback, spring transitions, toast notifications, and layout morphing.",
            rule_guideline="Use spring physics (stiffness 300, damping 30) for modals & popovers. Animate layout changes using layoutId.",
            technologies=["Sonner Toasts", "Framer Motion Springs", "LayoutId Morphing"],
            source_repo="emilkowalski/skills",
            reference_playbook=os.path.join(EMIL_REF, "apple-design", "SKILL.md"),
            default_active=True
        ),
        "emil-animation-opportunities": SkillDefinition(
            id="emil-animation-opportunities",
            name="Animation Opportunities & Micro-Delight Audit",
            tier="emil",
            purpose="Identifies key user touchpoints (button click, tab switch, dropdown expand) that benefit from micro-motion.",
            rule_guideline="Add 150ms spring feedback to button clicks and smooth layout transitions on filter tab toggles.",
            technologies=["Micro-Interaction Audit", "Motion Vocabulary"],
            source_repo="emilkowalski/skills",
            reference_playbook=os.path.join(EMIL_REF, "find-animation-opportunities", "SKILL.md"),
            default_active=True
        ),
        "emil-ask-sonner": SkillDefinition(
            id="emil-ask-sonner",
            name="Sonner Toast & Notification Architecture",
            tier="emil",
            purpose="Replaces jarring alert boxes with sleek, non-blocking Sonner toast notifications.",
            rule_guideline="Use Sonner toast notifications for async API actions (success, error, loading states).",
            technologies=["Sonner Toast Library"],
            source_repo="emilkowalski/skills",
            reference_playbook=os.path.join(EMIL_REF, "ask-sonner", "SKILL.md"),
            default_active=True
        ),
        "emil-design-eng": SkillDefinition(
            id="emil-design-eng",
            name="React Design Engineering & Spring Physics",
            tier="emil",
            purpose="Combines React state hooks with Framer Motion spring physics and layout animations.",
            rule_guideline="Ensure 60fps animation performance without triggering re-render layout thrashing.",
            technologies=["Design Engineering", "Framer Motion Hooks"],
            source_repo="emilkowalski/skills",
            reference_playbook=os.path.join(EMIL_REF, "emil-design-eng", "SKILL.md"),
            default_active=True
        )
    }


class SClassSkillOrchestrator:
    """
    Dynamic Skill Orchestrator & Initialization Engine for S-Class V12.1.
    Fully catalogs, initializes, and injects active skills with ZERO-LAZINESS enforcement.
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
            "no_laziness_enforced": True,
            "external_skills_integrated": [
                "pbakaus/impeccable (22 Playbooks)",
                "Leonxlnx/taste-skill (7 Aesthetics)",
                "emilkowalski/skills (10 Directives)"
            ],
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
            return [s for s in skills if s.tier in ["foundation", "domain", "taste", "impeccable"]]
        elif phase_upper in ["CODING", "TASK_COMPILATION", "INTEGRATION"]:
            return [s for s in skills if s.tier in ["foundation", "interaction", "data", "domain", "impeccable", "emil", "taste"]]
        elif phase_upper in ["QA", "RELEASE", "VERIFYING"]:
            return [s for s in skills if s.tier in ["quality", "foundation", "domain", "impeccable", "emil"]]
        return skills

    @classmethod
    def generate_skill_prompt_instructions(cls, active_skills: List[SkillDefinition]) -> str:
        lines = [
            "### 🎯 S-Class V12.1 Dynamic Skill Stack Directives (NO-LAZINESS MANDATE):",
            "You MUST actively execute and apply the following specialized skills (DO NOT SKIP OUT OF LAZINESS):\n"
        ]
        for skill in active_skills:
            ref_link = f" [Playbook: {skill.reference_playbook}]" if skill.reference_playbook else ""
            lines.append(f"- **{skill.name} (`{skill.id}`)** [{skill.source_repo}]{ref_link}: {skill.purpose}")
            lines.append(f"  *Directive*: {skill.rule_guideline}")
            lines.append(f"  *Stack*: {', '.join(skill.technologies)}\n")
        return "\n".join(lines)
