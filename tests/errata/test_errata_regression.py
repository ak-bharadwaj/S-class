"""Regression test suite proving normative fixes for ERR-001 through ERR-010.

Authoritative specification: 02-v6.0.1-NORMATIVE-ERRATA.md.
"""
from __future__ import annotations

import dataclasses
import sys
from dataclasses import replace
from pathlib import Path

import pytest

_conformance_dir = Path(__file__).resolve().parents[2] / "10-CONFORMANCE"
_runtime_dir = Path(__file__).resolve().parents[2] / "20-RUNTIME"
if str(_conformance_dir) not in sys.path:
    sys.path.insert(0, str(_conformance_dir))
if str(_runtime_dir) not in sys.path:
    sys.path.insert(0, str(_runtime_dir))

from sclass_runtime_v6_0_1 import SQLiteEventStore, _budget_add, _budget_sub
from sclass_semantics_v6_0_1 import (
    COMMIT_SCHEMA_VERSION,
    GENESIS_EVENT_HASH,
    REFERENCE_REDUCER,
    ActionType,
    ActorIdentity,
    ActorKind,
    BreakGlassAuthority,
    CanonicalEvent,
    Capability,
    CommitRecord,
    CommitState,
    Digest,
    EffectScope,
    EventType,
    EvidenceKind,
    ExecutionGeneration,
    ExecutionGenerationStatus,
    ExternalEffectRule,
    FreshnessDimension,
    FrozenMap,
    FsAccess,
    FsMode,
    FsRule,
    GateResult,
    NetAccess,
    NetRule,
    NetworkDestination,
    ProcessRule,
    QuiescenceProof,
    RequestedEffect,
    ResourceBudget,
    ScopeAuthorizationResult,
    SignatureBlock,
    SignedEvidencePayload,
    StateBinding,
    UtcInstant,
    VerificationStatus,
    WorkerClaimStatus,
    WorkResult,
    _canonical_rel,
    admit_work_result,
    authorize_with_authorities,
    authorized,
    capability_authorizes,
    commit_record_digest,
    engineering_state_digest,
    genesis_engineering_state,
    signed_payload_digest,
)


def fmap(items=()):
    return FrozenMap.from_items(items)


def z() -> ResourceBudget:
    return ResourceBudget(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)



def empty_scope(**kw) -> EffectScope:
    return EffectScope(
        kw.get("fs_rules", ()),
        kw.get("process_rules", ()),
        kw.get("network_rules", ()),
        kw.get("allowed_env", fmap()),
        kw.get("working_directory", "."),
        kw.get("credential_grants", ()),
        kw.get("external_effect_rules", ()),
        kw.get("resource_budget", z()),
    )


def req(fs=(), process=(), network=(), environment=None, budget=None) -> RequestedEffect:
    return RequestedEffect(
        tuple(fs), tuple(process), tuple(network),
        fmap(tuple((environment or {}).items())), (), (), budget or z()
    )


def _test_actor() -> ActorIdentity:

    return ActorIdentity("system-test", ActorKind.SYSTEM, None)


def _test_event(seq: int = 1, prev: Digest = GENESIS_EVENT_HASH, commit_id: str = "commit-1", workspace: str = "w") -> CanonicalEvent:
    return CanonicalEvent.create(
        f"evt-{seq}",
        commit_id,
        workspace,
        seq,
        EventType.SHUTDOWN_REQUESTED,
        1,
        "system",
        _test_actor(),
        "causation-1",
        "correlation-1",
        fmap((("reason", "errata-test"),)),
        prev,
        "pol-1",
        "6.0.1",
        UtcInstant(1000 * seq),
    )


def _commit_for_event(event: CanonicalEvent, state, commit_id: str = "commit-1", ws: str = "w") -> CommitRecord:
    sd = engineering_state_digest(state)
    provisional = CommitRecord(
        commit_id,
        ws,
        (event.event_id, f"state:{ws}"),
        (event.event_hash, sd),
        ("event", "state"),
        event.previous_event_hash,
        event.event_hash,
        state.state_revision,
        event.event_sequence,
        event.event_sequence,
        COMMIT_SCHEMA_VERSION,
        Digest("sha256:" + "0" * 64),
        CommitState.COMMITTED,
        1,
        1000000000,
        sd,
    )
    return replace(provisional, commit_digest=commit_record_digest(provisional))


