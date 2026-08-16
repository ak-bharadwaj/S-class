"""
S-Class EOS V11.2 - Hypothesis Property & Invariant Verification Adapter
Executes Hypothesis property testing campaigns against external target callables/modules
and produces structured S-Class evidence receipts with minimized serialized counterexamples.
"""

import os
import sys
import json
import hashlib
import inspect
from datetime import datetime, timezone
from dataclasses import dataclass, asdict, field
from typing import Dict, Any, Optional, Callable, List, Tuple, Union
import hypothesis
from hypothesis import given, settings, strategies as st, Phase

from evidence_ir import EpistemicStatus, UnifiedEvidenceReceipt, compute_source_hash


@dataclass
class PropertyEvidenceReceipt:
    obligation_id: str
    obligation_title: str
    domain: str
    target_identifier: str
    target_identifier_hash: str
    status: EpistemicStatus
    passed: bool
    cases_generated: int
    falsifying_example: Optional[Union[Dict[str, Any], str]] = None
    shrunk_counterexample: Optional[Union[Dict[str, Any], str]] = None
    error_message: Optional[str] = None
    reproducibility: Dict[str, Any] = field(default_factory=dict)
    environment: Dict[str, str] = field(default_factory=dict)
    provenance_hash: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self):
        if isinstance(self.status, str):
            try:
                self.status = EpistemicStatus(self.status)
            except ValueError:
                self.status = EpistemicStatus.TOOL_OUTPUT_INVALID
        # Authority Invariant: passed is True iff status is TARGET_CLEAN
        if self.status != EpistemicStatus.TARGET_CLEAN:
            self.passed = False
        if not self.provenance_hash:
            self.compute_provenance_hash()

    def compute_provenance_hash(self) -> str:
        payload = {
            "obligation_id": self.obligation_id,
            "obligation_title": self.obligation_title,
            "domain": self.domain,
            "target_identifier": self.target_identifier,
            "target_identifier_hash": self.target_identifier_hash,
            "status": self.status.value if isinstance(self.status, EpistemicStatus) else str(self.status),
            "passed": self.passed,
            "cases_generated": self.cases_generated,
            "falsifying_example": self.falsifying_example,
            "shrunk_counterexample": self.shrunk_counterexample,
            "error_message": self.error_message,
            "reproducibility": self.reproducibility,
            "environment": self.environment,
            "timestamp": self.timestamp
        }
        raw = json.dumps(payload, sort_keys=True, default=str)
        self.provenance_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return self.provenance_hash

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value if isinstance(self.status, EpistemicStatus) else str(self.status)
        return data

    def to_ir(self) -> UnifiedEvidenceReceipt:
        repro_cases = []
        if self.shrunk_counterexample:
            repro_cases.append({"type": "shrunk_counterexample", "data": self.shrunk_counterexample})
        elif self.falsifying_example:
            repro_cases.append({"type": "falsifying_example", "data": self.falsifying_example})

        return UnifiedEvidenceReceipt(
            obligation_id=self.obligation_id,
            provider_type="property_verifier",
            engine_name="Hypothesis",
            engine_version=hypothesis.__version__,
            status=self.status,
            passed=self.passed,
            target_name=self.obligation_title,
            target_identifier=self.target_identifier,
            target_source_hash=self.target_identifier_hash,
            execution_metadata={
                "domain": self.domain,
                "cases_generated": self.cases_generated,
                "reproducibility": self.reproducibility,
                "environment": self.environment
            },
            diagnostics=[{"message": self.error_message}] if self.error_message else [],
            reproducible_cases=repro_cases,
            provenance_hash=self.provenance_hash,
            timestamp=self.timestamp
        )


