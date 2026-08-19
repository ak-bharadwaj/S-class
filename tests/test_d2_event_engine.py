"""Tier 1 Adversarial, Determinism, Concurrency, Recovery & Benchmark Suite for S-Class D2 Event Engine.

Tests:
1. RFC 8785 (JCS) Standard Conformance: numbers, strings, control characters, unescaped slashes/Unicode, UTF-16 key sorting.
2. Canonicalization Input Boundary & Adversarial Vectors:
   - (a) Unsupported set → fails closed with CanonicalSerializationError.
   - (b) Unsupported frozenset → fails closed with CanonicalSerializationError.
   - (c) Custom arbitrary object → fails closed with CanonicalSerializationError.
   - (d) Non-string mapping key → fails closed with CanonicalSerializationError.
   - (e) Same valid payload → produces identical bytes and identical digest.
   - (f) Reordered mapping → produces identical digest.
   - (g) Changed array order → produces different digest.
3. Genesis event verification (sequence=1, parent_digest="0"*64).
4. Single event append, reduction, and state materialization.
5. Multi-event cryptographic digest chaining across sequence.
6. Full domain model reduction: Task, Obligation, Claim, Evidence, AssessmentReceipt.
7. Adversarial vector: Tampered payload rejected with DigestMismatchError.
8. Adversarial vector: Tampered parent_digest rejected with InvalidParentDigestError.
9. Adversarial vector: Tampered stored digest rejected with DigestMismatchError.
10. Replay determinism: identical event stream always produces identical MaterializedState.
11. Sequence violation: Duplicate sequence number rejected with DuplicateSequenceError.
12. Sequence violation: Sequence gap rejected with SequenceGapError.
13. Type violation: Invalid event type string rejected fail-closed.
14. Structural violation: Malformed event envelope rejected fail-closed.
15. Concurrency safety: Thread-safe concurrent append race fails safely without data corruption.
16. Recovery & Corruption Distinctions:
    - (a) Truncated final record at EOF (torn write) is safely recovered and truncated.
    - (b) Malformed JSON in historical log raises CorruptEventLogError and is never silently discarded.
    - (c) Validly parsed but digest-corrupted record raises CorruptEventLogError and is never silently discarded.
    - (d) Parent-chain corruption raises CorruptEventLogError and is never silently discarded.
17. File store operations: get_events, limits, offsets, empty stores, invalid parameters.
18. Large-log benchmark: 1k, 10k, and 100k event log append, verification, replay throughput, and explicit peak RSS memory (MB).
"""

from concurrent.futures import ThreadPoolExecutor
import gc
import json
import os
import sys
import tempfile
import time
from typing import List
import pytest

from domain.models import (
    EventEnvelope,
    Task,
    Obligation,
    Claim,
    ClaimSubject,
    Policy,
    PolicyExpression,
    PolicyRule,
    Evidence,
    EvidenceScope,
    EvidenceObservation,
    Provenance,
    HmacSessionSignature,
    AssessmentReceipt,
    ClaimAssessment,
    AsymmetricAuthoritySignature,
    RepositoryContext,
)
from domain.types import (
    EventType,
    ObligationStatus,
    ObligationCategory,
    Criticality,
    ClaimStatus,
    ClaimTier,
    TargetType,
    PolicyScope,
    RuleType,
    CombinatorType,
    EvidencePolarity,
    EvidenceValidity,
    RawStatus,
    AssessmentVerdict,
)
from domain.exceptions import DomainValidationError
from events import (
    EventEnvelope,
    EventType,
    EventEngineError,
    CanonicalSerializationError,
    DigestMismatchError,
    InvalidParentDigestError,
    SequenceGapError,
    DuplicateSequenceError,
    ConcurrencyConflictError,
    CorruptEventLogError,
    canonicalize_json,
    compute_event_preimage,
    compute_event_digest,
    verify_event_digest,
    create_event,
    MaterializedState,
    GENESIS_PARENT_DIGEST,
    reduce_event,
    replay_events,
    EventStoreInterface,
    InMemoryEventStore,
    FileAppendEventStore,
)


