"""Non-authoritative reference scaffold operating and proposal loop.

Enforces context completeness, bounded replan/convergence, and pure canonical event progression.
Provided for development, testing, and reference execution; not an authoritative
production execution runtime.
"""
from __future__ import annotations

import types
from typing import Any, Mapping, Optional

from sclass_semantics_v6_0_1 import (
    ActorIdentity,
    AuthorizationDecision,
    AuthorizationLease,
    AuthorizationLeaseClaims,
    AuthorizationState,
    AuthorizedWorkRequest,
    BudgetReservationState,
    Digest,
    EngineeringState,
    ExecutionLease,
    FrozenMap,
    ObligationStatus,
    SignatureBlock,
    StateBinding,
    UtcInstant,
    VerificationStatus,
    WorkerClaimStatus,
    WorkerContract,
    WorkProposal,
    digest,
    state_binding_digest,
)
from sclass_runtime_v6_0_1 import (
    KeyStatus,
    SignatureVerificationResult,
    SQLiteKeyDirectory,
    _budget_leq,
    _now,
    authorization_binding_digest,
    authorization_lease_signature_message,
    authorized_work_request_envelope_digest,
)
from sclass.reference_impl.verification import ReferenceVerificationProvider
from sclass.reference_impl.worker import is_work_result_admissible


def fmap(items=()):
    return FrozenMap.from_items(items)


def compute_request_content_digest(req: AuthorizedWorkRequest) -> Digest:
    """Normative request-content digest per 00-SPEC line 2629 (domain 'sclass/request/v1')."""
    obj_rev = (
        req.proposal.state_binding.objective_revision
        if (getattr(req, "proposal", None) and getattr(req.proposal, "state_binding", None))
        else ""
    )
    wg_rev = (
        req.proposal.state_binding.workgraph_revision
        if (getattr(req, "proposal", None) and getattr(req.proposal, "state_binding", None))
        else ""
    )
    ctx_dig = (
        getattr(req.proposal, "context_digest", "")
        if getattr(req, "proposal", None)
        else ""
    )
    return digest(
        "sclass/request/v1",
        (
            req.node_id,
            req.primary_obligation_id,
            req.satisfies_obligation_ids,
            req.action_type,
            req.action_description,
            req.requested_effect,
            ctx_dig,
            req.constraints,
            obj_rev,
            wg_rev,
        ),
    )


__all__ = ["ReferenceOperatingLoop", "compute_request_content_digest"]