# -----------------------------------------------------------------------------
# ERR-001: Canonical event/commit binding
# -----------------------------------------------------------------------------
def test_err_001_canonical_event_commit_binding(tmp_path):
    """ERR-001: CanonicalEvent must carry commit_id; CommitRecord is authoritative commit barrier."""
    # 1. CanonicalEvent carries commit_id
    ev = _test_event(1, commit_id="commit-alpha")
    assert ev.commit_id == "commit-alpha"

    from dataclasses import fields
    d = {f.name: getattr(ev, f.name) for f in fields(ev)}
    d["commit_id"] = "commit-tampered"
    with pytest.raises(ValueError, match="event hash mismatch"):
        CanonicalEvent(**d)

    # 2. CommitRecord is a frozen dataclass with required fields
    rec = CommitRecord(
        "c-1", "w", ("e-1", "state:w"), (Digest("sha256:" + "1" * 64), Digest("sha256:" + "2" * 64)),
        ("event", "state"), GENESIS_EVENT_HASH, Digest("sha256:" + "1" * 64), "rev-1",
        1, 1, COMMIT_SCHEMA_VERSION, Digest("sha256:" + "0" * 64), CommitState.COMMITTED, 1, 1000,
        Digest("sha256:" + "2" * 64),
    )
    assert rec.commit_id == "c-1"
    assert rec.state is CommitState.COMMITTED
    with pytest.raises(dataclasses.FrozenInstanceError):
        rec.commit_id = "c-2"  # Frozen dataclass must reject mutation

    # 3. SQLiteEventStore rejects appending an event whose commit_id differs from CommitRecord
    db_path = str(tmp_path / "err001.sqlite")
    store = SQLiteEventStore(db_path)
    state0 = genesis_engineering_state("w")
    ev1 = _test_event(1, GENESIS_EVENT_HASH, commit_id="commit-ev1")
    s1 = REFERENCE_REDUCER.reduce(state0, ev1)
    # Create commit with mismatched commit_id
    commit_mismatch = _commit_for_event(ev1, s1, commit_id="commit-different")
    with pytest.raises(ValueError, match="share the commit_id|share one commit ID"):
        store.append(ev1, commit_mismatch, GENESIS_EVENT_HASH)

    # Multi-event batch with mismatched event commit IDs is rejected
    ev2_mismatch = _test_event(2, ev1.event_hash, commit_id="commit-ev2")
    with pytest.raises(ValueError, match="share one commit ID|share the commit_id"):
        store.append_batch((ev1, ev2_mismatch), _commit_for_event(ev1, s1, commit_id="commit-ev1"), GENESIS_EVENT_HASH)

    # 4. Only CommitState.COMMITTED may be persisted
    commit_uncommitted = replace(commit_mismatch, commit_id="commit-ev1", state=CommitState.PREPARED)
    with pytest.raises(ValueError, match="COMMITTED"):
        store.append(ev1, commit_uncommitted, GENESIS_EVENT_HASH)
    store.close()


