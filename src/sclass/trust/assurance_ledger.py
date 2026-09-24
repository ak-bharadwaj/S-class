"""
S-Class Trust: Canonical Assurance Ledger.
Maintains canonical project truth: obligations, claims, verifications, and assessments.
Direct mutation from the execution plane is strictly forbidden.
"""

from sclass.trust.two_ledgers import AssuranceLedger

__all__ = ["AssuranceLedger"]
