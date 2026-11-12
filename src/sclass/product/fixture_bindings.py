"""Backward-compatibility shim for Block 2 fixture runner bindings.

All fixture runner bindings, metadata, and execution logic are consolidated
inside the permitted fixture runner module: sclass.product.fixture_runner (D2).
"""
from __future__ import annotations

from sclass.product.fixture_runner import (
    BLOCK2_6_PAIRS_BINDINGS,
    BLOCK2_17_SINGLE_BINDINGS,
    FixtureBinding,
    VALID_NOT_RUN_REASONS,
    execute_binding,
    verify_bindings_against_master,
)

__all__ = [
    "FixtureBinding",
    "VALID_NOT_RUN_REASONS",
    "BLOCK2_17_SINGLE_BINDINGS",
    "BLOCK2_6_PAIRS_BINDINGS",
    "execute_binding",
    "verify_bindings_against_master",
]
