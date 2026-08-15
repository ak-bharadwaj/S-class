"""
S-Class EOS V8.0 - Epistemic Upstream-Traceable Task Compiler with Contract Verification

Defines:
1. TaskRecord (Executable coding task with full lineage: task -> lld -> hld -> req -> behavior)
2. TaskCompiler (Compiles LLDComponents into BDD contract-derived execution tasks, conditioning 403/audit criteria strictly on evidence)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Set, Any, Optional, Tuple
import hashlib
import json

from lld_compiler import LLDComponent, LLDComponentType
from requirement_ir import RequirementGraph, RequirementNode, NFRCategory, EpistemicStatus, ProvenanceKind
from behavior_graph import BehaviorGraph, BehaviorNodeType, BehaviorRelationType


class TaskCategory(str, Enum):
    """Category of execution tasks."""
    API_ENDPOINT = "api_endpoint"
    AUTHORIZATION_GUARD = "authorization_guard"
    STATE_TRANSITION = "state_transition"
    AUDIT_LOG = "audit_log"
    UI_COMPONENT = "ui_component"
    INTEGRATION_TEST = "integration_test"


@dataclass
class TaskRecord:
    """An executable task with complete upstream architectural lineage, cryptographic integrity hash, and BDD acceptance criteria."""
    id: str
    title: str
    description: str
    category: TaskCategory
    parent_lld: str
    parent_hld: str
    parent_reqs: List[str]
    parent_behaviors: List[str]
    verification_criteria: List[str] = field(default_factory=list)
    source_lld_hash: str = ""
    source_binding_hashes: List[str] = field(default_factory=list)
    task_hash: str = ""

    def __post_init__(self):
        if not self.task_hash:
            self.task_hash = self.compute_canonical_hash()

    def compute_canonical_hash(self) -> str:
        """Computes deterministic SHA-256 hash over all task fields, upstream LLD hash, and capability binding digests."""
        cat_val = self.category.value if hasattr(self.category, "value") else str(self.category)
        payload = {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "category": cat_val,
            "parent_lld": self.parent_lld,
            "parent_hld": self.parent_hld,
            "parent_reqs": sorted(self.parent_reqs),
            "parent_behaviors": sorted(self.parent_behaviors),
            "verification_criteria": sorted(self.verification_criteria),
            "source_lld_hash": self.source_lld_hash,
            "source_binding_hashes": sorted(self.source_binding_hashes)
        }
        canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        cat_val = self.category.value if hasattr(self.category, "value") else str(self.category)
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "category": cat_val,
            "parent_lld": self.parent_lld,
            "parent_hld": self.parent_hld,
            "parent_reqs": self.parent_reqs,
            "parent_behaviors": self.parent_behaviors,
            "verification_criteria": self.verification_criteria,
            "source_lld_hash": self.source_lld_hash,
            "source_binding_hashes": self.source_binding_hashes,
            "task_hash": self.task_hash
        }

    @classmethod
    def from_governed_dict(cls, data: Dict[str, Any]) -> 'TaskRecord':
        """Dedicated strict ingestion API for governed task artifacts."""
        return cls.from_dict(data, strict=True)

    @classmethod
    def from_dict(cls, data: Dict[str, Any], strict: bool = False) -> 'TaskRecord':
        if strict:
            mandatory = [
                "id", "title", "description", "category", "parent_lld", "parent_hld",
                "parent_reqs", "parent_behaviors", "verification_criteria",
                "source_lld_hash", "source_binding_hashes", "task_hash"
            ]
            for field_name in mandatory:
                if field_name not in data:
                    raise ValueError(f"Missing mandatory '{field_name}' in TaskRecord governed payload (strict mode)")
                val = data[field_name]
                if field_name in ["id", "title", "description", "category", "parent_lld", "parent_hld", "source_lld_hash", "task_hash"]:
                    if not isinstance(val, str) or not val.strip():
                        raise ValueError(f"Field '{field_name}' must be a non-empty string in TaskRecord strict ingestion, got {val!r}")
                elif field_name in ["parent_reqs", "parent_behaviors", "verification_criteria", "source_binding_hashes"]:
                    if not isinstance(val, list):
                        raise ValueError(f"Field '{field_name}' must be a list in TaskRecord strict ingestion, got {type(val)}")

            try:
                cat = TaskCategory(data["category"])
            except ValueError:
                raise ValueError(f"Invalid TaskCategory '{data.get('category')}' in TaskRecord strict ingestion")

            task = cls(
                id=data["id"],
                title=data["title"],
                description=data["description"],
                category=cat,
                parent_lld=data["parent_lld"],
                parent_hld=data["parent_hld"],
                parent_reqs=data["parent_reqs"],
                parent_behaviors=data["parent_behaviors"],
                verification_criteria=data["verification_criteria"],
                source_lld_hash=data["source_lld_hash"],
                source_binding_hashes=data["source_binding_hashes"],
                task_hash=data["task_hash"]
            )

            computed_hash = task.compute_canonical_hash()
            if data["task_hash"] != computed_hash:
                raise ValueError(f"TaskRecord '{task.id}' task_hash mismatch (provided: {data['task_hash'][:8]}, computed: {computed_hash[:8]})")

            return task
        else:
            cat_raw = data.get("category", "api_endpoint")
            try:
                cat = TaskCategory(cat_raw)
            except ValueError:
                cat = TaskCategory.API_ENDPOINT

            return cls(
                id=data.get("id", ""),
                title=data.get("title", ""),
                description=data.get("description", ""),
                category=cat,
                parent_lld=data.get("parent_lld", ""),
                parent_hld=data.get("parent_hld", ""),
                parent_reqs=data.get("parent_reqs", []),
                parent_behaviors=data.get("parent_behaviors", []),
                verification_criteria=data.get("verification_criteria", []),
                source_lld_hash=data.get("source_lld_hash", ""),
                source_binding_hashes=data.get("source_binding_hashes", []),
                task_hash=data.get("task_hash", "")
            )


class TaskCompiler:
    """Compiles LLDComponents and RequirementGraph into BDD contract-derived TaskRecord entries."""

    @classmethod
    def compile_tasks(
        cls,
        lld_components: List[LLDComponent],
        r_graph: Optional[RequirementGraph] = None,
        b_graph: Optional[BehaviorGraph] = None
    ) -> List[TaskRecord]:
        tasks: List[TaskRecord] = []
        task_counter = 1

        req_lookup = r_graph.nodes if r_graph else {}

        for comp in lld_components:
            p_hld = comp.parent.hld_id
            p_reqs = comp.parent.req_ids
            p_behs = comp.parent.behavior_ids

            matching_req_objs = [req_lookup[rid] for rid in p_reqs if rid in req_lookup]

            source_lld_hash = comp.component_hash
            source_binding_hashes = sorted(list(set(
                b.binding_hash for b in comp.capability_bindings if b.behavior_id in p_behs
            )))
            if not source_binding_hashes and comp.capability_bindings:
                source_binding_hashes = sorted(list(set(b.binding_hash for b in comp.capability_bindings)))

            # PROPOSED_CANDIDATE & Speculative Epistemic Barrier:
            # Skip compiling executable tasks if parent behaviors are exclusively ungrounded PROPOSED/SPECULATIVE
            if b_graph and p_behs:
                beh_objs = [b_graph.get_node(b_id) for b_id in p_behs if b_graph.get_node(b_id)]
                if beh_objs and all(
                    getattr(b, "epistemic_status", None) == EpistemicStatus.PROPOSED or
                    getattr(b, "provenance", None) == ProvenanceKind.SPECULATIVE
                    for b in beh_objs
                ):
                    continue

            if comp.component_type in [LLDComponentType.CONTROLLER, LLDComponentType.SERVICE]:
                valid_endpoints = [ep for ep in comp.api_endpoints if "PROPOSED_CANDIDATE" not in ep]
                if not valid_endpoints:
                    continue

                for ep in valid_endpoints:
                    t_id = f"TASK-{task_counter:03d}"
                    task_counter += 1

                    bdd_criteria = []
                    for req in matching_req_objs:
                        actor_str = req.actor
                        pre_str = f"Given {req.target}.status == {req.preconditions[0].split('==')[1].strip()}" if req.preconditions else f"Given {req.target} exists"
                        post_str = f"Then {req.target}.status == {req.postconditions[0].split('==')[1].strip()}" if req.postconditions else f"Then {req.capability} execution commits"

                        base_bdd = [
                            f"{pre_str}",
                            f"And actor == '{actor_str}'",
                            f"When transport action '{ep}' is invoked",
                            f"{post_str}"
                        ]

                        # Check if authorization evidence exists before adding 403 assertion (PERFORMS != AUTHORIZED_FOR)
                        has_auth_evidence = False
                        if b_graph:
                            b_node = b_graph.get_node(req.capability)
                            if b_node:
                                incoming = b_graph._reverse_adjacency.get(b_node.id, [])
                                has_auth_evidence = any(e.relation == BehaviorRelationType.AUTHORIZED_FOR for e in incoming)

                        ev_text = " ".join(e.content for e in (req.evidence or [])) if req.evidence else ""
                        if has_auth_evidence or "role:" in ev_text.lower():
                            base_bdd.append(f"And unauthorized actor returns HTTP 403 Forbidden")

                        # Check if audit evidence exists before adding audit persistence assertion
                        has_audit_evidence = False
                        if b_graph:
                            b_node = b_graph.get_node(req.capability)
                            if b_node:
                                outgoing = b_graph._adjacency.get(b_node.id, [])
                                has_audit_evidence = any(e.relation == BehaviorRelationType.EMITS_SIDE_EFFECT for e in outgoing)
                        if req.nfr_category == NFRCategory.AUDITABILITY:
                            has_audit_evidence = True

                        if has_audit_evidence:
                            base_bdd.append("And audit log record is committed to persistent storage")

                        bdd_criteria.extend(base_bdd)

                    if not bdd_criteria:
                        bdd_criteria = [
                            f"Given valid request payload for {ep}",
                            f"When transport action {ep} is invoked",
                            "Then handler executes successfully and returns expected payload contract"
                        ]

                    tasks.append(TaskRecord(
                        id=t_id,
                        title=f"Implement Component Contract: {ep}",
                        description=f"Construct component logic for {ep} in {comp.name}.",
                        category=TaskCategory.API_ENDPOINT if comp.component_type == LLDComponentType.CONTROLLER else TaskCategory.STATE_TRANSITION,
                        parent_lld=comp.id,
                        parent_hld=p_hld,
                        parent_reqs=p_reqs,
                        parent_behaviors=p_behs,
                        verification_criteria=list(dict.fromkeys(bdd_criteria)),
                        source_lld_hash=source_lld_hash,
                        source_binding_hashes=source_binding_hashes
                    ))

            elif comp.component_type == LLDComponentType.UI_SURFACE:
                if not p_reqs or not matching_req_objs:
                    continue

                if b_graph and p_behs:
                    beh_objs = [b_graph.get_node(b_id) for b_id in p_behs if b_graph.get_node(b_id)]
                    if beh_objs and all(
                        getattr(b, "epistemic_status", None) == EpistemicStatus.PROPOSED or
                        getattr(b, "provenance", None) == ProvenanceKind.SPECULATIVE
                        for b in beh_objs
                    ):
                        continue

                t_id = f"TASK-{task_counter:03d}"
                task_counter += 1
                tasks.append(TaskRecord(
                    id=t_id,
                    title=f"Construct Behavioral UI Surface: {comp.name}",
                    description=f"Build modern React/Next.js frontend surface for {comp.name} at route {comp.route}.",
                    category=TaskCategory.UI_COMPONENT,
                    parent_lld=comp.id,
                    parent_hld=p_hld,
                    parent_reqs=p_reqs,
                    parent_behaviors=p_behs,
                    verification_criteria=[
                        f"Renders behavioral workflow surface at route {comp.route}",
                        "Connects action triggers to backend transport contracts"
                    ],
                    source_lld_hash=source_lld_hash,
                    source_binding_hashes=source_binding_hashes
                ))

        return tasks
