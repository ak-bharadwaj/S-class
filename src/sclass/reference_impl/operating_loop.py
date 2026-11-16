"""Non-authoritative reference scaffold operating and proposal loop.

Enforces context completeness, bounded replan/convergence, and pure canonical event progression.
Provided for development, testing, and reference execution; not an authoritative
production execution runtime.
"""
from __future__ import annotations

import types
from typing import Any, Optional

from sclass_semantics_v6_0_1 import (
    ActionType,
    ActorIdentity,
    AuthorizationLease,
    AuthorizationLeaseClaims,
    AuthorizedWorkRequest,
    ContextItem,
    ContextItemKind,
    ContextPackage,
    DataClassification,
    Digest,
    EffectScope,
    ExecutionIdentity,
    ExecutionLease,
    FrozenMap,
    KeyStatus,
    ObligationStatus,
    RedactionReport,
    RequestedEffect,
    ResourceBudget,
    SignatureBlock,
    TokenUsage,
    TrustLevel,
    UtcInstant,
    VerificationStatus,
    WorkerClaimStatus,
    WorkerContract,
    WorkProposal,
    canonical_current_state_binding,
    digest,
    state_binding_digest,
)
from sclass.reference_impl.verification import ReferenceVerificationProvider


def fmap(items=()):
    return FrozenMap.from_items(items)