def get_process_rss_mb() -> float:
    """Returns current process working set / RSS memory in MB."""
    if sys.platform == "win32":
        try:
            import ctypes.wintypes
            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ('cb', ctypes.wintypes.DWORD),
                    ('PageFaultCount', ctypes.wintypes.DWORD),
                    ('PeakWorkingSetSize', ctypes.c_size_t),
                    ('WorkingSetSize', ctypes.c_size_t),
                    ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
                    ('QuotaPagedPoolUsage', ctypes.c_size_t),
                    ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
                    ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                    ('PagefileUsage', ctypes.c_size_t),
                    ('PeakPagefileUsage', ctypes.c_size_t),
                ]
            counters = PROCESS_MEMORY_COUNTERS()
            counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
            func = ctypes.windll.psapi.GetProcessMemoryInfo
            func.argtypes = [ctypes.wintypes.HANDLE, ctypes.POINTER(PROCESS_MEMORY_COUNTERS), ctypes.wintypes.DWORD]
            func.restype = ctypes.wintypes.BOOL
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            if func(handle, ctypes.byref(counters), counters.cb):
                return float(counters.WorkingSetSize) / (1024.0 * 1024.0)
        except Exception:
            pass
    else:
        try:
            import resource
            return float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) / 1024.0
        except Exception:
            pass
    return 0.0


# ============================================================================
# 1. RFC 8785 / JCS Standard Conformance Test Vectors
# ============================================================================

def test_rfc8785_number_conformance():
    """Verify RFC 8785 number formatting rules: no trailing .0 for integer floats, compact exponents."""
    assert canonicalize_json(0) == b"0"
    assert canonicalize_json(-0) == b"0"
    assert canonicalize_json(1) == b"1"
    assert canonicalize_json(-1) == b"-1"
    assert canonicalize_json(100.0) == b"100"
    assert canonicalize_json(0.5) == b"0.5"

    with pytest.raises(CanonicalSerializationError):
        canonicalize_json(float("nan"))

    with pytest.raises(CanonicalSerializationError):
        canonicalize_json(float("inf"))


def test_rfc8785_string_and_escaping_conformance():
    """Verify RFC 8785 string escaping: only quotation, reverse solidus, and control chars escaped; slashes and Unicode raw."""
    assert canonicalize_json('quotes: " \\') == b'"quotes: \\" \\\\"'
    assert canonicalize_json("https://sclass.dev/api/v1") == b'"https://sclass.dev/api/v1"'
    assert canonicalize_json("\b\t\n\f\r") == b'"\\b\\t\\n\\f\\r"'

    ctrl_str = chr(0) + chr(31)
    assert canonicalize_json(ctrl_str) == b'"\\u0000\\u001f"'

    unicode_str = "€ (Euro) and é (e-acute) and 𝄞 (Clef)"
    assert canonicalize_json(unicode_str) == unicode_str.encode("utf-8").join([b'"', b'"'])


def test_rfc8785_utf16_code_unit_key_sorting():
    """Verify RFC 8785 Section 3.2.3: Object keys must be sorted by UTF-16 code units."""
    data = {
        "\u0080": 1,
        "\u007f": 2,
        "a": 3,
        "\U00010000": 4,
        "\uFFFF": 5,
        "b": 6,
    }
    encoded = canonicalize_json(data)
    expected_order = sorted(data.keys(), key=lambda k: k.encode("utf-16-be"))
    parsed = json.loads(encoded.decode("utf-8"))
    actual_order = list(parsed.keys())
    assert actual_order == expected_order


def test_rfc8785_data_structures_and_types():
    """Verify canonical serialization of lists, tuples, booleans, None, and enums."""
    assert canonicalize_json([1, 2, 3]) == b"[1,2,3]"
    assert canonicalize_json((1, 2)) == b"[1,2]"
    assert canonicalize_json(None) == b"null"
    assert canonicalize_json(True) == b"true"
    assert canonicalize_json(False) == b"false"
    assert canonicalize_json(EventType.TASK_CREATED) == b'"TASK_CREATED"'


# ============================================================================
# 2. Canonicalization Input Boundary & Adversarial Vectors
# ============================================================================

def test_canonicalization_unsupported_set_fails_closed():
    """Adversarial vector: Sets and frozensets are rejected fail closed with CanonicalSerializationError."""
    with pytest.raises(CanonicalSerializationError):
        canonicalize_json({1, 2, 3})

    with pytest.raises(CanonicalSerializationError):
        canonicalize_json(frozenset(["a", "b"]))

    with pytest.raises(CanonicalSerializationError):
        canonicalize_json({"valid_key": {10, 20}})


