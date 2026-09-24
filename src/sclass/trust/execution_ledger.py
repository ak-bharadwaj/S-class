"""
S-Class Trust: Canonical Execution Ledger.
Maintains operational execution facts: tool calls, runtime events, operation lifecycles.
Execution state does not constitute project truth.
"""

from sclass.trust.two_ledgers import ExecutionLedger

__all__ = ["ExecutionLedger"]
