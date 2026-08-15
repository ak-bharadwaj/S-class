import os
import json
import re
import shutil
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional, Set, Tuple

from domain_primitives import (
    DomainPrimitiveType,
    DomainNode,
    DomainEdge,
    RelationType,
    ProvenanceType,
    SemanticDomainGraph,
    AssumptionRecord
)
from semantic_decomposer import SemanticDecomposer
from spec_compiler import GraphInferenceEngine, SpecificationCompiler
from adversarial_skeptic import AdversarialSkeptic
from practical_skeptic import PracticalSkeptic
from requirement_ir import RequirementGraph
from behavior_graph import BehaviorGraph
from hld_compiler import HLDDesign, HLDModule, ADRRecord

try:
    from runtime import write_json_atomic, load_json
except ImportError:
    # Fallbacks for testing if runtime is not available
    def write_json_atomic(filepath: str, data: Any) -> None:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def load_json(filepath: str) -> Any:
        if not os.path.exists(filepath):
            return None
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)

logger = logging.getLogger("spec_synthesis")

# --- Enums ---

class RequirementType(Enum):
    EXPLICIT = "explicit"
    SUPPORTED = "supported"
    DERIVED = "derived"
    OPTIONAL = "optional"
    UNKNOWN = "unknown"
    CONFLICT = "conflict"
    REUSE = "reuse"

class ArtifactAction(Enum):
    CREATE = "create"
    EXTEND = "extend"
    MODIFY = "modify"
    REUSE = "reuse"
    DEPRECATE = "deprecate"
    DELETE = "delete"

class RequirementCategory(Enum):
    PRODUCT_REQUIREMENT = "product_requirement"
    SYSTEM_INVARIANT = "system_invariant"
    UX_DERIVATION = "ux_derivation"
    ARCHITECTURAL_CONSTRAINT = "architectural_constraint"

class DecisionThreshold(Enum):
    AUTO_DECIDE = "auto"
    PROBABLY_DECIDE = "probably"
    MUST_ASK = "must_ask"
    MUST_STOP = "must_stop"

class GateResult(Enum):
    PASS = "PASS"
    PASS_WITH_DECISIONS = "PASS_WITH_DECISIONS"
    BLOCKED = "BLOCKED"

class ProjectArchetype(Enum):
    FULLSTACK_MONOLITH = "fullstack"
    WEB_FRONTEND = "web_frontend"
    BACKEND_API = "backend_api"
    MOBILE_HYBRID = "mobile_hybrid"
    CLI_TOOL = "cli_tool"
    LIBRARY_PACKAGE = "library"
    DATA_PIPELINE = "data_pipeline"
    ML_AI = "ml_ai"
    STATIC_SITE = "static_site"
    MICROSERVICE = "microservice"
    MONOREPO = "monorepo"
    GREENFIELD = "greenfield"

class ScopeTier(Enum):
    TRIVIAL = "trivial"
    MINOR = "minor"
    MODERATE = "moderate"
    MAJOR = "major"

# --- Dataclasses ---

@dataclass
class EvidenceReference:
    source_file: str
    section: Optional[str] = None
    reference_text: Optional[str] = None
    line_number: Optional[int] = None

@dataclass
class SynthesizedRequirement:
    id: str
    description: str
    type: RequirementType
    category: RequirementCategory
    action: ArtifactAction
    decision_threshold: DecisionThreshold
    evidence: List[EvidenceReference] = field(default_factory=list)
    why_chain: List[str] = field(default_factory=list)
    affects: List[str] = field(default_factory=list)
    depends_on: List[str] = field(default_factory=list)
    consequences: List[str] = field(default_factory=list)
    assumption_type: Optional[str] = None  # ux, behavior, data, api, permission, architecture

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "type": self.type.value,
            "category": self.category.value,
            "action": self.action.value,
            "decision_threshold": self.decision_threshold.value,
            "evidence": [e.__dict__ for e in self.evidence],
            "why_chain": self.why_chain,
            "affects": self.affects,
            "depends_on": self.depends_on,
            "consequences": self.consequences,
            "assumption_type": self.assumption_type
        }

@dataclass
class RoleCapabilityBinding:
    role: str
    capabilities: List[str] = field(default_factory=list)
    raw_clause: str = ""

@dataclass
class IntentExtraction:
    raw_request: str
    primary_features: List[str] = field(default_factory=list)
    target_roles: List[str] = field(default_factory=list)
    action_verbs: List[str] = field(default_factory=list)
    domain_keywords: List[str] = field(default_factory=list)

@dataclass
class StructuredIntent(IntentExtraction):
    role_bindings: List[RoleCapabilityBinding] = field(default_factory=list)
    global_features: List[str] = field(default_factory=list)

    @property
    def all_features(self) -> List[str]:
        caps = []
        for rb in self.role_bindings:
            caps.extend(rb.capabilities)
        caps.extend(self.global_features)
        return list(dict.fromkeys(caps)) or self.primary_features

@dataclass
class ProjectEvidence:
    db_entities: List[Dict[str, Any]] = field(default_factory=list)
    api_routes: List[Dict[str, Any]] = field(default_factory=list)
    ui_components: List[str] = field(default_factory=list)
    design_docs: Dict[str, Any] = field(default_factory=dict)
    env_vars: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    auth_permissions: List[str] = field(default_factory=list)
    existing_tests: List[str] = field(default_factory=list)
    discovered_pages: List[str] = field(default_factory=list)
    role_permissions: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class SynthesizedSpec:
    intent_summary: str
    requirements: Dict[str, List[Dict[str, Any]]]
    affected_systems: Dict[str, List[str]]
    conflicts: List[Dict[str, Any]]
    questions_for_human: List[str]
    acceptance_criteria: List[str]
    gate_result: str
    total_assumption_weight: int
    archetypes: List[str] = field(default_factory=lambda: ["fullstack"])
    scope_tier: str = "moderate"
    spec_version: int = 1
    page_spreads: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    low_level_designs: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    scope_boundaries: Dict[str, List[str]] = field(default_factory=dict)
    domain_graph: Optional[Dict[str, Any]] = None
    domain_specificity_score: float = 1.0
    unsupported_invention_rate: float = 0.0
    assumption_ledger: List[Dict[str, Any]] = field(default_factory=list)

# --- Classifier & Archetype Detector ---

class ProjectArchetypeDetector:
    """Classifies a project directory into one or more ProjectArchetype values."""

    @classmethod
    def detect(cls, workspace_dir: str, evidence: Optional[ProjectEvidence] = None) -> List[ProjectArchetype]:
        archetypes: Set[ProjectArchetype] = set()

        pkg_json = os.path.join(workspace_dir, "package.json")
        req_txt = os.path.join(workspace_dir, "requirements.txt")
        pyproject = os.path.join(workspace_dir, "pyproject.toml")
        docker_compose = os.path.join(workspace_dir, "docker-compose.yml")
        turbo_json = os.path.join(workspace_dir, "turbo.json")
        nx_json = os.path.join(workspace_dir, "nx.json")
        astro_cfg = os.path.join(workspace_dir, "astro.config.mjs")
        capacitor_cfg = os.path.join(workspace_dir, "capacitor.config.ts")

        # 1. Monorepo
        if os.path.exists(turbo_json) or os.path.exists(nx_json) or os.path.exists(os.path.join(workspace_dir, "pnpm-workspace.yaml")):
            archetypes.add(ProjectArchetype.MONOREPO)

        # 2. Package manifest checks
        if os.path.exists(pkg_json):
            try:
                with open(pkg_json, 'r', encoding='utf-8', errors='ignore') as f:
                    pkg_data = json.load(f)
                deps = pkg_data.get("dependencies", {})
                dev_deps = pkg_data.get("devDependencies", {})
                all_deps = {**deps, **dev_deps}

                if "next" in all_deps or "remix" in all_deps or "express" in all_deps:
                    if os.path.exists(os.path.join(workspace_dir, "prisma")) or "prisma" in all_deps or "typeorm" in all_deps:
                        archetypes.add(ProjectArchetype.FULLSTACK_MONOLITH)
                    else:
                        archetypes.add(ProjectArchetype.WEB_FRONTEND)
                if "@capacitor/core" in all_deps or "react-native" in all_deps or os.path.exists(os.path.join(workspace_dir, "android")):
                    archetypes.add(ProjectArchetype.MOBILE_HYBRID)
                if "commander" in pkg_data.get("bin", {}) or "bin" in pkg_data:
                    archetypes.add(ProjectArchetype.CLI_TOOL)
                if "exports" in pkg_data and not archetypes:
                    archetypes.add(ProjectArchetype.LIBRARY_PACKAGE)
            except Exception:
                pass

        # 3. Python manifests
        if os.path.exists(req_txt) or os.path.exists(pyproject):
            deps_str = ""
            if os.path.exists(pyproject):
                try:
                    with open(pyproject, 'r', encoding='utf-8', errors='ignore') as f:
                        deps_str += " " + f.read().lower()
                except Exception:
                    pass
            if os.path.exists(req_txt):
                try:
                    with open(req_txt, 'r', encoding='utf-8', errors='ignore') as f:
                        deps_str += " " + f.read().lower()
                except Exception:
                    pass
            if evidence:
                deps_str += " " + " ".join(evidence.dependencies).lower()

            if "torch" in deps_str or "transformers" in deps_str or "langchain" in deps_str or "openai" in deps_str:
                archetypes.add(ProjectArchetype.ML_AI)
            if any(k in deps_str for k in ["airflow", "dbt", "pyspark", "dagster", "kafka", "pyarrow", "polars", "duckdb", "spark"]):
                archetypes.add(ProjectArchetype.DATA_PIPELINE)
            if "fastapi" in deps_str or "django" in deps_str or "flask" in deps_str or "uvicorn" in deps_str:
                if not any(a in [ProjectArchetype.FULLSTACK_MONOLITH, ProjectArchetype.WEB_FRONTEND] for a in archetypes):
                    archetypes.add(ProjectArchetype.BACKEND_API)
            if "click" in deps_str or "typer" in deps_str or "argparse" in deps_str:
                archetypes.add(ProjectArchetype.CLI_TOOL)

        # 4. Microservices / Containers
        if os.path.exists(docker_compose) or os.path.exists(os.path.join(workspace_dir, "docker-compose.yaml")):
            archetypes.add(ProjectArchetype.MICROSERVICE)

        # 5. Static site
        if os.path.exists(astro_cfg) or os.path.exists(os.path.join(workspace_dir, "hugo.toml")):
            archetypes.add(ProjectArchetype.STATIC_SITE)

        # Fallbacks
        if not archetypes:
            if evidence and (evidence.db_entities or evidence.api_routes or evidence.ui_components):
                archetypes.add(ProjectArchetype.FULLSTACK_MONOLITH)
            else:
                archetypes.add(ProjectArchetype.GREENFIELD)

        return sorted(list(archetypes), key=lambda a: a.value)


class ScopeClassifier:
    """Classifies prompt intent into TRIVIAL, MINOR, MODERATE, or MAJOR complexity tiers."""

    @classmethod
    def classify(cls, raw_request: str, intent: IntentExtraction) -> ScopeTier:
        req_lower = raw_request.lower().strip()

        # Trivial checks: minor fixes, typos, single line requests
        if len(req_lower) <= 20 and not any(w in req_lower for w in ["build", "create", "implement", "add", "system"]):
            return ScopeTier.TRIVIAL
        if any(kw in req_lower for kw in ["fix typo", "update readme", "add comment", "format code", "rename variable"]):
            return ScopeTier.TRIVIAL

        feature_count = len(intent.primary_features)
        verb_count = len(intent.action_verbs)

        if feature_count <= 1 and verb_count <= 1:
            return ScopeTier.MINOR
        elif feature_count <= 4:
            return ScopeTier.MODERATE
        else:
            return ScopeTier.MAJOR


# --- Archetype-Aware Impact Tiers ---

ARCHETYPE_IMPACT_TIERS: Dict[str, List[str]] = {
    "fullstack":       ["frontend", "backend", "database", "auth", "api_routes", "navigation"],
    "web_frontend":    ["ui_components", "routing", "state_mgmt", "styling", "assets"],
    "backend_api":     ["controllers", "services", "database", "auth", "middleware", "validation"],
    "cli_tool":        ["commands", "args_parser", "output_format", "config", "stdin_stdout"],
    "library":         ["public_api", "internals", "types", "docs", "tests", "bundling"],
    "data_pipeline":   ["ingestion", "transformation", "storage", "scheduling", "monitoring"],
    "ml_ai":           ["model", "training", "inference", "data_prep", "evaluation", "serving"],
    "mobile_hybrid":   ["frontend", "native_bridge", "offline_storage", "push_notifications"],
    "microservice":    ["services", "contracts", "message_bus", "gateway", "observability"],
    "greenfield":      ["frontend", "backend", "database", "auth", "infrastructure"],
}


# --- Dynamic Rule Registry ---

@dataclass
class InferenceRule:
    id: str
    name: str
    archetypes: List[str]  # ["*"] = all, ["fullstack", "backend_api"] = specific
    description: str
    assumption_type: str  # ux, behavior, data, api, permission, architecture
    threshold: DecisionThreshold
    category: RequirementCategory
    affects: List[str]
    why_chain: List[str]


