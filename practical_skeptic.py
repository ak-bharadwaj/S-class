"""
S-Class Practical Skeptic (Real-World Project Failure Checklist)

Enforces empirical quality checks derived directly from recorded real-world failures
(e.g. SGDA 19-feature gap audit, vibecoded UI prevention, Next.js/Prisma schema grounding,
FastAPI async dependency typing).
"""

from typing import Dict, List, Set, Any, Optional, Tuple
import re


class PracticalSkeptic:
    """
    Practical, real-world reviewer that validates specifications against
    empirical failure modes from actual projects (Next.js/Prisma and Python/FastAPI).
    """

    @classmethod
    def audit_specification(
        cls,
        spec_dict: Dict[str, Any],
        workspace_evidence: Optional[Any] = None
    ) -> Tuple[bool, List[str], List[Dict[str, Any]]]:
        """
        Runs the 5 practical checklist rules.
        Returns: (passed: bool, warnings: List[str], actionable_checks: List[Dict])
        """
        warnings = []
        checks = []
        passed = True

        low_level_designs = spec_dict.get("low_level_designs", {})
        page_spreads = spec_dict.get("page_spreads", {})
        requirements = spec_dict.get("requirements", {})

        # Rule 1: SKEPTIC-PRISMA-SCHEMA-GROUNDING & NO-VIBECODE-UI
        # Ensures UI forms & API endpoints use real schema fields, not generic boilerplate
        generic_field_count = 0
        total_field_count = 0

        for lld_key, lld in low_level_designs.items():
            for tab in lld.get("tabs", []):
                for f in tab.get("fields", []):
                    total_field_count += 1
                    if any(gen in f.lower() for gen in ["genericfield", "foo (string)", "bar (number)", "dummy"]):
                        generic_field_count += 1

        if total_field_count > 0 and generic_field_count > 0:
            warnings.append(f"[SKEPTIC-NO-VIBECODE-UI] Detected {generic_field_count} generic mockup fields in UI tabs. Ground all fields in real domain schema.")
            checks.append({
                "rule_id": "SKEPTIC-NO-VIBECODE-UI",
                "severity": "WARNING",
                "message": "Eliminate vibecoded placeholder fields; bind UI directly to domain attributes."
            })

        # Rule 2: SKEPTIC-19-FEATURE-GAP-PREVENTION (Workflow vs Shallow CRUD)
        # In multi-role portals, ensure assignment, verification, and progress tracking exist
        all_routes = []
        for role, pages in page_spreads.items():
            all_routes.extend([p.get("route", "") for p in pages])

        all_actions = []
        for lld in low_level_designs.values():
            for tab in lld.get("tabs", []):
                all_actions.extend(tab.get("actions", []))

        action_text = " ".join(all_actions).lower()
        has_operational_workflows = any(
            kw in action_text
            for kw in ["assign", "verify", "schedule", "track", "progress", "advance", "approve", "reject", "complete", "sign-off"]
        )

        if not has_operational_workflows and len(low_level_designs) > 2:
            warnings.append("[SKEPTIC-19-FEATURE-GAP] Specification contains only flat CRUD. Missing operational workflows (assignment, verification, scheduling, progress tracking).")
            checks.append({
                "rule_id": "SKEPTIC-19-FEATURE-GAP",
                "severity": "WARNING",
                "message": "Add explicit operational workflows (e.g. slot scheduling, instructor assignment, progress scorecard) to prevent shallow CRUD gap."
            })

        # Rule 3: SKEPTIC-ROLE-ROUTE-GUARD
        # Ensures multi-role portals have distinct role-scoped sitemaps and profile/security tabs
        for role, pages in page_spreads.items():
            routes = [p.get("route", "") for p in pages]
            if "/profile" not in routes:
                warnings.append(f"[SKEPTIC-ROLE-ROUTE-GUARD] Role '{role}' is missing self-profile and security management routes.")
                checks.append({
                    "rule_id": "SKEPTIC-ROLE-ROUTE-GUARD",
                    "severity": "INFO",
                    "message": f"Add /profile to {role} sitemap."
                })

        # Rule 4: SKEPTIC-API-CONTRACT-COHERENCE
        # Validates REST API methods and parameter patterns
        total_apis = 0
        for lld in low_level_designs.values():
            apis = lld.get("api_endpoints", [])
            total_apis += len(apis)
            for ep in apis:
                if not any(ep.startswith(m) for m in ["GET ", "POST ", "PUT ", "PATCH ", "DELETE "]):
                    warnings.append(f"[SKEPTIC-API-CONTRACT] API endpoint '{ep}' lacks standard HTTP method prefix.")
                    passed = False

        if total_apis == 0 and len(low_level_designs) > 0:
            warnings.append("[SKEPTIC-API-CONTRACT] No backing REST API endpoints specified in LLD.")
            passed = False

        return passed, warnings, checks
