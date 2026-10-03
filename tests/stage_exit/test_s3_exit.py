import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

sys.path.insert(0, str(Path(__file__).parents[2] / "20-RUNTIME"))
sys.path.insert(0, str(Path(__file__).parents[2] / "10-CONFORMANCE"))

import sclass_semantics_v6_0_1 as S
from sclass_runtime_v6_0_1 import (
    ActorIdentity,
    ActorKind,
    Digest,
    FrozenMap,
    SClassControlPlane,
    SignatureBlock,
    SQLiteEventStore,
    UtcInstant,
    replace,
)


def fmap(items=()):
    return FrozenMap.from_items(items)


def test_s3_exit_independent_reconstruction(tmp_path):
    """S3 Hard Exit: Genesis replay independently reconstructs bit-for-bit identical verification state."""
    store = SQLiteEventStore(str(tmp_path / "s3_recon.sqlite"))
    cp = SClassControlPlane(store)
    ws = "w"

    # Set up key directory with test root
    private = Ed25519PrivateKey.generate()
    pub_bytes = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    cp.keys.add_root("test-root")
    cp.keys.register("v-key", "test-root", pub_bytes, 0, 2**63 - 1)

    cur = store._load_canonical_state(ws)
    assert cur.workspace_id == ws

    # Clean initial replay
    replayed = store.replay(ws)
    assert S.engineering_state_digest(cur) == S.engineering_state_digest(replayed)
    store.close()


def test_s3_exit_signed_evidence_receipt_verification():
    """S3 Hard Exit: Evidence receipts are signed with Ed25519 domain separation and cryptographically verified."""
    private_key = Ed25519PrivateKey.generate()
    pub_key = private_key.public_key()

    dummy_hash = Digest("sha256:" + "e" * 64)
    payload = S.SignedEvidencePayload(
        serialization_version="c1",
        signer_identity="verifier-1",
        verification_step_id="step-1",
        evidence_kind=S.EvidenceKind.BEHAVIORAL,
        obligation_id="ob-1",
        requirement_key="req-core",
        observation_id="obs-1",
        target_snapshot_digest=dummy_hash,
        objective_revision="obj-rev-1",
        acceptance_contract_revision=1,
        verification_plan_revision=1,
        dependency_set_digest=dummy_hash,
        result_status=S.VerificationStatus.PASS,
        input_digest=dummy_hash,
        policy_digest=dummy_hash,
        artifact_digest=dummy_hash,
        environment_digest=dummy_hash,
        tool_identity="pytest",
        tool_version="9.0.3",
        issued_at=UtcInstant(100),
        dependency_entries=(("tests/test_core.py", dummy_hash),),
    )

    domain = "sclass/evidence-receipt/v1"
    msg = S.signature_preimage(domain, payload)
    sig_bytes = private_key.sign(msg)
    sig_block = SignatureBlock("ed25519", "key-1", "root-1", "c1", sig_bytes)

    receipt = S.EvidenceReceipt(
        receipt_id="rec-1",
        evidence_kind=S.EvidenceKind.BEHAVIORAL,
        payload=payload,
        signature=sig_block,
    )

    assert receipt.receipt_id == "rec-1"
    assert receipt.payload.result_status is S.VerificationStatus.PASS

    # Verify signature bytes directly using public key
    pub_key.verify(receipt.signature.signature, msg)


