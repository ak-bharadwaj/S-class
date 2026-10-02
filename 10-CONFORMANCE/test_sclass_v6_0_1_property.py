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