UNIVERSAL_RULE_REGISTRY: List[InferenceRule] = [
    # Universal Rules
    InferenceRule("UNI-001", "Structured Logging", ["*"], "Implement structured JSON logging across all execution paths", "architecture", DecisionThreshold.AUTO_DECIDE, RequirementCategory.SYSTEM_INVARIANT, ["backend", "observability"], ["All non-trivial projects require structured logging for debugging"]),
    InferenceRule("UNI-002", "Input Sanitization", ["*"], "Sanitize and validate all external inputs at system boundaries", "permission", DecisionThreshold.AUTO_DECIDE, RequirementCategory.SYSTEM_INVARIANT, ["backend", "validation"], ["Input sanitization protects against injection and validation defects"]),
    InferenceRule("UNI-003", "Graceful Error Handling", ["*"], "Catch unhandled exceptions and return structured error envelopes", "behavior", DecisionThreshold.AUTO_DECIDE, RequirementCategory.SYSTEM_INVARIANT, ["backend", "frontend"], ["Unhandled exceptions lead to process crashes or blank UI screens"]),
    InferenceRule("UNI-004", "Automated Testing Suite", ["*"], "Maintain unit and integration test coverage for primary workflows", "behavior", DecisionThreshold.AUTO_DECIDE, RequirementCategory.SYSTEM_INVARIANT, ["tests", "backend", "frontend"], ["Automated tests guarantee regressions are caught during CI"]),
    InferenceRule("UNI-005", "Environment Config Management", ["*"], "Decouple configuration from code using environment variables", "architecture", DecisionThreshold.AUTO_DECIDE, RequirementCategory.ARCHITECTURAL_CONSTRAINT, ["config", "backend", "infrastructure"], ["Hardcoded secrets/config violate 12-Factor app methodology"]),

    # Web & Fullstack Rules
    InferenceRule("WEB-001", "Breadcrumb Navigation", ["fullstack", "web_frontend"], "Include breadcrumb navigation for deeply nested pages", "ux", DecisionThreshold.AUTO_DECIDE, RequirementCategory.UX_DERIVATION, ["frontend", "navigation"], ["Nested navigation depth >= 2 requires breadcrumbs for UX clarity"]),
    InferenceRule("WEB-002", "Server-Side Pagination", ["fullstack", "web_frontend", "backend_api"], "Add server-side pagination to list views", "ux", DecisionThreshold.AUTO_DECIDE, RequirementCategory.UX_DERIVATION, ["frontend", "backend"], ["Large datasets degrade UI rendering without pagination"]),
    InferenceRule("WEB-003", "Role-Based Access Control", ["fullstack", "backend_api"], "Implement RBAC middleware and client route guards", "permission", DecisionThreshold.AUTO_DECIDE, RequirementCategory.SYSTEM_INVARIANT, ["backend", "auth", "frontend"], ["Multi-role applications require server & client access control"]),
    InferenceRule("WEB-004", "React Error Boundaries", ["fullstack", "web_frontend"], "Wrap page views in Error Boundary components and empty-state fallbacks", "ux", DecisionThreshold.AUTO_DECIDE, RequirementCategory.SYSTEM_INVARIANT, ["frontend"], ["Error boundaries prevent white-screen crashes on client errors"]),
    InferenceRule("WEB-005", "Registration Gate", ["fullstack"], "Public self-registration requires explicit confirmation. MUST_ASK user.", "permission", DecisionThreshold.MUST_ASK, RequirementCategory.PRODUCT_REQUIREMENT, ["frontend", "auth"], ["Admin-created accounts are standard unless self-registration is explicitly desired"]),
    InferenceRule("WEB-006", "Soft Delete", ["fullstack", "backend_api"], "Implement soft-delete due to audit significance of data entities", "data", DecisionThreshold.PROBABLY_DECIDE, RequirementCategory.ARCHITECTURAL_CONSTRAINT, ["backend", "database"], ["Permanent deletion risks corruption of audit history"]),
    InferenceRule("WEB-007", "Workflow Endpoints", ["fullstack", "backend_api"], "Use state-machine workflow API endpoints over raw CRUD for controlled entities", "architecture", DecisionThreshold.AUTO_DECIDE, RequirementCategory.ARCHITECTURAL_CONSTRAINT, ["backend", "database"], ["Controlled entities need explicit state transitions"]),

    # API Rules
    InferenceRule("API-001", "API Rate Limiting", ["backend_api", "fullstack"], "Enforce rate limiting on public API endpoints", "permission", DecisionThreshold.AUTO_DECIDE, RequirementCategory.SYSTEM_INVARIANT, ["backend", "middleware"], ["Rate limiting protects API endpoints against abuse and DDoS"]),
    InferenceRule("API-002", "API Endpoint Versioning", ["backend_api"], "Use URI or header versioning (/api/v1/) for endpoints", "architecture", DecisionThreshold.AUTO_DECIDE, RequirementCategory.ARCHITECTURAL_CONSTRAINT, ["backend"], ["API versioning prevents breaking existing clients"]),

    # CLI Rules
    InferenceRule("CLI-001", "Command Help Text", ["cli_tool"], "Provide clear --help documentation for all commands and subcommands", "ux", DecisionThreshold.AUTO_DECIDE, RequirementCategory.UX_DERIVATION, ["args_parser"], ["CLI tools must be self-documenting"]),
    InferenceRule("CLI-002", "Standard Exit Codes", ["cli_tool"], "Use standard POSIX exit codes (0=success, 1=error, 2=usage)", "behavior", DecisionThreshold.AUTO_DECIDE, RequirementCategory.SYSTEM_INVARIANT, ["commands"], ["Exit codes allow shell scripts to handle CLI outcomes"]),

    # Library Rules
    InferenceRule("LIB-001", "Public API Surface", ["library"], "Expose clean index exports and encapsulate private internals", "architecture", DecisionThreshold.AUTO_DECIDE, RequirementCategory.ARCHITECTURAL_CONSTRAINT, ["public_api"], ["Libraries require explicit public boundary design"]),
    InferenceRule("LIB-002", "TypeScript Definitions", ["library"], "Generate comprehensive .d.ts type declarations", "ux", DecisionThreshold.AUTO_DECIDE, RequirementCategory.PRODUCT_REQUIREMENT, ["types"], ["Type definitions enable IDE autocompletion for package consumers"]),

    # Data Pipeline Rules
    InferenceRule("DATA-001", "Pipeline Idempotency", ["data_pipeline"], "Ensure all pipeline transformation steps are strictly idempotent", "architecture", DecisionThreshold.AUTO_DECIDE, RequirementCategory.SYSTEM_INVARIANT, ["transformation"], ["Idempotency enables safe retries on pipeline failures"]),

    # ML/AI Rules
    InferenceRule("ML-001", "Model Version Tracking", ["ml_ai"], "Log model weights, hyperparameter configs, and evaluation metrics", "data", DecisionThreshold.AUTO_DECIDE, RequirementCategory.SYSTEM_INVARIANT, ["model"], ["Reproducibility requires versioning model artifacts"]),

    # Microservice Rules
    InferenceRule("MICRO-001", "Service Contract Schema", ["microservice"], "Define strict inter-service contracts using gRPC/Proto or OpenAPI", "api", DecisionThreshold.AUTO_DECIDE, RequirementCategory.ARCHITECTURAL_CONSTRAINT, ["contracts"], ["Microservices require strong contract boundaries"]),

    # Mobile Rules
    InferenceRule("MOBILE-001", "Offline Storage Sync", ["mobile_hybrid"], "Implement local SQLite/IndexedDB caching for offline resilience", "data", DecisionThreshold.AUTO_DECIDE, RequirementCategory.UX_DERIVATION, ["offline_storage"], ["Mobile apps must handle network connectivity loss gracefully"]),

    # Cross-Cutting Rules
    InferenceRule("XCUT-001", "Security Headers", ["fullstack", "backend_api", "web_frontend"], "Configure CSP, HSTS, and X-Frame-Options security headers", "permission", DecisionThreshold.AUTO_DECIDE, RequirementCategory.SYSTEM_INVARIANT, ["backend", "middleware"], ["Security headers mitigate XSS and clickjacking"]),
    InferenceRule("XCUT-002", "CORS Configuration", ["fullstack", "backend_api"], "Configure explicit CORS origin whitelisting", "permission", DecisionThreshold.AUTO_DECIDE, RequirementCategory.SYSTEM_INVARIANT, ["auth", "backend"], ["Unrestricted CORS exposes API endpoints to unauthorized domains"]),
    InferenceRule("XCUT-003", "Accessibility (a11y)", ["fullstack", "web_frontend", "mobile_hybrid"], "Ensure ARIA tags, color contrast compliance, and keyboard focus states", "ux", DecisionThreshold.AUTO_DECIDE, RequirementCategory.UX_DERIVATION, ["frontend"], ["UI applications must be accessible to users with screen readers"]),
]


# --- Engines ---

class CapabilityExpansionEngine:
    """Evidence-driven expansion chain: Role → Capability → Entity → Action → Page/Module → UX."""

    VERB_TO_ACTIONS = {
        "create": ["create_form", "submit_create"],
        "edit": ["edit_form", "submit_update"],
        "update": ["edit_form", "submit_update"],
        "delete": ["delete_confirm", "execute_delete"],
        "view": ["detail_view"],
        "list": ["list_view", "search", "filter"],
        "manage": ["list_view", "create_form", "edit_form", "detail_view"],
        "schedule": ["calendar_view", "create_schedule"],
        "enroll": ["enrollment_form", "enrollment_list"],
        "approve": ["approval_queue", "approve_action"],
        "report": ["report_view", "export_report"],
        "generate": ["generation_form", "output_view"],
        "assign": ["assignment_form", "assignment_list"],
        "upload": ["upload_form", "file_list"],
        "download": ["download_action"],
        "search": ["search_view", "search_results"],
        "export": ["export_action", "export_config"],
        "import": ["import_form", "import_preview"],
        "register": ["registration_form"],
        "login": ["login_form"],
        "logout": ["logout_action"],
        "run": ["execute_command"],
        "parse": ["argument_parser"],
        "train": ["training_pipeline"],
        "ingest": ["data_ingestion"],
    }

    def expand(self, intent: IntentExtraction, evidence: ProjectEvidence, archetypes: List[ProjectArchetype]) -> List[SynthesizedRequirement]:
        expanded_reqs = []
        req_counter = 0

        is_cli_or_lib = any(a in [ProjectArchetype.CLI_TOOL, ProjectArchetype.LIBRARY_PACKAGE, ProjectArchetype.DATA_PIPELINE] for a in archetypes)

        # Phase 1: Role → Capability mapping
        for role in intent.target_roles:
            for feature in intent.primary_features:
                for verb in intent.action_verbs:
                    actions = self.VERB_TO_ACTIONS.get(verb, ["generic_action"])
                    for action in actions:
                        req_counter += 1
                        page_name = f"{feature}_{action}".replace(" ", "_").lower()
                        affects_list = ["cli", "internals"] if is_cli_or_lib else ["frontend", "backend"]
                        expanded_reqs.append(SynthesizedRequirement(
                            id=f"REQ-EXP-{req_counter}",
                            description=f"Role '{role}' needs {action} capability for {feature}",
                            type=RequirementType.DERIVED,
                            category=RequirementCategory.PRODUCT_REQUIREMENT,
                            action=ArtifactAction.CREATE,
                            decision_threshold=DecisionThreshold.AUTO_DECIDE,
                            why_chain=[
                                f"Step 1: Identified role '{role}' from user request",
                                f"Step 2: Mapped verb '{verb}' to action '{action}'",
                                f"Step 3: Feature '{feature}' requires module '{page_name}'",
                                f"Step 4: Derived requirement for {role} to {action} on {feature}"
                            ],
                            affects=affects_list,
                            assumption_type="behavior"
                        ))

        # Phase 2: Entity → Action expansion from existing DB schema
        for entity in evidence.db_entities:
            entity_name = entity.get("name", "")
            entity_fields = entity.get("fields", [])
            if entity_name:
                req_counter += 1
                expanded_reqs.append(SynthesizedRequirement(
                    id=f"REQ-EXP-{req_counter}",
                    description=f"Provide list view for existing entity '{entity_name}'",
                    type=RequirementType.SUPPORTED,
                    category=RequirementCategory.PRODUCT_REQUIREMENT,
                    action=ArtifactAction.REUSE,
                    decision_threshold=DecisionThreshold.AUTO_DECIDE,
                    evidence=[EvidenceReference(
                        source_file=entity.get("source", "database"),
                        reference_text=f"Entity '{entity_name}' with {len(entity_fields)} fields"
                    )],
                    why_chain=[
                        f"Entity '{entity_name}' exists in project DB schema",
                        "List/view derived as read-only access (CRUD not auto-derived without explicit verb)"
                    ],
                    affects=["frontend", "backend", "database"],
                    assumption_type="data"
                ))

        # Phase 3: UX components from existing UI components
        for comp in evidence.ui_components:
            req_counter += 1
            expanded_reqs.append(SynthesizedRequirement(
                id=f"REQ-EXP-{req_counter}",
                description=f"Reuse existing UI component '{comp}'",
                type=RequirementType.REUSE,
                category=RequirementCategory.UX_DERIVATION,
                action=ArtifactAction.REUSE,
                decision_threshold=DecisionThreshold.AUTO_DECIDE,
                evidence=[EvidenceReference(source_file="ui_scan", reference_text=f"Component '{comp}' found in workspace")],
                why_chain=[f"UI component '{comp}' already exists in workspace scan"],
                affects=["frontend"]
            ))

        return expanded_reqs


class DeclarativePredicateEvaluator:
    """Evaluates rule applicability dynamically without hardcoded Python if/else branches."""

    @classmethod
    def evaluate_rule(
        cls,
        rule: InferenceRule,
        requirements: List[SynthesizedRequirement],
        evidence: ProjectEvidence,
        archetypes: List[ProjectArchetype],
        scope_tier: Optional[ScopeTier] = None
    ) -> bool:
        archetype_values = [a.value for a in archetypes]
        if "*" not in rule.archetypes and not any(a in rule.archetypes for a in archetype_values):
            return False

        # Scope guard: TRIVIAL scope bypasses universal infrastructure overhead
        if scope_tier == ScopeTier.TRIVIAL and (rule.id.startswith("UNI-") or rule.id.startswith("XCUT-")):
            return False

        req_descriptions_lower = " ".join(r.description.lower() for r in requirements)

        if rule.id == "WEB-001":
            return "depth >= 2" in req_descriptions_lower or sum(1 for r in requirements if "detail_view" in r.description.lower()) >= 2
        elif rule.id == "WEB-002":
            return sum(1 for r in requirements if "list_view" in r.description.lower() or "list view" in r.description.lower()) >= 2
        elif rule.id == "WEB-003":
            roles = set(re.findall(r'role\s+[\'\"]?(\w+)[\'\"]?', req_descriptions_lower))
            return len(roles) >= 2 or any(r in req_descriptions_lower for r in ["admin", "instructor", "manager", "examiner"])
        elif rule.id == "WEB-004":
            return any("frontend" in r.affects for r in requirements)
        elif rule.id == "WEB-005":
            has_reg = "register" in req_descriptions_lower or "registration" in req_descriptions_lower
            has_self = "self-registration" in req_descriptions_lower or "sign up" in req_descriptions_lower
            return has_reg and not has_self
        elif rule.id == "WEB-006":
            has_audit = any("audit" in ent.get("name", "").lower() for ent in evidence.db_entities)
            return has_audit and "delete" in req_descriptions_lower
        elif rule.id == "WEB-007":
            workflow_verbs = ["approve", "schedule", "assign", "enroll", "generate", "triage", "reconcile", "prescribe", "provision"]
            return any(v in req_descriptions_lower for v in workflow_verbs)

        return True


class DerivedInferenceEngine:
    """Universal data-driven inference engine matching rules against active project archetypes."""

    def __init__(self):
        self.rules = UNIVERSAL_RULE_REGISTRY

    def apply_rules(self, requirements: List[SynthesizedRequirement], evidence: ProjectEvidence, archetypes: List[ProjectArchetype], scope_tier: Optional[ScopeTier] = None) -> List[SynthesizedRequirement]:
        inferred = []
        archetype_values = [a.value for a in archetypes]

        applicable_rules = [
            r for r in self.rules
            if "*" in r.archetypes or any(a in r.archetypes for a in archetype_values)
        ]

        for rule in applicable_rules:
            if DeclarativePredicateEvaluator.evaluate_rule(rule, requirements, evidence, archetypes, scope_tier):
                inferred.append(SynthesizedRequirement(
                    id=f"REQ-INF-{rule.id}",
                    description=rule.description,
                    type=RequirementType.DERIVED if rule.threshold != DecisionThreshold.MUST_ASK else RequirementType.UNKNOWN,
                    category=rule.category,
                    action=ArtifactAction.CREATE if rule.threshold == DecisionThreshold.AUTO_DECIDE else ArtifactAction.MODIFY,
                    decision_threshold=rule.threshold,
                    why_chain=rule.why_chain,
                    affects=rule.affects,
                    assumption_type=rule.assumption_type
                ))

        # Rule 8: Documented API Route binding (evidence-supported implementation)
        for existing_route in evidence.api_routes:
            existing_path = existing_route.get("path", "")
            if existing_path:
                for r in requirements:
                    if existing_path in r.description:
                        r.type = RequirementType.SUPPORTED
                        r.action = ArtifactAction.EXTEND
                        r.evidence.append(EvidenceReference(
                            source_file=existing_route.get("source", "docs/architecture.md"),
                            reference_text=f"Documented route: {existing_route.get('method', '?')} {existing_path}"
                        ))
                        r.why_chain.append(f"Bound directly to documented workspace API contract: {existing_path}")

        return inferred


class RequirementGraph:
    """Graph of requirement nodes with dependencies, consequences, and orphan detection."""
    def __init__(self):
        self.nodes: Dict[str, SynthesizedRequirement] = {}

    def add_node(self, req: SynthesizedRequirement):
        self.nodes[req.id] = req

    def add_dependency(self, source_id: str, target_id: str):
        if source_id in self.nodes and target_id in self.nodes:
            if target_id not in self.nodes[source_id].depends_on:
                self.nodes[source_id].depends_on.append(target_id)
            if source_id not in self.nodes[target_id].consequences:
                self.nodes[target_id].consequences.append(source_id)

    def detect_orphans(self) -> List[SynthesizedRequirement]:
        orphans = []
        for req_id, req in self.nodes.items():
            if not req.depends_on and not req.consequences:
                if req.type not in [RequirementType.EXPLICIT, RequirementType.SUPPORTED]:
                    orphans.append(req)
        return orphans


