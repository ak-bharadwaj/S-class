"""
S-Class EOS V11.2 - D1 Domain Spec Compiler (Bridge 1).
Compiles unstructured tasks, task specifications, and synthesized requirements
into canonical, deeply immutable D1 domain objects (Task, Obligation DAG, Policy, Claim).
"""

from __future__ import annotations
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

from domain.models import (
    Task,
    TaskConstraints,
    RepositoryContext,
    Obligation,
    Claim,
    ClaimSubject,
    Policy,
    PolicyRule,
    PolicyExpression,
    _validate_pattern,
)
from domain.types import (
    TASK_ID_PATTERN,
    OBLIGATION_ID_PATTERN,
    CLAIM_ID_PATTERN,
    POLICY_ID_PATTERN,
    HEX_40_PATTERN,
    ObligationCategory,
    Criticality,
    ObligationStatus,
    ClaimTier,
    ClaimStatus,
    TargetType,
    PolicyScope,
    RuleType,
    CombinatorType,
)
from domain.dag import ObligationGraph
from domain.exceptions import DomainValidationError


DEFAULT_BASE_SHA = "a" * 40


def _sanitize_slug(text: str) -> str:
    """Produces a clean alphanumeric slug suitable for canonical IDs."""
    cleaned = re.sub(r"[^A-Za-z0-9_]", "-", text.strip())
    cleaned = re.sub(r"-+", "-", cleaned).strip("-")
    return cleaned.upper() or "DEFAULT"


@dataclass(frozen=True)
class CompiledDomainPackage:
    """Immutable, fully validated bundle of canonical domain models for a governed task."""
    task: Task
    obligations: Tuple[Obligation, ...]
    claims: Tuple[Claim, ...]
    policies: Tuple[Policy, ...]

    def __post_init__(self):
        if not isinstance(self.task, Task):
            raise DomainValidationError("task must be an instance of Task.")
        if not self.obligations:
            raise DomainValidationError("CompiledDomainPackage must contain at least one Obligation.")
        for obl in self.obligations:
            if not isinstance(obl, Obligation):
                raise DomainValidationError("Every obligation item must be an instance of Obligation.")
        for clm in self.claims:
            if not isinstance(clm, Claim):
                raise DomainValidationError("Every claim item must be an instance of Claim.")
        for pol in self.policies:
            if not isinstance(pol, Policy):
                raise DomainValidationError("Every policy item must be an instance of Policy.")

    @property
    def obligations_by_id(self) -> Dict[str, Obligation]:
        return {obl.obligation_id: obl for obl in self.obligations}

    @property
    def policies_by_id(self) -> Dict[str, Policy]:
        return {pol.policy_id: pol for pol in self.policies}

    @property
    def claims_by_id(self) -> Dict[str, Claim]:
        return {clm.claim_id: clm for clm in self.claims}