# -----------------------------------------------------------------------------
# ERR-002: Direct authority conjunction & Generation admission
# -----------------------------------------------------------------------------
def test_err_002_direct_authority_conjunction():
    """ERR-002: Conjunction of attested, policy, and lease scopes is authoritative."""
    # Scope conjunction: if attested allows, policy denies, result MUST be not authorized
    attested_allow = empty_scope(fs_rules=(FsRule("work/file.txt", frozenset({FsMode.READ, FsMode.WRITE})),))
    policy_deny = empty_scope(fs_rules=(FsRule("work/file.txt", frozenset({FsMode.READ})),))  # Write denied
    lease_allow = empty_scope(fs_rules=(FsRule("work/file.txt", frozenset({FsMode.READ, FsMode.WRITE})),))

    r_write = req((FsAccess("work/file.txt", FsMode.WRITE),))
    # All three must authorize; policy restricts to READ only
    res = authorize_with_authorities(r_write, attested_allow, policy_deny, lease_allow)
    assert res is not ScopeAuthorizationResult.AUTHORIZED

    # If attested denies, policy allows, lease allows -> result must NOT be authorized
    attested_deny = empty_scope(fs_rules=(FsRule("work/file.txt", frozenset({FsMode.READ})),))
    policy_allow = empty_scope(fs_rules=(FsRule("work/file.txt", frozenset({FsMode.READ, FsMode.WRITE})),))
    res_att_deny = authorize_with_authorities(r_write, attested_deny, policy_allow, lease_allow)
    assert res_att_deny is not ScopeAuthorizationResult.AUTHORIZED

    # If lease denies, attested allows, policy allows -> result must NOT be authorized
    lease_deny = empty_scope(fs_rules=(FsRule("work/file.txt", frozenset({FsMode.READ})),))
    res_lease_deny = authorize_with_authorities(r_write, attested_allow, policy_allow, lease_deny)
    assert res_lease_deny is not ScopeAuthorizationResult.AUTHORIZED

    # If all three authorize, result is AUTHORIZED
    res_ok = authorize_with_authorities(r_write, attested_allow, policy_allow, lease_allow)
    assert res_ok is ScopeAuthorizationResult.AUTHORIZED

    # Stale generation check in admit_work_result
    gen_active = ExecutionGeneration(
        "node-1", 3, "att-3", "epoch-1", "worker-1",
        Digest("sha256:" + "1" * 64), Digest("sha256:" + "2" * 64),
        "b-lineage", "obj-rev-1", "wg-rev-1", ExecutionGenerationStatus.ACTIVE
    )
    res_stale = WorkResult(
        "res-1", "req-1", Digest("sha256:" + "1" * 64), Digest("sha256:" + "2" * 64),
        2,  # Stale: generation 2 != current generation 3
        "att-3", Digest("sha256:" + "1" * 64), Digest("sha256:" + "2" * 64),
        "b-lineage", "obj-rev-1", "wg-rev-1", "worker-1",
        WorkerClaimStatus.CLAIMED_COMPLETE, 10, 10, Digest("sha256:" + "3" * 64),
        Digest("sha256:" + "4" * 64), ()
    )
    assert admit_work_result(gen_active, res_stale) is GateResult.DENIED_STALE_GENERATION

    # Non-ACTIVE generation rejects even with matching generation number
    gen_superseded = replace(gen_active, status=ExecutionGenerationStatus.SUPERSEDED)
    res_matching = replace(res_stale, execution_generation=3)
    assert admit_work_result(gen_superseded, res_matching) is GateResult.DENIED_STALE_GENERATION


# -----------------------------------------------------------------------------
# ERR-003: Action-bound capability & QuiescenceProof
# -----------------------------------------------------------------------------
def test_err_003_action_bound_capability_and_quiescence():
    """ERR-003: Capabilities are bound to exact action_type and time window; QuiescenceProof binds attempt."""
    cap = Capability(ActionType.CODE_READ, empty_scope(), (), UtcInstant(100), UtcInstant(200))

    # Correct action within validity window
    assert capability_authorizes((cap,), ActionType.CODE_READ, UtcInstant(150), req(), empty_scope(), empty_scope(), {})

    # Boundary check: valid_from <= trusted_now < valid_until
    assert capability_authorizes((cap,), ActionType.CODE_READ, UtcInstant(100), req(), empty_scope(), empty_scope(), {})
    assert not capability_authorizes((cap,), ActionType.CODE_READ, UtcInstant(200), req(), empty_scope(), empty_scope(), {})

    # Action mismatch rejected
    assert not capability_authorizes((cap,), ActionType.CODE_EDIT, UtcInstant(150), req(), empty_scope(), empty_scope(), {})

    # Outside time window rejected
    assert not capability_authorizes((cap,), ActionType.CODE_READ, UtcInstant(50), req(), empty_scope(), empty_scope(), {})
    assert not capability_authorizes((cap,), ActionType.CODE_READ, UtcInstant(250), req(), empty_scope(), empty_scope(), {})

    # QuiescenceProof requires non-empty execution_attempt_id
    with pytest.raises(ValueError):
        QuiescenceProof(
            proof_id="qp-1",
            boundary_id="b-1",
            mechanism="cgroup",
            target_execution_identity_digest=Digest("sha256:" + "1" * 64),
            execution_lease_id="lease-1",
            execution_generation=1,
            execution_attempt_id="",  # EMPTY attempt_id must fail closed
            worker_identity="worker-1",
            process_id=1234,
            process_start_time_ns=1000,
            proven_at=UtcInstant(2000),
            proof_digest=Digest("sha256:" + "2" * 64),
            attestation_key_id="k-1",
        )


