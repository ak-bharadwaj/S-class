"""Compatibility facade over the versioned S-Class semantic runtime."""
import sclass_semantics_v6_0_1 as _semantic
for _name, _value in _semantic.__dict__.items():
    if not _name.startswith('__'):
        globals()[_name] = _value
assert_reducer_totality()
