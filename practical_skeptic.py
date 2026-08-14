"""
S-Class Practical Skeptic (Real-World Project Failure Checklist)

Enforces empirical quality checks derived directly from recorded real-world failures.
Every single active rule in this class maps 1:1 to an empirical entry in regression_cases.json:
- SKEPTIC-NO-VIBECODE-UI (FAIL-SGDA-001)
- SKEPTIC-19-FEATURE-GAP (FAIL-SGDA-GAP-002)
- SKEPTIC-FASTAPI-ASYNC-TYPING (FAIL-AMISRU-003)
- SKEPTIC-FRONTEND-LEAKAGE-IN-BACKEND (FAIL-AMISRU-004)
- SKEPTIC-ROLE-ROUTE-GUARD (FAIL-PORTAL-005)
- SKEPTIC-ROLE-EXTRACTION-SANITY (FAIL-PORTAL-006)
- SKEPTIC-NON-ENTITY-API (FAIL-SYNTH-007)
- SKEPTIC-SOURCE-DECISION-PRESERVATION (FAIL-DOC-008)
"""

from typing import Dict, List, Set, Any, Optional, Tuple
import re

INVALID_ENTITY_NAMES = {
    "fast", "quick", "slow", "complete", "simple", "easy", "complex", "hard", "full",
    "partial", "automated", "manual", "single", "multi", "great", "good", "new", "old",
    "best", "smart", "high", "low", "real", "time", "custom", "tool", "portal", "system",
    "platform", "app", "application", "codebase", "make", "build", "add", "item", "items",
    "reads", "writes", "pushes", "pulls", "views", "view", "access", "accesses",
    "doc", "docs", "documentation", "spec", "specs", "specification", "architecture"
}

INVALID_ROLE_NAMES = {
    "college", "school", "university", "department", "company", "enterprise", "organization",
    "system", "platform", "app", "application", "tool", "portal", "codebase"
}