# -----------------------------------------------------------------------------
# ERR-004: Path canonicalization & BreakGlassAuthority scope
# -----------------------------------------------------------------------------
def test_err_004_path_canonicalization_and_break_glass():
    """ERR-004: Canonical paths must be normalized and reject escape syntax; BreakGlass scope is tuple."""
    import unicodedata

    # Valid paths
    assert _canonical_rel(".") is True
    assert _canonical_rel("src/main.py") is True
    assert _canonical_rel("a/b/c") is True

    # Unicode normalization: NFC valid, NFD rejected
    nfc = unicodedata.normalize("NFC", "café")
    nfd = unicodedata.normalize("NFD", "café")
    assert _canonical_rel(nfc) is True
    assert _canonical_rel(nfd) is False

    # Invalid paths must be rejected
    for bad_path in ("a/../b", "a/./b", "a//b", "a/b/", "/a/b", "a\\b", "a\x00b", "C:foo", ""):
        assert _canonical_rel(bad_path) is False

    # BreakGlassAuthority.scope_obligation_ids is a tuple of strings
    bg = BreakGlassAuthority(
        "bg-1", "key-1", ("ob-1", "ob-2"), "w", "v1", 1,
        UtcInstant(100), True, Digest("sha256:" + "1" * 64),
        SignatureBlock("ed25519", "key-1", "root", "c1", b"\x00" * 64)
    )
    assert isinstance(bg.scope_obligation_ids, tuple)
    assert bg.scope_obligation_ids == ("ob-1", "ob-2")