def test_canonicalization_custom_object_fails_closed():
    """Adversarial vector: Arbitrary custom classes without domain schema definition fail closed."""
    class ArbitraryClass:
        def __init__(self):
            self.val = 42

    with pytest.raises(CanonicalSerializationError):
        canonicalize_json(ArbitraryClass())

    with pytest.raises(CanonicalSerializationError):
        canonicalize_json({"nested": ArbitraryClass()})


def test_canonicalization_non_string_mapping_key_fails_closed():
    """Adversarial vector: Mappings with non-string keys fail closed."""
    with pytest.raises(CanonicalSerializationError):
        canonicalize_json({123: "number_key"})

    with pytest.raises(CanonicalSerializationError):
        canonicalize_json({(1, 2): "tuple_key"})


def test_canonicalization_same_valid_payload_identical_bytes_and_digest():
    """Adversarial vector: Identical payloads always produce byte-for-byte identical canonical serialization and digest."""
    p1 = {"task_id": "TASK-001", "constraints": ["PYTHON", "SECURITY"], "budget": 100.5}
    p2 = {"task_id": "TASK-001", "constraints": ["PYTHON", "SECURITY"], "budget": 100.5}

    b1 = canonicalize_json(p1)
    b2 = canonicalize_json(p2)
    assert b1 == b2

    d1 = compute_event_digest("EVT-001", EventType.TASK_CREATED, 1, "TASK-001", "2026-08-19T10:00:00Z", p1, GENESIS_PARENT_DIGEST)
    d2 = compute_event_digest("EVT-001", EventType.TASK_CREATED, 1, "TASK-001", "2026-08-19T10:00:00Z", p2, GENESIS_PARENT_DIGEST)
    assert d1 == d2


def test_canonicalization_reordered_mapping_identical_digest():
    """Adversarial vector: Reordering keys in a dictionary (and nested sub-dictionaries) produces identical canonical digest."""
    m1 = {"z": 100, "a": 200, "meta": {"owner": "alice", "active": True}}
    m2 = {"a": 200, "meta": {"active": True, "owner": "alice"}, "z": 100}

    assert canonicalize_json(m1) == canonicalize_json(m2)

    d1 = compute_event_digest("EVT-001", EventType.TASK_CREATED, 1, "TASK-001", "2026-08-19T10:00:00Z", m1, GENESIS_PARENT_DIGEST)
    d2 = compute_event_digest("EVT-001", EventType.TASK_CREATED, 1, "TASK-001", "2026-08-19T10:00:00Z", m2, GENESIS_PARENT_DIGEST)
    assert d1 == d2


def test_canonicalization_changed_array_order_different_digest():
    """Adversarial vector: Changing array/list element ordering strictly produces different canonical bytes and different digest."""
    a1 = {"elements": [1, 2, 3]}
    a2 = {"elements": [3, 2, 1]}

    assert canonicalize_json(a1) != canonicalize_json(a2)

    d1 = compute_event_digest("EVT-001", EventType.TASK_CREATED, 1, "TASK-001", "2026-08-19T10:00:00Z", a1, GENESIS_PARENT_DIGEST)
    d2 = compute_event_digest("EVT-001", EventType.TASK_CREATED, 1, "TASK-001", "2026-08-19T10:00:00Z", a2, GENESIS_PARENT_DIGEST)
    assert d1 != d2


# ============================================================================
# 3. Genesis, Single Event, and Multi-Event Chaining
# ============================================================================

def make_test_task_event(
    seq: int = 1,
    parent_digest: str = GENESIS_PARENT_DIGEST,
    task_id: str = "TASK-001",
) -> EventEnvelope:
    task = Task(
        task_id=task_id,
        raw_prompt="Build pure event engine",
        repository_context=RepositoryContext(
            repository_id="sclass-core",
            base_commit_sha="a" * 40,
            branch="master",
            dirty_working_tree=False,
        ),
    )
    return create_event(
        event_id=f"EVT-TASK-{seq:05d}",
        event_type=EventType.TASK_CREATED,
        sequence_number=seq,
        aggregate_id=task_id,
        timestamp="2026-08-19T10:00:00Z",
        payload={"task": task, "task_id": task_id},
        parent_digest=parent_digest,
    )