class ReferenceOperatingLoop:
    """Non-authoritative reference scaffold D8 operating and proposal loop.

    Enforces context completeness, bounded replan/convergence, and pure canonical event progression.
    A6.2 / R1-F5:
      - Does NOT manufacture AuthorizationLeaseClaims, AuthorizationLease, ExecutionLease, or SignatureBlock.
      - Requires genuine caller-supplied AuthorizedWorkRequest; fails closed when omitted or invalid.
      - Enforces WorkResult admissibility at the boundary before accepting CLAIMED_COMPLETE.
      - Disallows 1-argument observation-provider path; observation provider must receive (proposal, worker_result).
      - Enforces mandatory observation binding across request_id, execution_attempt_id, execution_generation,
        worker_identity, and worker_result_digest / output_digest (missing fields fail closed).
      - Enforces genuine Ed25519 authorization lease verification against SQLiteKeyDirectory, active key status,
        validity window, canonical authorization decisions in state, and authorization binding digests.
    """

    def __init__(
        self,
        store: Any,
        verification_provider: Optional[ReferenceVerificationProvider] = None,
        max_iterations: int = 10,
        key_directory: Optional[Any] = None,
    ):
        self.store = store
        self.verification_provider = verification_provider or ReferenceVerificationProvider()
        self.max_iterations = max_iterations
        self.key_directory = key_directory

    def run_cycle(
        self,
        workspace_id: str,
        actor: ActorIdentity,
        worker: Optional[WorkerContract] = None,
        observation_provider: Optional[Any] = None,
        authorized_request: Optional[AuthorizedWorkRequest] = None,
        authorized_requests: Optional[Any] = None,
        key_directory: Optional[Any] = None,
        now: Optional[UtcInstant] = None,
        expected_audience: Optional[str] = None,
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

            # Expressly permitted non-execution outcomes
            # A6.2 fail-closed: If no real worker capability is provided,
            # never fabricate synthetic observations or claim convergence.
            if worker is None:
                # Authentic canonical blank state with no obligations converges safely
                if isinstance(state, EngineeringState):
                    obligations_obj = getattr(state, "obligations", None)
                    obl_map = getattr(obligations_obj, "_obligations", None) if obligations_obj is not None else None
                    if not obl_map or not any(getattr(o, "status", None) is not ObligationStatus.SATISFIED for o in obl_map.values()):
                        return {
                            "status": "CONVERGED",
                            "iterations": iterations,
                            "proposals": tuple(proposals),
                            "satisfied": tuple(satisfied),
                            "error": None,
                        }
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

            # R1-F5 fail-closed: Caller must provide authorized work request on execution path.
            if authorized_request is None and authorized_requests is None:
                return {
                    "status": "IN_DOUBT",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "missing_authorized_work_request",
                }

            # Finding 1: Canonical state guard on any path capable of authorized execution.
            # Must occur before accessing canonical-state fields or obligations.
            if not isinstance(state, EngineeringState):
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "non_canonical_engineering_state",
                }

            # Genuine canonical EngineeringState verified; inspect obligations safely
            obligations_obj = getattr(state, "obligations", None)
            obl_map = getattr(obligations_obj, "_obligations", None) if obligations_obj is not None else None
            if not obl_map:
                return {
                    "status": "CONVERGED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": None,
                }

            unsatisfied = [
                obl
                for obl in obl_map.values()
                if getattr(obl, "status", None) is not ObligationStatus.SATISFIED
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

            # Resolve caller-supplied request
            req = None
            if authorized_request is not None:
                if not isinstance(authorized_request, AuthorizedWorkRequest):
                    return {
                        "status": "ESCALATED",
                        "iterations": iterations,
                        "proposals": tuple(proposals),
                        "satisfied": tuple(satisfied),
                        "error": "invalid_authorized_work_request_type",
                    }
                req = authorized_request
            elif authorized_requests is not None:
                if callable(authorized_requests):
                    try:
                        req = authorized_requests(current_obl)
                    except Exception as e:
                        return {
                            "status": "ESCALATED",
                            "iterations": iterations,
                            "proposals": tuple(proposals),
                            "satisfied": tuple(satisfied),
                            "error": f"authorized_requests_error: {e}",
                        }
                elif isinstance(authorized_requests, Mapping):
                    req = authorized_requests.get(current_obl.obligation_id)
                if req is not None and not isinstance(req, AuthorizedWorkRequest):
                    return {
                        "status": "ESCALATED",
                        "iterations": iterations,
                        "proposals": tuple(proposals),
                        "satisfied": tuple(satisfied),
                        "error": "invalid_authorized_work_request_type",
                    }

            if req is None:
                return {
                    "status": "IN_DOUBT",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "missing_authorized_work_request",
                }

            # Check that caller-supplied request corresponds to current obligation
            if req.primary_obligation_id != current_obl.obligation_id and current_obl.obligation_id not in req.satisfies_obligation_ids:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": f"authorized_work_request_obligation_mismatch: {req.primary_obligation_id} != {current_obl.obligation_id}",
                }

            # R1-F5 Complete Canonical Authorization Chain Verification
            # 1. Structural validation of WorkProposal, StateBinding, and Leases
            proposal = getattr(req, "proposal", None)
            if proposal is None or not isinstance(proposal, WorkProposal):
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "missing_or_invalid_work_proposal",
                }

            sb = getattr(proposal, "state_binding", None)
            if sb is None or not isinstance(sb, StateBinding):
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "missing_or_invalid_state_binding",
                }

            auth_lease = getattr(req, "authorization_lease", None)
            if auth_lease is None or not isinstance(auth_lease, AuthorizationLease):
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "missing_or_invalid_authorization_lease",
                }

            claims = getattr(auth_lease, "claims", None)
            sig = getattr(auth_lease, "signature", None)
            if claims is None or not isinstance(claims, AuthorizationLeaseClaims) or sig is None or not isinstance(sig, SignatureBlock):
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "invalid_authorization_lease_structure",
                }

            ex_lease = getattr(req, "execution_lease", None)
            if ex_lease is None or not isinstance(ex_lease, ExecutionLease):
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "missing_or_invalid_execution_lease",
                }

            # 2. Validity window and audience validation
            current_time = now if now is not None else _now()
            if not (claims.issued_at.epoch_ns <= current_time.epoch_ns < claims.expires_at.epoch_ns):
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "expired_authorization_lease",
                }

            if not (ex_lease.issued_at.epoch_ns <= current_time.epoch_ns < ex_lease.expires_at.epoch_ns):
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "expired_execution_lease",
                }

            if not claims.audience:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "missing_authorization_audience",
                }

            exp_aud = expected_audience if expected_audience is not None else "worker"
            if claims.audience != exp_aud:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": f"authorization_audience_mismatch: {claims.audience} != {exp_aud}",
                }

            active_policy = getattr(state, "active_policy", None)
            if active_policy is not None:
                auth_rules = getattr(active_policy, "authorization_rules", None)
                allowed_audiences = getattr(auth_rules, "allowed_audiences", None) if auth_rules is not None else None
                if allowed_audiences is not None and claims.audience not in allowed_audiences:
                    return {
                        "status": "ESCALATED",
                        "iterations": iterations,
                        "proposals": tuple(proposals),
                        "satisfied": tuple(satisfied),
                        "error": f"authorization_audience_not_allowed_by_policy: {claims.audience}",
                    }

            # 3. Key directory resolution and trusted active Ed25519 key verification
            kd = (
                key_directory
                or self.key_directory
                or getattr(self.store, "key_directory", None)
                or getattr(self.store, "_key_directory", None)
                or getattr(getattr(self.store, "control_plane", None), "keys", None)
            )
            if kd is None:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "missing_key_directory_for_signature_verification",
                }

            key_status = kd.status(sig.key_id, sig.trust_root, current_time)
            if key_status is KeyStatus.UNKNOWN:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": f"unknown_authorization_key: {sig.key_id}",
                }
            if key_status is KeyStatus.REVOKED:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": f"revoked_authorization_key: {sig.key_id}",
                }
            if key_status is not KeyStatus.ACTIVE:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": f"inactive_authorization_key_{key_status.value}: {sig.key_id}",
                }

            if claims.issuer_identity != sig.key_id:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "authorization_key_issuer_mismatch",
                }

            lease_msg = authorization_lease_signature_message(claims)
            v_sig = kd.verify_current(sig, lease_msg, current_time)
            if v_sig is not SignatureVerificationResult.VALID:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": f"invalid_authorization_lease_signature: {v_sig.value}",
                }

            # 4. Canonical authorization decision in state
            auth_decisions = getattr(state, "authorization_decisions", None)
            decision = None
            if isinstance(auth_decisions, Mapping) or hasattr(auth_decisions, "get"):
                decision = auth_decisions.get(claims.decision_id)

            if decision is None or not isinstance(decision, AuthorizationDecision):
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": f"missing_or_invalid_authorization_decision: {claims.decision_id}",
                }

            if decision.decision is not AuthorizationState.ALLOW:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": f"authorization_decision_not_allow: {decision.decision.value}",
                }

            if decision.proposal_id != proposal.proposal_id:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "authorization_decision_proposal_mismatch",
                }

            if claims.expires_at.epoch_ns > decision.expires_at.epoch_ns:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "authorization_lease_expires_after_decision",
                }

            if not decision.worker_identity or decision.worker_identity != ex_lease.worker_identity:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "authorization_worker_identity_mismatch",
                }

            # 5. Request-content digest and proposal binding
            recomputed_request_content = compute_request_content_digest(req)
            req_content = getattr(proposal, "request_content_digest", None)
            if not req_content or req_content != recomputed_request_content:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "request_content_digest_mismatch: proposal",
                }
            if claims.request_content_digest != recomputed_request_content:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "request_content_digest_mismatch: claims",
                }
            if decision.request_content_digest != recomputed_request_content:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "request_content_digest_mismatch: decision",
                }
            if ex_lease.request_content_digest != recomputed_request_content:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "request_content_digest_mismatch: execution_lease",
                }

            # Finding 2: Fail-closed context completeness and binding verification
            ctx = getattr(req, "context", None)
            if ctx is None:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "missing_request_context",
                }

            repo_map = getattr(ctx, "repo_map", None)
            if repo_map is None:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "missing_context_repo_map",
                }

            repo_map_digest = getattr(repo_map, "content_digest", None)
            if not repo_map_digest:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "missing_repo_map_content_digest",
                }

            if repo_map_digest != req.proposal.context_digest:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "context_digest_mismatch: repo_map",
                }

            # 6. State-binding, workspace, policy, and snapshot binding
            computed_binding = state_binding_digest(sb)
            if req.state_binding_digest != computed_binding:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "state_binding_mismatch: request",
                }
            if claims.state_binding_digest != computed_binding:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "state_binding_mismatch: claims",
                }
            if decision.state_binding_digest != computed_binding:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "state_binding_mismatch: decision",
                }
            if ex_lease.state_binding_digest != computed_binding:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "state_binding_mismatch: execution_lease",
                }

            state_ws = getattr(state, "workspace_id", None)
            if claims.workspace_id != state_ws or sb.workspace_id != state_ws or ex_lease.workspace_id != state_ws:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "workspace_binding_mismatch",
                }

            state_pol = getattr(state, "policy_version", None)
            if (
                claims.policy_version != state_pol
                or decision.policy_version != state_pol
                or sb.policy_version != state_pol
                or ex_lease.policy_version != state_pol
            ):
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "policy_version_binding_mismatch",
                }

            state_snap = getattr(state, "workspace_snapshot_id", None)
            if (
                claims.workspace_snapshot_id != state_snap
                or decision.workspace_snapshot_id != state_snap
                or sb.workspace_snapshot_id != state_snap
                or ex_lease.workspace_snapshot_id != state_snap
            ):
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "snapshot_binding_mismatch",
                }

            # 7. Effect-scope consistency
            if decision.effect_scope != claims.allowed_effects or decision.effect_scope != req.effect_scope:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "effect_scope_mismatch",
                }

            # 8. Budget reservation, budget lineage, and execution generation
            if not req.budget_reservation_id or ex_lease.budget_reservation_id != req.budget_reservation_id:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "budget_reservation_id_mismatch",
                }

            reservations = getattr(state, "budget_reservations", None)
            reservation = None
            if isinstance(reservations, Mapping) or hasattr(reservations, "get"):
                reservation = reservations.get(req.budget_reservation_id)
            if reservation is None:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": f"missing_budget_reservation: {req.budget_reservation_id}",
                }

            if getattr(reservation, "lifecycle_state", None) is not BudgetReservationState.RESERVED:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": f"budget_reservation_not_reserved: {getattr(reservation, 'lifecycle_state', None)}",
                }

            if reservation.workspace_id != state_ws or reservation.request_id != req.request_id:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "budget_reservation_binding_mismatch",
                }

            if (
                reservation.governing_budget_lineage_id != req.governing_budget_lineage_id
                or ex_lease.governing_budget_lineage_id != req.governing_budget_lineage_id
            ):
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "budget_lineage_mismatch",
                }

            if reservation.expires_at.epoch_ns < claims.expires_at.epoch_ns:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "budget_reservation_expires_before_lease",
                }

            req_eff = getattr(req, "requested_effect", None)
            if req_eff is not None and hasattr(req_eff, "requested_budget") and hasattr(reservation, "amount"):
                if not _budget_leq(req_eff.requested_budget, reservation.amount):
                    return {
                        "status": "ESCALATED",
                        "iterations": iterations,
                        "proposals": tuple(proposals),
                        "satisfied": tuple(satisfied),
                        "error": "requested_budget_exceeds_reservation",
                    }

            work_graph = getattr(state, "work_graph", None)
            nodes = getattr(work_graph, "_nodes", None) if work_graph is not None else None
            if nodes is None or not isinstance(nodes, Mapping) or req.node_id not in nodes:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": f"node_not_in_work_graph: {req.node_id}",
                }

            node = nodes[req.node_id]
            if (
                getattr(node, "execution_generation", None) != req.execution_generation
                or ex_lease.execution_generation != req.execution_generation
            ):
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "execution_generation_mismatch",
                }
            if getattr(node, "worker_id", None) is not None and node.worker_id != decision.worker_identity:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "work_node_worker_identity_mismatch",
                }

            # 9. Authorization lease to execution lease linkage
            if ex_lease.authorization_lease_id != claims.lease_id:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "execution_lease_authorization_linkage_mismatch",
                }

            if ex_lease.node_id != req.node_id:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "execution_lease_node_id_mismatch",
                }

            # 10. Recomputed authorization binding digest
            expected_auth_binding = authorization_binding_digest(decision, auth_lease)
            if req.authorization_binding_digest != expected_auth_binding:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "authorization_binding_mismatch: authorization_binding_digest",
                }

            # 11. Recomputed request envelope digest via canonical runtime helper
            if (
                getattr(state, "causal_frontier", None) is None
                or not getattr(state.causal_frontier, "authorization_epoch", None)
            ):
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "missing_or_invalid_canonical_state_or_frontier",
                }

            expected_envelope = authorized_work_request_envelope_digest(req, state, decision)
            if req.envelope_digest != expected_envelope:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "authorization_binding_mismatch: envelope_digest",
                }

            if proposal.proposal_id not in proposals:
                proposals.append(proposal.proposal_id)

            # Execute worker with authentic AuthorizedWorkRequest
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

            # R1-F1: Before accepting CLAIMED_COMPLETE, require the returned WorkResult
            # to pass the defined admissibility check. A result with absent measurements (None)
            # must NOT progress to observation or verification.
            if not is_work_result_admissible(worker_result):
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "inadmissible_work_result_missing_metrics",
                }

            # R1-F5: Observation provider must receive proposal and genuine worker_result.
            # Do NOT allow 1-argument fallback for an execution requiring provenance binding.
            try:
                obs = observation_provider(proposal, worker_result)
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

            # R1-F5: Mandatory observation provenance binding.
            # Observation must contain and match request ID, attempt ID, generation,
            # worker identity, and worker-result output digest. Missing fields fail closed.
            obs_req_id = getattr(obs, "request_id", None)
            if obs_req_id is None:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "observation_binding_missing_field: request_id",
                }
            if obs_req_id != req.request_id:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": f"observation_binding_mismatch: request_id mismatch ({obs_req_id} != {req.request_id})",
                }

            obs_attempt = getattr(obs, "execution_attempt_id", None)
            if obs_attempt is None:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "observation_binding_missing_field: execution_attempt_id",
                }
            if obs_attempt != req.execution_attempt_id:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": f"observation_binding_mismatch: execution_attempt_id mismatch ({obs_attempt} != {req.execution_attempt_id})",
                }

            obs_gen = getattr(obs, "execution_generation", None)
            if obs_gen is None:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "observation_binding_missing_field: execution_generation",
                }
            if obs_gen != req.execution_generation:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": f"observation_binding_mismatch: execution_generation mismatch ({obs_gen} != {req.execution_generation})",
                }

            obs_worker = getattr(obs, "worker_identity", None)
            w_identity = getattr(worker_result, "worker_identity", None)
            if obs_worker is None:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "observation_binding_missing_field: worker_identity",
                }
            if not w_identity or obs_worker != w_identity:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": f"observation_binding_mismatch: worker_identity mismatch ({obs_worker} != {w_identity})",
                }

            obs_result_dig = getattr(obs, "worker_result_digest", None) or getattr(obs, "output_digest", None)
            w_out_dig = getattr(worker_result, "output_digest", None)
            if obs_result_dig is None:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "observation_binding_missing_field: worker_result_digest",
                }
            if not w_out_dig or obs_result_dig != w_out_dig:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": f"observation_binding_mismatch: worker_result_digest mismatch ({obs_result_dig} != {w_out_dig})",
                }

            step = getattr(current_obl, "verification_step", None)
            v_res = self.verification_provider.verify(current_obl, step, obs)
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
