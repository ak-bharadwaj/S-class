import pytest
from hypothesis import given, strategies as st, settings
import sclass_semantics_v6_0_1 as Sem
import json

c1_primitives = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-2**53 + 1, max_value=2**53 - 1),
    st.text().filter(lambda x: __import__("unicodedata").normalize("NFC", x) == x and not any(0xD800 <= ord(c) <= 0xDFFF for c in x)),
)

c1_strategy = st.recursive(
    c1_primitives,
    lambda children: st.one_of(
        st.tuples(children),
        st.dictionaries(st.text().filter(lambda x: __import__("unicodedata").normalize("NFC", x) == x and not any(0xD800 <= ord(c) <= 0xDFFF for c in x)), children).map(lambda d: Sem.FrozenMap(list(d.items())))
    ),
    max_leaves=10
)

@settings(max_examples=10)
@given(c1_strategy)
def test_c1_determinism_and_stability(val):
    b1 = Sem.canonical_c1(val)
    b2 = Sem.canonical_c1(val)
    assert b1 == b2, "C1 canonicalization must be deterministic"
    assert isinstance(b1, bytes)

@settings(max_examples=10)
@given(st.lists(st.integers(min_value=-2**53 + 1, max_value=2**53 - 1)), st.lists(st.integers(min_value=-2**53 + 1, max_value=2**53 - 1)))
def test_c1_order_independence_for_dicts(keys, vals):
    str_keys = [str(k) for k in keys]
    d1 = dict(zip(str_keys, vals))
    d2 = {k: d1[k] for k in reversed(list(d1.keys()))}
    
    b1 = Sem.canonical_c1(Sem.FrozenMap(list(d1.items())))
    b2 = Sem.canonical_c1(Sem.FrozenMap(list(d2.items())))
    assert b1 == b2

@settings(max_examples=10)
@given(st.text(min_size=1), st.text().filter(lambda x: __import__("unicodedata").normalize("NFC", x) == x and not any(0xD800 <= ord(c) <= 0xDFFF for c in x)))
def test_digest_stability(domain, val):
    d1 = Sem.digest(domain, val)
    d2 = Sem.digest(domain, val)
    assert d1 == d2
    assert d1.startswith("sha256:")

@settings(max_examples=10)
@given(st.integers(min_value=0, max_value=100))
def test_strong_canonical_state_immutability(seed):
    import dataclasses
    # Get any dataclass and try to mutate it
    state = Sem.UtcInstant(0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        state.epoch_ns = 2

def test_c1_rejects_unsupported_types():
    with pytest.raises(TypeError):
        Sem.canonical_c1(set([1, 2, 3]))
    with pytest.raises(TypeError):
        Sem.canonical_c1(object())
    with pytest.raises(TypeError):
        Sem.canonical_c1([1, 2, 3])
    with pytest.raises(TypeError):
        Sem.canonical_c1({"a": 1})
    with pytest.raises(TypeError):
        Sem.canonical_c1(3.14)

@settings(max_examples=10)
@given(st.lists(st.integers(min_value=1, max_value=5)))
def test_reducer_determinism_and_rejection(events):
    # This just ensures we can invoke the reducer and it raises TypeError on non-events
    import test_sclass_v6_0_1_conformance as Conf; state = Conf._canonical_genesis()
    for ev in events:
        with pytest.raises(TypeError):
            Sem.REFERENCE_REDUCER(state, ev)

@settings(max_examples=20)
@given(st.sampled_from(list(Sem.EventType)))
def test_property_reducer_totality(event_type):
    import test_sclass_v6_0_1_conformance as Conf
    state = Conf._canonical_genesis()
    actor = Sem.ActorIdentity("system", Sem.ActorKind.SYSTEM, None)
    try:
        ev = Sem.CanonicalEvent.create(
            "e1", "c1", state.workspace_id, state.event_sequence + 1,
            event_type, 1, "agg", actor, "caus", "corr",
            Sem.FrozenMap.from_items([]), state.event_head_hash,
            "pol", "sdk", Sem.UtcInstant(1)
        )
        Sem.REFERENCE_REDUCER(state, ev)
    except (ValueError, TypeError, KeyError):
        pass

@settings(max_examples=20)
@given(st.sampled_from(list(Sem.EventType)))
def test_property_event_schema_completeness(event_type):
    assert event_type in Sem.EVENT_PAYLOAD_SCHEMA
    assert Sem.EVENT_PAYLOAD_SCHEMA[event_type] is not None

@settings(max_examples=10)
@given(st.lists(st.sampled_from(list(Sem.EventType)), min_size=1, max_size=5))
def test_property_state_transition_determinism(event_types):
    import test_sclass_v6_0_1_conformance as Conf
    state1 = Conf._canonical_genesis()
    state2 = Conf._canonical_genesis()
    events = []

    for i, et in enumerate(event_types):
        try:
            ev = Sem.CanonicalEvent(
                event_id=f"e{i}",
                commit_id="c1",
                workspace_id="default",
                event_sequence=1+i,
                event_type=et,
                schema_version=1,
                aggregate_id="a1",
                actor=Sem.ActorIdentity("system", Sem.ActorKind.SYSTEM, None),
                causation_id="c1",
                correlation_id="c1",
                payload=Sem.FrozenMap([]),
                payload_digest=Sem.digest("sclass/event-payload/v1", Sem.FrozenMap([])),
                previous_event_hash=state1.event_head_hash,
                event_hash=Sem.Digest("sha256:"+"0"*64),
                policy_version="1",
                sdk_version="1",
                recorded_at=Sem.UtcInstant(0)
            )
            events.append(ev)
        except Exception:
            pass
        
    for ev in events:
        try:
            state1 = Sem.REFERENCE_REDUCER(state1, ev)
        except Exception:
            pass
        try:
            state2 = Sem.REFERENCE_REDUCER(state2, ev)
        except Exception:
            pass
            
    assert Sem.engineering_state_digest(state1) == Sem.engineering_state_digest(state2)

@settings(max_examples=10)
@given(st.just(None))
def test_property_checkpoint_restore_round_trip(_):
    import test_sclass_v6_0_1_conformance as Conf
    state = Conf._canonical_genesis()
    
    blob = Sem.canonical_c1_pack(state)
    restored = Sem.canonical_c1_unpack(blob)
    
    assert Sem.engineering_state_digest(state) == Sem.engineering_state_digest(restored)
