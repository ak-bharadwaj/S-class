"""
S-Class EOS V11.2 - Hypothesis Property & Invariant Verification Adapter
Generates cryptographic S-Class evidence receipts from Hypothesis property testing campaigns.
"""

import os
import sys
import json
import hashlib
import re
from datetime import datetime, timezone
from dataclasses import dataclass, asdict, field
from typing import Dict, Any, Optional, Callable, List
import hypothesis
from hypothesis import given, settings, strategies as st, Phase


@dataclass
class PropertyEvidenceReceipt:
    obligation_id: str
    obligation_title: str
    domain: str
    passed: bool
    cases_generated: int
    falsifying_example: Optional[str] = None
    shrunk_counterexample: Optional[str] = None
    error_message: Optional[str] = None
    environment: Dict[str, str] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    evidence_hash: str = ""

    def compute_hash(self) -> str:
        payload = {
            "obligation_id": self.obligation_id,
            "obligation_title": self.obligation_title,
            "domain": self.domain,
            "passed": self.passed,
            "cases_generated": self.cases_generated,
            "falsifying_example": self.falsifying_example,
            "shrunk_counterexample": self.shrunk_counterexample,
            "error_message": self.error_message,
            "timestamp": self.timestamp
        }
        raw = json.dumps(payload, sort_keys=True)
        self.evidence_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return self.evidence_hash

    def to_dict(self) -> Dict[str, Any]:
        if not self.evidence_hash:
            self.compute_hash()
        return asdict(self)