# -----------------------------------------------------------------------------
# ERR-005: Budget/numeric domains
# -----------------------------------------------------------------------------
def test_err_005_budget_numeric_domains():
    """ERR-005: Bounded numeric fields and checked arithmetic reject negative or overflow values."""
    # Negative budget value rejected
    with pytest.raises(ValueError):
        ResourceBudget(-1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)

    # Overflow beyond 2^63 - 1 rejected
    with pytest.raises(ValueError):
        ResourceBudget(2**63, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)

    # Port range bounds: 1..65535 enforced
    for bad_port in (0, 65536, True, -1):
        with pytest.raises((ValueError, TypeError)):
            NetworkDestination("example.com", bad_port, "tcp", True, ())
    for good_port in (1, 80, 443, 65535):
        dest = NetworkDestination("example.com", good_port, "tcp", True, ())
        assert dest.port == good_port
    with pytest.raises(ValueError, match="invalid port"):
        NetRule("example.com", ("192.0.2.1/32",), frozenset({0}), "tcp", True, False)
    with pytest.raises(ValueError, match="invalid port"):
        NetRule("example.com", ("192.0.2.1/32",), frozenset({65536}), "tcp", True, False)

    # Checked arithmetic: _budget_add overflow and _budget_sub underflow
    b_max = ResourceBudget(2**63 - 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    b_one = ResourceBudget(1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    with pytest.raises(ValueError, match="overflow"):
        _budget_add(b_max, b_one)

    b_zero = ResourceBudget(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    with pytest.raises(ValueError, match="negative"):
        _budget_sub(b_zero, b_one)


# -----------------------------------------------------------------------------
# ERR-006: Evidence binding
# -----------------------------------------------------------------------------
def test_err_006_evidence_binding():
    """ERR-006: SignedEvidencePayload binds all required fields into its digest."""
    payload = SignedEvidencePayload(
        serialization_version="1.0",
        signer_identity="verifier-1",
        verification_step_id="step-1",
        evidence_kind=EvidenceKind.BEHAVIORAL,
        obligation_id="obl-1",
        requirement_key="req-core",
        observation_id="obs-1",
        target_snapshot_digest=Digest("sha256:" + "1" * 64),
        objective_revision="obj-1",
        acceptance_contract_revision=1,
        verification_plan_revision=1,
        dependency_set_digest=Digest("sha256:" + "2" * 64),
        result_status=VerificationStatus.PASS,
        input_digest=Digest("sha256:" + "3" * 64),
        policy_digest=Digest("sha256:" + "4" * 64),
        artifact_digest=Digest("sha256:" + "5" * 64),
        environment_digest=Digest("sha256:" + "6" * 64),
        tool_identity="pytest",
        tool_version="8.0.0",
        issued_at=UtcInstant(100),
        dependency_entries=(("dep-1", Digest("sha256:" + "7" * 64)),),
    )
    d1 = signed_payload_digest("sclass/evidence-payload/v1", payload)
    assert str(d1).startswith("sha256:")

    # Any change to obligation_id, requirement_key, revisions, snapshot, or dependencies must alter the digest
    p_altered = replace(payload, obligation_id="obl-tampered")
    assert signed_payload_digest("sclass/evidence-payload/v1", p_altered) != d1

    p_req_altered = replace(payload, requirement_key="req-tampered")
    assert signed_payload_digest("sclass/evidence-payload/v1", p_req_altered) != d1

    p_snap_altered = replace(payload, target_snapshot_digest=Digest("sha256:" + "9" * 64))
    assert signed_payload_digest("sclass/evidence-payload/v1", p_snap_altered) != d1

    p_dep_altered = replace(payload, dependency_set_digest=Digest("sha256:" + "8" * 64))
    assert signed_payload_digest("sclass/evidence-payload/v1", p_dep_altered) != d1

    p_rev_altered = replace(payload, verification_plan_revision=2)
    assert signed_payload_digest("sclass/evidence-payload/v1", p_rev_altered) != d1


# -----------------------------------------------------------------------------
# ERR-007: Freshness floor
# -----------------------------------------------------------------------------
def test_err_007_freshness_floor():
    """ERR-007: StateBinding includes all freshness digests, generation, and epoch."""
    binding = StateBinding(
        workspace_id="w",
        objective_revision="obj-v1",
        workgraph_revision="wg-v1",
        policy_version="pol-v1",
        workspace_snapshot_id="snap-1",
        target_snapshot_digest=Digest("sha256:" + "1" * 64),
        causal_frontier_digest=Digest("sha256:" + "2" * 64),
        governing_budget_lineage_id="lineage-1",
        execution_generation=1,
        authorization_epoch="epoch-1",
        event_head_hash=GENESIS_EVENT_HASH,
    )
    assert binding.execution_generation == 1
    assert binding.governing_budget_lineage_id == "lineage-1"

    # All normative FreshnessDimension values exist
    expected_dimensions = {
        "TARGET_SNAPSHOT", "OBJECTIVE_REVISION", "POLICY",
        "ACCEPTANCE_CONTRACT", "VERIFICATION_PLAN", "VERIFIER_CONFIG",
        "ENVIRONMENT", "DEPENDENT_ARTIFACTS", "EVENT_HEAD",
    }
    actual_dimensions = {d.name for d in FreshnessDimension}
    assert expected_dimensions.issubset(actual_dimensions)


# -----------------------------------------------------------------------------
# ERR-008: Execution generation in WorkResult
# -----------------------------------------------------------------------------
def test_err_008_execution_generation_work_result():
    """ERR-008: WorkResult carries full binding fields; reducer/admit rejects mismatched attempts."""
    gen = ExecutionGeneration(
        "node-1", 2, "attempt-alpha", "epoch-1", "worker-1",
        Digest("sha256:" + "1" * 64), Digest("sha256:" + "2" * 64),
        "b-lineage", "obj-1", "wg-1", ExecutionGenerationStatus.ACTIVE
    )
    valid_res = WorkResult(
        "res-1", "req-1", Digest("sha256:" + "1" * 64), Digest("sha256:" + "2" * 64),
        2, "attempt-alpha", Digest("sha256:" + "1" * 64), Digest("sha256:" + "2" * 64),
        "b-lineage", "obj-1", "wg-1", "worker-1",
        WorkerClaimStatus.CLAIMED_COMPLETE, 50, 100,
        Digest("sha256:" + "3" * 64), Digest("sha256:" + "4" * 64), ()
    )
    # Valid matching result accepted
    assert admit_work_result(gen, valid_res) is GateResult.ACCEPTED

    # Stale attempt rejected
    bad_attempt = replace(valid_res, execution_attempt_id="attempt-stale")
    assert admit_work_result(gen, bad_attempt) is GateResult.DENIED_BINDING

    # Mismatched target_snapshot_digest rejected
    bad_snapshot = replace(valid_res, target_snapshot_digest=Digest("sha256:" + "9" * 64))
    assert admit_work_result(gen, bad_snapshot) is GateResult.DENIED_BINDING

    # Mismatched state_binding_digest rejected
    bad_binding = replace(valid_res, state_binding_digest=Digest("sha256:" + "9" * 64))
    assert admit_work_result(gen, bad_binding) is GateResult.DENIED_BINDING

    # Mismatched governing_budget_lineage_id rejected
    bad_lineage = replace(valid_res, governing_budget_lineage_id="lineage-tampered")
    assert admit_work_result(gen, bad_lineage) is GateResult.DENIED_BINDING

    # Mismatched objective_revision rejected
    bad_obj = replace(valid_res, objective_revision="obj-tampered")
    assert admit_work_result(gen, bad_obj) is GateResult.DENIED_BINDING

    # Mismatched workgraph_revision rejected
    bad_wg = replace(valid_res, workgraph_revision="wg-tampered")
    assert admit_work_result(gen, bad_wg) is GateResult.DENIED_BINDING


# -----------------------------------------------------------------------------
# ERR-009: Process and external rule uniqueness
# -----------------------------------------------------------------------------
def test_err_009_process_and_external_rule_uniqueness():
    """ERR-009: Ingress rejects duplicate canonical keys for process and external-effect rules."""
    from sclass_kernel_v6_0_1 import _validate_scope_rules

    # Duplicate process rules (same executable, argv) rejected
    dup_process = empty_scope(process_rules=(
        ProcessRule(b"python", b"test.py", True, ()),
        ProcessRule(b"python", b"test.py", False, ()),
    ))
    with pytest.raises(ValueError, match="duplicate process authorization rule"):
        _validate_scope_rules(dup_process)

    # Distinct process rules accepted
    distinct_process = empty_scope(process_rules=(
        ProcessRule(b"python", b"test1.py", True, ()),
        ProcessRule(b"python", b"test2.py", True, ()),
    ))
    _validate_scope_rules(distinct_process)

    # Duplicate external effect rules (same target_system, effect_kind) rejected
    dup_effects = empty_scope(external_effect_rules=(
        ExternalEffectRule("cloud-storage", frozenset({"read"}), 10),
        ExternalEffectRule("cloud-storage", frozenset({"read"}), 50),
    ))
    with pytest.raises(ValueError, match="duplicate external-effect authorization rule"):
        _validate_scope_rules(dup_effects)

    # Distinct external effect rules accepted
    distinct_effects = empty_scope(external_effect_rules=(
        ExternalEffectRule("cloud-storage", frozenset({"read"}), 10),
        ExternalEffectRule("cloud-storage", frozenset({"write"}), 50),
        ExternalEffectRule("email-service", frozenset({"send"}), 1),
    ))
    _validate_scope_rules(distinct_effects)


# -----------------------------------------------------------------------------
# ERR-010: Network resolution and redirects
# -----------------------------------------------------------------------------
def test_err_010_network_resolution_and_redirects():
    """ERR-010: Redirects re-evaluate destination authority; allow_redirects=False disables redirects."""
    # When allow_redirects=False, redirection destination is rejected
    no_redirect_rule = NetRule("origin.com", ("192.0.2.1/32",), frozenset({443}), "tcp", True, False)  # allow_redirects=False
    scope_no_redir = empty_scope(network_rules=(no_redirect_rule,))
    access_with_redir = NetAccess(
        "origin.com", ("192.0.2.1",), 443, "tcp", True,
        (NetworkDestination("redirect.com", 443, "tcp", True, ("198.51.100.1",)),)
    )
    dns_boundary = {"origin.com": ("192.0.2.1",), "redirect.com": ("198.51.100.1",)}
    assert authorized(req(network=(access_with_redir,)), scope_no_redir, dns_boundary) is not ScopeAuthorizationResult.AUTHORIZED

    # DNS spoofing rejection: requester claims IPs that boundary DNS didn't resolve
    spoofed_access = NetAccess(
        "origin.com", ("192.0.2.99",), 443, "tcp", True, ()
    )
    assert authorized(req(network=(spoofed_access,)), scope_no_redir, dns_boundary) is ScopeAuthorizationResult.DENIED_NETWORK

    # When allow_redirects=True, but redirect destination is not in allowed rules -> rejected
    redir_rule = NetRule("origin.com", ("192.0.2.1/32",), frozenset({443}), "tcp", True, True)
    scope_redir_unauth = empty_scope(network_rules=(redir_rule,))  # redirect.com not authorized
    assert authorized(req(network=(access_with_redir,)), scope_redir_unauth, dns_boundary) is not ScopeAuthorizationResult.AUTHORIZED

    # When redirect destination IS authorized -> AUTHORIZED
    dest_rule = NetRule("redirect.com", ("198.51.100.1/32",), frozenset({443}), "tcp", True, False)
    scope_redir_auth = empty_scope(network_rules=(redir_rule, dest_rule))
    assert authorized(req(network=(access_with_redir,)), scope_redir_auth, dns_boundary) is ScopeAuthorizationResult.AUTHORIZED

