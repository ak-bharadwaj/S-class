"""Test evidence contracts immutability and hashing."""
import pytest
from sclass.contracts.evidence_contracts import RawObservable, EvidencePayload

def test_raw_observable_immutability():
    obs = RawObservable(exit_code=0, stdout_sha256="abc", stderr_sha256="def", duration_ms=12.5)
    with pytest.raises(AttributeError):
        obs.exit_code = 1  # Frozen dataclass must reject mutation

def test_evidence_payload_instantiation():
    obs = RawObservable(exit_code=0, stdout_sha256="abc", stderr_sha256="def", duration_ms=12.5)
    payload = EvidencePayload(action_id="act-1", observable=obs, verifier_id="v-proc", verified_at_timestamp=100.0)
    assert payload.action_id == "act-1"
    assert payload.observable.exit_code == 0