class PracticalSkeptic:
    """
    Practical, real-world reviewer that validates specifications against
    empirical failure modes from actual projects (Next.js/Prisma, Python/FastAPI, and CLI tools).
    """

    ACTIVE_RULES: Set[str] = {
        "SKEPTIC-NO-VIBECODE-UI",
        "SKEPTIC-19-FEATURE-GAP",
        "SKEPTIC-FASTAPI-ASYNC-TYPING",
        "SKEPTIC-FRONTEND-LEAKAGE-IN-BACKEND",
        "SKEPTIC-ROLE-ROUTE-GUARD",
        "SKEPTIC-ROLE-EXTRACTION-SANITY",
        "SKEPTIC-NON-ENTITY-API",
        "SKEPTIC-SOURCE-DECISION-PRESERVATION",
        "SKEPTIC-PROSE-CRUD-DUPLICATION",
        "SKEPTIC-NON-NOUN-API",
        "SKEPTIC-ACTOR-COMPLETENESS",
        "SKEPTIC-STRUCTURAL-GROUNDING",
        "SKEPTIC-EPISTEMIC-BEHAVIOR-GROUNDING"
    }

    @classmethod
    def audit_specification(
        cls,
        spec_dict: Dict[str, Any],
        workspace_evidence: Optional[Any] = None,
        archetypes: Optional[List[str]] = None
    ) -> Tuple[bool, List[str], List[Dict[str, Any]]]:
        warnings = []
        checks = []
        passed = True

        low_level_designs = spec_dict.get("low_level_designs", {})
        page_spreads = spec_dict.get("page_spreads", {})
        requirements = spec_dict.get("requirements", {})

        # 1. SKEPTIC-NON-ENTITY-API (Adjectives/Verbs hallucinated into REST APIs)
        for lld_key, lld in low_level_designs.items():
            apis = lld.get("api_endpoints", [])
            for ep in apis:
                url_path = ep.split()[1] if len(ep.split()) > 1 else ep
                # Extract clean path segments (e.g. /api/fasts -> ['fasts'], /attendance/reports/low-attendance -> ['attendance', 'reports', 'low-attendance'])
                segments = [s.lower() for s in url_path.split('/') if s and not s.startswith('{') and not s.startswith(':') and s not in ['api', 'v1', 'v2', 'public']]
                if segments:
                    primary_seg = segments[0]
                    norm_primary = primary_seg[:-1] if primary_seg.endswith('s') and len(primary_seg) > 3 else primary_seg
                    if norm_primary in INVALID_ENTITY_NAMES:
                        warnings.append(f"[SKEPTIC-NON-ENTITY-API] Hallucinated REST API '{ep}' is derived from adjective/verb token '{primary_seg}' instead of a real domain entity.")
                        checks.append({
                            "rule_id": "SKEPTIC-NON-ENTITY-API",
                            "severity": "BLOCKING",
                            "message": f"Remove hallucinated endpoint '{ep}' based on invalid root entity '{primary_seg}'."
                        })
                        passed = False

        # 2. SKEPTIC-ROLE-EXTRACTION-SANITY (Non-actor container nouns parsed as roles)
        for role in page_spreads.keys():
            if role.lower() in INVALID_ROLE_NAMES:
                warnings.append(f"[SKEPTIC-ROLE-EXTRACTION-SANITY] Extracted role '{role}' is an organization/container, not a human actor.")
                checks.append({
                    "rule_id": "SKEPTIC-ROLE-EXTRACTION-SANITY",
                    "severity": "BLOCKING",
                    "message": f"Fix role extraction: '{role}' is a container noun. Expected human actors (e.g. faculty, hod, student, admin)."
                })
                passed = False

        # 3. SKEPTIC-FRONTEND-LEAKAGE-IN-BACKEND (UI components in pure CLI/FastAPI backends)
        if archetypes and any(a in ["cli_tool", "backend_api", "library_package", "data_pipeline"] for a in archetypes) and not any(a in ["fullstack", "web_frontend", "mobile_hybrid"] for a in archetypes):
            ui_count = 0
            for lld in low_level_designs.values():
                for comp in lld.get("sub_components", []):
                    if any(ui_kw in comp.lower() for ui_kw in ["matrix", "drawer", "modal", "badge", "chart", "table", "uploader"]):
                        ui_count += 1
            if ui_count > 5:
                warnings.append(f"[SKEPTIC-FRONTEND-LEAKAGE-IN-BACKEND] Pure backend/CLI project has {ui_count} hallucinated UI components in specification.")
                checks.append({
                    "rule_id": "SKEPTIC-FRONTEND-LEAKAGE-IN-BACKEND",
                    "severity": "WARNING",
                    "message": "Pure backend project should specify API contracts and schemas, not frontend UI components."
                })

        # 4. SKEPTIC-NO-VIBECODE-UI (Generic mockup placeholder fields)
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

        # 5. SKEPTIC-19-FEATURE-GAP (Operational workflows vs shallow CRUD)
        all_actions = []
        for lld in low_level_designs.values():
            for tab in lld.get("tabs", []):
                all_actions.extend(tab.get("actions", []))
            all_actions.extend(lld.get("api_endpoints", []))

        action_text = " ".join(all_actions).lower()
        has_operational_workflows = any(
            kw in action_text
            for kw in [
                "assign", "verify", "schedule", "track", "progress", "advance", "approve",
                "reject", "complete", "sign-off", "publish", "revise", "host", "co-author",
                "override", "revaluation", "eligible", "spotlight", "status"
            ]
        )

        if not has_operational_workflows and len(low_level_designs) > 2:
            warnings.append("[SKEPTIC-19-FEATURE-GAP] Specification contains only flat CRUD. Missing operational workflows (assignment, verification, scheduling, progress tracking).")
            checks.append({
                "rule_id": "SKEPTIC-19-FEATURE-GAP",
                "severity": "WARNING",
                "message": "Add explicit operational workflows to prevent shallow CRUD gap."
            })

        # 6. SKEPTIC-ROLE-ROUTE-GUARD (Missing /profile and self-security routes)
        if not (archetypes and any(a in ["cli_tool", "backend_api", "data_pipeline"] for a in archetypes)):
            for role, pages in page_spreads.items():
                page_list = pages.get("pages", [pages]) if isinstance(pages, dict) else (pages if isinstance(pages, list) else [])
                routes = [p.get("route", "") for p in page_list if isinstance(p, dict)]
                if "/profile" not in routes and role.lower() not in ["system", "admin"]:
                    warnings.append(f"[SKEPTIC-ROLE-ROUTE-GUARD] Role '{role}' is missing self-profile and security management routes.")
                    checks.append({
                        "rule_id": "SKEPTIC-ROLE-ROUTE-GUARD",
                        "severity": "INFO",
                        "message": f"Add /profile to {role} sitemap."
                    })

        # 7. SKEPTIC-FASTAPI-ASYNC-TYPING (FastAPI async session & response typing)
        if archetypes and any(a in ["backend_api", "data_pipeline"] for a in archetypes) and not any(a in ["cli_tool"] for a in archetypes):
            for lld_key, lld in low_level_designs.items():
                apis = lld.get("api_endpoints", [])
                val_rules = lld.get("validation_rules", [])
                if apis and not any("async" in r.lower() or "pydantic" in r.lower() or "schema" in r.lower() for r in val_rules):
                    warnings.append(f"[SKEPTIC-FASTAPI-ASYNC-TYPING] Backend API '{lld_key}' is missing async session dependency and response model typing contracts.")
                    checks.append({
                        "rule_id": "SKEPTIC-FASTAPI-ASYNC-TYPING",
                        "severity": "INFO",
                        "message": "Specify async DB session injection and Pydantic response models on API endpoints."
                    })

        # 8. SKEPTIC-SOURCE-DECISION-PRESERVATION (Preserve explicit decisions & routes from source docs)
        for lld_key, lld in low_level_designs.items():
            for ep in lld.get("api_endpoints", []):
                # Check for file extension leakage in routes
                if any(ext in ep.lower() for ext in [".md", ".markdown", ".json", ".ts", ".py", ".prisma"]):
                    warnings.append(f"[SKEPTIC-SOURCE-DECISION-PRESERVATION] API endpoint '{ep}' contains leaked documentation file extension.")
                    checks.append({
                        "rule_id": "SKEPTIC-SOURCE-DECISION-PRESERVATION",
                        "severity": "BLOCKING",
                        "message": f"Remove file-extension artifact from endpoint '{ep}'."
                    })
                    passed = False

        if workspace_evidence and getattr(workspace_evidence, "api_routes", None):
            all_spec_apis = []
            for lld in low_level_designs.values():
                all_spec_apis.extend(lld.get("api_endpoints", []))
            all_spec_api_str = " ".join(all_spec_apis)

            # Check if any explicit architecture routes are completely dropped
            explicit_routes = getattr(workspace_evidence, "api_routes", [])
            missing_critical = []
            for er in explicit_routes[:10]:
                er_path = er.get("path", "")
                if er_path and er_path not in all_spec_api_str:
                    missing_critical.append(er_path)

            if len(missing_critical) > 5:
                warnings.append(f"[SKEPTIC-SOURCE-DECISION-PRESERVATION] Specification dropped {len(missing_critical)} explicit API routes documented in workspace architecture files.")
                checks.append({
                    "rule_id": "SKEPTIC-SOURCE-DECISION-PRESERVATION",
                    "severity": "WARNING",
                    "message": f"Incorporate documented API routes: {missing_critical[:3]}"
                })

        # 9. SKEPTIC-PROSE-CRUD-DUPLICATION (Detects generic CRUD duplication & broken irregular plurals)
        invalid_plurals = ["alumnis", "datas", "staffs", "equipments", "telemetrys", "categorys", "facultys"]
        for lld_key, lld in low_level_designs.items():
            apis = lld.get("api_endpoints", [])
            for ep in apis:
                url_path = ep.split()[1] if len(ep.split()) > 1 else ep
                for inv_p in invalid_plurals:
                    if f"/{inv_p}" in url_path.lower():
                        warnings.append(f"[SKEPTIC-PROSE-CRUD-DUPLICATION] API endpoint '{ep}' contains invalid irregular pluralization '{inv_p}'.")
                        checks.append({
                            "rule_id": "SKEPTIC-PROSE-CRUD-DUPLICATION",
                            "severity": "BLOCKING",
                            "message": f"Fix pluralization for '{inv_p}' in endpoint '{ep}'."
                        })
                        passed = False

        all_apis_flat = [ep.split()[1] if len(ep.split()) > 1 else ep for lld in low_level_designs.values() for ep in lld.get("api_endpoints", [])]
        for ep in all_apis_flat:
            if ep.startswith("/api/"):
                entity_name = ep.replace("/api/", "").split("/")[0]
                if entity_name and len(entity_name) > 3 and not entity_name.startswith("{") and entity_name not in ["auth", "account", "user", "users"]:
                    # Check if explicit non-/api/ route exists for same concept (e.g. /api/advancements vs /batches/{id}/advance-semester)
                    has_explicit_override = any(
                        not other.startswith("/api/") and entity_name.rstrip('s') in other
                        for other in all_apis_flat
                    )
                    if has_explicit_override:
                        warnings.append(f"[SKEPTIC-PROSE-CRUD-DUPLICATION] Generic CRUD route '{ep}' duplicates explicit documented domain route.")
                        checks.append({
                            "rule_id": "SKEPTIC-PROSE-CRUD-DUPLICATION",
                            "severity": "WARNING",
                            "message": f"Suppress generic fallback endpoint '{ep}' in favor of documented explicit route."
                        })

        # 10. SKEPTIC-NON-NOUN-API (Detects prose verb/adverb/preposition API resources)
        non_noun_tokens = [
            "accrues", "accrue", "blocks", "block", "waives", "waive", "dailies", "daily",
            "furthers", "further", "haves", "have", "untils", "until", "paids", "paid",
            "checkeds", "checked", "overdues", "overdue", "multiples", "multiple"
        ]
        for ep in all_apis_flat:
            for nn in non_noun_tokens:
                if f"/api/{nn}" in ep.lower() or ep.lower().endswith(f"/{nn}"):
                    warnings.append(f"[SKEPTIC-NON-NOUN-API] API endpoint '{ep}' contains non-noun verb/adverb token '{nn}'.")
                    checks.append({
                        "rule_id": "SKEPTIC-NON-NOUN-API",
                        "severity": "BLOCKING",
                        "message": f"Eliminate non-noun API resource '{nn}' in endpoint '{ep}'."
                    })
                    passed = False

        # 11. SKEPTIC-ACTOR-COMPLETENESS (Audits for dropped human roles named in prompt)
        intent_summary = spec_dict.get("intent_summary", "").lower()
        if intent_summary and page_spreads:
            active_spread_roles = {r.lower() for r in page_spreads.keys()}
            non_role_stops = {
                'system', 'app', 'application', 'platform', 'management', 'portal', 'interface',
                'module', 'page', 'view', 'screen', 'console', 'hub', 'dashboard', 'feature',
                'service', 'tool', 'workflow', 'process', 'solution', 'software', 'database',
                'table', 'field', 'data', 'record', 'entry', 'list', 'item', 'details', 'info',
                'information', 'type', 'status', 'action', 'role', 'roles', 'user', 'users',
                'actor', 'actors', 'with', 'for', 'and', 'including', 'featuring', 'such', 'like', 'real'
            }
            candidate_roles = set()
            role_enum_matches = re.findall(
                r'\b(?:roles?|for|actors?|users?)\s*[:=]?\s*([a-zA-Z0-9_\-\s,&\/]+?)(?:\.|\n|;|\bwith\b|\bincluding\b|$)',
                intent_summary,
                re.IGNORECASE
            )
            for enum_chunk in role_enum_matches:
                items = re.split(r',|\band\b|\b&\b|\bor\b', enum_chunk)
                for item in items:
                    clean_item = item.strip().lower()
                    clean_item = re.sub(r'^[^\w]+|[^\w]+$', '', clean_item)
                    if clean_item and len(clean_item) >= 2 and clean_item not in non_role_stops:
                        norm_r = clean_item[:-1] if (clean_item.endswith('s') and len(clean_item) > 3 and not clean_item.endswith('ss')) else clean_item
                        if clean_item.endswith('es') and len(clean_item) > 4:
                            norm_r = clean_item[:-2]
                        if norm_r not in non_role_stops:
                            candidate_roles.add(norm_r)

            for w_norm in candidate_roles:
                if not any(w_norm in r or r in w_norm for r in active_spread_roles):
                    warnings.append(f"[SKEPTIC-ACTOR-COMPLETENESS] Named human role '{w_norm}' in prompt was omitted from synthesized sitemap.")
                    checks.append({
                        "rule_id": "SKEPTIC-ACTOR-COMPLETENESS",
                        "severity": "BLOCKING",
                        "message": f"Synthesize dedicated workspace page spread for named role '{w_norm}'."
                    })
                    passed = False

        # Rule 12: SKEPTIC-STRUCTURAL-GROUNDING — Verify endpoints resolve to behavior nodes, domain primitives, or explicit routes
        lld_cat = spec_dict.get("low_level_designs", spec_dict.get("low_level_design_catalog", {}))
        spreads_map = spec_dict.get("page_spreads", {})
        if "SKEPTIC-STRUCTURAL-GROUNDING" in cls.ACTIVE_RULES and lld_cat:
            explicit_routes_set = set()
            if workspace_evidence and getattr(workspace_evidence, "api_routes", None):
                for er in workspace_evidence.api_routes:
                    explicit_routes_set.add(f"{er.get('method', '').upper()} {er.get('path', '')}")

            valid_stems = set()
            if spreads_map:
                for r_key, pages in spreads_map.items():
                    page_list = pages.get("pages", [pages]) if isinstance(pages, dict) else (pages if isinstance(pages, list) else [])
                    for p in page_list:
                        if isinstance(p, dict):
                            mod_k = p.get("module_key", p.get("page_name", "")).lower().replace("entity_", "").replace("wf_", "").replace("doc_", "").replace("resource_", "")
                            if mod_k:
                                valid_stems.add(mod_k)

            unsupported_endpoints = []
            for lld_key, lld in lld_cat.items():
                endpoints = lld.get("api_endpoints", [])
                for ep in endpoints:
                    if ep in explicit_routes_set or any(sys_kw in ep.lower() for sys_kw in ["/api/auth", "/api/account", "/api/session", "cli://"]):
                        continue
                    tokens = [t.lower() for t in re.split(r'[/_\-\s]', ep) if t and not t.startswith('{') and not t.startswith(':')]
                    if not any(stem in tokens or any(t.startswith(stem) or stem.startswith(t) for t in tokens if len(t) >= 4) for stem in valid_stems if stem):
                        unsupported_endpoints.append(ep)

            if unsupported_endpoints:
                warnings.append(f"[SKEPTIC-STRUCTURAL-GROUNDING] Synthesized API endpoints lack structural IR grounding: {', '.join(unsupported_endpoints[:5])}")

        # Rule 13: SKEPTIC-EPISTEMIC-BEHAVIOR-GROUNDING — Verify no PROPOSED or unbacked speculative behavior nodes compiled to HLD/LLD
        if "SKEPTIC-EPISTEMIC-BEHAVIOR-GROUNDING" in cls.ACTIVE_RULES:
            behavior_graph = spec_dict.get("behavior_graph")
            if behavior_graph and hasattr(behavior_graph, "nodes"):
                proposed_nodes = [n for n in behavior_graph.nodes.values() if getattr(n, "epistemic_status", None) == "proposed"]
                if proposed_nodes:
                    warnings.append(f"[SKEPTIC-EPISTEMIC-BEHAVIOR-GROUNDING] Gated {len(proposed_nodes)} unbacked PROPOSED behaviors from HLD/LLD compilation.")

        return passed, warnings, checks