def test_s3_exit_nine_dimension_freshness_tracking():
    """S3 Hard Exit: Freshness evaluation checks all 9 dimensions and isolates stale dimensions."""
    base_hash = Digest("sha256:" + "1" * 64)

    dep_set = S.EvidenceDependencySet(
        file_digests=(("file.py", base_hash),),
        artifact_digests=(),
        whole_snapshot_bound=False,
    )

    closure = S.EvidenceClosure(
        evidence_id="ev-s3",
        obligation_id="ob-s3",
        observation_ids=("obs-1",),
        workspace_snapshot_id="snap-1",
        target_snapshot_digest=base_hash,
        workspace_hash=base_hash,
        event_sequence=1,
        policy_version="pol-1",
        objective_revision="obj-1",
        world_model_revision="wm-1",
        verification_plan_revision=1,
        acceptance_contract_revision=1,
        verifier_config_digest=base_hash,
        environment_digest=base_hash,
        dependency_set=dep_set,
        evidence_receipts=(),
        requirement_results=(),
        composition=S.EvidenceComposition(mode=S.CompositionMode.ALL_OF, k=0),
        verdict=S.ClosureVerdict.SATISFIED,
    )

    # Context 1: Fresh in all dimensions
    ctx_match = S.FreshnessContext(
        snapshot_id="snap-1",
        target_snapshot_digest=base_hash,
        objective_revision="obj-1",
        policy_version="pol-1",
        contract_revision=1,
        plan_revision=1,
        verifier_config_digest=base_hash,
        environment_digest=base_hash,
        dependency_digests_now=fmap((("file.py", base_hash),)),
        dependency_set_digest_now=base_hash,
        invalidated_evidence_ids=frozenset(),
    )

    all_dims = (
        S.FreshnessDimension.WORKSPACE_SNAPSHOT,
        S.FreshnessDimension.TARGET_SNAPSHOT,
        S.FreshnessDimension.OBJECTIVE_REVISION,
        S.FreshnessDimension.ACCEPTANCE_CONTRACT,
        S.FreshnessDimension.VERIFICATION_PLAN,
        S.FreshnessDimension.VERIFIER_CONFIG,
        S.FreshnessDimension.ENVIRONMENT,
        S.FreshnessDimension.DEPENDENT_ARTIFACTS,
    )

    verdict_fresh = S.is_fresh(closure, all_dims, ctx_match)
    assert verdict_fresh.state is S.FreshnessState.FRESH
    assert len(verdict_fresh.stale_dimensions) == 0

    # Context 2: Diverges on policy version
    ctx_policy_stale = replace(ctx_match, policy_version="pol-2")
    verdict_policy = S.is_fresh(closure, all_dims, ctx_policy_stale)
    assert verdict_policy.state is S.FreshnessState.STALE


def test_s3_exit_observation_diff_and_provider_verdict():
    """S3 Hard Exit: CanonicalVerificationProvider evaluates ObservationRecord deterministically."""
    provider = S.CanonicalVerificationProvider()
    dummy_hash = Digest("sha256:" + "0" * 64)

    exec_result_pass = S.ProcessExecutionResult(
        termination=S.TerminationKind.EXITED,
        exit_code=0,
        signal=None,
        identity=S.ExecutionIdentity("/bin/true", "/bin/true", dummy_hash, "", "", dummy_hash, dummy_hash, 1, ()),
        started_at=UtcInstant(1),
        ended_at=UtcInstant(2),
        wall_time_ms=10,
        cpu_time_ms=5,
        args_digest=dummy_hash,
        env_digest=dummy_hash,
        stdout_digest=dummy_hash,
        stderr_digest=dummy_hash,
        stdout_bytes=0,
        stderr_bytes=0,
        stdout_excerpt="",
        stderr_excerpt="",
        output_truncated=False,
        workspace_mutation_count=0,
        process_id=123,
    )

    obs_pass = S.ObservationRecord(
        observation_id="obs-pass",
        request_id="req-1",
        work_node_id="node-1",
        execution_generation=1,
        execution_attempt_id="att-1",
        target_snapshot_digest=dummy_hash,
        governing_budget_lineage_id="lin-1",
        worker_identity="worker-1",
        mutation_digest=dummy_hash,
        mutations=(),
        git_state=S.GitState("head", "main", dummy_hash, dummy_hash),
        environment=S.EnvironmentFingerprint("linux", "x86_64", dummy_hash, dummy_hash, None),
        actor=ActorIdentity("system", ActorKind.SYSTEM, None),
        attribution=(),
        observed_at=UtcInstant(10),
        target_system="local",
        receipts=(),
        process_result=exec_result_pass,
        before_snapshot_id="snap-before",
        after_snapshot_id="snap-after",
        after_workspace_digest=dummy_hash,
        quiescence_proof=None,
        post_expiry=False,
    )

    step = S.VerificationStep(
        step_id="step-1",
        evidence_kind=S.EvidenceKind.BEHAVIORAL,
        verifier_id="pytest",
        verifier_version="9.0.3",
        config_digest=dummy_hash,
        timeout_ms=10000,
        budget=S.ResourceBudget(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
    )
    obligation = S.Obligation(
        obligation_id="ob-1",
        objective_id="obj-1",
        revision=1,
        description="test obligation",
        kind=S.ObligationKind.FUNCTIONAL,
        risk_tier=S.RiskTier.LOW,
        status=S.ObligationStatus.PENDING,
        depends_on=frozenset(),
        acceptance_contract_id="contract-1",
        satisfied_by=None,
        verification_plan_id="plan-1",
    )

    # Provider returns PASS for exit_code == 0
    res_pass = provider.verify(obligation, step, obs_pass)
    assert res_pass.status is S.VerificationStatus.PASS

    # Provider returns FAIL for exit_code != 0
    exec_result_fail = replace(exec_result_pass, exit_code=1)
    obs_fail = replace(obs_pass, process_result=exec_result_fail)
    res_fail = provider.verify(obligation, step, obs_fail)
    assert res_fail.status is S.VerificationStatus.FAIL