def make_test_obligation_event(
    seq: int,
    parent_digest: str,
    obligation_id: str,
    task_id: str = "TASK-001",
    depends_on: tuple = (),
) -> EventEnvelope:
    return create_event(
        event_id=f"EVT-OBL-{seq:05d}",
        event_type=EventType.OBLIGATION_DERIVED,
        sequence_number=seq,
        aggregate_id=task_id,
        timestamp="2026-08-19T10:00:01Z",
        payload={"obligation_id": obligation_id, "title": f"Obligation {obligation_id}"},
        parent_digest=parent_digest,
    )


def test_genesis_event_verification():
    """Verify genesis event constraints: sequence_number == 1 and parent_digest == '0'*64."""
    event = make_test_task_event(seq=1, parent_digest=GENESIS_PARENT_DIGEST)
    assert event.sequence_number == 1
    assert event.parent_digest == GENESIS_PARENT_DIGEST
    assert len(event.parent_digest) == 64
    assert len(event.digest) == 64
    assert verify_event_digest(event) is True


def test_single_event_append_and_reduction():
    """Verify single event append, reduction, and initial state derivation."""
    store = InMemoryEventStore()
    event = make_test_task_event(seq=1)
    store.append(event)

    assert len(store) == 1
    assert store.get_latest_event() == event

    state = store.replay()
    assert state.last_sequence_number == 1
    assert state.last_digest == event.digest
    assert state.last_event_id == event.event_id
    assert state.task is not None
    assert state.task.task_id == "TASK-001"


def test_multi_event_digest_chain():
    """Verify multi-event sequential append with valid cryptographic chaining."""
    store = InMemoryEventStore()
    e1 = make_test_task_event(seq=1, parent_digest=GENESIS_PARENT_DIGEST)
    store.append(e1)

    e2 = make_test_obligation_event(seq=2, parent_digest=e1.digest, obligation_id="OBL-001")
    store.append(e2)

    e3 = make_test_obligation_event(seq=3, parent_digest=e2.digest, obligation_id="OBL-002", depends_on=("OBL-001",))
    store.append(e3)

    assert len(store) == 3
    assert store.verify_integrity() is True

    state = store.replay()
    assert state.last_sequence_number == 3
    assert state.last_digest == e3.digest


