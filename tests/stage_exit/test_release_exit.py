import sys
import types
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "20-RUNTIME"))
sys.path.insert(0, str(Path(__file__).parents[2] / "10-CONFORMANCE"))

import sclass_semantics_v6_0_1 as S
from test_sclass_v6_0_1_conformance import _assessment_release_fixture


def test_release_evaluation_produces_signed_ready_certificate(monkeypatch):
    """Release Evaluation gate: verifies evaluate_release generates signed READY release certificate."""
    state, rel, policy = _assessment_release_fixture(1, 1)

    monkeypatch.setattr(
        "sclass_semantics_v6_0_1.evaluate_evidence_composition",
        lambda *a, **k: types.SimpleNamespace(verdict=S.ClosureVerdict.SATISFIED),
    )

    input_dig = S.Digest("sha256:" + "a" * 64)
    monkeypatch.setattr(
        "sclass_semantics_v6_0_1.assessment_input_digest",
        lambda a, s: input_dig,
    )

    a = state.assessments["a0"]
    a.input_digest = input_dig
    sig = S.SignatureBlock("ed25519", "key-1", "root-1", "c1", b"sigbytes")
    a.signature = sig
    signed_payload = S.Digest("sha256:" + "b" * 64)
    monkeypatch.setattr(
        "sclass_semantics_v6_0_1.assessment_signed_payload_digest",
        lambda a: signed_payload,
    )

    rec = S.SignatureVerificationRecord(
        "a0",
        signed_payload,
        S.signature_block_digest(sig),
        "key-1",
        S.SignatureVerificationResult.VALID,
        S.UtcInstant(100),
    )
    state.signature_verification_records = S.FrozenMap.from_items([("a0", rec)])

    # Evaluate release
    eval_result = S.evaluate_release(state, rel, policy, S.UtcInstant(100))

    # Assert formal READY certificate
    assert eval_result.verdict is S.ReleaseVerdict.READY
    assert eval_result.release_id == rel.release_id
    assert eval_result.evaluation_digest is not None
    assert str(eval_result.evaluation_digest).startswith("sha256:")
    assert eval_result.evaluated_at == S.UtcInstant(100)
    assert "o0" in eval_result.derived_obligation_results
    assert eval_result.derived_obligation_results["o0"] == "SATISFIED"
    assert "a0" in eval_result.derived_assessment_results


def test_release_evaluation_blocks_unsatisfied_obligation(monkeypatch):
    """Release Evaluation gate: blocks release when an obligation is not SATISFIED."""
    state, rel, policy = _assessment_release_fixture(1, 1)
    monkeypatch.setattr(
        "sclass_semantics_v6_0_1.evaluate_evidence_composition",
        lambda *a, **k: types.SimpleNamespace(verdict=S.ClosureVerdict.SATISFIED),
    )

    # Set obligation to PENDING
    state.obligations._obligations["o0"].status = S.ObligationStatus.PENDING

    eval_result = S.evaluate_release(state, rel, policy, S.UtcInstant(100))
    assert eval_result.verdict is S.ReleaseVerdict.BLOCKED


def test_release_evaluation_blocks_unsatisfied_evidence(monkeypatch):
    """Release Evaluation gate: blocks release when evidence closure verdict is not SATISFIED."""
    state, rel, policy = _assessment_release_fixture(1, 1)
    monkeypatch.setattr(
        "sclass_semantics_v6_0_1.evaluate_evidence_composition",
        lambda *a, **k: types.SimpleNamespace(verdict=S.ClosureVerdict.SATISFIED),
    )

    # Set evidence verdict to UNSATISFIED
    ev = state.evidence["e0"]
    ev.verdict = S.ClosureVerdict.UNSATISFIED

    eval_result = S.evaluate_release(state, rel, policy, S.UtcInstant(100))
    assert eval_result.verdict is S.ReleaseVerdict.BLOCKED


def test_release_evaluation_rejects_snapshot_mismatch_as_not_evaluable():
    """Release Evaluation gate: rejects mismatched acceptance snapshot as NOT_EVALUABLE."""
    state, rel, policy = _assessment_release_fixture(1, 1)
    bad_rel = replace(rel, acceptance_snapshot_digest=S.Digest("sha256:" + "0" * 64))

    eval_result = S.evaluate_release(state, bad_rel, policy, S.UtcInstant(100))
    assert eval_result.verdict is S.ReleaseVerdict.NOT_EVALUABLE


def test_release_evaluation_rejects_policy_version_mismatch():
    """Release Evaluation gate: rejects policy version mismatch as NOT_EVALUABLE."""
    state, rel, policy = _assessment_release_fixture(1, 1)
    bad_rel = replace(rel, release_policy_version="mismatched-policy-v999")

    eval_result = S.evaluate_release(state, bad_rel, policy, S.UtcInstant(100))
    assert eval_result.verdict is S.ReleaseVerdict.NOT_EVALUABLE
