import os
import json
import re
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional, Set

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
class IntentExtraction:
    raw_request: str
    primary_features: List[str] = field(default_factory=list)
    target_roles: List[str] = field(default_factory=list)
    action_verbs: List[str] = field(default_factory=list)

@dataclass
class ProjectEvidence:
    db_entities: List[Dict[str, Any]] = field(default_factory=list)
    api_routes: List[Dict[str, Any]] = field(default_factory=list)
    ui_components: List[str] = field(default_factory=list)
    design_docs: Dict[str, Any] = field(default_factory=dict)
    env_vars: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)

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

# --- Engines ---

class CapabilityExpansionEngine:
    """Evidence-driven expansion chain (Role -> Capability -> Entity -> Action -> Page -> UX)."""
    def expand(self, intent: IntentExtraction, evidence: ProjectEvidence) -> List[SynthesizedRequirement]:
        expanded_reqs = []
        # Basic mock expansion logic
        for role in intent.target_roles:
            for feature in intent.primary_features:
                for verb in intent.action_verbs:
                    req_id = f"REQ-EXP-{len(expanded_reqs)+1}"
                    expanded_reqs.append(SynthesizedRequirement(
                        id=req_id,
                        description=f"Role '{role}' needs capability to {verb} {feature}",
                        type=RequirementType.DERIVED,
                        category=RequirementCategory.PRODUCT_REQUIREMENT,
                        action=ArtifactAction.CREATE,
                        decision_threshold=DecisionThreshold.AUTO_DECIDE,
                        why_chain=[
                            f"Identified role: {role}",
                            f"Mapped capability: {verb} {feature}",
                            f"Resulting user flow needed for {feature} management."
                        ],
                        affects=["frontend", "backend", "auth"],
                        assumption_type="behavior"
                    ))
        return expanded_reqs

class DerivedInferenceEngine:
    """Conservative, conditional rules."""
    def apply_rules(self, requirements: List[SynthesizedRequirement], evidence: ProjectEvidence) -> List[SynthesizedRequirement]:
        inferred = []
        # Example rule: Breadcrumbs for deep navigation
        has_deep_nav = any("depth >= 2" in r.description.lower() for r in requirements)
        if has_deep_nav:
            inferred.append(SynthesizedRequirement(
                id=f"REQ-INF-BC",
                description="Include breadcrumb navigation for deeply nested pages",
                type=RequirementType.DERIVED,
                category=RequirementCategory.UX_DERIVATION,
                action=ArtifactAction.CREATE,
                decision_threshold=DecisionThreshold.AUTO_DECIDE,
                why_chain=["Detected nested navigation depth >= 2", "Breadcrumbs improve UX for deep hierarchies"],
                affects=["frontend", "navigation"],
                assumption_type="ux"
            ))
            
        # Example rule: Soft delete
        has_audit = any("audit" in (ent.get("name", "").lower()) for ent in evidence.db_entities)
        has_delete = any("delete" in r.description.lower() for r in requirements)
        if has_audit and has_delete:
             inferred.append(SynthesizedRequirement(
                id=f"REQ-INF-SD",
                description="Implement soft-delete due to audit significance of entity",
                type=RequirementType.DERIVED,
                category=RequirementCategory.ARCHITECTURAL_CONSTRAINT,
                action=ArtifactAction.MODIFY,
                decision_threshold=DecisionThreshold.PROBABLY_DECIDE,
                why_chain=["Audit entity detected in DB", "Delete action requested", "Soft delete prevents audit corruption"],
                affects=["backend", "database"],
                assumption_type="data"
            ))
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
    """Evaluates semantic validity and computes gate results."""
    ASSUMPTION_WEIGHTS = {
        "ux": 1,
        "behavior": 2,
        "data": 3,
        "api": 3,
        "permission": 4,
        "architecture": 5
    }
    MAX_WEIGHT = 10

    @staticmethod
    def validate_dict(spec_dict: Dict[str, Any], workspace_dir: Optional[str] = None) -> Dict[str, Any]:
        """Validates semantic coherence of a spec dictionary for verifier.py."""
        errors = []
        has_roles = spec_dict.get("has_roles", False)
        has_role_analysis = spec_dict.get("has_role_analysis", True)
        if has_roles and not has_role_analysis:
            errors.append("Roles detected but no role capability analysis performed.")

        has_ui = spec_dict.get("has_ui_requirements", False)
        affected = spec_dict.get("affected", spec_dict.get("affected_systems", {}))
        if has_ui and not affected.get("frontend"):
            errors.append("UI requirements exist but no frontend impact declared.")

        gate_result = spec_dict.get("gate_result", "")
        if gate_result == "BLOCKED":
            errors.append("Gate result is BLOCKED.")

        return {"passed": len(errors) == 0, "errors": errors}

    def evaluate(self, requirements: List[SynthesizedRequirement], evidence: ProjectEvidence) -> tuple[GateResult, int]:
        total_weight = 0
        has_must_stop = False
        has_must_ask = False
        
        for req in requirements:
            if req.assumption_type in self.ASSUMPTION_WEIGHTS:
                total_weight += self.ASSUMPTION_WEIGHTS[req.assumption_type]
                
            if req.decision_threshold == DecisionThreshold.MUST_STOP:
                has_must_stop = True
            elif req.decision_threshold == DecisionThreshold.MUST_ASK:
                has_must_ask = True

        if has_must_stop or total_weight > self.MAX_WEIGHT:
            return GateResult.BLOCKED, total_weight
            
        if has_must_ask:
            return GateResult.PASS_WITH_DECISIONS, total_weight
            
        return GateResult.PASS, total_weight