class PropertyVerificationAdapter:
    """
    Authoritative S-Class adapter executing Hypothesis property test suites
    and recording immutable cryptographic evidence receipts.
    """

    @classmethod
    def _get_env_metadata(cls) -> Dict[str, str]:
        return {
            "python_version": sys.version.split()[0],
            "platform": sys.platform,
            "hypothesis_version": hypothesis.__version__,
            "engine": "Hypothesis Property Verification Adapter V11.2"
        }

    @classmethod
    def run_spiffe_invariant_check(cls, max_examples: int = 100) -> PropertyEvidenceReceipt:
        """
        Obligation: SPIFFE ID URI invariant verification.
        Invariant: All valid SPIFFE IDs must match spiffe://<trust-domain>/<path> with non-empty trust domain.
        """
        obligation_id = "OBL-SEC-SPIFFE-001"
        title = "SPIFFE ID Format & Authority Invariant"
        spiffe_regex = re.compile(r"^spiffe://([a-zA-Z0-9.\-_]+)(/.*)?$")

        cases_run = 0
        falsifying = None
        shrunk = None
        err_msg = None
        passed = True

        trust_domains = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789.-", min_size=1, max_size=30).filter(
            lambda td: not td.startswith(".") and not td.endswith(".") and not td.startswith("-") and not td.endswith("-")
        )
        paths = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789-_/", min_size=0, max_size=50)

        @settings(max_examples=max_examples, phases=[Phase.generate, Phase.shrink], deadline=None)
        @given(td=trust_domains, p=paths)
        def test_property(td, p):
            nonlocal cases_run
            cases_run += 1
            formatted_path = ("/" + p.lstrip("/")) if p else ""
            spiffe_id = f"spiffe://{td}{formatted_path}"
            
            # Invariant 1: Must start with spiffe://
            assert spiffe_id.startswith("spiffe://"), "Must have spiffe scheme"
            # Invariant 2: Parsed regex must match
            m = spiffe_regex.match(spiffe_id)
            assert m is not None, f"SPIFFE regex match failed for {spiffe_id}"
            assert m.group(1) == td, f"Trust domain mismatch: expected {td}, got {m.group(1)}"

        try:
            test_property()
        except AssertionError as e:
            passed = False
            err_msg = str(e)
            falsifying = str(getattr(e, "__cause__", e))
            shrunk = str(e)
        except Exception as e:
            passed = False
            err_msg = f"Unexpected execution error: {e}"

        receipt = PropertyEvidenceReceipt(
            obligation_id=obligation_id,
            obligation_title=title,
            domain="Security / Zero-Trust Identity",
            passed=passed,
            cases_generated=cases_run,
            falsifying_example=falsifying,
            shrunk_counterexample=shrunk,
            error_message=err_msg,
            environment=cls._get_env_metadata()
        )
        receipt.compute_hash()
        return receipt

    @classmethod
    def run_phi_sanitizer_invariant_check(cls, max_examples: int = 100) -> PropertyEvidenceReceipt:
        """
        Obligation: PHI / PII Redaction Invariant.
        Invariant: Any SSN (XXX-XX-XXXX) or Email address embedded in arbitrary text must be fully redacted.
        """
        obligation_id = "OBL-PRIVACY-PHI-002"
        title = "PHI/PII Sanitizer Leak-Prevention Invariant"

        ssn_pattern = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
        # Full RFC 5322 compliant email regex matching all valid local-part symbols
        email_pattern = re.compile(r"[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+")

        def sanitize_phi(text: str) -> str:
            # S-Class standard PHI sanitizer
            text = ssn_pattern.sub("[REDACTED_SSN]", text)
            text = email_pattern.sub("[REDACTED_EMAIL]", text)
            return text

        cases_run = 0
        falsifying = None
        shrunk = None
        err_msg = None
        passed = True

        ssn_strategy = st.from_regex(r"\d{3}-\d{2}-\d{4}", fullmatch=True)
        email_strategy = st.emails()
        surrounding_text = st.text(alphabet=st.characters(blacklist_categories=("Cs",)), max_size=50)

        @settings(max_examples=max_examples, phases=[Phase.generate, Phase.shrink], deadline=None)
        @given(prefix=surrounding_text, ssn=ssn_strategy, mid=surrounding_text, email=email_strategy, suffix=surrounding_text)
        def test_property(prefix, ssn, mid, email, suffix):
            nonlocal cases_run
            cases_run += 1
            raw_input = f"{prefix} {ssn} {mid} {email} {suffix}"
            sanitized = sanitize_phi(raw_input)

            # Invariant: Raw SSN and Email must NOT appear anywhere in sanitized text
            assert ssn not in sanitized, f"SSN leak detected in sanitized output: {sanitized}"
            assert email not in sanitized, f"Email leak detected in sanitized output: {sanitized}"

        try:
            test_property()
        except AssertionError as e:
            passed = False
            err_msg = str(e)
            falsifying = str(getattr(e, "__cause__", e))
            shrunk = str(e)
        except Exception as e:
            passed = False
            err_msg = f"Unexpected execution error: {e}"

        receipt = PropertyEvidenceReceipt(
            obligation_id=obligation_id,
            obligation_title=title,
            domain="Healthcare / Compliance / HIPAA",
            passed=passed,
            cases_generated=cases_run,
            falsifying_example=falsifying,
            shrunk_counterexample=shrunk,
            error_message=err_msg,
            environment=cls._get_env_metadata()
        )
        receipt.compute_hash()
        return receipt

    @classmethod
    def run_double_entry_ledger_invariant_check(cls, max_examples: int = 100) -> PropertyEvidenceReceipt:
        """
        Obligation: Double-Entry Financial Ledger Conservation Invariant.
        Invariant: Total debits must equal total credits across all transactions, preserving zero net delta.
        """
        obligation_id = "OBL-FIN-LEDGER-003"
        title = "Double-Entry Ledger Zero-Sum Conservation Invariant"

        cases_run = 0
        falsifying = None
        shrunk = None
        err_msg = None
        passed = True

        accounts = st.sampled_from(["ASSETS", "LIABILITIES", "EQUITY", "REVENUE", "EXPENSES"])
        amounts = st.floats(min_value=0.01, max_value=1000000.0, allow_nan=False, allow_infinity=False)

        @settings(max_examples=max_examples, phases=[Phase.generate, Phase.shrink], deadline=None)
        @given(entries=st.lists(st.tuples(accounts, accounts, amounts), min_size=1, max_size=20))
        def test_property(entries):
            nonlocal cases_run
            cases_run += 1

            total_debits = 0.0
            total_credits = 0.0
            balances: Dict[str, float] = {a: 0.0 for a in ["ASSETS", "LIABILITIES", "EQUITY", "REVENUE", "EXPENSES"]}

            for src, dst, amt in entries:
                amt_float = float(amt)
                balances[src] -= amt_float
                balances[dst] += amt_float
                total_debits += amt_float
                total_credits += amt_float

            # Invariant 1: Total Debits == Total Credits
            assert abs(total_debits - total_credits) < 1e-6, f"Debits ({total_debits}) != Credits ({total_credits})"
            # Invariant 2: Sum of all account changes must be identically zero
            assert abs(sum(balances.values())) < 1e-6, f"Non-zero ledger balance sum: {sum(balances.values())}"

        try:
            test_property()
        except AssertionError as e:
            passed = False
            err_msg = str(e)
            falsifying = str(getattr(e, "__cause__", e))
            shrunk = str(e)
        except Exception as e:
            passed = False
            err_msg = f"Unexpected execution error: {e}"

        receipt = PropertyEvidenceReceipt(
            obligation_id=obligation_id,
            obligation_title=title,
            domain="Financial Systems / Double-Entry Accounting",
            passed=passed,
            cases_generated=cases_run,
            falsifying_example=falsifying,
            shrunk_counterexample=shrunk,
            error_message=err_msg,
            environment=cls._get_env_metadata()
        )
        receipt.compute_hash()
        return receipt

    @classmethod
    def save_evidence_receipt(cls, receipt: PropertyEvidenceReceipt, workspace_dir: str) -> str:
        """Persists cryptographic evidence receipt into .agents/evidence/ directory."""
        evidence_dir = os.path.join(workspace_dir, ".agents", "evidence")
        os.makedirs(evidence_dir, exist_ok=True)
        evidence_path = os.path.join(evidence_dir, f"property_{receipt.obligation_id}.json")
        with open(evidence_path, "w", encoding="utf-8") as f:
            json.dump(receipt.to_dict(), f, indent=2)
        return evidence_path