def test_full_domain_model_reduction():
    """Verify reduction across all domain entity events: Task, Obligation, Claim, Evidence, AssessmentReceipt."""
    events = []
    parent = GENESIS_PARENT_DIGEST

    # 1. Task Created
    task = Task(
        task_id="TASK-001",
        raw_prompt="Implement D2",
        repository_context=RepositoryContext(
            repository_id="sclass-core",
            base_commit_sha="0" * 40,
            branch="main",
            dirty_working_tree=False,
        ),
    )
    e1 = create_event(
        "EVT-001", EventType.TASK_CREATED, 1, "TASK-001", "2026-08-19T10:00:00Z",
        {"task": task}, parent
    )
    events.append(e1)
    parent = e1.digest

    # 2. Obligation Derived
    obl = Obligation(
        obligation_id="OBL-001",
        task_id="TASK-001",
        title="Test Obligation",
        description="Verify",
        category=ObligationCategory.SECURITY_INTEGRITY,
        criticality=Criticality.CRITICAL,
        status=ObligationStatus.OPEN,
        depends_on=(),
        claim_ids=("CLM-001",),
        policy_id="POL-001",
    )
    e2 = create_event(
        "EVT-002", EventType.OBLIGATION_DERIVED, 2, "TASK-001", "2026-08-19T10:00:01Z",
        {"obligation": obl}, parent
    )
    events.append(e2)
    parent = e2.digest

    # 3. Claim Registered
    claim = Claim(
        claim_id="CLM-001",
        obligation_id="OBL-001",
        tier=ClaimTier.V2_BEHAVIORAL,
        subject=ClaimSubject(
            target_type=TargetType.ENDPOINT,
            identifier="DELETE:/users/{id}",
        ),
        predicate="REJECTS_UNAUTHORIZED_REQUEST",
        context={"role": "GUEST"},
        expected={"status_code": 403},
        criticality=Criticality.HIGH,
        status=ClaimStatus.UNSUPPORTED,
        required_provider_capabilities=("API_CONTRACT_FUZZING",),
    )
    e3 = create_event(
        "EVT-003", EventType.CLAIM_REGISTERED, 3, "TASK-001", "2026-08-19T10:00:02Z",
        {"claim": claim}, parent
    )
    events.append(e3)
    parent = e3.digest

    # 4. Evidence Collected
    ev = Evidence(
        evidence_id="EV-001",
        claim_id="CLM-001",
        provider_id="schemathesis-runner",
        capability="API_CONTRACT_FUZZING",
        execution_id="EXEC-12345",
        source_sha="a" * 40,
        scope=EvidenceScope(
            targets_evaluated=("DELETE:/users/{id}",),
            aspects_covered=("AUTH_ENFORCEMENT",),
        ),
        observation=EvidenceObservation(
            raw_status=RawStatus.PASS,
            diagnostics=("All 50 test cases passed.",),
            counterexample={"input": "valid", "response": 200},
        ),
        polarity=EvidencePolarity.SUPPORTS,
        validity=EvidenceValidity.VALID,
        independence_group="INDEP-PROVIDER-01",
        provenance=Provenance(
            engine_name="schemathesis",
            engine_version="3.39.0",
            environment_hash="b" * 64,
            timestamp="2026-08-19T10:00:00Z",
        ),
        signature=HmacSessionSignature(
            algorithm="HMAC-SHA256",
            key_id="KEY-001",
            nonce="NONCE-999",
            raw_stdout_digest="c" * 64,
            signature_hex="d" * 64,
            timestamp="2026-08-19T10:00:00Z",
        ),
    )
    e4 = create_event(
        "EVT-004", EventType.EVIDENCE_COLLECTED, 4, "TASK-001", "2026-08-19T10:00:03Z",
        {"evidence": ev}, parent
    )
    events.append(e4)
    parent = e4.digest

    # 5. Assessment Produced
    rcpt = AssessmentReceipt(
        receipt_id="RCPT-001",
        obligation_id="OBL-001",
        policy_version=1,
        repository_sha="a" * 40,
        verdict=AssessmentVerdict.SATISFIED,
        claim_assessments=(
            ClaimAssessment(
                claim_id="CLM-001",
                status=ClaimStatus.SUPPORTED,
                supporting_evidence_ids=("EV-001",),
                refuting_evidence_ids=(),
            ),
        ),
        signature=AsymmetricAuthoritySignature(
            algorithm="ED25519",
            signer_identity="EVALUATOR_SERVICE_01",
            public_key_fingerprint="e" * 64,
            payload_digest="f" * 64,
            signature_hex="1" * 128,
            timestamp="2026-08-19T10:00:00Z",
        ),
    )
    e5 = create_event(
        "EVT-005", EventType.ASSESSMENT_PRODUCED, 5, "TASK-001", "2026-08-19T10:00:04Z",
        {"assessment_receipt": rcpt}, parent
    )
    events.append(e5)

    state = replay_events(events)
    assert state.task.task_id == "TASK-001"
    assert "OBL-001" in state.obligations
    assert "CLM-001" in state.claims
    assert "EV-001" in state.evidence
    assert "RCPT-001" in state.assessments


# ============================================================================
# 4. Adversarial Tampering Vectors & Replay Determinism
# ============================================================================

def test_tampered_payload_rejected():
    """Adversarial vector: Mutating payload bytes causes digest mismatch and reduction failure."""
    e1 = make_test_task_event(seq=1)
    forged_event = EventEnvelope(
        event_id=e1.event_id,
        event_type=e1.event_type,
        sequence_number=e1.sequence_number,
        aggregate_id=e1.aggregate_id,
        timestamp=e1.timestamp,
        payload={"task_id": "TASK-001", "raw_prompt": "MALICIOUS_TAMPERED_PROMPT"},
        parent_digest=e1.parent_digest,
        digest=e1.digest,
    )

    assert verify_event_digest(forged_event) is False

    store = InMemoryEventStore()
    with pytest.raises(DigestMismatchError):
        store.append(forged_event)

    state = MaterializedState()
    with pytest.raises(DigestMismatchError):
        reduce_event(state, forged_event)