class ReferenceOperatingLoop:
    """Non-authoritative reference scaffold D8 operating and proposal loop.

    Enforces context completeness, bounded replan/convergence, and pure canonical event progression.
    A6.2: Removes fabricated observations, synthetic successful process results, and default-pass behavior.
    """

    def __init__(
        self,
        store: Any,
        verification_provider: Optional[ReferenceVerificationProvider] = None,
        max_iterations: int = 10,
    ):
        self.store = store
        self.verification_provider = verification_provider or ReferenceVerificationProvider()
        self.max_iterations = max_iterations

    def run_cycle(
        self,
        workspace_id: str,
        actor: ActorIdentity,
        worker: Optional[WorkerContract] = None,
        observation_provider: Optional[Any] = None,
    ) -> dict:
        iterations = 0
        proposals = []
        satisfied = []

        if self.max_iterations <= 0:
            return {
                "status": "BOUND_EXCEEDED",
                "iterations": 0,
                "proposals": (),
                "satisfied": (),
                "error": "max_iterations_exceeded",
            }

        while iterations < self.max_iterations:
            iterations += 1
            state = self.store._load_canonical_state(workspace_id)

            if not state.obligations or not getattr(state.obligations, "_obligations", None):
                return {
                    "status": "CONVERGED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": None,
                }

            unsatisfied = [
                obl
                for obl in state.obligations._obligations.values()
                if obl.status is not ObligationStatus.SATISFIED
            ]
            if not unsatisfied:
                return {
                    "status": "CONVERGED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": None,
                }

            current_obl = unsatisfied[0]
            prop_id = f"prop-{current_obl.obligation_id}-{iterations}"
            proposals.append(prop_id)

            # A6.2 fail-closed: If no real worker or verification capability is provided,
            # never fabricate synthetic observations or claim convergence.
            if worker is None:
                return {
                    "status": "IN_DOUBT",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "missing_worker_capability",
                }

            # A6.2 fail-closed: Missing observation capture capability produces IN_DOUBT.
            # Never fabricate synthetic ObservationRecord with default pass results.
            if observation_provider is None:
                return {
                    "status": "IN_DOUBT",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "missing_observation_capture_capability",
                }

            binding = canonical_current_state_binding(state, 1, "lineage-default")
            req_budget = ResourceBudget(1, 1, 0, 100, 0, 1, 1, 0, 0, 10, 1)
            effect = RequestedEffect(
                filesystem=(),
                subprocess=(),
                network=(),
                environment=fmap(),
                credentials=(),
                external_side_effects=(),
                requested_budget=req_budget,
            )
            req_content = (
                current_obl.obligation_id,
                getattr(current_obl, "requirement_id", "req-1"),
            )
            req_content_digest = digest("sclass/request-content/v1", req_content)
            ctx_digest = digest(
                "sclass/context/v1",
                (state.workspace_id, binding.objective_revision, current_obl.obligation_id),
            )

            proposal = WorkProposal(
                prop_id,
                current_obl.obligation_id,
                req_content_digest,
                binding,
                ctx_digest,
                effect,
            )

            sb_digest = state_binding_digest(binding)
            env_digest = digest("sclass/envelope/v1", (prop_id, sb_digest, req_content_digest))

            scope = EffectScope(
                fs_rules=(),
                process_rules=(),
                network_rules=(),
                allowed_env=fmap(),
                working_directory=state.workspace_id,
                credential_grants=(),
                external_effect_rules=(),
                resource_budget=req_budget,
            )

            claims = AuthorizationLeaseClaims(
                lease_id=f"lease-{prop_id}",
                decision_id=f"dec-{prop_id}",
                request_content_digest=req_content_digest,
                state_binding_digest=sb_digest,
                policy_version=state.policy_version,
                allowed_effects=scope,
                workspace_id=state.workspace_id,
                workspace_snapshot_id=state.workspace_snapshot_id,
                audience="worker",
                nonce=f"nonce-{iterations}",
                issuer_identity=actor.actor_id,
                issued_at=UtcInstant(0),
                expires_at=UtcInstant(3600),
            )
            sig_bytes = digest("sclass/lease-signature/v1", (claims.lease_id, sb_digest)).encode()
            sig = SignatureBlock(
                algorithm="ed25519",
                key_id=actor.actor_id,
                trust_root="root",
                canonicalization_version="c1",
                signature=sig_bytes,
            )
            auth_lease = AuthorizationLease(claims, sig)

            worker_id = getattr(worker.profile(), "profile_id", "ref-worker") if hasattr(worker, "profile") else "ref-worker"
            ex_identity = ExecutionIdentity(
                path="/bin/worker",
                resolved_identity=worker_id,
                digest=digest("sclass/worker-identity/v1", worker_id),
                version="1.0",
                interpreter="python",
                parent_executable_digest=digest("sclass/parent-exec/v1", "sclass"),
                environment_digest=digest("sclass/env/v1", state.workspace_id),
                process_start_time_ns=0,
                child_lineage=(),
            )
            ex_lease = ExecutionLease(
                lease_id=f"ex-lease-{prop_id}",
                workspace_id=state.workspace_id,
                node_id=current_obl.obligation_id,
                request_content_digest=req_content_digest,
                execution_generation=binding.execution_generation,
                execution_attempt_id=f"attempt-{iterations}",
                state_binding_digest=sb_digest,
                governing_budget_lineage_id=binding.governing_budget_lineage_id,
                budget_reservation_id=f"res-{iterations}",
                workspace_snapshot_id=state.workspace_snapshot_id,
                target_snapshot_digest=binding.target_snapshot_digest,
                authorization_lease_id=auth_lease.claims.lease_id,
                objective_revision=binding.objective_revision,
                policy_version=state.policy_version,
                worker_identity=worker_id,
                executable_identity=ex_identity,
                execution_environment_digest=digest("sclass/env/v1", state.workspace_id),
                state_revision=getattr(state, "state_revision", "rev-1"),
                fencing_token=1,
                issued_at=UtcInstant(0),
                expires_at=UtcInstant(3600),
            )

            ctx_item = ContextItem(
                item_id="repo-map",
                kind=ContextItemKind.REPO_MAP,
                source_snapshot_id=state.workspace_snapshot_id,
                path=None,
                range=None,
                symbol=None,
                content_digest=ctx_digest,
                classification=DataClassification.INTERNAL,
                trust=TrustLevel.TRUSTED,
                rank=1,
                token_estimate=10,
            )
            ctx_pkg = ContextPackage(
                budget=4000,
                repo_map=ctx_item,
                items=(),
                obligation_context=current_obl.obligation_id,
                constraints=(),
                prior_evidence=(),
                token_accounting=TokenUsage(0, 0, 0, 0, 10, 10, 0),
                redaction=RedactionReport(state.policy_version, (), 0, ctx_digest),
                ranking_policy_version="ranking-v1",
            )

            req = AuthorizedWorkRequest(
                request_id=f"req-{prop_id}",
                node_id=current_obl.obligation_id,
                execution_generation=binding.execution_generation,
                execution_attempt_id=f"attempt-{iterations}",
                governing_budget_lineage_id=binding.governing_budget_lineage_id,
                budget_reservation_id=f"res-{iterations}",
                state_binding_digest=sb_digest,
                primary_obligation_id=current_obl.obligation_id,
                satisfies_obligation_ids=frozenset({current_obl.obligation_id}),
                action_description=f"Execute {current_obl.obligation_id}",
                action_type=ActionType.CODE_EDIT,
                requested_effect=effect,
                effect_scope=scope,
                context=ctx_pkg,
                constraints=(),
                proposal=proposal,
                authorization_lease=auth_lease,
                execution_lease=ex_lease,
                authorization_binding_digest=digest("sclass/auth-binding/v1", (auth_lease.claims.lease_id, sb_digest)),
                envelope_digest=env_digest,
            )

            try:
                worker_result = worker.execute(req)
            except Exception as e:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": f"worker_execution_error: {e}",
                }

            if worker_result is None or getattr(worker_result, "claim_status", None) is not WorkerClaimStatus.CLAIMED_COMPLETE:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "worker_execution_failed",
                }

            # Call observation_provider passing proposal and the genuine worker_result
            try:
                import inspect
                sig = inspect.signature(observation_provider)
                if len(sig.parameters) >= 2:
                    obs = observation_provider(proposal, worker_result)
                else:
                    obs = observation_provider(proposal)
            except Exception as e:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": f"observation_provider_error: {e}",
                }

            if obs is None:
                return {
                    "status": "IN_DOUBT",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "observation_missing",
                }

            # CL Finding R1-F5: Observation must be demonstrably bound to the execution
            obs_req_id = getattr(obs, "request_id", None)
            if obs_req_id and obs_req_id != req.request_id:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": f"observation_binding_mismatch: request_id mismatch ({obs_req_id} != {req.request_id})",
                }

            obs_attempt = getattr(obs, "execution_attempt_id", None)
            if obs_attempt and obs_attempt != req.execution_attempt_id:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": f"observation_binding_mismatch: attempt_id mismatch ({obs_attempt} != {req.execution_attempt_id})",
                }

            obs_gen = getattr(obs, "execution_generation", None)
            if obs_gen is not None and obs_gen != req.execution_generation:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": f"observation_binding_mismatch: generation mismatch ({obs_gen} != {req.execution_generation})",
                }

            obs_worker = getattr(obs, "worker_identity", None)
            w_identity = getattr(worker_result, "worker_identity", None)
            if obs_worker and w_identity and obs_worker != w_identity:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": f"observation_binding_mismatch: worker_identity mismatch ({obs_worker} != {w_identity})",
                }

            obs_result_dig = getattr(obs, "worker_result_digest", None)
            w_out_dig = getattr(worker_result, "output_digest", None)
            if obs_result_dig and w_out_dig and obs_result_dig != w_out_dig:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": f"observation_binding_mismatch: worker_result_digest mismatch ({obs_result_dig} != {w_out_dig})",
                }

            step = getattr(current_obl, "verification_step", None)
            v_res = self.verification_provider.verify(current_obl, step, obs)
            from sclass_semantics_v6_0_1 import VerificationStatus
            if v_res.status is not VerificationStatus.PASS:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "verification_failed",
                }

            satisfied.append(current_obl.obligation_id)
            return {
                "status": "PROGRESSING",
                "iterations": iterations,
                "proposals": tuple(proposals),
                "satisfied": tuple(satisfied),
                "error": None,
            }

        return {
            "status": "BOUND_EXCEEDED",
            "iterations": iterations,
            "proposals": tuple(proposals),
            "satisfied": tuple(satisfied),
            "error": "max_iterations_exceeded",
        }