class PropertyVerificationAdapter:
    """
    Authoritative S-Class adapter executing Hypothesis property test suites
    against supplied target callables and recording verifiable evidence receipts with exact minimized inputs.
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
    def verify_spiffe_parser(
        cls,
        target_parser_fn: Callable[[str], Dict[str, str]],
        obligation_id: str = "OBL-SEC-SPIFFE-001",
        max_examples: int = 100
    ) -> PropertyEvidenceReceipt:
        """
        Obligation: SPIFFE ID URI invariant verification against a target parser.
        Invariant: All valid SPIFFE IDs must match spiffe://<trust-domain>/<path>
        and target_parser_fn must return matching scheme and trust domain.
        """
        title = "SPIFFE ID Format & Authority Invariant"
        target_name = getattr(target_parser_fn, "__qualname__", str(target_parser_fn))
        target_id_hash = compute_source_hash(target_parser_fn)

        cases_run = 0
        last_case = None
        falsifying = None
        shrunk = None
        err_msg = None
        status = EpistemicStatus.TARGET_CLEAN

        trust_domains = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789.-", min_size=1, max_size=30).filter(
            lambda td: not td.startswith(".") and not td.endswith(".") and not td.startswith("-") and not td.endswith("-")
        )
        paths = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789-_/", min_size=0, max_size=50)

        @settings(max_examples=max_examples, phases=[Phase.generate, Phase.shrink], deadline=None)
        @given(td=trust_domains, p=paths)
        def test_property(td, p):
            nonlocal cases_run, last_case
            cases_run += 1
            formatted_path = ("/" + p.lstrip("/")) if p else ""
            spiffe_id = f"spiffe://{td}{formatted_path}"
            last_case = {
                "trust_domain": td,
                "path": p,
                "input_spiffe_id": spiffe_id
            }

            parsed = target_parser_fn(spiffe_id)
            assert isinstance(parsed, dict), f"Target parser must return dict, got {type(parsed)}"
            assert parsed.get("scheme") == "spiffe", f"Expected scheme 'spiffe', got {parsed.get('scheme')}"
            assert parsed.get("trust_domain") == td, f"Trust domain mismatch: expected {td}, got {parsed.get('trust_domain')}"

        try:
            test_property()
        except AssertionError as e:
            status = EpistemicStatus.TARGET_COUNTEREXAMPLE_FOUND
            err_msg = str(e)
            shrunk = last_case
            falsifying = last_case
        except Exception as e:
            status = EpistemicStatus.TARGET_VERIFICATION_FAILED
            err_msg = f"Target exception during property execution: {e}"
            shrunk = last_case
            falsifying = last_case

        passed = (status == EpistemicStatus.TARGET_CLEAN)

        receipt = PropertyEvidenceReceipt(
            obligation_id=obligation_id,
            obligation_title=title,
            domain="Security / Zero-Trust Identity",
            target_identifier=target_name,
            target_identifier_hash=target_id_hash,
            status=status,
            passed=passed,
            cases_generated=cases_run,
            falsifying_example=falsifying,
            shrunk_counterexample=shrunk,
            error_message=err_msg,
            reproducibility={
                "max_examples": max_examples,
                "phases": ["generate", "shrink"],
                "strategy": "trust_domains x paths"
            },
            environment=cls._get_env_metadata()
        )
        receipt.compute_provenance_hash()
        return receipt

    @classmethod
    def verify_phi_sanitizer(
        cls,
        target_sanitizer_fn: Callable[[str], str],
        obligation_id: str = "OBL-PRIVACY-PHI-002",
        max_examples: int = 100
    ) -> PropertyEvidenceReceipt:
        """
        Obligation: PHI / PII Redaction Invariant against a target sanitizer callable.
        Invariant: Any SSN (XXX-XX-XXXX) or Email address embedded in arbitrary text must be redacted by target.
        """
        title = "PHI/PII Sanitizer Leak-Prevention Invariant"
        target_name = getattr(target_sanitizer_fn, "__qualname__", str(target_sanitizer_fn))
        target_id_hash = compute_source_hash(target_sanitizer_fn)

        cases_run = 0
        last_case = None
        falsifying = None
        shrunk = None
        err_msg = None
        status = EpistemicStatus.TARGET_CLEAN

        ssn_strategy = st.from_regex(r"\d{3}-\d{2}-\d{4}", fullmatch=True)
        email_strategy = st.emails()
        surrounding_text = st.text(alphabet=st.characters(blacklist_categories=("Cs",)), max_size=50)

        @settings(max_examples=max_examples, phases=[Phase.generate, Phase.shrink], deadline=None)
        @given(prefix=surrounding_text, ssn=ssn_strategy, mid=surrounding_text, email=email_strategy, suffix=surrounding_text)
        def test_property(prefix, ssn, mid, email, suffix):
            nonlocal cases_run, last_case
            cases_run += 1
            raw_input = f"{prefix} {ssn} {mid} {email} {suffix}"
            last_case = {
                "prefix": prefix,
                "ssn": ssn,
                "mid": mid,
                "email": email,
                "suffix": suffix,
                "raw_input": raw_input
            }

            sanitized = target_sanitizer_fn(raw_input)

            # Invariant: Raw SSN and Email must NOT appear anywhere in target's output
            assert ssn not in sanitized, f"SSN leak detected: '{ssn}' found in output '{sanitized}'"
            assert email not in sanitized, f"Email leak detected: '{email}' found in output '{sanitized}'"

        try:
            test_property()
        except AssertionError as e:
            status = EpistemicStatus.TARGET_COUNTEREXAMPLE_FOUND
            err_msg = str(e)
            shrunk = last_case
            falsifying = last_case
        except Exception as e:
            status = EpistemicStatus.TARGET_VERIFICATION_FAILED
            err_msg = f"Target exception during property execution: {e}"
            shrunk = last_case
            falsifying = last_case

        passed = (status == EpistemicStatus.TARGET_CLEAN)

        receipt = PropertyEvidenceReceipt(
            obligation_id=obligation_id,
            obligation_title=title,
            domain="Healthcare / Compliance / HIPAA",
            target_identifier=target_name,
            target_identifier_hash=target_id_hash,
            status=status,
            passed=passed,
            cases_generated=cases_run,
            falsifying_example=falsifying,
            shrunk_counterexample=shrunk,
            error_message=err_msg,
            reproducibility={
                "max_examples": max_examples,
                "phases": ["generate", "shrink"],
                "strategy": "prefix x ssn x mid x email x suffix"
            },
            environment=cls._get_env_metadata()
        )
        receipt.compute_provenance_hash()
        return receipt

    @classmethod
    def verify_double_entry_ledger(
        cls,
        target_ledger_fn: Callable[[List[Tuple[str, str, float]]], Dict[str, float]],
        obligation_id: str = "OBL-FIN-LEDGER-003",
        max_examples: int = 100
    ) -> PropertyEvidenceReceipt:
        """
        Obligation: Double-Entry Financial Ledger Conservation Invariant against a target ledger callable.
        Invariant: Total debits must equal total credits, and net account balance delta sum must equal 0.0.
        """
        title = "Double-Entry Ledger Zero-Sum Conservation Invariant"
        target_name = getattr(target_ledger_fn, "__qualname__", str(target_ledger_fn))
        target_id_hash = compute_source_hash(target_ledger_fn)

        cases_run = 0
        last_case = None
        falsifying = None
        shrunk = None
        err_msg = None
        status = EpistemicStatus.TARGET_CLEAN

        accounts = st.sampled_from(["ASSETS:BANK", "LIABILITIES:LOAN", "EQUITY:RETAINED", "REVENUE:SALES", "EXPENSES:OPS"])
        amounts = st.floats(min_value=0.01, max_value=1_000_000.0, allow_nan=False, allow_infinity=False)
        transactions = st.lists(
            st.tuples(accounts, accounts, amounts).filter(lambda t: t[0] != t[1]),
            min_size=1,
            max_size=20
        )

        @settings(max_examples=max_examples, phases=[Phase.generate, Phase.shrink], deadline=None)
        @given(txns=transactions)
        def test_property(txns):
            nonlocal cases_run, last_case
            cases_run += 1
            last_case = {"transactions": txns}

            balances = target_ledger_fn(txns)
            assert isinstance(balances, dict), f"Target ledger must return dict of balances, got {type(balances)}"

            # Invariant: Net delta across all accounts in a double-entry ledger must sum to exactly 0.0 (within micro-cent tolerance)
            net_delta = sum(balances.values())
            assert abs(net_delta) < 1e-4, f"Double-entry ledger invariant violated: net balance delta sum = {net_delta}"

        try:
            test_property()
        except AssertionError as e:
            status = EpistemicStatus.TARGET_COUNTEREXAMPLE_FOUND
            err_msg = str(e)
            shrunk = last_case
            falsifying = last_case
        except Exception as e:
            status = EpistemicStatus.TARGET_VERIFICATION_FAILED
            err_msg = f"Target exception during property execution: {e}"
            shrunk = last_case
            falsifying = last_case

        passed = (status == EpistemicStatus.TARGET_CLEAN)

        receipt = PropertyEvidenceReceipt(
            obligation_id=obligation_id,
            obligation_title=title,
            domain="Financial / Accounting / GAAP",
            target_identifier=target_name,
            target_identifier_hash=target_id_hash,
            status=status,
            passed=passed,
            cases_generated=cases_run,
            falsifying_example=falsifying,
            shrunk_counterexample=shrunk,
            error_message=err_msg,
            reproducibility={
                "max_examples": max_examples,
                "phases": ["generate", "shrink"],
                "strategy": "double_entry_transactions_list"
            },
            environment=cls._get_env_metadata()
        )
        receipt.compute_provenance_hash()
        return receipt

    @classmethod
    def save_evidence_receipt(cls, receipt: PropertyEvidenceReceipt, workspace_dir: str) -> str:
        """Persists property verification evidence receipt into .agents/evidence/ directory."""
        evidence_dir = os.path.join(workspace_dir, ".agents", "evidence")
        os.makedirs(evidence_dir, exist_ok=True)
        evidence_path = os.path.join(evidence_dir, f"property_{receipt.obligation_id}.json")
        with open(evidence_path, "w", encoding="utf-8") as f:
            json.dump(receipt.to_dict(), f, indent=2, default=str)
        return evidence_path