def test_tampered_parent_digest_rejected():
    """Adversarial vector: Tampered parent_digest breaks cryptographic chain link."""
    e1 = make_test_task_event(seq=1)
    bad_parent = "f" * 64
    e2_forged = create_event(
        event_id="EVT-OBL-00002",
        event_type=EventType.OBLIGATION_DERIVED,
        sequence_number=2,
        aggregate_id="TASK-001",
        timestamp="2026-08-19T10:00:01Z",
        payload={"obligation_id": "OBL-001"},
        parent_digest=bad_parent,
    )

    store = InMemoryEventStore()
    store.append(e1)

    with pytest.raises(InvalidParentDigestError):
        store.append(e2_forged)

    state = reduce_event(MaterializedState(), e1)
    with pytest.raises(InvalidParentDigestError):
        reduce_event(state, e2_forged)


def test_tampered_stored_digest_rejected():
    """Adversarial vector: Forging stored digest string fails digest verification."""
    e1 = make_test_task_event(seq=1)
    forged_digest = "e" * 64
    forged_event = EventEnvelope(
        event_id=e1.event_id,
        event_type=e1.event_type,
        sequence_number=e1.sequence_number,
        aggregate_id=e1.aggregate_id,
        timestamp=e1.timestamp,
        payload=e1.payload,
        parent_digest=e1.parent_digest,
        digest=forged_digest,
    )

    assert verify_event_digest(forged_event) is False
    store = InMemoryEventStore()
    with pytest.raises(DigestMismatchError):
        store.append(forged_event)


def test_replay_determinism():
    """Verify replay determinism: identical event stream always produces identical MaterializedState."""
    events = []
    parent = GENESIS_PARENT_DIGEST
    e1 = make_test_task_event(seq=1, parent_digest=parent)
    events.append(e1)
    parent = e1.digest

    for i in range(2, 20):
        e = make_test_obligation_event(seq=i, parent_digest=parent, obligation_id=f"OBL-{i:03d}")
        events.append(e)
        parent = e.digest

    state1 = replay_events(events)
    state2 = replay_events(events)
    state3 = replay_events(events)

    assert state1.last_digest == state2.last_digest == state3.last_digest
    assert state1.last_sequence_number == state2.last_sequence_number == 19
    assert state1.last_event_id == state2.last_event_id == state3.last_event_id


def test_duplicate_sequence_rejected():
    """Verify appending duplicate sequence number is rejected with DuplicateSequenceError."""
    store = InMemoryEventStore()
    e1 = make_test_task_event(seq=1)
    store.append(e1)

    e1_dup = make_test_task_event(seq=1)
    with pytest.raises(DuplicateSequenceError):
        store.append(e1_dup)

    state = reduce_event(MaterializedState(), e1)
    with pytest.raises(DuplicateSequenceError):
        reduce_event(state, e1_dup)


def test_sequence_gap_rejected():
    """Verify appending sequence number with a gap is rejected with SequenceGapError."""
    store = InMemoryEventStore()
    e1 = make_test_task_event(seq=1)
    store.append(e1)

    e3_gap = make_test_obligation_event(seq=3, parent_digest=e1.digest, obligation_id="OBL-001")
    with pytest.raises(SequenceGapError):
        store.append(e3_gap)

    state = reduce_event(MaterializedState(), e1)
    with pytest.raises(SequenceGapError):
        reduce_event(state, e3_gap)


def test_invalid_event_type_rejected():
    """Verify invalid event type fails closed."""
    with pytest.raises((DomainValidationError, ValueError, TypeError)):
        EventEnvelope(
            event_id="EVT-00001",
            event_type="UNAUTHORIZED_TYPE",
            sequence_number=1,
            aggregate_id="TASK-001",
            timestamp="2026-08-19T10:00:00Z",
            payload={},
            parent_digest=GENESIS_PARENT_DIGEST,
            digest="a" * 64,
        )


def test_malformed_event_fails_closed():
    """Verify malformed event parameters fail closed."""
    with pytest.raises(DomainValidationError):
        create_event("bad_id", EventType.TASK_CREATED, 1, "TASK-001", "2026-08-19T10:00:00Z", {}, GENESIS_PARENT_DIGEST)

    with pytest.raises(DomainValidationError):
        create_event("EVT-00001", EventType.TASK_CREATED, 1, "TASK-001", "invalid-time", {}, GENESIS_PARENT_DIGEST)


