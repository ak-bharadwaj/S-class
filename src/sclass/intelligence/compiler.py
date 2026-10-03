"""Intent-to-Engineering Compiler (04-INTELLIGENCE).

Transforms plain-language user requests into canonical S-Class structures
(Objective, Requirements, Obligations, VerificationPlan, WorkGraph) using a
hybrid two-pass approach with a robust deterministic fallback.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from sclass_semantics_v6_0_1 import (
    AcceptanceContract,
    ActionType,
    Authority,
    CanonicalObjective,
    CompositionMode,
    Constraint,
    ConstraintType,
    ContentManifestState,
    Decision,
    DecisionOption,
    Digest,
    DiscoveryMethod,
    EffectScope,
    EnforcementPhase,
    EngineeringSnapshot,
    EvidenceComposition,
    EvidenceKind,
    FrozenMap,
    FsAccess,
    FsMode,
    Idempotency,
    IndependenceLevel,
    IndependenceProfile,
    ObjectiveRevision,
    Obligation,
    ObligationGraph,
    ObligationKind,
    ObligationStatus,
    RequestedEffect,
    RequiredEvidence,
    Requirement,
    ResourceBudget,
    RiskTier,
    SemanticGraph,
    Severity,
    SourceType,
    StructuredIntent,
    VerificationPlan,
    VerificationStep,
    WaiverRules,
    WorkGraph,
    WorkNode,
    WorkNodeStatus,
)

from sclass.intelligence.world_model import EngineeringWorldModel

fmap = FrozenMap.from_items


@dataclass(frozen=True)
class EngineeringProgram:
    """Canonical compiled engineering program representing the goal and work breakdown."""

    objective: CanonicalObjective
    requirements: tuple[Requirement, ...]
    obligations: tuple[Obligation, ...]
    obligation_graph: ObligationGraph
    acceptance_contracts: tuple[AcceptanceContract, ...]
    verification_plans: tuple[VerificationPlan, ...]
    work_graph: WorkGraph


class IntentCompiler:
    """Hybrid two-pass compiler transforming plain-language intent into canonical S-Class structures."""

    def __init__(self, policy_version: str = "pol-1"):
        self.policy_version = policy_version

    def compile(
        self, intent: str, world_model: EngineeringWorldModel
    ) -> EngineeringProgram:
        """Compile plain-language intent against the given world model."""
        # Pass 1: Deterministic repository and intent inspection
        analysis = self._analyze_intent_and_repo(intent, world_model)

        # Pass 2: Structured intent decomposition & canonical synthesis
        return self._synthesize_program(analysis, world_model)

    def _analyze_intent_and_repo(
        self, intent: str, world_model: EngineeringWorldModel
    ) -> dict:
        """Pass 1: Extract keywords, target paths, testing requirements, and risk tier."""
        clean_intent = intent.strip()
        intent_lower = clean_intent.lower()

        # Extract probable target paths
        target_paths: list[str] = []
        path_matches = re.findall(r"[\w/\.-]+\.py", clean_intent)
        for p in path_matches:
            target_paths.append(p.lstrip("/"))

        # If no explicit paths found, dynamically infer target paths from entities and repository symbols
        if not target_paths:
            # Check if any existing file in the world model matches words in the intent
            matched_repo_files: list[str] = []
            for file_path in world_model.files:
                stem = Path(file_path).stem.lower()
                if stem in intent_lower and len(stem) > 3:
                    matched_repo_files.append(file_path)

            if matched_repo_files:
                target_paths = matched_repo_files
            else:
                # Dynamic entity extraction: search for CamelCase class/module names
                camel_matches = re.findall(r"\b[A-Z][a-zA-Z0-9]+\b", clean_intent)
                filter_tokens = {
                    "Implement", "Create", "Build", "Add", "Write", "Update",
                    "Fix", "Develop", "Introduce", "Make", "Refactor", "Setup",
                    "Python", "HTTP", "API", "JSON", "REST", "RPC", "CLI", "SDK", "IDE",
                }
                candidates = [c for c in camel_matches if c not in filter_tokens]

                if candidates:
                    primary = candidates[0]
                    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", primary)
                    slug = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()
                else:
                    # Search for noun phrases following action verbs
                    action_match = re.search(
                        r"\b(?:implement|add|create|build|write|develop|introduce)\s+(?:a\s+|an\s+|the\s+)?([a-zA-Z0-9_\s]+?)(?:\s+(?:with|for|in|and|to|$))",
                        clean_intent,
                        re.IGNORECASE,
                    )
                    if action_match:
                        phrase = action_match.group(1).strip()
                        raw_slug = re.sub(r"\s+", "_", phrase).lower()
                        slug = raw_slug[:30].strip("_")
                    else:
                        slug = re.sub(r"[^\w]+", "_", intent_lower)[:20].strip("_") or "feature"

                target_paths = [f"src/sclass/{slug}.py", f"tests/test_{slug}.py"]

        # Detect verification classes dynamically
        requires_hypothesis = any(k in intent_lower for k in ["hypothesis", "property", "fuzz", "invariant"])
        requires_pytest = any(k in intent_lower for k in ["test", "unit", "pytest", "spec", "verify", "validation"]) or bool(world_model.files)
        requires_ruff = any(k in intent_lower for k in ["type", "lint", "ruff", "annotation", "clean", "format", "style"]) or True

        # Detect risk tier dynamically
        if any(k in intent_lower for k in ["critical", "security", "auth", "crypto", "vulnerability"]):
            risk_tier = RiskTier.CRITICAL
        elif any(k in intent_lower for k in ["high", "concurrency", "distributed"]):
            risk_tier = RiskTier.HIGH
        elif any(k in intent_lower for k in ["api", "data", "database", "storage", "network"]):
            risk_tier = RiskTier.MODERATE
        else:
            risk_tier = RiskTier.LOW

        return {
            "intent": clean_intent,
            "target_paths": tuple(target_paths),
            "requires_pytest": requires_pytest,
            "requires_hypothesis": requires_hypothesis,
            "requires_ruff": requires_ruff,
            "risk_tier": risk_tier,
        }

    def _synthesize_program(
        self, analysis: dict, world_model: EngineeringWorldModel
    ) -> EngineeringProgram:
        """Pass 2: Synthesize canonical S-Class structures with deterministic fallback."""
        intent = analysis["intent"]
        target_paths: Sequence[str] = analysis["target_paths"]
        risk_tier: RiskTier = analysis["risk_tier"]

        # Deterministic IDs derived from intent hash
        intent_sha = hashlib.sha256(intent.encode("utf-8")).hexdigest()
        intent_prefix = intent_sha[:8]

        obj_id = f"obj-{intent_prefix}"
        obj_rev_id = f"rev-{intent_prefix}"
        ws_id = world_model.workspace_id

        # 1. Structured Intent
        structured_intent = StructuredIntent(
            schema_version=1,
            goal=intent[:2000],
            in_scope=tuple(f"Implement and verify {p}" for p in target_paths),
            out_of_scope=("Unrelated modifications", "Third-party network dependencies"),
            target_paths=tuple(target_paths),
            acceptance_summary=("All unit tests pass", "Static type and lint checks pass"),
        )

        # 2. Requirements
        req_func_id = f"req-{intent_prefix}-impl"
        req_verify_id = f"req-{intent_prefix}-ver"
        source_prov = Digest(f"sha256:{intent_sha}")

        req_func = Requirement(
            requirement_id=req_func_id,
            description=f"Implement functionality for: {intent[:400]}",
            authority=Authority.USER,
            source_type=SourceType.USER_INPUT,
            source_provenance=source_prov,
            discovery_method=DiscoveryMethod.USER_STATED,
            confidence_bp=10000,
            objective_revision=obj_rev_id,
            parent_requirement=None,
            derived_obligations=(f"obl-{intent_prefix}-impl",),
        )

        req_verify = Requirement(
            requirement_id=req_verify_id,
            description="Verify correctness, test coverage, and code hygiene",
            authority=Authority.USER,
            source_type=SourceType.USER_INPUT,
            source_provenance=source_prov,
            discovery_method=DiscoveryMethod.USER_STATED,
            confidence_bp=10000,
            objective_revision=obj_rev_id,
            parent_requirement=None,
            derived_obligations=(f"obl-{intent_prefix}-ver",),
        )
        requirements = (req_func, req_verify)

        # 3. Constraints & Decisions
        constraints = (
            Constraint(
                constraint_id=f"con-{intent_prefix}-quality",
                description="Must adhere to static analysis and test suite requirements",
                constraint_type=ConstraintType.TECHNICAL,
                authority=Authority.USER,
                enforcement_phase=EnforcementPhase.VERIFICATION,
                severity=Severity.BLOCKING,
                scope=(),
                version=1,
            ),
        )

        dec_opt1 = DecisionOption("opt-python", "Native Python Implementation", 10, 9500)
        decisions = (
            Decision(
                decision_id=f"dec-{intent_prefix}-arch",
                question="Target implementation runtime and language style",
                options=(dec_opt1,),
                selected_option_id="opt-python",
                rationale="Native Python provides direct integration with existing S-Class pipeline",
                constraint_ids=(f"con-{intent_prefix}-quality",),
                evidence_ids=(),
                policy_version=self.policy_version,
                decision_scope="architecture",
                revisit_conditions=(),
                expires_at=None,
                created_by="IntentCompiler",
            ),
        )

        # 4. EngineeringSnapshot & Objective
        zero_dig = Digest("sha256:" + "0" * 64)
        snapshot = EngineeringSnapshot(
            snapshot_id=f"es-{intent_prefix}",
            snapshot_schema_version=1,
            baseline_state_hash=world_model.target_snapshot.workspace_state_digest,
            workspace_state=ContentManifestState(
                manifest_digest=world_model.target_snapshot.workspace_state_digest,
                file_count=len(world_model.files),
            ),
            world_model_revision=world_model.revision_id,
            policy_version=self.policy_version,
            risk_classifier_version="sclass-classifier-v1",
            sdk_version="6.0.1",
            toolchain_version="python-3.14",
            platform_fingerprint=zero_dig,
        )

        obj_rev = ObjectiveRevision(
            revision_id=obj_rev_id,
            revision_number=1,
            structured_intent=structured_intent,
            requirements=requirements,
            constraints=constraints,
            decisions=decisions,
            snapshot=snapshot,
            parent_revision_id=None,
        )
        objective = CanonicalObjective(
            objective_id=obj_id,
            workspace_id=ws_id,
            revisions=(obj_rev,),
        )

        # 5. Obligations
        obl_impl_id = f"obl-{intent_prefix}-impl"
        obl_ver_id = f"obl-{intent_prefix}-ver"
        act_impl_id = f"act-{intent_prefix}-impl"
        act_ver_id = f"act-{intent_prefix}-ver"
        plan_ver_id = f"plan-{intent_prefix}-ver"

        obl_impl = Obligation(
            obligation_id=obl_impl_id,
            objective_id=obj_id,
            revision=1,
            description=f"Implement source changes for: {intent[:200]}",
            kind=ObligationKind.FUNCTIONAL,
            risk_tier=risk_tier,
            status=ObligationStatus.READY,
            depends_on=frozenset(),
            acceptance_contract_id=act_impl_id,
            satisfied_by=None,
            verification_plan_id=None,
        )

        obl_ver = Obligation(
            obligation_id=obl_ver_id,
            objective_id=obj_id,
            revision=1,
            description="Verify implementation passing pytest and ruff checks",
            kind=ObligationKind.NON_FUNCTIONAL,
            risk_tier=risk_tier,
            status=ObligationStatus.PENDING,
            depends_on=frozenset({obl_impl_id}),
            acceptance_contract_id=act_ver_id,
            satisfied_by=None,
            verification_plan_id=plan_ver_id,
        )
        obligations = (obl_impl, obl_ver)

        # ObligationGraph
        empty_graph = SemanticGraph((), ())
        obl_graph = ObligationGraph(empty_graph, fmap()).add(obl_impl).add(obl_ver)

        # 6. AcceptanceContracts
        ind_none = IndependenceProfile(
            IndependenceLevel.NONE,
            IndependenceLevel.NONE,
            IndependenceLevel.NONE,
            IndependenceLevel.NONE,
            IndependenceLevel.NONE,
        )
        req_ev_impl = RequiredEvidence(
            requirement_key="req-key-impl",
            evidence_kind=EvidenceKind.BEHAVIORAL,
            verifier_id="patch-worker",
            min_independence=ind_none,
            freshness=(),
            mandatory=True,
            min_receipts=1,
        )
        contract_impl = AcceptanceContract(
            contract_id=act_impl_id,
            obligation_id=obl_impl_id,
            revision=1,
            required_evidence=(req_ev_impl,),
            composition=EvidenceComposition(CompositionMode.ALL_OF, 0),
            waiver_rules=WaiverRules((), 1000, False),
            authored_by=Authority.USER,
        )

        required_ver_evidences: list[RequiredEvidence] = [
            RequiredEvidence(
                requirement_key="req-pytest",
                evidence_kind=EvidenceKind.BEHAVIORAL,
                verifier_id="pytest",
                min_independence=ind_none,
                freshness=(),
                mandatory=True,
                min_receipts=1,
            ),
            RequiredEvidence(
                requirement_key="req-ruff",
                evidence_kind=EvidenceKind.STATIC,
                verifier_id="ruff",
                min_independence=ind_none,
                freshness=(),
                mandatory=True,
                min_receipts=1,
            ),
        ]
        if analysis["requires_hypothesis"]:
            required_ver_evidences.append(
                RequiredEvidence(
                    requirement_key="req-hypothesis",
                    evidence_kind=EvidenceKind.PROPERTY,
                    verifier_id="hypothesis",
                    min_independence=ind_none,
                    freshness=(),
                    mandatory=True,
                    min_receipts=1,
                )
            )

        contract_ver = AcceptanceContract(
            contract_id=act_ver_id,
            obligation_id=obl_ver_id,
            revision=1,
            required_evidence=tuple(required_ver_evidences),
            composition=EvidenceComposition(CompositionMode.ALL_OF, 0),
            waiver_rules=WaiverRules((), 1000, False),
            authored_by=Authority.USER,
        )
        acceptance_contracts = (contract_impl, contract_ver)

        # 7. VerificationPlan
        steps: list[VerificationStep] = [
            VerificationStep(
                step_id=f"step-{intent_prefix}-pytest",
                evidence_kind=EvidenceKind.BEHAVIORAL,
                verifier_id="pytest",
                verifier_version="8.0.0",
                config_digest=Digest("sha256:" + "1" * 64),
                timeout_ms=30000,
                budget=ResourceBudget(0, 0, 0, 30000, 0, 0, 0, 0, 0, 0, 0),
            ),
            VerificationStep(
                step_id=f"step-{intent_prefix}-ruff",
                evidence_kind=EvidenceKind.STATIC,
                verifier_id="ruff",
                verifier_version="0.8.0",
                config_digest=Digest("sha256:" + "2" * 64),
                timeout_ms=10000,
                budget=ResourceBudget(0, 0, 0, 10000, 0, 0, 0, 0, 0, 0, 0),
            ),
        ]
        if analysis["requires_hypothesis"]:
            steps.append(
                VerificationStep(
                    step_id=f"step-{intent_prefix}-hypothesis",
                    evidence_kind=EvidenceKind.PROPERTY,
                    verifier_id="hypothesis",
                    verifier_version="6.100.0",
                    config_digest=Digest("sha256:" + "3" * 64),
                    timeout_ms=45000,
                    budget=ResourceBudget(0, 0, 0, 45000, 0, 0, 0, 0, 0, 0, 0),
                )
            )

        verification_plan = VerificationPlan(
            plan_id=plan_ver_id,
            obligation_id=obl_ver_id,
            revision=1,
            contract_revision=1,
            steps=tuple(steps),
        )
        verification_plans = (verification_plan,)

        # 8. WorkGraph
        node_impl_id = f"node-{intent_prefix}-impl"
        node_ver_id = f"node-{intent_prefix}-ver"

        fs_writes = tuple(FsAccess(path=p, mode=FsMode.WRITE) for p in target_paths)
        fs_reads = tuple(FsAccess(path=p, mode=FsMode.READ) for p in target_paths)
        z_budget = ResourceBudget(0, 0, 0, 30000, 0, 0, 0, 0, 0, 0, 0)

        scope_impl = EffectScope((), (), (), fmap(), ".", (), (), z_budget)
        scope_ver = EffectScope((), (), (), fmap(), ".", (), (), z_budget)

        req_eff_impl = RequestedEffect(
            filesystem=fs_writes,
            subprocess=(),
            network=(),
            environment=fmap(),
            credentials=(),
            external_side_effects=(),
            requested_budget=z_budget,
            delta_digest=None,
        )
        req_eff_ver = RequestedEffect(
            filesystem=fs_reads,
            subprocess=(),
            network=(),
            environment=fmap(),
            credentials=(),
            external_side_effects=(),
            requested_budget=z_budget,
            delta_digest=None,
        )

        node_impl = WorkNode(
            node_id=node_impl_id,
            primary_obligation_id=obl_impl_id,
            satisfies_obligation_ids=frozenset({obl_impl_id}),
            action_description=f"Generate and write implementation for {', '.join(target_paths)}",
            action_type=ActionType.CODE_EDIT,
            requested_effect=req_eff_impl,
            effect_scope=scope_impl,
            estimated_tokens=4000,
            estimated_duration_ms=5000,
            status=WorkNodeStatus.READY,
            idempotency=Idempotency.IDEMPOTENT,
            worker_id=None,
            retry_budget_id=f"retry-{intent_prefix}-impl",
            effective_risk_tier=risk_tier,
            execution_generation=1,
            governing_budget_lineage_id=f"lineage-{intent_prefix}",
        )

        node_ver = WorkNode(
            node_id=node_ver_id,
            primary_obligation_id=obl_ver_id,
            satisfies_obligation_ids=frozenset({obl_ver_id}),
            action_description="Execute verification plane against mutations",
            action_type=ActionType.TEST_RUN,
            requested_effect=req_eff_ver,
            effect_scope=scope_ver,
            estimated_tokens=2000,
            estimated_duration_ms=10000,
            status=WorkNodeStatus.PENDING,
            idempotency=Idempotency.IDEMPOTENT,
            worker_id=None,
            retry_budget_id=f"retry-{intent_prefix}-ver",
            effective_risk_tier=risk_tier,
            execution_generation=1,
            governing_budget_lineage_id=f"lineage-{intent_prefix}",
        )

        wg_nodes = (node_impl_id, node_ver_id)
        wg_edges = ((node_ver_id, node_impl_id, "depends_on"),)
        sem_graph = SemanticGraph(nodes=tuple(sorted(wg_nodes)), edges=tuple(sorted(wg_edges)))

        work_graph = WorkGraph(
            revision_id=f"wg-{intent_prefix}",
            objective_revision=obj_rev_id,
            obligation_graph_revision="og-1",
            policy_version=self.policy_version,
            world_model_revision=world_model.revision_id,
            _graph=sem_graph,
            _nodes=fmap(((node_impl_id, node_impl), (node_ver_id, node_ver))),
        )

        return EngineeringProgram(
            objective=objective,
            requirements=requirements,
            obligations=obligations,
            obligation_graph=obl_graph,
            acceptance_contracts=acceptance_contracts,
            verification_plans=verification_plans,
            work_graph=work_graph,
        )