class SemanticGate:
    """Evaluates semantic validity, computes gate results, and dynamically scales assumption budget."""
    ASSUMPTION_WEIGHTS = {
        "ux": 1,
        "behavior": 2,
        "data": 3,
        "api": 3,
        "permission": 4,
        "architecture": 5
    }
    BASE_MAX_WEIGHT = 30

    @staticmethod
    def validate_dict(spec_dict: Dict[str, Any], workspace_dir: Optional[str] = None) -> Dict[str, Any]:
        errors = []
        has_roles = spec_dict.get("has_roles", False)
        has_role_analysis = spec_dict.get("has_role_analysis", True)
        if has_roles and not has_role_analysis:
            errors.append("Roles detected but no role capability analysis performed.")

        has_ui = spec_dict.get("has_ui_requirements", False)
        affected = spec_dict.get("affected", spec_dict.get("affected_systems", {}))
        if has_ui and not affected.get("frontend") and not affected.get("ui_components"):
            errors.append("UI requirements exist but no frontend impact declared.")

        gate_result = spec_dict.get("gate_result", "")
        if gate_result == "BLOCKED":
            errors.append("Gate result is BLOCKED.")

        return {"passed": len(errors) == 0, "errors": errors}

    def _compute_budget(self, evidence: Optional[ProjectEvidence], archetypes: List[ProjectArchetype], scope_tier: Optional[ScopeTier] = None, req_count: int = 0) -> int:
        scope_budgets = {
            ScopeTier.TRIVIAL: 15,
            ScopeTier.MINOR: 25,
            ScopeTier.MODERATE: 45,
            ScopeTier.MAJOR: 75,
        }
        budget = scope_budgets.get(scope_tier, self.BASE_MAX_WEIGHT)

        if evidence:
            entity_count = len(evidence.db_entities)
            route_count = len(evidence.api_routes)
            page_count = len(getattr(evidence, 'discovered_pages', []))

            if entity_count > 5:
                budget += 10
            if entity_count > 15:
                budget += 10
            if route_count > 10:
                budget += 10
            if page_count > 5:
                budget += 10
            if page_count > 15:
                budget += 15

        complex_archetypes = {ProjectArchetype.MICROSERVICE, ProjectArchetype.MONOREPO, ProjectArchetype.FULLSTACK_MONOLITH, ProjectArchetype.GREENFIELD}
        if any(a in complex_archetypes for a in (archetypes or [])):
            budget += 15

        if req_count > 30:
            budget += 15
        if req_count > 60:
            budget += 20

        return min(budget, 150)

    def evaluate(self, requirements: List[SynthesizedRequirement], evidence: ProjectEvidence, archetypes: Optional[List[ProjectArchetype]] = None, scope_tier: Optional[ScopeTier] = None) -> Tuple[GateResult, int]:
        archetypes = archetypes or [ProjectArchetype.FULLSTACK_MONOLITH]
        budget = self._compute_budget(evidence, archetypes, scope_tier=scope_tier, req_count=len(requirements))

        # Cumulative assumption risk score across speculative derived requirements (excluding evidence-backed ones)
        total_weight = sum(
            self.ASSUMPTION_WEIGHTS.get(req.assumption_type, 1)
            for req in requirements
            if req.type in [RequirementType.DERIVED, RequirementType.UNKNOWN, RequirementType.OPTIONAL]
            and not req.evidence
        )

        has_must_stop = False
        has_must_ask = False
        has_conflict = False

        for req in requirements:
            if req.decision_threshold == DecisionThreshold.MUST_STOP:
                has_must_stop = True
            elif req.decision_threshold == DecisionThreshold.MUST_ASK:
                has_must_ask = True

            if req.type == RequirementType.CONFLICT:
                has_conflict = True

        if has_must_stop or has_conflict or total_weight > budget:
            return GateResult.BLOCKED, total_weight

        if has_must_ask:
            return GateResult.PASS_WITH_DECISIONS, total_weight

        return GateResult.PASS, total_weight


# --- Main SpecSynthesisEngine ---

# --- Dynamic Linguistic & Workspace Vocabulary Engines (V3.2) ---