def test_concurrent_append_race_fails_safely():
    """Verify thread-safety: concurrent workers appending to store fail safely without corruption."""
    store = InMemoryEventStore()
    e1 = make_test_task_event(seq=1)
    store.append(e1)

    competing_events = [
        make_test_obligation_event(seq=2, parent_digest=e1.digest, obligation_id=f"OBL-{idx:03d}")
        for idx in range(10)
    ]

    successes = 0
    failures = 0

    def try_append(evt):
        nonlocal successes, failures
        try:
            store.append(evt)
            successes += 1
        except (DuplicateSequenceError, SequenceGapError, InvalidParentDigestError):
            failures += 1

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(try_append, competing_events))

    assert successes == 1
    assert failures == 9
    assert len(store) == 2
    assert store.verify_integrity() is True


# ============================================================================
# 5. Four Distinct Recovery & Corruption Tests
# ============================================================================

def test_recovery_truncated_final_record():
    """(1) Truncated final record at EOF (torn write) is safely recovered and truncated to last valid record."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = os.path.join(tmpdir, "events.jsonl")

        store = FileAppendEventStore(log_file)
        e1 = make_test_task_event(seq=1)
        e2 = make_test_obligation_event(seq=2, parent_digest=e1.digest, obligation_id="OBL-001")
        store.append(e1)
        store.append(e2)
        assert len(store) == 2

        # Simulate power failure / torn write at EOF: partial unclosed fragment without newline
        with open(log_file, "ab") as f:
            f.write(b'{"event_id": "EVT-CRASHED", "sequence_number": 3, "payload": {"corrupt')

        reloaded_store = FileAppendEventStore(log_file)
        assert len(reloaded_store) == 2
        assert reloaded_store.verify_integrity() is True
        assert reloaded_store.get_latest_event().event_id == e2.event_id

        # Can append sequence 3 normally after torn write truncation
        e3 = make_test_obligation_event(seq=3, parent_digest=e2.digest, obligation_id="OBL-002")
        reloaded_store.append(e3)
        assert len(reloaded_store) == 3


def test_recovery_malformed_json_fails_closed():
    """(2) Malformed JSON in historical log raises CorruptEventLogError and is never silently discarded."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = os.path.join(tmpdir, "malformed.jsonl")

        store = FileAppendEventStore(log_file)
        e1 = make_test_task_event(seq=1)
        e2 = make_test_obligation_event(seq=2, parent_digest=e1.digest, obligation_id="OBL-001")
        store.append(e1)
        store.append(e2)

        # Inject malformed JSON line in the middle of log followed by another line
        with open(log_file, "ab") as f:
            f.write(b'{not valid json line}\n')
            f.write(b'{"event_id": "EVT-003"}\n')

        with pytest.raises(CorruptEventLogError, match="Corrupt event record at line"):
            FileAppendEventStore(log_file)


def test_recovery_valid_json_digest_corrupted_fails_closed():
    """(3) Validly parsed JSON but digest-corrupted record raises CorruptEventLogError and is never silently discarded."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = os.path.join(tmpdir, "digest_corrupted.jsonl")

        store = FileAppendEventStore(log_file)
        e1 = make_test_task_event(seq=1)
        e2 = make_test_obligation_event(seq=2, parent_digest=e1.digest, obligation_id="OBL-001")
        e3 = make_test_obligation_event(seq=3, parent_digest=e2.digest, obligation_id="OBL-002")
        store.append(e1)
        store.append(e2)
        store.append(e3)

        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # Modify record at line 2 (tamper title while leaving JSON valid)
        lines[1] = lines[1].replace('"title":"Obligation OBL-001"', '"title":"TAMPERED_RECORD"')

        with open(log_file, "w", encoding="utf-8") as f:
            f.writelines(lines)

        with pytest.raises(CorruptEventLogError, match="Cryptographic digest forgery/corruption"):
            FileAppendEventStore(log_file)


def test_recovery_parent_chain_corruption_fails_closed():
    """(4) Parent-chain corruption raises CorruptEventLogError and is never silently discarded."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = os.path.join(tmpdir, "parent_corrupted.jsonl")

        store = FileAppendEventStore(log_file)
        e1 = make_test_task_event(seq=1)
        # Construct e2 with broken parent_digest and compute valid internal hash for it
        e2_forged = create_event(
            event_id="EVT-OBL-00002",
            event_type=EventType.OBLIGATION_DERIVED,
            sequence_number=2,
            aggregate_id="TASK-001",
            timestamp="2026-08-19T10:00:01Z",
            payload={"obligation_id": "OBL-001"},
            parent_digest="f" * 64,  # Does not link to e1.digest!
        )
        store.append(e1)

        # Force-write e2_forged into the file
        event_dict = {
            "event_id": e2_forged.event_id,
            "event_type": e2_forged.event_type.value,
            "sequence_number": e2_forged.sequence_number,
            "aggregate_id": e2_forged.aggregate_id,
            "timestamp": e2_forged.timestamp,
            "payload": e2_forged.payload,
            "parent_digest": e2_forged.parent_digest,
            "digest": e2_forged.digest,
        }
        with open(log_file, "ab") as f:
            f.write(canonicalize_json(event_dict) + b"\n")

        with pytest.raises(CorruptEventLogError, match="Cryptographic chain broken"):
            FileAppendEventStore(log_file)