class SpecSynthesisEngine:
    """Full 6-step orchestrator saving spec output."""
    
    def __init__(self):
        self.capability_engine = CapabilityExpansionEngine()
        self.inference_engine = DerivedInferenceEngine()
        self.gate = SemanticGate()

    def extract_intent(self, raw_request: str) -> IntentExtraction:
        # Regex-based extraction (simplified)
        verbs = ["create", "edit", "delete", "view", "list", "manage", "update"]
        found_verbs = [v for v in verbs if v in raw_request.lower()]
        
        roles = ["admin", "user", "student", "instructor", "manager"]
        found_roles = [r for r in roles if r in raw_request.lower()]
        if not found_roles:
            found_roles = ["user"] # default role
            
        features = [word for word in raw_request.split() if len(word) > 5 and word.lower() not in verbs + roles]
        # Just grab a couple features as a mock
        primary_features = list(set(features))[:3]
        
        return IntentExtraction(
            raw_request=raw_request,
            primary_features=primary_features,
            target_roles=found_roles,
            action_verbs=found_verbs
        )

    def discover_project(self, workspace_dir: str) -> ProjectEvidence:
        evidence = ProjectEvidence()
        agents_dir = os.path.join(workspace_dir, ".agents")
        
        digest_path = os.path.join(agents_dir, "workspace_digest.json")
        if os.path.exists(digest_path):
            data = load_json(digest_path) or {}
            evidence.db_entities = data.get("db_entities", [])
            evidence.api_routes = data.get("api_routes", [])
            
        # Simplified discovery...
        return evidence

    def synthesize_requirements(self, intent: IntentExtraction, evidence: ProjectEvidence) -> List[SynthesizedRequirement]:
        reqs = []
        
        # 1. Base requirements from explicit intent
        for i, feature in enumerate(intent.primary_features):
            reqs.append(SynthesizedRequirement(
                id=f"REQ-BASE-{i}",
                description=f"Implement feature: {feature}",
                type=RequirementType.EXPLICIT,
                category=RequirementCategory.PRODUCT_REQUIREMENT,
                action=ArtifactAction.CREATE,
                decision_threshold=DecisionThreshold.MUST_ASK if i == 0 else DecisionThreshold.AUTO_DECIDE, # mock logic
                evidence=[EvidenceReference(source_file="user_request", reference_text=feature)],
                affects=["frontend", "backend"]
            ))
            
        # 2. Capability Expansion
        expanded_reqs = self.capability_engine.expand(intent, evidence)
        reqs.extend(expanded_reqs)
        
        # 3. Derived Inference
        inferred_reqs = self.inference_engine.apply_rules(reqs, evidence)
        reqs.extend(inferred_reqs)
        
        return reqs

    def analyze_impact(self, requirements: List[SynthesizedRequirement]) -> Dict[str, List[str]]:
        impact = {"frontend": [], "backend": [], "database": [], "auth": [], "navigation": []}
        for req in requirements:
            for sys in req.affects:
                if sys in impact:
                    impact[sys].append(req.id)
        return impact

    def check_conflicts(self, requirements: List[SynthesizedRequirement], evidence: ProjectEvidence) -> List[SynthesizedRequirement]:
        conflicts = []
        for req in requirements:
            if req.type == RequirementType.CONFLICT:
                conflicts.append(req)
        return conflicts
        
    def generate_acceptance_criteria(self, intent: IntentExtraction, requirements: List[SynthesizedRequirement]) -> List[str]:
        ac = []
        for req in requirements:
            if req.type in [RequirementType.EXPLICIT, RequirementType.SUPPORTED]:
                ac.append(f"Verify that {req.description} is functioning as expected.")
        return ac

    def run_synthesis(self, raw_request: str, workspace_dir: str) -> SynthesizedSpec:
        logger.info("Starting Specification Synthesis Pipeline")
        
        intent = self.extract_intent(raw_request)
        evidence = self.discover_project(workspace_dir)
        
        requirements_list = self.synthesize_requirements(intent, evidence)
        
        # Build Graph & Resolve Dependencies / Orphan Detection
        graph = RequirementGraph()
        for req in requirements_list:
            graph.add_node(req)

        # Wire dependencies between derived/supported requirements and explicit parent requirements
        for req in requirements_list:
            if req.type in [RequirementType.DERIVED, RequirementType.SUPPORTED, RequirementType.OPTIONAL]:
                for parent in requirements_list:
                    if parent.id != req.id and parent.type in [RequirementType.EXPLICIT, RequirementType.REUSE]:
                        if any(sys in parent.affects for sys in req.affects):
                            graph.add_dependency(req.id, parent.id)

        orphans = graph.detect_orphans()
        if orphans:
            logger.warning(f"[SpecSynthesis] Detected {len(orphans)} orphaned requirement(s): {[o.id for o in orphans]}")
            
        impacts = self.analyze_impact(requirements_list)
        conflicts = self.check_conflicts(requirements_list, evidence)
        gate_result_enum, total_weight = self.gate.evaluate(requirements_list, evidence)
        
        questions = [r.description for r in requirements_list if r.decision_threshold in [DecisionThreshold.MUST_ASK, DecisionThreshold.MUST_STOP]]
        acceptance_criteria = self.generate_acceptance_criteria(intent, requirements_list)
        
        # Group requirements for output
        grouped_reqs = {}
        for req in requirements_list:
            typ = req.type.value
            if typ not in grouped_reqs:
                grouped_reqs[typ] = []
            grouped_reqs[typ].append(req.to_dict())

        spec = SynthesizedSpec(
            intent_summary=f"Implement {len(intent.primary_features)} features for roles: {intent.target_roles}",
            requirements=grouped_reqs,
            affected_systems=impacts,
            conflicts=[c.to_dict() for c in conflicts],
            questions_for_human=questions,
            acceptance_criteria=acceptance_criteria,
            gate_result=gate_result_enum.value,
            total_assumption_weight=total_weight
        )
        
        # Save Outputs
        agents_dir = os.path.join(workspace_dir, ".agents")
        os.makedirs(agents_dir, exist_ok=True)
        
        json_path = os.path.join(agents_dir, "synthesized_spec.json")
        md_path = os.path.join(agents_dir, "synthesized_spec.md")
        
        # Write JSON
        try:
            write_json_atomic(json_path, spec.__dict__)
            
            # Instantiate and save IntentContract
            from intent_contract import IntentContract
            ic = IntentContract(
                goal=spec.intent_summary,
                scope_boundaries=[],
                acceptance_criteria=spec.acceptance_criteria,
                error_paths=[]
            )
            write_json_atomic(os.path.join(agents_dir, "intent_contract.json"), ic.to_dict())
        except Exception as e:
            logger.error(f"Failed to write JSON outputs: {e}")
            
        # Write Markdown
        try:
            md_content = f"# Synthesized Specification\n\n"
            md_content += f"**Intent**: {spec.intent_summary}\n"
            md_content += f"**Gate Result**: {spec.gate_result} (Assumption Weight: {spec.total_assumption_weight}/10)\n\n"
            
            md_content += f"## Questions for Human\n"
            for q in spec.questions_for_human:
                md_content += f"- {q}\n"
                
            md_content += f"\n## Acceptance Criteria\n"
            for ac in spec.acceptance_criteria:
                md_content += f"- {ac}\n"
                
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(md_content)
        except Exception as e:
            logger.error(f"Failed to write MD output: {e}")

        logger.info("Synthesis completed.")
        return spec