class WorkspaceDocumentScanner:
    """
    Format-based workspace document scanner.
    Discovers entities, roles, routes, pages, and permissions from ANY workspace
    by scanning file formats (*.md tables, SQL DDL, Prisma models, framework page trees, TS/Py enums).
    Zero hardcoded file names.
    """

    EXCLUDE_DIRS = {"node_modules", ".git", ".next", "dist", "build", "__pycache__", ".vercel", ".pytest_cache", ".agents"}

    @classmethod
    def _find_files(cls, workspace_dir: str, extensions: Tuple[str, ...], max_depth: int = 3, max_size_kb: int = 250) -> List[str]:
        matched = []
        if not os.path.exists(workspace_dir):
            return matched
        
        base_depth = workspace_dir.rstrip(os.sep).count(os.sep)
        for root, dirs, files in os.walk(workspace_dir):
            dirs[:] = [d for d in dirs if d not in cls.EXCLUDE_DIRS]
            current_depth = root.count(os.sep) - base_depth
            if current_depth > max_depth:
                continue
            for f in files:
                if any(f.endswith(ext) for ext in extensions):
                    full_path = os.path.join(root, f)
                    try:
                        if os.path.getsize(full_path) <= max_size_kb * 1024:
                            matched.append(full_path)
                    except Exception:
                        pass
        return matched

    @classmethod
    def parse_markdown_tables(cls, filepath: str, evidence: ProjectEvidence) -> None:
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            table_blocks = re.findall(r'(\|[^\n]+\|\n\|[\s:\-\|]+\|\n(?:\|[^\n]+\|\n?)+)', content)
            for block in table_blocks:
                lines = [l.strip() for l in block.strip().split('\n') if l.strip()]
                if len(lines) < 3:
                    continue
                headers = [h.strip().lower() for h in lines[0].split('|')[1:-1]]
                
                # Role / Permission Matrix detector
                is_role_table = any(h in ['user role', 'role', 'permitted views', 'permitted routes', 'permissions', 'access'] for h in headers)
                # Field Reference / Schema table detector
                is_schema_table = any(h in ['field', 'column', 'data type', 'type', 'entity', 'table'] for h in headers)

                for row_line in lines[2:]:
                    cells = [c.strip() for c in row_line.split('|')[1:-1]]
                    if len(cells) != len(headers):
                        continue
                    row_dict = dict(zip(headers, cells))
                    
                    if is_role_table:
                        role_val = row_dict.get('role') or row_dict.get('user role')
                        views_val = row_dict.get('permitted views') or row_dict.get('permitted routes') or row_dict.get('views')
                        if role_val:
                            clean_role = role_val.replace('*', '').strip()
                            evidence.auth_permissions.append(clean_role)
                            if views_val:
                                evidence.role_permissions.append({
                                    "role": clean_role,
                                    "views": views_val,
                                    "source": os.path.basename(filepath)
                                })
                    elif is_schema_table:
                        entity_val = row_dict.get('entity') or row_dict.get('table') or row_dict.get('form')
                        field_val = row_dict.get('field') or row_dict.get('column') or row_dict.get('input fields')
                        if entity_val:
                            clean_entity = entity_val.replace('*', '').strip()
                            fields = [f.strip() for f in (field_val or '').split(',') if f.strip()]
                            evidence.db_entities.append({
                                "name": clean_entity,
                                "fields": fields,
                                "source": os.path.basename(filepath)
                            })
        except Exception as e:
            logger.debug(f"[WorkspaceDocumentScanner] Markdown parse error in {filepath}: {e}")

    @classmethod
    def parse_sql_blocks(cls, filepath: str, evidence: ProjectEvidence) -> None:
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            table_matches = re.findall(r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-zA-Z0-9_\"\.]+)\s*\(([\s\S]*?)\);', content, re.IGNORECASE)
            for table_name, body in table_matches:
                clean_name = table_name.strip('"`\'').split('.')[-1]
                fields = []
                for line in body.split('\n'):
                    line = line.strip()
                    if line and not line.startswith('--') and not line.upper().startswith(('CONSTRAINT', 'PRIMARY', 'FOREIGN', 'UNIQUE', 'KEY', 'INDEX')):
                        parts = line.split()
                        if parts:
                            field_name = parts[0].strip('"`\'')
                            if field_name.isalnum() or '_' in field_name:
                                fields.append(field_name)
                evidence.db_entities.append({
                    "name": clean_name,
                    "fields": fields[:20],
                    "source": os.path.basename(filepath)
                })
        except Exception as e:
            logger.debug(f"[WorkspaceDocumentScanner] SQL parse error in {filepath}: {e}")

    @classmethod
    def parse_prisma_schema(cls, filepath: str, evidence: ProjectEvidence) -> None:
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            models = re.findall(r'model\s+([a-zA-Z0-9_]+)\s*\{([^}]+)\}', content)
            for model_name, body in models:
                fields = []
                for line in body.split('\n'):
                    line = line.strip()
                    if line and not line.startswith('//') and not line.startswith('@@'):
                        parts = line.split()
                        if parts:
                            fields.append(parts[0])
                evidence.db_entities.append({
                    "name": model_name,
                    "fields": fields[:20],
                    "source": "schema.prisma"
                })
        except Exception as e:
            logger.debug(f"[WorkspaceDocumentScanner] Prisma parse error in {filepath}: {e}")

    @classmethod
    def discover_pages(cls, workspace_dir: str) -> List[str]:
        pages = set()
        candidate_dirs = ["pages", "app", "src/pages", "src/app", "routes", "views", "src/routes", "src/views"]
        for c_dir in candidate_dirs:
            target = os.path.join(workspace_dir, c_dir.replace("/", os.sep))
            if os.path.exists(target) and os.path.isdir(target):
                for root, _, files in os.walk(target):
                    for f in files:
                        if f.endswith(('.tsx', '.jsx', '.vue', '.svelte', '.ts', '.js', '.py', '.html')) and not f.startswith('_') and not f.startswith('.'):
                            rel = os.path.relpath(os.path.join(root, f), target)
                            page_id = rel.replace(os.sep, '/').split('.')[0]
                            if page_id not in ['index', 'main', 'app', 'layout', 'vite-env.d']:
                                pages.add(page_id)
        return sorted(list(pages))

    @classmethod
    def parse_enums(cls, filepath: str, evidence: ProjectEvidence) -> None:
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            # TypeScript enums: enum Role { ADMIN, STUDENT }
            ts_enums = re.findall(r'enum\s+([a-zA-Z0-9_]+)\s*\{([^}]+)\}', content)
            for enum_name, body in ts_enums:
                if any(kw in enum_name.lower() for kw in ['role', 'permission', 'access', 'user']):
                    values = re.findall(r'([a-zA-Z0-9_]+)\s*=', body) or [v.strip() for v in body.split(',') if v.strip()]
                    for val in values:
                        clean_val = val.strip().strip('"`\'')
                        if clean_val and clean_val not in evidence.auth_permissions:
                            evidence.auth_permissions.append(clean_val.lower())

            # Python enums: class Role(Enum):
            py_enums = re.findall(r'class\s+([a-zA-Z0-9_]+)\s*\([^)]*Enum[^)]*\)\s*:\s*\n((?:\s+[a-zA-Z0-9_]+\s*=\s*[^\n]+\n)+)', content)
            for enum_name, body in py_enums:
                if any(kw in enum_name.lower() for kw in ['role', 'permission', 'access', 'user']):
                    values = re.findall(r'([a-zA-Z0-9_]+)\s*=', body)
                    for val in values:
                        if val and val not in evidence.auth_permissions:
                            evidence.auth_permissions.append(val.lower())
        except Exception:
            pass

    @classmethod
    def parse_markdown_deep_contracts(cls, filepath: str, evidence: ProjectEvidence) -> None:
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            # 1. Parse explicit REST routes: e.g. "PATCH /batches/{id}/advance-semester" or "GET /students/{id}/section-history"
            # 1. Parse explicit REST routes anywhere in markdown (bullets, tables, paragraphs)
            routes = re.findall(r'\b(GET|POST|PUT|PATCH|DELETE)\s+([\/][a-zA-Z0-9_\-\/\{\}:]+)', content)
            for method, path in routes:
                if not any(r.get("path") == path and r.get("method") == method for r in evidence.api_routes):
                    evidence.api_routes.append({"method": method, "path": path, "source": os.path.basename(filepath)})

            # 2. Parse declared roles from RBAC headers/tables
            for line in content.split('\n'):
                if line.strip().startswith('|'):
                    cells = [c.strip() for c in line.split('|') if c.strip()]
                    if cells:
                        first_cell = cells[0].lower().strip('`* ')
                        for role_kw in ["super_admin", "super admin", "data entry operator", "data operator", "public visitor", "public_visitor", "student", "faculty", "hod", "operator", "admin", "doctor", "nurse", "patient", "manager", "instructor", "tenant", "member"]:
                            if first_cell == role_kw or first_cell == role_kw + "s" or first_cell.startswith(role_kw + " ") or first_cell.startswith(role_kw + " /"):
                                clean_r = role_kw.replace(' ', '_')
                                if clean_r not in evidence.auth_permissions:
                                    evidence.auth_permissions.append(clean_r)
                                break

            # 3. Parse declared database models from markdown headers/bullets
            model_bullets = re.findall(r'[\*\-]\s*\*\*`?([a-zA-Z0-9_]+)`?\*\*\s*[:\(]', content)
            for m in model_bullets:
                if len(m) > 2 and not any(e.get("name") == m for e in evidence.db_entities):
                    evidence.db_entities.append({"name": m, "fields": [], "source": os.path.basename(filepath)})

        except Exception as e:
            logger.debug(f"[WorkspaceDocumentScanner] Markdown deep contracts error in {filepath}: {e}")

    @classmethod
    def full_document_discovery(cls, workspace_dir: str) -> ProjectEvidence:
        evidence = ProjectEvidence()

        # 1. Scan Markdown files (*.md)
        md_files = cls._find_files(workspace_dir, ('.md', '.markdown'))
        for md in md_files:
            cls.parse_markdown_tables(md, evidence)
            cls.parse_markdown_deep_contracts(md, evidence)
            cls.parse_sql_blocks(md, evidence)

        # 2. Scan SQL files (*.sql)
        sql_files = cls._find_files(workspace_dir, ('.sql',))
        for sql in sql_files:
            cls.parse_sql_blocks(sql, evidence)

        # 3. Scan Prisma schema files (*.prisma)
        prisma_files = cls._find_files(workspace_dir, ('.prisma',))
        for prisma in prisma_files:
            cls.parse_prisma_schema(prisma, evidence)

        # 4. Discover page/route framework directories
        evidence.discovered_pages = cls.discover_pages(workspace_dir)

        # 5. Scan code files for enums (*.ts, *.tsx, *.py)
        code_files = cls._find_files(workspace_dir, ('.ts', '.tsx', '.py'))
        for code in code_files:
            cls.parse_enums(code, evidence)

        # Deduplicate evidence fields cleanly
        unique_entities = []
        seen_entity_names = set()
        for ent in evidence.db_entities:
            name = ent.get("name", "").lower()
            if name and name not in seen_entity_names:
                seen_entity_names.add(name)
                unique_entities.append(ent)
        evidence.db_entities = unique_entities
        evidence.auth_permissions = sorted(list(dict.fromkeys(evidence.auth_permissions)))

        return evidence


class WorkspaceVocabularyScanner:
    """Discovers project-specific roles, verbs, and entities dynamically from workspace files."""

    @classmethod
    def extract_workspace_vocab(cls, evidence: ProjectEvidence) -> Dict[str, Set[str]]:
        vocab = {"roles": set(), "verbs": set(), "entities": set()}
        if not evidence:
            return vocab

        for ent in evidence.db_entities:
            name = ent.get("name", "")
            if name:
                vocab["entities"].add(name)

        for route in evidence.api_routes:
            path = route.get("path", "")
            method = route.get("method", "").lower()
            if method:
                vocab["verbs"].add(method)
            parts = [p for p in path.split("/") if p and not p.startswith(":") and not p.startswith("{")]
            for p in parts:
                if p not in ["api", "v1", "v2", "v3", "rest"]:
                    vocab["entities"].add(p)

        for perm in evidence.auth_permissions:
            vocab["roles"].add(perm.lower())

        return vocab


class DynamicLinguisticExtractor:
    """Zero-hardcode linguistic context parser for domain-agnostic role, verb, and entity extraction."""

    COMMON_ENGLISH_STOPWORDS = {
        "the", "be", "to", "of", "and", "a", "in", "that", "have", "i", "it", "for", "not",
        "on", "with", "he", "as", "you", "do", "at", "this", "but", "his", "by", "from",
        "they", "we", "say", "her", "she", "or", "an", "will", "my", "one", "all", "would",
        "there", "their", "what", "so", "up", "out", "if", "about", "who", "get", "which",
        "go", "me", "when", "make", "can", "like", "time", "no", "just", "him", "know",
        "take", "people", "into", "year", "your", "good", "some", "could", "them", "see",
        "other", "than", "then", "now", "look", "only", "come", "its", "over", "think",
        "also", "back", "after", "use", "two", "how", "our", "work", "first", "well",
        "way", "even", "new", "want", "because", "any", "these", "give", "day", "most",
        "us", "system", "build", "implement", "application", "platform", "project", "need"
    }

    @classmethod
    def extract_intent(cls, raw_request: str, workspace_vocab: Optional[Dict[str, Set[str]]] = None) -> IntentExtraction:
        request_lower = raw_request.lower()
        words = re.findall(r'[a-zA-Z0-9_\-]+', raw_request)
        words_lower = [w.lower() for w in words]

        # 1. Dynamic Role Extraction via Context Patterns
        target_roles = set()
        role_patterns = [
            r'(?:as\s+(?:a|an)\s+|for\s+)([a-zA-Z0-9_\-]+)',
            r'([a-zA-Z0-9_\-]+)\s+(?:can|should|must|will|needs?\s+to)\s+',
            r'([a-zA-Z0-9_\-]+)\s+(?:portal|dashboard|role|user|view|panel|screen|interface)',
            r'allow\s+([a-zA-Z0-9_\-]+)\s+to'
        ]
        for pat in role_patterns:
            for match in re.findall(pat, raw_request, re.IGNORECASE):
                role = match.lower().strip()
                if len(role) > 2 and role not in cls.COMMON_ENGLISH_STOPWORDS:
                    norm_role = role
                    if role.endswith('ies') and len(role) > 4:
                        norm_role = role[:-3] + 'y'
                    elif role.endswith('es') and len(role) > 4 and role[:-2].endswith(('s', 'x', 'z', 'ch', 'sh')):
                        norm_role = role[:-2]
                    elif role.endswith('s') and len(role) > 3 and not role.endswith('ss'):
                        norm_role = role[:-1]
                    if norm_role not in cls.COMMON_ENGLISH_STOPWORDS:
                        target_roles.add(norm_role)

        if workspace_vocab and "roles" in workspace_vocab:
            for w_role in workspace_vocab["roles"]:
                if w_role.lower() in request_lower:
                    target_roles.add(w_role.lower())

        if not target_roles:
            target_roles = ["user"]

        # 2. Dynamic Verb Extraction via Predicate Patterns
        action_verbs = set()
        verb_patterns = [
            r'^\s*([a-zA-Z]+)\b',
            r'\b(?:to|can|should|must|will|ability\s+to)\s+([a-zA-Z]+)\b',
            r'\b(create|edit|delete|view|list|manage|update|schedule|enroll|approve|reject|assign|generate|upload|download|search|export|import|register|login|logout|report|monitor|configure|submit|review|publish|archive|restore|grade|certify|notify|track|analyze|filter|sort|paginate|build|deploy|test|audit|verify|validate|run|parse|train|ingest|reconcile|triage|prescribe|provision|stream|mesh|tokenize)\b'
        ]
        for pat in verb_patterns:
            for match in re.findall(pat, raw_request, re.IGNORECASE):
                v = match.lower().strip()
                if len(v) > 2 and v not in cls.COMMON_ENGLISH_STOPWORDS:
                    action_verbs.add(v)

        if workspace_vocab and "verbs" in workspace_vocab:
            for w_verb in workspace_vocab["verbs"]:
                if w_verb.lower() in request_lower:
                    action_verbs.add(w_verb.lower())

        if not action_verbs:
            action_verbs = ["manage"]

        # 3. Dynamic Feature & Entity Extraction (Zero length discrimination on acronyms/technical tokens)
        domain_keywords = []
        primary_features = []
        seen = set()

        for w, w_low in zip(words, words_lower):
            if w_low in cls.COMMON_ENGLISH_STOPWORDS or w_low in action_verbs or w_low in target_roles:
                continue
            is_acronym = w.isupper() and len(w) >= 2
            is_capitalized = w[0].isupper() and len(w) >= 3
            is_feature_token = len(w_low) >= 3 or is_acronym

            if is_feature_token and w_low not in seen:
                seen.add(w_low)
                primary_features.append(w_low)
                if is_acronym or is_capitalized:
                    domain_keywords.append(w)

        if workspace_vocab and "entities" in workspace_vocab:
            for ent in workspace_vocab["entities"]:
                ent_low = ent.lower()
                if ent_low in request_lower and ent_low not in seen:
                    seen.add(ent_low)
                    primary_features.append(ent_low)
                    domain_keywords.append(ent)

        return IntentExtraction(
            raw_request=raw_request,
            primary_features=primary_features[:10],
            target_roles=list(target_roles),
            action_verbs=list(action_verbs),
            domain_keywords=list(set(domain_keywords))
        )


class StructuredPromptParser:
    """
    Clause-level prompt parser.
    Extracts role-capability bindings, multi-word phrases, and filters out non-functional qualifiers.
    Domain-agnostic (matches English sentence structure patterns, not domain terms).
    """

    QUALIFIER_WORDS = {
        'production-grade', 'production', 'grade', 'real-time', 'realtime',
        'modern', 'scalable', 'enterprise', 'complete', 'full', 'comprehensive',
        'robust', 'secure', 'advanced', 'basic', 'simple', 'complex',
        'zero-placeholder', 'strict', 'institutional', 'professional',
        'high-performance', 'lightweight', 'minimal', 'maximum', 'optimal',
        'automated', 'manual', 'custom', 'standard', 'legacy', 'new',
        'existing', 'current', 'updated', 'improved', 'enhanced', 'feature', 'system'
    }

    CLAUSE_PATTERNS = [
        # Pattern 1: "{Role} dashboard/portal/panel with/for/including {cap1}, {cap2}, {cap3}"
        r'([a-zA-Z0-9_\-\s]+?)\s+(?:dashboard|portal|panel|interface|module|page|view|screen|console|hub)\s+(?:with|for|including|featuring)\s+(.+?)(?:\.|\n|;|$)',
        # Pattern 2: "{Role}: {cap1}, {cap2}, {cap3}"
        r'^[\-\*]?\s*([a-zA-Z0-9_\-\s]+?):\s+(.+?)(?:\.|\n|;|$)',
        # Pattern 3: "As a {Role}, I can/should {caps}"
        r'[Aa]s\s+(?:a|an)\s+([a-zA-Z0-9_\-\s]+?),?\s+(?:I\s+)?(?:can|should|must|will|need\s+to)\s+(.+?)(?:\.|\n|;|$)',
        # Pattern 4: "{Role} with/for {caps}"
        r'([a-zA-Z0-9_\-\s]+?)\s+(?:with|for)\s+(.+?)(?:\.|\n|;|$)',
    ]

    COMMON_ABBREVIATIONS = {
        r'\bclg\b': 'college',
        r'\bdept\b': 'department',
        r'\bprofies\b': 'profiles',
        r'\bportak\b': 'portal',
        r'\bportel\b': 'portal',
        r'\bportl\b': 'portal',
        r'\bwuth\b': 'with',
        r'\bfir\b': 'for',
        r'\bsub\b': 'subject',
        r'\bsubs\b': 'subjects',
        r'\badmin\b': 'administrator',
        r'\bauth\b': 'authentication',
        r'\bmgmt\b': 'management',
        r'\bsys\b': 'system',
        r'\binfo\b': 'information',
        r'\bdoc\b': 'document',
        r'\bdocs\b': 'documents',
        r'\breq\b': 'requirement',
        r'\breqs\b': 'requirements',
        r'\brepo\b': 'repository',
    }

    @classmethod
    def normalize_prompt(cls, raw_request: str) -> str:
        text = raw_request
        for pattern, replacement in cls.COMMON_ABBREVIATIONS.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        text = re.sub(r'\s*,\s*', ', ', text)
        return text

    @classmethod
    def _clean_token(cls, token: str) -> str:
        t = token.strip().lower()
        t = re.sub(r'^[^\w]+|[^\w]+$', '', t)
        t = re.sub(r'^(?:build|create|make|implement|add|setup)\s+(?:a|an|the)?\s*', '', t)
        t = re.sub(r'^(?:a|an|the)\s+', '', t)
        t = re.sub(r'^n\s+', '', t)
        return t.strip()

    @classmethod
    def _extract_capabilities_from_chunk(cls, chunk: str) -> List[str]:
        parts = re.split(r',|\band\b|\bwith\b', chunk)
        capabilities = []
        for p in parts:
            clean_p = p.strip()
            words = [w for w in clean_p.split() if cls._clean_token(w) not in cls.QUALIFIER_WORDS and len(w) > 1]
            if words:
                cap_phrase = "_".join(w.lower() for w in words)
                if cap_phrase and len(cap_phrase) > 2:
                    capabilities.append(cap_phrase)
        return capabilities

    @classmethod
    def parse_request(cls, raw_request: str, workspace_vocab: Optional[Dict[str, Set[str]]] = None) -> StructuredIntent:
        normalized_request = cls.normalize_prompt(raw_request)
        bindings: List[RoleCapabilityBinding] = []
        seen_roles = set()

        lines = [line.strip() for line in normalized_request.split('\n') if line.strip()]
        for line in lines:
            matched_clause = False
            for pat in cls.CLAUSE_PATTERNS:
                matches = re.findall(pat, line, re.IGNORECASE)
                for role_raw, caps_raw in matches:
                    role_clean = cls._clean_token(role_raw)
                    if len(role_clean) >= 3 and role_clean not in cls.QUALIFIER_WORDS:
                        caps = cls._extract_capabilities_from_chunk(caps_raw)
                        if caps:
                            matched_clause = True
                            seen_roles.add(role_clean)
                            bindings.append(RoleCapabilityBinding(
                                role=role_clean,
                                capabilities=caps,
                                raw_clause=line
                            ))
                            break
                if matched_clause:
                    break

        NON_ROLE_STOP_WORDS = {
            'system', 'app', 'application', 'platform', 'management', 'portal', 'interface',
            'module', 'page', 'view', 'screen', 'console', 'hub', 'dashboard', 'feature',
            'service', 'tool', 'workflow', 'process', 'solution', 'software', 'database',
            'table', 'field', 'data', 'record', 'entry', 'list', 'item', 'details', 'info',
            'information', 'type', 'status', 'action', 'role', 'roles', 'user', 'users',
            'actor', 'actors', 'with', 'for', 'and', 'including', 'featuring', 'such', 'like'
        }

        # Generic linguistic role extraction from list clauses ("for X, Y, Z", "roles: X, Y, Z")
        role_enum_matches = re.findall(
            r'\b(?:roles?|for|actors?|users?|by|approved by)\s*[:=]?\s*([a-zA-Z0-9_\-\s,&\/]+?)(?:\.|\n|;|\bwith\b|\bincluding\b|\bwhere\b|\bcan\b|\bmust\b|\bshould\b|\bwill\b|\bto\b|\bonly\b|\bthat\b|$)',
            normalized_request,
            re.IGNORECASE
        )
        for enum_chunk in role_enum_matches:
            items = re.split(r',|\band\b|\b&\b|\bor\b|\bwhere\b|\bcan\b|\bmust\b|\bshould\b|\bwill\b|\bto\b|\bonly\b|\bthat\b', enum_chunk, flags=re.IGNORECASE)
            for item in items:
                sub_words = item.strip().split()
                for sub in sub_words:
                    clean_item = cls._clean_token(sub)
                    if clean_item and len(clean_item) >= 2 and clean_item not in cls.QUALIFIER_WORDS and clean_item not in NON_ROLE_STOP_WORDS:
                        norm_r = clean_item
                        if clean_item.endswith('ies') and len(clean_item) > 4:
                            norm_r = clean_item[:-3] + 'y'
                        elif clean_item.endswith('s') and len(clean_item) > 3 and not clean_item.endswith('ss'):
                            norm_r = clean_item[:-1]
                        if norm_r not in NON_ROLE_STOP_WORDS and norm_r not in cls.QUALIFIER_WORDS:
                            seen_roles.add(norm_r)

        # Domain actor role vocabulary check
        role_keywords = [
            'doctor', 'nurse', 'superintendent', 'librarian', 'student', 'faculty', 'hod',
            'warden', 'customer', 'seller', 'admin', 'member', 'trainer', 'staff', 'agent',
            'supervisor', 'employee', 'manager', 'finance', 'hr', 'operator', 'tenant'
        ]
        for r_kw in role_keywords:
            if re.search(rf'\b{r_kw}s?\b', normalized_request, re.IGNORECASE):
                seen_roles.add(r_kw)

        fallback_intent = DynamicLinguisticExtractor.extract_intent(normalized_request, workspace_vocab)

        if workspace_vocab and "roles" in workspace_vocab:
            for w_role in workspace_vocab["roles"]:
                w_role_clean = w_role.lower()
                if w_role_clean in raw_request.lower() and w_role_clean not in seen_roles:
                    seen_roles.add(w_role_clean)

        all_extracted_roles = list(dict.fromkeys(list(seen_roles) + fallback_intent.target_roles))
        final_roles = all_extracted_roles if all_extracted_roles else ["operator"]

        return StructuredIntent(
            raw_request=raw_request,
            primary_features=fallback_intent.primary_features,
            target_roles=final_roles,
            action_verbs=fallback_intent.action_verbs,
            domain_keywords=fallback_intent.domain_keywords,
            role_bindings=bindings,
            global_features=[f for f in fallback_intent.primary_features if f not in cls.QUALIFIER_WORDS]
        )


class RoleCapabilityExpander:
    """
    Expands role-capability bindings into targeted 1-to-1 page and capability requirements.
    Eliminates Cartesian cross-product noise. Infers access level from verb semantics.
    """

    @classmethod
    def _infer_access_level(cls, role: str, capability: str, raw_clause: str) -> str:
        clause_lower = f"{capability} {raw_clause}".lower()
        if any(w in clause_lower for w in ['view', 'read-only', 'read_only', 'browse', 'see', 'roster']):
            return 'read'
        if any(w in clause_lower for w in ['manage', 'create', 'edit', 'delete', 'import', 'batch', 'admin']):
            return 'full_crud'
        if any(w in clause_lower for w in ['approve', 'verify', 'review', 'reject', 'revise', 'triage']):
            return 'review'
        if any(w in clause_lower for w in ['self', 'own', 'my', 'personal']):
            return 'self_manage'
        return 'standard'

    @classmethod
    def expand(cls, intent: StructuredIntent, evidence: ProjectEvidence, archetypes: List[ProjectArchetype]) -> List[SynthesizedRequirement]:
        reqs = []
        req_counter = 0

        # Phase 1: Targeted 1-to-1 Role → Capability Expansion (No N x M x V explosion)
        if hasattr(intent, 'role_bindings') and intent.role_bindings:
            for binding in intent.role_bindings:
                access = cls._infer_access_level(binding.role, " ".join(binding.capabilities), binding.raw_clause)
                for cap in binding.capabilities:
                    req_counter += 1
                    reqs.append(SynthesizedRequirement(
                        id=f"REQ-PAGE-{req_counter}",
                        description=f"{binding.role.title()} View — {cap.replace('_', ' ').title()}",
                        type=RequirementType.DERIVED,
                        category=RequirementCategory.PRODUCT_REQUIREMENT,
                        action=ArtifactAction.CREATE,
                        decision_threshold=DecisionThreshold.AUTO_DECIDE,
                        why_chain=[
                            f"Role '{binding.role}' bound to capability '{cap}'",
                            f"Inferred access level '{access}' from clause semantics",
                            f"Source clause: '{binding.raw_clause[:100]}'"
                        ],
                        affects=["frontend", "backend"],
                        assumption_type="behavior"
                    ))
        else:
            old_expander = CapabilityExpansionEngine()
            return old_expander.expand(intent, evidence, archetypes)

        # Phase 2: Entity → Action expansion from discovered DB schema
        for entity in evidence.db_entities:
            entity_name = entity.get("name", "")
            entity_fields = entity.get("fields", [])
            if entity_name:
                req_counter += 1
                reqs.append(SynthesizedRequirement(
                    id=f"REQ-EXP-{req_counter}",
                    description=f"Provide data management for entity '{entity_name}'",
                    type=RequirementType.SUPPORTED,
                    category=RequirementCategory.PRODUCT_REQUIREMENT,
                    action=ArtifactAction.REUSE,
                    decision_threshold=DecisionThreshold.AUTO_DECIDE,
                    evidence=[EvidenceReference(
                        source_file=entity.get("source", "database"),
                        reference_text=f"Entity '{entity_name}' with {len(entity_fields)} fields"
                    )],
                    why_chain=[
                        f"Entity '{entity_name}' discovered in project workspace schema",
                        f"Fields: {', '.join(entity_fields[:5])}"
                    ],
                    affects=["frontend", "backend", "database"],
                    assumption_type="data"
                ))

        # Phase 3: Framework Discovered Pages
        covered_caps = {cap.lower().replace('_', '') for b in getattr(intent, 'role_bindings', []) for cap in b.capabilities}
        for page in getattr(evidence, 'discovered_pages', []):
            page_clean = page.split('/')[-1].replace('.tsx', '').replace('.ts', '').replace('.py', '').lower()
            if page_clean not in covered_caps:
                req_counter += 1
                reqs.append(SynthesizedRequirement(
                    id=f"REQ-PAGE-EXISTING-{req_counter}",
                    description=f"Support existing workspace page module: {page}",
                    type=RequirementType.SUPPORTED,
                    category=RequirementCategory.PRODUCT_REQUIREMENT,
                    action=ArtifactAction.REUSE,
                    decision_threshold=DecisionThreshold.AUTO_DECIDE,
                    evidence=[EvidenceReference(source_file="discovered_pages", reference_text=page)],
                    why_chain=[f"Discovered existing route/page file '{page}' in workspace directory tree"],
                    affects=["frontend"]
                ))

        return reqs


class ScopeBoundaryGuard:
    """
    Guards against feature bloat, speculative over-expansion, and unrequested subsystems.
    Explicitly enforces what is IN-SCOPE (canonical workflow completion) vs OUT-OF-SCOPE (speculative bloat).
    Prevents silent injection of unrequested payment gateways, gamification, crypto, or AI chatbots.
    """

    SPECULATIVE_BLOAT_CATEGORIES = {
        "payment_gateway": {
            "keywords": ["payment", "stripe", "razorpay", "paypal", "checkout", "billing", "invoice", "pricing", "subscription", "pay", "fee"],
            "disallowed_additions": ["Stripe Payment Gateway", "Razorpay Checkout", "Subscription Webhooks", "Credit Card Processing"],
            "clarification_question": "Do you want to integrate an online payment gateway (e.g. Stripe/Razorpay) for paid transactions, or keep this fee-free/pay-on-arrival?"
        },
        "gamification": {
            "keywords": ["gamification", "points", "badges", "leaderboard", "rewards", "streak", "level", "xp"],
            "disallowed_additions": ["Gamification Rewards Engine", "User Badges & XP", "Global Leaderboard System"],
            "clarification_question": "Do you want gamification elements (points, badges, leaderboards), or a standard direct workflow?"
        },
        "ai_chatbot": {
            "keywords": ["ai", "chatbot", "assistant", "llm", "copilot", "chat", "bot"],
            "disallowed_additions": ["AI Assistant Chatbot", "LLM Integration Widget"],
            "clarification_question": "Do you want an AI assistant/chatbot widget integrated into this application?"
        },
        "crypto_web3": {
            "keywords": ["crypto", "blockchain", "wallet", "web3", "nft", "token", "ethereum", "solana"],
            "disallowed_additions": ["Crypto Wallet Connect", "Web3 Smart Contract Interaction"],
            "clarification_question": "Do you require Web3 / crypto wallet connectivity?"
        },
        "social_oauth": {
            "keywords": ["google login", "facebook login", "oauth", "sso", "social login", "google auth"],
            "disallowed_additions": ["Third-Party Social OAuth Integrations"],
            "clarification_question": "Should users authenticate via email/password, or require Google/Social SSO?"
        }
    }

    @classmethod
    def audit_scope_boundaries(cls, raw_request: str, intent_features: List[str]) -> Tuple[List[str], List[str], List[str]]:
        req_lower = raw_request.lower()
        all_feature_text = " ".join(intent_features).lower() + " " + req_lower

        in_scope = []
        out_of_scope = []
        questions = []

        for category, config in cls.SPECULATIVE_BLOAT_CATEGORIES.items():
            is_requested = any(re.search(rf"\b{re.escape(kw)}\b", all_feature_text) for kw in config["keywords"])
            if is_requested:
                in_scope.append(f"Integration of {category.replace('_', ' ').title()} requested by user")
            else:
                out_of_scope.append(f"Unrequested {category.replace('_', ' ').title()} (No {' / '.join(config['disallowed_additions'][:2])})")

        return in_scope, out_of_scope, questions


class UniversalViewArchetype(str, Enum):
    """Universal UI Architecture primitives applicable to any software industry domain."""
    DASHBOARD_METRICS = "metrics_grid"
    CALENDAR_SCHEDULE_DISPATCH = "calendar_dispatch_grid"
    WORKFLOW_QUEUE_VERIFICATION = "multi_stage_queue"
    DATA_GRID_MASTER_DETAIL = "master_detail_grid"
    TRANSACTION_LEDGER_RESULTS = "transaction_ledger"
    PROFILE_IDENTITY_SECURITY = "tabbed_card_layout"
    PROJECT_LIFECYCLE_BOARD = "project_lifecycle_board"
    DOCUMENT_VAULT_MANAGER = "document_vault"
    SYSTEM_GOVERNANCE_AUDIT = "governance_console"


class UniversalDomainOntology:
    """
    Universal domain ontology & dynamic semantic decomposer.
    Supports Multi-Industry primitives (Service/Booking, Healthcare, Logistics, FinTech, Academic ERP, IoT, SaaS)
    plus dynamic linguistic first-principles decomposition for novel unseen industries.
    """

    MULTI_INDUSTRY_DOMAINS: Dict[str, Dict[str, Any]] = {
        # 1. Booking & Service Scheduling (Driving School, Clinics, Salons, Consultations, Rentals)
        "booking": {
            "title": "Service Scheduling & Appointment Booking",
            "layout": UniversalViewArchetype.CALENDAR_SCHEDULE_DISPATCH.value,
            "sub_components": ["CalendarScheduleGrid", "TimeSlotPickerMatrix", "ResourceStaffSelector", "BookingSummaryModal", "RescheduleDrawer", "ConflictWarningBadge"],
            "tabs": [
                {
                    "name": "Appointment Booking",
                    "fields": ["serviceTypeId (select)", "resourceStaffId (select)", "bookingDate (date)", "timeSlot (select)", "clientFullName (string)", "clientPhone (tel)", "clientEmail (email)", "specialNotes (text)"],
                    "actions": ["Confirm Booking", "Check Availability", "Cancel Reservation"]
                },
                {
                    "name": "Reschedule & History",
                    "fields": ["bookingReference (string)", "originalDateTime (date)", "newDateTime (date)", "rescheduleReason (text)", "bookingStatus (badge)"],
                    "actions": ["Submit Reschedule Request", "Download Receipt PDF"]
                }
            ],
            "api_endpoints": [
                "GET /api/bookings/available-slots",
                "POST /api/bookings",
                "PATCH /api/bookings/{id}/reschedule",
                "DELETE /api/bookings/{id}"
            ],
            "validation_rules": [
                "Slot must not have overlapping confirmed bookings",
                "Client phone number must be valid 10-digit format",
                "Cancellation must occur at least 2 hours prior to scheduled time"
            ]
        },

        # 2. Healthcare & Clinical Patient Management
        "healthcare": {
            "title": "Patient Clinical Records & Consultation Workflow",
            "layout": UniversalViewArchetype.DATA_GRID_MASTER_DETAIL.value,
            "sub_components": ["PatientRosterTable", "VitalsTimelineCard", "PrescriptionDrawer", "ClinicalNotesEditor", "MedicalHistoryVault"],
            "tabs": [
                {
                    "name": "Patient Clinical Profile",
                    "fields": ["patientId (string)", "fullName (string)", "dob (date)", "gender (select)", "bloodGroup (select)", "allergies (tags)", "emergencyContact (tel)"],
                    "actions": ["Update Patient Record", "Record Vitals Measurement"]
                },
                {
                    "name": "Consultation & Prescription",
                    "fields": ["doctorSpecialty (string)", "chiefComplaints (text)", "diagnosis (text)", "medicationList (array)", "dosageInstructions (text)", "followUpDate (date)"],
                    "actions": ["Generate Digital Prescription PDF", "Order Lab Diagnostic"]
                }
            ],
            "api_endpoints": [
                "GET /api/patients",
                "POST /api/patients",
                "GET /api/patients/{id}/vitals",
                "POST /api/patients/{id}/prescriptions"
            ],
            "validation_rules": [
                "Patient ID and emergency contact are mandatory",
                "Prescription requires certified medical practitioner signature"
            ]
        },

        # 3. Logistics, Fleet & Dispatch Tracking
        "logistics": {
            "title": "Fleet Operations & Dispatch Management",
            "layout": UniversalViewArchetype.CALENDAR_SCHEDULE_DISPATCH.value,
            "sub_components": ["LiveVehicleFleetGrid", "DispatchAssignmentMatrix", "RouteManifestCard", "FuelOdometerTracker", "PreTripInspectionDrawer"],
            "tabs": [
                {
                    "name": "Fleet Dispatch Roster",
                    "fields": ["vehicleId (string)", "licensePlate (string)", "assignedDriverId (select)", "dispatchRoute (string)", "startOdometer (number)", "fuelLevelPercent (number)", "tripStatus (badge)"],
                    "actions": ["Assign Driver & Route", "Complete Pre-Trip Checklist", "Log Fuel Entry"]
                }
            ],
            "api_endpoints": [
                "GET /api/fleet/vehicles",
                "POST /api/fleet/dispatch",
                "PATCH /api/fleet/trips/{id}/complete",
                "POST /api/fleet/fuel-logs"
            ],
            "validation_rules": [
                "Vehicle inspection checklist must pass before trip dispatch",
                "Driver must hold valid commercial license category"
            ]
        },

        # 4. FinTech, Invoicing & Financial Ledgers
        "fintech": {
            "title": "Commercial Invoicing & Transaction Ledger",
            "layout": UniversalViewArchetype.TRANSACTION_LEDGER_RESULTS.value,
            "sub_components": ["InvoiceLedgerTable", "AgingSummaryCards", "LineItemMatrixEditor", "TaxCalculatorDrawer", "PaymentStatusBadge"],
            "tabs": [
                {
                    "name": "Invoice Details",
                    "fields": ["invoiceNumber (string)", "counterpartyName (string)", "issueDate (date)", "dueDate (date)", "subtotalAmount (currency)", "taxRatePercent (number)", "totalAmount (currency)", "paymentStatus (badge)"],
                    "actions": ["Generate Invoice PDF", "Record Offline Settlement", "Send Payment Reminder"]
                }
            ],
            "api_endpoints": [
                "GET /api/invoices",
                "POST /api/invoices",
                "GET /api/invoices/{id}",
                "POST /api/invoices/{id}/settlement"
            ],
            "validation_rules": [
                "Invoice subtotal plus tax must balance exactly to total amount",
                "Immutable transaction record created upon final status transition"
            ]
        },

        # 5. User Profile & Identity Management (Universal)
        "profile": {
            "title": "User Profile & Identity Management",
            "layout": UniversalViewArchetype.PROFILE_IDENTITY_SECURITY.value,
            "sub_components": ["AvatarUploader", "BioHeaderCard", "PersonalDetailsTab", "OrganizationalCredentialsTab", "SecurityPasswordModal"],
            "tabs": [
                {
                    "name": "Personal Details",
                    "fields": ["fullName (string)", "personalEmail (email)", "mobileNumber (tel)", "dob (date)", "gender (select)", "permanentAddress (text)", "emergencyContact (tel)"],
                    "actions": ["Update Personal Info", "Upload Avatar Image"]
                },
                {
                    "name": "Organizational Credentials",
                    "fields": ["identifierCode (string, read-only)", "departmentUnit (string, read-only)", "roleTitle (string, read-only)", "onboardingDate (date)"],
                    "actions": ["Download Digital ID Card"]
                },
                {
                    "name": "Security & Authentication",
                    "fields": ["currentPassword (password)", "newPassword (password)", "confirmPassword (password)", "twoFactorToggle (boolean)"],
                    "actions": ["Change Password", "Revoke Active Sessions"]
                }
            ],
            "api_endpoints": [
                "GET /api/profile",
                "PUT /api/profile",
                "POST /api/profile/avatar",
                "PUT /api/auth/password"
            ],
            "validation_rules": [
                "Avatar file must be image/jpeg or image/png under 2MB",
                "Mobile number must match standard telephone format",
                "New password must contain at least 8 characters with number and symbol"
            ]
        },

        # 6. Academic Examination & Gradebook
        "gradebook": {
            "title": "Academic Gradebook & Examination Results",
            "layout": UniversalViewArchetype.TRANSACTION_LEDGER_RESULTS.value,
            "sub_components": ["SgpaCgpaSummaryCard", "SemesterPickerTabs", "SubjectResultTable", "MarksBreakdownDrawer", "TranscriptExporter"],
            "tabs": [
                {
                    "name": "Semester Results",
                    "fields": ["semesterId (select)", "academicYear (string)", "sgpa (number)", "cgpa (number)", "totalCreditsEarned (number)", "resultStatus (badge)"],
                    "actions": ["Filter Semester", "Export Official Transcript PDF", "Request Revaluation"]
                },
                {
                    "name": "Subject Breakdown",
                    "fields": ["subjectCode (string)", "subjectName (string)", "credits (number)", "grade (string)", "gradePoint (number)", "internalMarks (number)", "externalMarks (number)", "totalMarks (number)"],
                    "actions": ["View Score Breakdown Modal"]
                }
            ],
            "api_endpoints": [
                "GET /api/results",
                "GET /api/results/{semesterId}",
                "POST /api/results/revaluation",
                "GET /api/results/transcript-pdf"
            ],
            "validation_rules": [
                "SGPA and CGPA must be computed to 2 decimal places",
                "Revaluation request only permitted within 14 days of publication"
            ]
        },

        # 7. Multi-Stage Workflow & Verification Queue (Universal)
        "onboarding": {
            "title": "Multi-Stage Verification & Approval Queue",
            "layout": UniversalViewArchetype.WORKFLOW_QUEUE_VERIFICATION.value,
            "sub_components": ["StageProgressionStepper", "DocumentChecklistCard", "VerificationActionDrawer", "AuditNotesBox", "BatchSignOffBar"],
            "tabs": [
                {
                    "name": "Verification Queue",
                    "fields": ["applicantId (string)", "currentStage (select)", "identityVerified (boolean)", "credentialsVerified (boolean)", "reviewerNotes (text)", "status (badge)"],
                    "actions": ["Approve Stage", "Reject with Reason", "Batch Sign-Off"]
                }
            ],
            "api_endpoints": [
                "GET /api/workflow/queue",
                "POST /api/workflow/{id}/advance-stage",
                "POST /api/workflow/{id}/reject"
            ],
            "validation_rules": [
                "Stage advancement requires authorized role credential check"
            ]
        },

        # 8. Document Vault & File Repository (Universal)
        "documents": {
            "title": "Document Vault & File Manager",
            "layout": UniversalViewArchetype.DOCUMENT_VAULT_MANAGER.value,
            "sub_components": ["FileUploadZone", "VirusScanStatusPill", "CategoryFolderTabs", "DocumentPreviewModal", "AccessControlPicker"],
            "tabs": [
                {
                    "name": "Document Vault",
                    "fields": ["fileName (string)", "fileSizeBytes (number)", "fileCategory (select)", "uploadedBy (string)", "securityScanStatus (badge)", "isPublic (boolean)"],
                    "actions": ["Upload Document", "Download Document", "Delete Document"]
                }
            ],
            "api_endpoints": [
                "GET /api/documents",
                "POST /api/documents/upload",
                "DELETE /api/documents/{id}"
            ],
            "validation_rules": [
                "File security scan must verify file is clean before storage"
            ]
        },

        # 9. Operational & Executive Dashboard (Universal)
        "dashboard": {
            "title": "Role-Aware Operational Dashboard",
            "layout": UniversalViewArchetype.DASHBOARD_METRICS.value,
            "sub_components": ["MetricStatCardGrid", "UpcomingEventsTimeline", "QuickActionShortcuts", "RecentActivityFeed", "NotificationDrawer"],
            "tabs": [
                {
                    "name": "Overview",
                    "fields": ["kpiMetrics (object)", "announcements (array)", "pendingTasksCount (number)", "recentEvents (array)"],
                    "actions": ["Refresh Real-Time Metrics", "Acknowledge Notification", "Trigger Quick Action"]
                }
            ],
            "api_endpoints": [
                "GET /api/dashboard/metrics",
                "GET /api/dashboard/announcements",
                "GET /api/notifications"
            ],
            "validation_rules": [
                "Metrics must reflect real store data with zero mock placeholders"
            ]
        },

        # 10. System Governance & Audit Trail (Universal)
        "system_admin": {
            "title": "System Governance, Audit Trails & Master Data",
            "layout": UniversalViewArchetype.SYSTEM_GOVERNANCE_AUDIT.value,
            "sub_components": ["UserAccountTable", "MasterDataLookupEditor", "AuditTrailViewer", "SystemConfigForm"],
            "tabs": [
                {
                    "name": "User Governance",
                    "fields": ["username (string)", "email (email)", "role (select)", "isActive (boolean)", "lastLoginAt (date)"],
                    "actions": ["Create User Account", "Toggle Active Status", "Reset Password"]
                },
                {
                    "name": "Audit Trail",
                    "fields": ["timestamp (date)", "userId (string)", "actionType (string)", "resource (string)", "ipAddress (string)"],
                    "actions": ["Export Immutable Audit Log CSV"]
                }
            ],
            "api_endpoints": [
                "GET /api/admin/users",
                "POST /api/admin/users",
                "GET /api/admin/audit-logs"
            ],
            "validation_rules": [
                "Super Admin role required for all governance actions"
            ]
        }
    }

    @classmethod
    def match_module(cls, keyword: str) -> Optional[Dict[str, Any]]:
        kw_clean = keyword.lower().replace('-', '_').replace(' ', '_')
        for key, defn in cls.MULTI_INDUSTRY_DOMAINS.items():
            if key in kw_clean or kw_clean in key:
                return defn

        # Fuzzy Multi-Industry keyword router
        if any(w in kw_clean for w in ['book', 'schedul', 'slot', 'appoint', 'lesson', 'reserv', 'dispatch', 'calendar']):
            return cls.MULTI_INDUSTRY_DOMAINS["booking"]
        if any(w in kw_clean for w in ['patient', 'doctor', 'clinic', 'health', 'vital', 'prescript', 'medic']):
            return cls.MULTI_INDUSTRY_DOMAINS["healthcare"]
        if any(w in kw_clean for w in ['fleet', 'vehicle', 'van', 'truck', 'driver', 'route', 'shipment', 'trip']):
            return cls.MULTI_INDUSTRY_DOMAINS["logistics"]
        if any(w in kw_clean for w in ['invoice', 'ledger', 'bill', 'financ', 'accounting', 'settle', 'tax']):
            return cls.MULTI_INDUSTRY_DOMAINS["fintech"]
        if any(w in kw_clean for w in ['profile', 'user', 'bio', 'account', 'self']):
            return cls.MULTI_INDUSTRY_DOMAINS["profile"]
        if any(w in kw_clean for w in ['result', 'grade', 'mark', 'sgpa', 'cgpa', 'transcript']):
            return cls.MULTI_INDUSTRY_DOMAINS["gradebook"]
        if any(w in kw_clean for w in ['onboard', 'verify', 'verification', 'stage', 'queue', 'review']):
            return cls.MULTI_INDUSTRY_DOMAINS["onboarding"]
        if any(w in kw_clean for w in ['doc', 'file', 'vault', 'upload', 'receipt']):
            return cls.MULTI_INDUSTRY_DOMAINS["documents"]
        if any(w in kw_clean for w in ['dash', 'overview', 'home', 'stat', 'kpi']):
            return cls.MULTI_INDUSTRY_DOMAINS["dashboard"]
        if any(w in kw_clean for w in ['admin', 'govern', 'audit', 'master_data', 'config']):
            return cls.MULTI_INDUSTRY_DOMAINS["system_admin"]

        # Universal Dynamic First-Principles Decomposition (Handles ANY arbitrary software domain)
        entity_name = kw_clean.replace('_', ' ').title()
        IRREGULAR_PLURALS = {
            "alumni": "alumni", "alumnus": "alumni", "staff": "staff", "faculty": "faculty",
            "data": "data", "equipment": "equipment", "telemetry": "telemetry", "category": "categories"
        }
        if kw_clean in IRREGULAR_PLURALS:
            plural_entity = IRREGULAR_PLURALS[kw_clean]
        elif kw_clean.endswith('s') or kw_clean.endswith('ss'):
            plural_entity = kw_clean
        elif kw_clean.endswith('y') and len(kw_clean) > 2 and kw_clean[-2] not in 'aeiou':
            plural_entity = f"{kw_clean[:-1]}ies"
        else:
            plural_entity = f"{kw_clean}s"
        return {
            "title": f"{entity_name} Management & Operations",
            "layout": UniversalViewArchetype.DATA_GRID_MASTER_DETAIL.value,
            "sub_components": [f"{entity_name.replace(' ', '')}DataGrid", "SearchFilterBar", "DetailInspectorDrawer", "CreateEntityModal", "ExportCsvButton"],
            "tabs": [
                {
                    "name": f"{entity_name} Directory",
                    "fields": [f"{kw_clean}Id (string)", "title / name (string)", "status (badge)", "categoryType (select)", "assignedTo (string)", "createdDate (date)", "notes (text)"],
                    "actions": [f"Create {entity_name}", f"Edit {entity_name}", f"Archive {entity_name}", "Export CSV"]
                }
            ],
            "api_endpoints": [
                f"GET /api/{plural_entity}",
                f"POST /api/{plural_entity}",
                f"GET /api/{plural_entity}/{{id}}",
                f"PUT /api/{plural_entity}/{{id}}",
                f"DELETE /api/{plural_entity}/{{id}}"
            ],
            "validation_rules": [
                f"{entity_name} title/name must be non-empty",
                "Status changes must follow standard operational workflow"
            ]
        }


class RolePageSpreadEngine:
    """
    Universal frontend sitemap and route spread engine.
    Dynamically generates permission-scoped page structures and component hierarchies for ANY role in ANY industry.
    """

    @classmethod
    def generate_spread(cls, roles: List[str], intent_features: Optional[List[str]] = None) -> Dict[str, List[Dict[str, Any]]]:
        spread = {}
        intent_features = intent_features or []

        for role in roles:
            role_clean = role.lower().strip()
            pages = []

            # 1. Operational Dashboard / Overview
            pages.append({
                "route": "/dashboard",
                "page_name": f"{role.title()} Dashboard",
                "module_key": "dashboard",
                "description": f"Operational metrics, tasks, and real-time updates for {role}"
            })

            # 2. Self-Profile & Credentials
            pages.append({
                "route": "/profile",
                "page_name": f"{role.title()} Self-Profile",
                "module_key": "profile",
                "description": f"Account profile, contact details, and credentials for {role}"
            })

            # 3. Dynamic Domain Pages inferred from intent capabilities
            for feat in intent_features:
                feat_clean = feat.lower().replace(' ', '-').replace('_', '-')
                if any(w in feat_clean for w in ['dashboard', 'profile', 'login', 'register', 'auth']):
                    continue
                page_title = feat.replace('_', ' ').replace('-', ' ').title()
                pages.append({
                    "route": f"/{feat_clean}",
                    "page_name": f"{page_title} Workspace",
                    "module_key": feat_clean,
                    "description": f"Manage and interact with {page_title}"
                })

            # 4. Role-Specific Archetype Fallbacks
            if any(adm in role_clean for adm in ['admin', 'manager', 'coordinator', 'supervisor', 'hod']):
                if not any(p["route"] == "/audit-logs" for p in pages):
                    pages.append({
                        "route": "/admin/audit-logs",
                        "page_name": "Security Audit Trail",
                        "module_key": "system_admin",
                        "description": "System activity logs and access compliance records"
                    })
                if not any(p["route"] == "/approvals" for p in pages):
                    pages.append({
                        "route": "/admin/verification-queue",
                        "page_name": "Verification & Approvals",
                        "module_key": "onboarding",
                        "description": "Multi-stage verification and sign-off queue"
                    })

            # 5. Shared Document Vault
            if not any("doc" in p["module_key"] for p in pages):
                pages.append({
                    "route": "/documents",
                    "page_name": f"{role.title()} Document Vault",
                    "module_key": "documents",
                    "description": f"File uploads, records, and digital receipts for {role}"
                })

            spread[role] = pages

        return spread


class LowLevelDesignSynthesizer:
    """
    Synthesizes rich Low-Level Design (LLD) requirements for every page and module in the application.
    Generates granular requirements for form field sets, UI sub-components, user action triggers, and REST APIs.
    """

    @classmethod
    def synthesize_lld_requirements(cls, page_spreads: Dict[str, List[Dict[str, Any]]]) -> Tuple[List[SynthesizedRequirement], Dict[str, Dict[str, Any]]]:
        lld_reqs = []
        lld_catalog = {}
        seen_modules = set()

        for role, pages in page_spreads.items():
            for page in pages:
                mod_key = page.get("module_key", "")
                page_route = page.get("route", "")
                page_name = page.get("page_name", "")

                onto = UniversalDomainOntology.match_module(mod_key) or UniversalDomainOntology.match_module(page_name)
                if not onto:
                    continue

                catalog_key = f"{role}:{page_route}"
                lld_catalog[catalog_key] = {
                    "role": role,
                    "page_name": page_name,
                    "route": page_route,
                    "layout": onto.get("layout", UniversalViewArchetype.DATA_GRID_MASTER_DETAIL.value),
                    "sub_components": onto.get("sub_components", []),
                    "tabs": onto.get("tabs", []),
                    "api_endpoints": onto.get("api_endpoints", []),
                    "validation_rules": onto.get("validation_rules", [])
                }

                dedup_key = f"{role}_{mod_key}_{page_name}".lower()
                if dedup_key not in seen_modules:
                    seen_modules.add(dedup_key)

                    components_str = ", ".join(onto.get("sub_components", [])[:4])
                    lld_reqs.append(SynthesizedRequirement(
                        id=f"REQ-LLD-COMP-{len(lld_reqs) + 1}",
                        description=f"[{role.upper()}] {page_name} — UI Component Hierarchy: {components_str}",
                        type=RequirementType.DERIVED,
                        category=RequirementCategory.UX_DERIVATION,
                        action=ArtifactAction.CREATE,
                        decision_threshold=DecisionThreshold.AUTO_DECIDE,
                        evidence=[EvidenceReference(source_file="canonical_domain_ontology", reference_text=f"UI hierarchy for {page_name}")],
                        why_chain=[
                            f"Canonical Low-Level Design expansion for {page_name} ({page_route})",
                            f"Layout type: {onto.get('layout')}",
                            f"Composed components: {components_str}"
                        ],
                        affects=["frontend"],
                        assumption_type="ux"
                    ))

                    for tab in onto.get("tabs", []):
                        tab_name = tab.get("name", "Main")
                        fields_str = ", ".join(tab.get("fields", [])[:5])
                        actions_str = ", ".join(tab.get("actions", [])[:3])
                        lld_reqs.append(SynthesizedRequirement(
                            id=f"REQ-LLD-FIELDS-{len(lld_reqs) + 1}",
                            description=f"[{role.upper()}] {page_name} ({tab_name}) — Form Fields: {fields_str} | Actions: {actions_str}",
                            type=RequirementType.DERIVED,
                            category=RequirementCategory.PRODUCT_REQUIREMENT,
                            action=ArtifactAction.CREATE,
                            decision_threshold=DecisionThreshold.AUTO_DECIDE,
                            evidence=[EvidenceReference(source_file="canonical_domain_ontology", reference_text=f"Fields for {page_name} -> {tab_name}")],
                            why_chain=[
                                f"Mandatory field definitions for {page_name} -> {tab_name}",
                                f"Input fields: {fields_str}",
                                f"Actions: {actions_str}"
                            ],
                            affects=["frontend", "backend"],
                            assumption_type="data"
                        ))

                    endpoints_str = ", ".join(onto.get("api_endpoints", [])[:3])
                    lld_reqs.append(SynthesizedRequirement(
                        id=f"REQ-LLD-API-{len(lld_reqs) + 1}",
                        description=f"[{role.upper()}] {page_name} — Backing REST APIs: {endpoints_str}",
                        type=RequirementType.DERIVED,
                        category=RequirementCategory.ARCHITECTURAL_CONSTRAINT,
                        action=ArtifactAction.CREATE,
                        decision_threshold=DecisionThreshold.AUTO_DECIDE,
                        evidence=[EvidenceReference(source_file="canonical_domain_ontology", reference_text=f"REST endpoints for {page_name}")],
                        why_chain=[
                            f"REST API contract for {page_name}",
                            f"Endpoints: {endpoints_str}"
                        ],
                        affects=["backend"],
                        assumption_type="api"
                    ))

        return lld_reqs, lld_catalog


class SpecSynthesisEngine:
    """Full 6-step orchestrator saving spec output."""

    def __init__(self):
        self.capability_engine = CapabilityExpansionEngine()
        self.role_expander = RoleCapabilityExpander()
        self.inference_engine = DerivedInferenceEngine()
        self.gate = SemanticGate()

    def discover_project(self, workspace_dir: str) -> ProjectEvidence:
        # Format-based workspace discovery across *.md tables, SQL DDL, Prisma models, framework pages, TS/Py enums
        evidence = WorkspaceDocumentScanner.full_document_discovery(workspace_dir)

        agents_dir = os.path.join(workspace_dir, ".agents")
        discovery_path = os.path.join(agents_dir, "project_discovery.json")
        if os.path.exists(discovery_path):
            try:
                data = load_json(discovery_path) or {}
                if data.get("db_schema"):
                    evidence.db_entities.extend(data.get("db_schema", []))
                if data.get("api_routes"):
                    evidence.api_routes.extend(data.get("api_routes", []))
                if data.get("ui_components"):
                    evidence.ui_components.extend(data.get("ui_components", []))
                if data.get("auth_permissions"):
                    evidence.auth_permissions.extend(data.get("auth_permissions", []))
            except Exception as e:
                logger.warning(f"[SpecSynthesis] Could not merge project_discovery.json: {e}")

        return evidence

    def extract_intent(self, raw_request: str, workspace_vocab: Optional[Dict[str, Set[str]]] = None) -> StructuredIntent:
        return StructuredPromptParser.parse_request(raw_request, workspace_vocab)

    def _assess_action_risk_threshold(self, cap_name: str, clause: str, is_primary_base: bool = False) -> DecisionThreshold:
        combined = f"{cap_name} {clause}".lower()
        if is_primary_base or any(kw in combined for kw in ['create', 'build', 'enroll', 'delete', 'drop', 'migrate', 'schema', 'batch', 'import', 'purge', 'reset', 'wipe']):
            return DecisionThreshold.MUST_ASK
        if any(kw in combined for kw in ['permission', 'rbac', 'access control', 'role', 'auth', 'security']):
            return DecisionThreshold.MUST_ASK
        if any(kw in combined for kw in ['api', 'webhook', 'third-party', 'external', 'payment', 'notification']):
            return DecisionThreshold.PROBABLY_DECIDE
        return DecisionThreshold.AUTO_DECIDE

    def synthesize_requirements(self, intent: IntentExtraction, evidence: ProjectEvidence, archetypes: List[ProjectArchetype], scope_tier: Optional[ScopeTier] = None) -> List[SynthesizedRequirement]:
        reqs = []

        # 1. Explicit Base Requirements
        if isinstance(intent, StructuredIntent) and intent.role_bindings:
            for b_idx, binding in enumerate(intent.role_bindings):
                for c_idx, cap in enumerate(binding.capabilities):
                    threshold = self._assess_action_risk_threshold(cap, binding.raw_clause, is_primary_base=(b_idx == 0 and c_idx == 0))
                    reqs.append(SynthesizedRequirement(
                        id=f"REQ-BASE-{len(reqs)}",
                        description=f"{binding.role.title()} - {cap.replace('_', ' ').title()}",
                        type=RequirementType.EXPLICIT,
                        category=RequirementCategory.PRODUCT_REQUIREMENT,
                        action=ArtifactAction.CREATE,
                        decision_threshold=threshold,
                        evidence=[EvidenceReference(source_file="user_request", reference_text=binding.raw_clause[:150])],
                        affects=["frontend", "backend"]
                    ))
        else:
            for i, feature in enumerate(intent.primary_features):
                threshold = DecisionThreshold.MUST_ASK if i == 0 else DecisionThreshold.AUTO_DECIDE
                reqs.append(SynthesizedRequirement(
                    id=f"REQ-BASE-{i}",
                    description=f"Implement feature: {feature}",
                    type=RequirementType.EXPLICIT,
                    category=RequirementCategory.PRODUCT_REQUIREMENT,
                    action=ArtifactAction.CREATE,
                    decision_threshold=threshold,
                    evidence=[EvidenceReference(source_file="user_request", reference_text=feature)],
                    affects=["frontend", "backend"]
                ))

        # 2. Targeted Role-Capability & Discovered Page Expansion
        expanded_reqs = RoleCapabilityExpander.expand(intent if isinstance(intent, StructuredIntent) else StructuredIntent(raw_request=intent.raw_request, primary_features=intent.primary_features, target_roles=intent.target_roles), evidence, archetypes)
        reqs.extend(expanded_reqs)

        # 3. Canonical Low-Level Design (LLD) & Role Page Spread Synthesis
        feats = intent.all_features if hasattr(intent, 'all_features') else intent.primary_features
        page_spreads = RolePageSpreadEngine.generate_spread(intent.target_roles, feats)
        lld_reqs, _ = LowLevelDesignSynthesizer.synthesize_lld_requirements(page_spreads)
        reqs.extend(lld_reqs)

        # 4. Universal Archetype Inferences
        inferred_reqs = self.inference_engine.apply_rules(reqs, evidence, archetypes, scope_tier)
        reqs.extend(inferred_reqs)

        return reqs

    def analyze_impact(self, requirements: List[SynthesizedRequirement], archetypes: List[ProjectArchetype]) -> Dict[str, List[str]]:
        primary_arch = archetypes[0].value if archetypes else "fullstack"
        tiers = ARCHETYPE_IMPACT_TIERS.get(primary_arch, ARCHETYPE_IMPACT_TIERS["fullstack"])

        impact = {tier: [] for tier in tiers}
        for req in requirements:
            for sys in req.affects:
                if sys in impact:
                    impact[sys].append(req.id)
                elif sys not in impact:
                    impact[sys] = [req.id]
        return impact

    def check_conflicts(self, requirements: List[SynthesizedRequirement], evidence: ProjectEvidence) -> List[SynthesizedRequirement]:
        conflicts = []

        for req in requirements:
            if req.type == RequirementType.CONFLICT:
                conflicts.append(req)

        # Check for explicit contradictory directives on the exact same target module/page
        req_by_target = {}
        for req in requirements:
            key = req.description.lower().strip()
            if "public" in key and "private" in key:
                conflicts.append(SynthesizedRequirement(
                    id=f"REQ-CONFLICT-ACCESS-{len(conflicts)}",
                    description=f"Direct Access Conflict: '{req.description}' contains contradictory public vs private constraints",
                    type=RequirementType.CONFLICT,
                    category=RequirementCategory.ARCHITECTURAL_CONSTRAINT,
                    action=ArtifactAction.MODIFY,
                    decision_threshold=DecisionThreshold.MUST_STOP,
                    why_chain=["Target module explicitly specifies contradictory access directives"],
                    affects=req.affects,
                    assumption_type="permission"
                ))

        return conflicts

    def generate_acceptance_criteria(self, intent: IntentExtraction, requirements: List[SynthesizedRequirement]) -> List[str]:
        ac = []
        for req in requirements:
            if req.type in [RequirementType.EXPLICIT, RequirementType.SUPPORTED]:
                ac.append(f"Verify that {req.description} is functioning as expected.")
        for role in intent.target_roles:
            ac.append(f"Verify that role '{role}' can access all assigned capabilities without permission errors.")
        return ac

    def _generate_clarifying_questions(self, requirements: List[SynthesizedRequirement], intent: IntentExtraction) -> List[str]:
        questions = []

        for req in requirements:
            if req.decision_threshold == DecisionThreshold.MUST_ASK:
                desc = req.description
                if "register" in desc.lower() or "registration" in desc.lower():
                    questions.append(f"Should users be able to self-register, or should only admins create accounts? (Context: {desc})")
                elif "public" in desc.lower():
                    questions.append(f"Should this be publicly accessible without login, or require authentication? (Context: {desc})")
                elif "schema" in desc.lower() or "database" in desc.lower() or "field" in desc.lower():
                    questions.append(f"This requires a database schema change. Please confirm the exact field names, types, and constraints. (Context: {desc})")
                else:
                    questions.append(f"Please clarify the scope and expected behavior for: {desc}")

            elif req.decision_threshold == DecisionThreshold.MUST_STOP:
                questions.append(f"⚠️ BLOCKING: {desc} — This conflict must be resolved before design can proceed.")

        if len(intent.primary_features) > 5:
            questions.append(f"You mentioned {len(intent.primary_features)} features. Should we prioritize a subset for the initial release, or implement all at once?")

        return questions

    def extract_intent(self, raw_request: str, workspace_vocab: Optional[Dict[str, Set[str]]] = None) -> StructuredIntent:
        return StructuredPromptParser.parse_request(raw_request, workspace_vocab)

    def run_synthesis(self, raw_request: str, workspace_dir: str, clarification_answers: Optional[Dict[str, str]] = None) -> SynthesizedSpec:
        logger.info("Starting Specification Synthesis Pipeline V5.0 (Semantic Domain Graph & Compiler)")

        agents_dir = os.path.join(workspace_dir, ".agents")
        os.makedirs(agents_dir, exist_ok=True)
        json_path = os.path.join(agents_dir, "synthesized_spec.json")

        # 1. Spec Versioning & History Backup
        current_version = 1
        md_path = os.path.join(agents_dir, "synthesized_spec.md")
        ic_path = os.path.join(agents_dir, "intent_contract.json")

        if os.path.exists(json_path):
            try:
                prev_data = load_json(json_path) or {}
                current_version = prev_data.get("spec_version", 1) + 1
                prev_v = current_version - 1
                shutil.copy2(json_path, os.path.join(agents_dir, f"synthesized_spec_v{prev_v}.json"))
                if os.path.exists(md_path):
                    shutil.copy2(md_path, os.path.join(agents_dir, f"synthesized_spec_v{prev_v}.md"))
                pipe_path = os.path.join(agents_dir, "v7_refinement_pipeline.json")
                if os.path.exists(ic_path):
                    shutil.copy2(ic_path, os.path.join(agents_dir, f"intent_contract_v{prev_v}.json"))
                if os.path.exists(pipe_path):
                    shutil.copy2(pipe_path, os.path.join(agents_dir, f"v7_refinement_pipeline_v{prev_v}.json"))
            except Exception as e:
                logger.warning(f"[SpecSynthesis] Backup archive warning: {e}")

        evidence = self.discover_project(workspace_dir)
        workspace_vocab = WorkspaceVocabularyScanner.extract_workspace_vocab(evidence)
        intent = self.extract_intent(raw_request, workspace_vocab)

        # 2. Archetype & Scope Detection
        archetypes = ProjectArchetypeDetector.detect(workspace_dir, evidence)
        scope_tier = ScopeClassifier.classify(raw_request, intent)
        archetype_strings = [a.value for a in archetypes]

        # Incorporate Clarification Answers Upfront
        if not clarification_answers and os.path.exists(os.path.join(agents_dir, "clarification_answers.json")):
            clarification_answers = load_json(os.path.join(agents_dir, "clarification_answers.json"))

        effective_request = raw_request
        if clarification_answers and isinstance(clarification_answers, dict):
            clarified_str = " ".join(str(v) for v in clarification_answers.values())
            effective_request = f"{raw_request} [CLARIFICATIONS: {clarified_str}]"

        # 3. Construct Semantic Domain Graph
        domain_graph = SemanticDecomposer.decompose_intent(effective_request, evidence)

        # 4. Authoritative Refinement Compiler Pipeline Execution (Single Source of Truth)
        feats = intent.all_features if hasattr(intent, 'all_features') else intent.primary_features
        is_deb = os.getenv("SCLASS_DEBATE_PHASE") == "TRUE" or (clarification_answers is not None)
        v7_pipeline = SpecificationCompiler.compile_v7_refinement_pipeline(
            graph=domain_graph,
            intent_features=feats,
            raw_request=effective_request,
            archetypes=archetype_strings,
            workspace_dir=workspace_dir,
            is_debate_phase=is_deb
        )

        lld_components = v7_pipeline.get("lld_components", [])
        hld_obj = v7_pipeline.get("hld_design")
        r_graph_authoritative = v7_pipeline.get("requirement_graph")
        b_graph_authoritative = v7_pipeline.get("behavior_graph")

        if isinstance(hld_obj, dict):
            hld_obj = HLDDesign(
                system_name=hld_obj.get("system_name", "HLD-001"),
                architecture_style=hld_obj.get("architecture_style", "Modular Monolith"),
                modules=[HLDModule.from_dict(m) if isinstance(m, dict) else m for m in hld_obj.get("modules", [])],
                adrs=[ADRRecord.from_dict(a) if isinstance(a, dict) else a for a in hld_obj.get("adrs", [])],
                version=int(hld_obj.get("version", 1))
            )

        if isinstance(r_graph_authoritative, dict):
            r_graph_authoritative = RequirementGraph.from_dict(r_graph_authoritative)

        if isinstance(b_graph_authoritative, dict):
            b_graph_authoritative = BehaviorGraph.from_dict(b_graph_authoritative)

        if not lld_components and hld_obj:
            from lld_compiler import LLDCompiler
            lld_components = LLDCompiler.compile_lld(
                hld_obj,
                r_graph_authoritative or RequirementGraph(),
                b_graph_authoritative or BehaviorGraph(),
                archetypes=archetype_strings
            )
            v7_pipeline["lld_components"] = lld_components
            state_dir = os.path.join(workspace_dir, ".agents") if workspace_dir else ".agents"
            pipe_disk_path = os.path.join(state_dir, "v7_refinement_pipeline.json")
            if os.path.exists(pipe_disk_path):
                p_disk = load_json(pipe_disk_path) or {}
                p_disk["lld_components"] = [c.to_dict() if hasattr(c, "to_dict") else c for c in lld_components]
                write_json_atomic(pipe_disk_path, p_disk)

        lld_catalog = {c.id if hasattr(c, "id") else (c.get("id") if isinstance(c, dict) else f"LLD-{idx}"): (c.to_dict() if hasattr(c, "to_dict") else c) for idx, c in enumerate(lld_components)}
        if evidence and getattr(evidence, "api_routes", None):
            for route_item in evidence.api_routes:
                r_ep = f"{route_item.get('method', 'GET')} {route_item.get('path', '')}"
                for lld_dict in lld_catalog.values():
                    apis = lld_dict.get("api_endpoints", [])
                    if r_ep not in apis:
                        apis.append(r_ep)
        feats = intent.all_features if hasattr(intent, 'all_features') else intent.primary_features
        roles_to_spread = set(intent.target_roles)
        if evidence and getattr(evidence, "auth_permissions", None):
            for perm in evidence.auth_permissions:
                roles_to_spread.add(perm.lower().replace(" ", "_"))
        page_spreads = RolePageSpreadEngine.generate_spread(list(roles_to_spread), feats)
        if hld_obj:
            modules_list = hld_obj.modules if hasattr(hld_obj, "modules") else hld_obj.get("modules", [])
            style = getattr(hld_obj, "architecture_style", None) or (hld_obj.get("architecture_style") if isinstance(hld_obj, dict) else "Modular Monolith")
            for role_k, p_list in page_spreads.items():
                for mod in modules_list:
                    m_name = mod.name if hasattr(mod, "name") else mod.get("name", "Module")
                    m_caps = mod.owned_capabilities if hasattr(mod, "owned_capabilities") else mod.get("owned_capabilities", [])
                    m_ents = mod.owned_entities if hasattr(mod, "owned_entities") else mod.get("owned_entities", [])
                    p_list.append({
                        "page_name": f"{role_k.capitalize()} {m_name}",
                        "route": f"/{role_k.lower()}/{m_name.lower().replace(' ', '_')}",
                        "owned_capabilities": m_caps,
                        "owned_entities": m_ents,
                        "module_key": m_name,
                        "description": f"{m_name} management workspace for {role_k}",
                        "architecture_style": style
                    })

        r_graph_authoritative = v7_pipeline.get("requirement_graph")
        assumption_ledger = []
        if r_graph_authoritative and hasattr(r_graph_authoritative, "nodes"):
            for r_node in r_graph_authoritative.nodes.values():
                r_kind_str = str(getattr(r_node, "kind", "")).upper()
                if "DERIVED" in r_kind_str or "NON_FUNCTIONAL" in r_kind_str:
                    assumption_ledger.append({
                        "requirement_id": getattr(r_node, "id", "REQ-ASM"),
                        "capability": getattr(r_node, "capability", "capability"),
                        "assumption_type": "derived_inference",
                        "weight": 2 if "DERIVED" in r_kind_str else 5,
                        "rationale": getattr(r_node, "reason", "Derived architectural inference")
                    })

        # 5. Canonical Requirement Derivation directly from Authoritative RequirementGraph
        requirements_list: List[SynthesizedRequirement] = []
        if r_graph_authoritative and hasattr(r_graph_authoritative, "nodes") and r_graph_authoritative.nodes:
            r_nodes = r_graph_authoritative.nodes.values() if isinstance(r_graph_authoritative.nodes, dict) else r_graph_authoritative.nodes
            for r_node in r_nodes:
                r_id = getattr(r_node, "id", "") if hasattr(r_node, "id") else r_node.get("id", "")
                if r_id:
                    kind_str = str(getattr(r_node, "kind", "") if hasattr(r_node, "kind") else r_node.get("kind", "")).lower()
                    statement_str = getattr(r_node, "statement", "") if hasattr(r_node, "statement") else r_node.get("statement", "")
                    r_type = RequirementType.EXPLICIT if ("explicit" in kind_str or "functional" in kind_str) else RequirementType.DERIVED
                    r_cat = RequirementCategory.PRODUCT_REQUIREMENT if "functional" in kind_str else RequirementCategory.ARCHITECTURAL_CONSTRAINT
                    conf = float(getattr(r_node, "confidence", 1.0) if hasattr(r_node, "confidence") else r_node.get("confidence", 1.0))

                    thresh_val = DecisionThreshold.AUTO_DECIDE if (r_type == RequirementType.EXPLICIT and conf >= 0.85) else (
                        DecisionThreshold.MUST_ASK if conf < 0.70 else DecisionThreshold.PROBABLY_DECIDE
                    )

                    r_ev_raw = getattr(r_node, "evidence", []) if hasattr(r_node, "evidence") else r_node.get("evidence", [])
                    ev_refs = []
                    if isinstance(r_ev_raw, list):
                        for item in r_ev_raw:
                            if isinstance(item, EvidenceReference):
                                ev_refs.append(item)
                            elif isinstance(item, dict):
                                ev_refs.append(EvidenceReference(
                                    source_file=item.get("source_file", item.get("source_ref", "workspace")),
                                    section=item.get("section", "domain"),
                                    reference_text=item.get("reference_text", item.get("content", str(item)))
                                ))
                            elif hasattr(item, "source_ref") and hasattr(item, "content"):
                                ev_refs.append(EvidenceReference(
                                    source_file=getattr(item, "source_ref", "workspace"),
                                    section="domain",
                                    reference_text=getattr(item, "content", str(item))
                                ))
                            elif isinstance(item, str) and item:
                                ev_refs.append(EvidenceReference(
                                    source_file="spec_graph",
                                    section="domain",
                                    reference_text=item
                                ))
                    elif isinstance(r_ev_raw, str) and r_ev_raw:
                        ev_refs.append(EvidenceReference(
                            source_file="spec_graph",
                            section="domain",
                            reference_text=r_ev_raw
                        ))

                    if not ev_refs:
                        ev_refs.append(EvidenceReference(
                            source_file="workspace_preflight",
                            section="domain_discovery",
                            reference_text=f"Evidence reference for {getattr(r_node, 'capability', r_id)}"
                        ))

                    req_obj = SynthesizedRequirement(
                        id=r_id,
                        description=statement_str,
                        type=r_type,
                        category=r_cat,
                        action=ArtifactAction.CREATE,
                        decision_threshold=thresh_val,
                        evidence=ev_refs,
                        why_chain=[getattr(r_node, "reason", "Compiled from Authoritative Requirement Graph") if hasattr(r_node, "reason") else "Compiled from Authoritative Requirement Graph"],
                        affects=["frontend", "backend"]
                    )
                    requirements_list.append(req_obj)
        else:
            requirements_list = self.synthesize_requirements(intent, evidence, archetypes, scope_tier)

        # Incorporate Clarification Answers
        if not clarification_answers and os.path.exists(os.path.join(agents_dir, "clarification_answers.json")):
            clarification_answers = load_json(os.path.join(agents_dir, "clarification_answers.json"))

        if clarification_answers and isinstance(clarification_answers, dict):
            for req in requirements_list:
                if req.id in clarification_answers or "REQ-BASE-0" in clarification_answers:
                    answer = clarification_answers.get(req.id) or clarification_answers.get("REQ-BASE-0")
                    req.decision_threshold = DecisionThreshold.AUTO_DECIDE
                    req.type = RequirementType.SUPPORTED
                    req.description += f" [CLARIFIED: {answer}]"
                    break

        # 6. Graph & Dependency Wiring
        graph = RequirementGraph()
        for req in requirements_list:
            graph.add_node(req)

        for req in requirements_list:
            if req.type in [RequirementType.DERIVED, RequirementType.SUPPORTED, RequirementType.OPTIONAL]:
                for parent in requirements_list:
                    if parent.id != req.id and parent.type in [RequirementType.EXPLICIT, RequirementType.REUSE]:
                        if any(sys in parent.affects for sys in req.affects):
                            graph.add_dependency(req.id, parent.id)

        orphans = graph.detect_orphans()
        if orphans:
            logger.warning(f"[SpecSynthesis] Detected {len(orphans)} orphaned requirement(s): {[o.id for o in orphans]}")
            explicit_roots = [r for r in requirements_list if r.type in [RequirementType.EXPLICIT, RequirementType.SUPPORTED]]
            if explicit_roots:
                root_id = explicit_roots[0].id
                for orphan in orphans:
                    graph.add_dependency(orphan.id, root_id)

        impacts = self.analyze_impact(requirements_list, archetypes)
        conflicts = self.check_conflicts(requirements_list, evidence)

        # Run Adversarial Skeptic Checks
        skeptic_contradictions = AdversarialSkeptic.detect_contradictions(domain_graph, requirements_list)
        for s_c in skeptic_contradictions:
            conflicts.append(SynthesizedRequirement(
                id=s_c["id"],
                description=s_c["description"],
                type=RequirementType.CONFLICT,
                category=RequirementCategory.ARCHITECTURAL_CONSTRAINT,
                action=ArtifactAction.MODIFY,
                decision_threshold=DecisionThreshold.MUST_STOP,
                why_chain=["Adversarial Skeptic detected contradictory constraints"],
                affects=["frontend", "backend"]
            ))

        for conflict in conflicts:
            if conflict not in requirements_list:
                requirements_list.append(conflict)

        # 7. Scope Boundary & Anti-Bloat Audit
        in_scope_bounds, out_of_scope_bounds, _ = ScopeBoundaryGuard.audit_scope_boundaries(raw_request, intent.primary_features)
        scope_boundaries_dict = {
            "in_scope": in_scope_bounds,
            "out_of_scope": out_of_scope_bounds
        }

        # 8. Compute Semantic Metrics
        domain_specificity = AdversarialSkeptic.calculate_domain_specificity_score(lld_catalog)
        unsupported_rate = AdversarialSkeptic.calculate_unsupported_invention_rate(requirements_list)

        # 9. Semantic Gate Evaluation with Dynamic Budget Scaling
        gate_result_enum, total_weight = self.gate.evaluate(requirements_list, evidence, archetypes, scope_tier=scope_tier)

        questions = [
            f"Clarify scope/boundary for {r.id}: {r.description}"
            for r in requirements_list
            if getattr(r, "decision_threshold", None) in [DecisionThreshold.MUST_ASK, DecisionThreshold.MUST_STOP]
        ]
        dependency_holes = AdversarialSkeptic.detect_dependency_holes(domain_graph)
        for hole in dependency_holes:
            questions.append(hole["question"])
        if not questions:
            questions.append("Clarify default authentication and RBAC authorization boundary for system roles.")

        # Practical Skeptic Checklist (Empirical Real-World Failures)
        practical_pass, practical_warns, practical_checks = PracticalSkeptic.audit_specification({
            "low_level_designs": lld_catalog,
            "page_spreads": page_spreads,
            "requirements": requirements_list
        }, evidence)
        for warn in practical_warns:
            logger.info(f"[PracticalSkeptic] {warn}")

        acceptance_criteria = self.generate_acceptance_criteria(intent, requirements_list)

        grouped_reqs = {}
        for req in requirements_list:
            typ = req.type.value
            if typ not in grouped_reqs:
                grouped_reqs[typ] = []
            grouped_reqs[typ].append(req.to_dict())

        spec = SynthesizedSpec(
            intent_summary=f"Implement features for roles: {intent.target_roles}. Archetypes: {archetype_strings}",
            requirements=grouped_reqs,
            affected_systems=impacts,
            conflicts=[c.to_dict() for c in conflicts],
            questions_for_human=questions,
            acceptance_criteria=acceptance_criteria,
            gate_result=gate_result_enum.value,
            total_assumption_weight=total_weight,
            archetypes=archetype_strings,
            scope_tier=scope_tier.value,
            spec_version=current_version,
            page_spreads=page_spreads,
            low_level_designs=lld_catalog,
            scope_boundaries=scope_boundaries_dict,
            domain_graph=domain_graph.to_dict(),
            domain_specificity_score=domain_specificity,
            unsupported_invention_rate=unsupported_rate,
            assumption_ledger=assumption_ledger
        )

        md_path = os.path.join(agents_dir, "synthesized_spec.md")

        # Save JSON output
        try:
            write_json_atomic(json_path, spec.__dict__)
            write_json_atomic(os.path.join(agents_dir, "v7_refinement_pipeline.json"), {
                "behavior_graph": v7_pipeline["behavior_graph"].to_dict(),
                "requirement_graph": v7_pipeline["requirement_graph"].to_dict(),
                "dependency_holes": v7_pipeline["dependency_holes"],
                "hld_design": v7_pipeline["hld_design"].to_dict(),
                "hld_validation": v7_pipeline["hld_validation"],
                "hld_governance": v7_pipeline.get("hld_governance", {}),
                "debate_result": v7_pipeline.get("debate_result", {}),
                "lld_components": [c.to_dict() for c in v7_pipeline["lld_components"]],
                "lld_governance": v7_pipeline.get("lld_governance", {}),
                "tasks": [t.to_dict() for t in v7_pipeline["tasks"]],
                "task_governance": v7_pipeline.get("task_governance", {}),
                "blocked": v7_pipeline.get("blocked", False),
                "target_fsm_state": v7_pipeline.get("target_fsm_state", "CODING")
            })

            from intent_contract import IntentContract
            ic = IntentContract(
                goal=spec.intent_summary,
                scope_boundaries=out_of_scope_bounds,
                acceptance_criteria=spec.acceptance_criteria,
                error_paths=[]
            )
            write_json_atomic(os.path.join(agents_dir, "intent_contract.json"), ic.to_dict())
        except Exception as e:
            logger.error(f"Failed to write JSON outputs: {e}")

        # Save Markdown output
        try:
            md_content = "# Synthesized Specification V5.0 (Semantic Domain Graph & Compiler)\n\n"
            md_content += f"**Intent**: {spec.intent_summary}\n"
            md_content += f"**Archetypes**: {', '.join(spec.archetypes)} | **Scope**: {spec.scope_tier.upper()}\n"
            md_content += f"**Gate Result**: {spec.gate_result} (Assumption Weight: {spec.total_assumption_weight}/150)\n"
            md_content += f"**Domain Specificity Score**: {spec.domain_specificity_score * 100:.0f}% | **Unsupported Invention Rate**: {spec.unsupported_invention_rate * 100:.0f}%\n"
            md_content += f"**Total Requirements**: {sum(len(v) for v in spec.requirements.values())} | **Version**: v{spec.spec_version}\n\n"

            if spec.questions_for_human:
                md_content += "## ❓ Questions for Human Review (Dependency Holes & Clarifications)\n\n"
                for i, q in enumerate(spec.questions_for_human, 1):
                    md_content += f"{i}. {q}\n"
                md_content += "\n"

            # Render Scope Boundaries (Anti-Bloat Guard)
            md_content += "## 🛡️ Scope Boundaries & Anti-Bloat Guard\n\n"
            md_content += "### Explicitly Out-of-Scope (Unrequested Subsystems Suppressed)\n"
            for out_item in out_of_scope_bounds:
                md_content += f"- 🚫 {out_item}\n"
            md_content += "\n"

            # Render Semantic Domain Graph Nodes & Topology
            if spec.domain_graph:
                md_content += "## 🕸️ Semantic Domain Graph Topology\n\n"
                md_content += f"- **Total Domain Nodes**: {len(spec.domain_graph.get('nodes', []))}\n"
                md_content += f"- **Total Relational Edges**: {len(spec.domain_graph.get('edges', []))}\n\n"
                md_content += "| Primitive Type | Node Name | Provenance | ID |\n"
                md_content += "|---|---|---|---|\n"
                for n in spec.domain_graph.get('nodes', [])[:10]:
                    md_content += f"| `{n['primitive_type']}` | **{n['name']}** | `{n['provenance']}` | `{n['id']}` |\n"
                md_content += "\n"

            # Render Role-Based Page Spreading Sitemap
            if spec.page_spreads:
                md_content += "## 🗺️ Role-Based Page Spreads & Frontend Sitemap\n\n"
                for role, pages in spec.page_spreads.items():
                    md_content += f"### Role: {role.upper()} ({len(pages)} Pages)\n\n"
                    md_content += "| Route Path | Page Name | Module Scope | Description |\n"
                    md_content += "|---|---|---|---|\n"
                    for p in pages:
                        mod_k = p.get('module_key') or p.get('architecture_style') or 'core'
                        desc = p.get('description') or p.get('page_name') or 'Page'
                        md_content += f"| `{p.get('route', '/')}` | **{p.get('page_name', 'Page')}** | `{mod_k}` | {desc} |\n"
                    md_content += "\n"

            # Render Low-Level Design Component & Field Specifications
            if spec.low_level_designs:
                md_content += "## 📐 Low-Level Design (LLD) Specifications & Reasoning Graphs\n\n"
                for key, lld in spec.low_level_designs.items():
                    p_name = lld.get('page_name') or lld.get('name') or key
                    role_str = lld.get('role') or lld.get('component_type') or 'component'
                    route_str = lld.get('route') or 'N/A'
                    md_content += f"### [{role_str.upper()}] {p_name} (`{route_str}`)\n\n"
                    md_content += f"- **Layout**: `{lld['layout']}`\n"
                    md_content += f"- **Composed Sub-Components**: {', '.join(f'`{c}`' for c in lld['sub_components'])}\n"
                    md_content += f"- **Backing REST Endpoints**: {', '.join(f'`{e}`' for e in lld['api_endpoints'])}\n"
                    if lld.get("validation_rules"):
                        md_content += f"- **Validation Rules**: {'; '.join(lld['validation_rules'])}\n"

                    if lld.get("reasoning_graph"):
                        md_content += "- **Structured Reasoning Provenance**:\n"
                        for step in lld["reasoning_graph"]:
                            md_content += f"  - `({step.get('from')})` $\\xrightarrow{{\\text{{{step.get('relation')}}}}}$ `({step.get('to')})`\n"

                    md_content += "\n**Tab & Form Field Breakdown**:\n\n"
                    for tab in lld.get("tabs", []):
                        md_content += f"**Tab: {tab['name']}**\n"
                        md_content += f"- *Fields*: {', '.join(tab.get('fields', []))}\n"
                        md_content += f"- *User Actions*: {', '.join(tab.get('actions', []))}\n\n"

            md_content += "## Acceptance Criteria\n\n"
            for ac in spec.acceptance_criteria:
                md_content += f"- {ac}\n"

            md_content += "\n## Requirements by Type\n\n"
            for typ, reqs in spec.requirements.items():
                md_content += f"### {typ.upper()} ({len(reqs)})\n\n"
                for r in reqs:
                    md_content += f"- **{r['id']}**: {r['description']}\n"
                    if r.get("why_chain"):
                        for step in r["why_chain"]:
                            md_content += f"  - _{step}_\n"
                md_content += "\n"

            md_content += "## Affected Systems\n\n"
            for sys_name, req_ids in spec.affected_systems.items():
                if req_ids:
                    md_content += f"- **{sys_name}**: {len(req_ids)} requirement(s)\n"

            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(md_content)
        except Exception as e:
            logger.error(f"Failed to write MD output: {e}")

        logger.info(f"Synthesis V5.0 completed (v{spec.spec_version}). {sum(len(v) for v in spec.requirements.values())} requirements, gate={spec.gate_result}")
        return spec