class SpecCompiler:
    """Compiles task specifications into canonical D1 domain models with strict fail-closed validation."""

    @classmethod
    def compile(
        cls,
        spec_data: Union[Dict[str, Any], str],
        repository_context: Optional[RepositoryContext] = None,
        default_base_sha: str = DEFAULT_BASE_SHA,
        default_repo_id: str = "REPO-MAIN",
    ) -> CompiledDomainPackage:
        """
        Compiles raw dictionary, JSON string, or prompt text into a CompiledDomainPackage.
        
        Enforces:
        - Canonical ID formatting (TASK-*, OBL-*, CLM-*, POL-*).
        - Obligation DAG acyclicity and single-task containment.
        - Initial ClaimStatus.UNSUPPORTED and ObligationStatus.OPEN.
        - Deep immutability and schema pattern constraints.
        """
        if isinstance(spec_data, str):
            raw_prompt = spec_data.strip()
            task_raw_id = f"TASK-{uuid.uuid4().hex[:8].upper()}"
            invariants: List[str] = [raw_prompt]
            domain_name = "General"
            raw_obligations: List[Dict[str, Any]] = []
        elif isinstance(spec_data, dict):
            raw_prompt = spec_data.get("raw_prompt") or spec_data.get("description") or "Execute governed task"
            task_raw_id = spec_data.get("task_id") or f"TASK-{uuid.uuid4().hex[:8].upper()}"
            invariants = spec_data.get("must_invariants") or spec_data.get("invariants") or []
            domain_name = spec_data.get("domain", "General")
            raw_obligations = spec_data.get("obligations") or []
        else:
            raise DomainValidationError(f"Unsupported spec_data type: {type(spec_data)}")

        # 1. Format and validate Task ID
        slug = _sanitize_slug(task_raw_id)
        if not slug.startswith("TASK-"):
            task_id = f"TASK-{slug}"
        else:
            task_id = slug

        if not TASK_ID_PATTERN.match(task_id):
            raise DomainValidationError(f"Synthesized task_id '{task_id}' does not match TASK_ID_PATTERN.")

        # 2. Build or validate RepositoryContext
        if repository_context is None:
            if isinstance(spec_data, dict) and "repository_context" in spec_data:
                rc_dict = spec_data["repository_context"]
                repository_context = RepositoryContext(
                    repository_id=rc_dict.get("repository_id", default_repo_id),
                    base_commit_sha=rc_dict.get("base_commit_sha", default_base_sha),
                    branch=rc_dict.get("branch", "master"),
                )
            else:
                repository_context = RepositoryContext(
                    repository_id=default_repo_id,
                    base_commit_sha=default_base_sha,
                    branch="master",
                )

        # 3. Build Task
        task = Task(
            task_id=task_id,
            raw_prompt=raw_prompt,
            repository_context=repository_context,
            constraints=TaskConstraints(languages=("python",), timeout_seconds=120),
            environment={"domain": domain_name, "compiler": "SpecCompiler-V11.2"},
        )

        # 4. Synthesize Policy
        pol_id = f"POL-{task_id[5:]}" if task_id.startswith("TASK-") else f"POL-{task_id}"
        if not POLICY_ID_PATTERN.match(pol_id):
            pol_id = f"POL-{_sanitize_slug(pol_id)}"

        policy = Policy(
            policy_id=pol_id,
            scope_level=PolicyScope.PROJECT,
            version=1,
            expression=PolicyExpression(
                combinator=CombinatorType.ALL,
                rules=(PolicyRule(rule_type=RuleType.NO_CONFLICTS, parameters={}),),
            ),
        )

        # 5. Extract and build Obligations and Claims
        obligations: List[Obligation] = []
        claims: List[Claim] = []

        if raw_obligations:
            for idx, raw_obl in enumerate(raw_obligations):
                obl_raw_id = raw_obl.get("obligation_id") or f"OBL-{task_id[5:]}-{idx+1}"
                obl_id = obl_raw_id if obl_raw_id.startswith("OBL-") else f"OBL-{obl_raw_id}"
                
                clm_id = f"CLM-{obl_id[4:]}"
                if not CLAIM_ID_PATTERN.match(clm_id):
                    clm_id = f"CLM-{_sanitize_slug(clm_id)}"

                cat_str = raw_obl.get("category", "CORRECTNESS_FUNCTIONAL")
                try:
                    cat = ObligationCategory(cat_str)
                except ValueError:
                    cat = ObligationCategory.CORRECTNESS_FUNCTIONAL

                crit_str = raw_obl.get("criticality", "HIGH")
                try:
                    crit = Criticality(crit_str)
                except ValueError:
                    crit = Criticality.HIGH

                target_module = raw_obl.get("target", "target_module.py")
                claim = Claim(
                    claim_id=clm_id,
                    obligation_id=obl_id,
                    tier=ClaimTier.V0_OBSERVABLE,
                    subject=ClaimSubject(target_type=TargetType.FUNCTION, identifier=target_module),
                    predicate=f"{_sanitize_slug(raw_obl.get('title', 'INVARIANT'))}_SATISFIED",
                    context={"domain": domain_name},
                    expected={"status": "PASS"},
                    criticality=crit,
                    status=ClaimStatus.UNSUPPORTED,
                    required_provider_capabilities=("CAP_EXEC_TEST", "UNIT_TEST_EXECUTION"),
                )
                claims.append(claim)

                obl = Obligation(
                    obligation_id=obl_id,
                    task_id=task_id,
                    title=raw_obl.get("title", f"Requirement {idx+1}"),
                    description=raw_obl.get("description", raw_prompt),
                    category=cat,
                    criticality=crit,
                    status=ObligationStatus.OPEN,
                    depends_on=tuple(raw_obl.get("depends_on", ())),
                    claim_ids=(clm_id,),
                    policy_id=pol_id,
                )
                obligations.append(obl)

        elif invariants:
            for idx, inv_text in enumerate(invariants):
                obl_id = f"OBL-{task_id[5:]}-{idx+1}"
                if not OBLIGATION_ID_PATTERN.match(obl_id):
                    obl_id = f"OBL-{_sanitize_slug(obl_id)}"

                clm_id = f"CLM-{obl_id[4:]}"
                if not CLAIM_ID_PATTERN.match(clm_id):
                    clm_id = f"CLM-{_sanitize_slug(clm_id)}"

                # Determine category by keyword heuristics
                inv_lower = inv_text.lower()
                if any(k in inv_lower for k in ("security", "auth", "token", "permission", "sanitize")):
                    cat = ObligationCategory.SECURITY_INTEGRITY
                elif any(k in inv_lower for k in ("performance", "latency", "scale", "throughput")):
                    cat = ObligationCategory.PERFORMANCE_SCALE
                elif any(k in inv_lower for k in ("safety", "overdraft", "limit", "floor", "rate")):
                    cat = ObligationCategory.OPERATIONAL_SAFETY
                else:
                    cat = ObligationCategory.CORRECTNESS_FUNCTIONAL

                claim = Claim(
                    claim_id=clm_id,
                    obligation_id=obl_id,
                    tier=ClaimTier.V0_OBSERVABLE,
                    subject=ClaimSubject(target_type=TargetType.FUNCTION, identifier="target_module.py"),
                    predicate=f"INVARIANT_{idx+1}_SATISFIED",
                    context={"invariant_text": inv_text, "domain": domain_name},
                    expected={"status": "PASS"},
                    criticality=Criticality.HIGH,
                    status=ClaimStatus.UNSUPPORTED,
                    required_provider_capabilities=("CAP_EXEC_TEST", "UNIT_TEST_EXECUTION"),
                )
                claims.append(claim)

                obl = Obligation(
                    obligation_id=obl_id,
                    task_id=task_id,
                    title=f"Invariant {idx+1}: {inv_text[:40]}...",
                    description=inv_text,
                    category=cat,
                    criticality=Criticality.HIGH,
                    status=ObligationStatus.OPEN,
                    depends_on=(),
                    claim_ids=(clm_id,),
                    policy_id=pol_id,
                )
                obligations.append(obl)

        else:
            # Single baseline obligation
            obl_id = f"OBL-{task_id[5:]}-1"
            clm_id = f"CLM-{obl_id[4:]}"

            claim = Claim(
                claim_id=clm_id,
                obligation_id=obl_id,
                tier=ClaimTier.V0_OBSERVABLE,
                subject=ClaimSubject(target_type=TargetType.FUNCTION, identifier="target_module.py"),
                predicate="TASK_GOAL_SATISFIED",
                context={"domain": domain_name},
                expected={"status": "PASS"},
                criticality=Criticality.HIGH,
                status=ClaimStatus.UNSUPPORTED,
                required_provider_capabilities=("CAP_EXEC_TEST", "UNIT_TEST_EXECUTION"),
            )
            claims.append(claim)

            obl = Obligation(
                obligation_id=obl_id,
                task_id=task_id,
                title="Task Correctness Goal",
                description=raw_prompt,
                category=ObligationCategory.CORRECTNESS_FUNCTIONAL,
                criticality=Criticality.HIGH,
                status=ObligationStatus.OPEN,
                depends_on=(),
                claim_ids=(clm_id,),
                policy_id=pol_id,
            )
            obligations.append(obl)

        # 6. Validate Obligation DAG acyclicity and constraints
        dag = ObligationGraph(task_id=task_id)
        for obl in obligations:
            dag.add_obligation(obl)
        dag.validate()

        return CompiledDomainPackage(
            task=task,
            obligations=tuple(obligations),
            claims=tuple(claims),
            policies=(policy,),
        )