def test_file_store_operations_and_error_handling():
    """Verify store API methods: get_events, limits, offsets, error handling."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = os.path.join(tmpdir, "file_ops.jsonl")
        store = FileAppendEventStore(log_file)

        assert store.get_latest_event() is None
        assert store.get_events() == ()

        e1 = make_test_task_event(seq=1)
        e2 = make_test_obligation_event(seq=2, parent_digest=e1.digest, obligation_id="OBL-001")
        e3 = make_test_obligation_event(seq=3, parent_digest=e2.digest, obligation_id="OBL-002")

        store.append(e1)
        store.append(e2)
        store.append(e3)

        assert len(store.get_events(after_sequence=1)) == 2
        assert len(store.get_events(after_sequence=1, limit=1)) == 1
        assert store.get_latest_event() == e3

        with pytest.raises(TypeError):
            store.append("not_an_event")

        # In-memory store operations
        mem_store = InMemoryEventStore()
        assert mem_store.get_latest_event() is None
        mem_store.append(e1)
        mem_store.append(e2)
        assert len(mem_store.get_events(after_sequence=1)) == 1
        with pytest.raises(TypeError):
            mem_store.append("invalid")


# ============================================================================
# 6. Large-Log Replay Benchmark with Peak Memory Tracking (1k / 10k / 100k Events)
# ============================================================================

def test_large_log_replay_benchmark_with_memory():
    """Benchmark append throughput, verification rate, replay latency, and peak RAM (MB) for 1k, 10k, 100k events."""
    benchmark_scales = [1_000, 10_000]
    if os.environ.get("SKIP_100K_BENCHMARK") != "1":
        benchmark_scales.append(100_000)

    print("\n" + "=" * 95)
    print(f"{'Scale (Events)':<15} | {'Append (s)':<12} | {'Verify (s)':<12} | {'Replay (s)':<12} | {'Peak RSS (MB)':<14} | {'Events/sec':<12}")
    print("-" * 95)

    for scale in benchmark_scales:
        gc.collect()
        initial_rss = get_process_rss_mb()

        store = InMemoryEventStore()

        # 1. Append Benchmark
        t0_append = time.perf_counter()
        parent = GENESIS_PARENT_DIGEST
        e1 = make_test_task_event(seq=1, parent_digest=parent)
        store.append(e1)
        parent = e1.digest

        for i in range(2, scale + 1):
            e = make_test_obligation_event(seq=i, parent_digest=parent, obligation_id=f"OBL-{i:06d}")
            store.append(e)
            parent = e.digest

        append_duration = time.perf_counter() - t0_append

        # 2. Verification Benchmark
        t0_verify = time.perf_counter()
        valid = store.verify_integrity()
        verify_duration = time.perf_counter() - t0_verify
        assert valid is True

        # 3. Replay Benchmark
        t0_replay = time.perf_counter()
        state = store.replay()
        replay_duration = time.perf_counter() - t0_replay
        assert state.last_sequence_number == scale

        final_rss = get_process_rss_mb()
        peak_rss_mb = max(final_rss, initial_rss)

        replay_rate = scale / replay_duration if replay_duration > 0 else 0

        print(f"{scale:<15} | {append_duration:<12.4f} | {verify_duration:<12.4f} | {replay_duration:<12.4f} | {peak_rss_mb:<14.2f} | {replay_rate:<12.1f}")

        # Assert performance and memory gates:
        if scale == 1_000:
            assert replay_duration < 0.20
        elif scale == 10_000:
            assert replay_duration < 2.0
        elif scale == 100_000:
            assert replay_duration < 20.0

    print("=" * 95)
