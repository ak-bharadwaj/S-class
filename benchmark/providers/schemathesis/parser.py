"""
S-Class EOS V11.2 - Schemathesis Output & Failure Parser.
Parses Schemathesis check failures, exceptions, and execution events into native S-Class ContractViolation records.
Strict boundary invariant: Zero Schemathesis internal objects escape through this parser.
"""

from typing import List, Dict, Any, Optional
from .models import ContractViolation


class SchemathesisParser:
    """Parses raw Schemathesis execution events and exceptions into native S-Class models."""

    @staticmethod
    def parse_exception(
        exc: Exception,
        path: str = "",
        method: str = "",
        status_code: Optional[int] = None,
        curl_command: Optional[str] = None
    ) -> List[ContractViolation]:
        """Extracts structured violations from a Schemathesis exception or FailureGroup."""
        violations: List[ContractViolation] = []
        exc_type = type(exc).__name__

        # Handle Python 3.11+ ExceptionGroup / Schemathesis FailureGroup
        exceptions_to_process = []
        if hasattr(exc, "exceptions"):
            exceptions_to_process.extend(getattr(exc, "exceptions", []))
        elif hasattr(exc, "__cause__") and exc.__cause__ and hasattr(exc.__cause__, "exceptions"):
            exceptions_to_process.extend(getattr(exc.__cause__, "exceptions", []))
        else:
            exceptions_to_process.append(exc)

        for sub_exc in exceptions_to_process:
            sub_type = type(sub_exc).__name__
            msg = str(sub_exc)
            sub_status_code = getattr(sub_exc, "status_code", None) or status_code
            sub_curl = curl_command

            # Check if case or request information is attached
            case_obj = getattr(sub_exc, "case", None)
            if case_obj is not None:
                path = path or str(getattr(case_obj, "path", ""))
                method = method or str(getattr(case_obj, "method", ""))
                if not sub_curl and hasattr(case_obj, "as_curl_command"):
                    try:
                        sub_curl = case_obj.as_curl_command()
                    except Exception:
                        sub_curl = None

            response_obj = getattr(sub_exc, "response", None)
            if response_obj is not None and hasattr(response_obj, "status_code"):
                sub_status_code = response_obj.status_code

            schema_path = getattr(sub_exc, "schema_path", None)

            violations.append(
                ContractViolation(
                    error_type=sub_type,
                    message=msg,
                    path=path or "unknown",
                    method=(method or "unknown").upper(),
                    status_code=sub_status_code,
                    curl_command=sub_curl,
                    schema_path=schema_path,
                    details={"raw_exception_class": sub_type}
                )
            )

        if not violations:
            violations.append(
                ContractViolation(
                    error_type=exc_type,
                    message=str(exc),
                    path=path or "unknown",
                    method=(method or "unknown").upper(),
                    status_code=status_code,
                    curl_command=curl_command,
                    details={"raw_exception_class": exc_type}
                )
            )

        return violations

    @staticmethod
    def parse_raw_failure_entry(entry: Dict[str, Any]) -> ContractViolation:
        """Parses a dictionary representing a failure into a ContractViolation."""
        return ContractViolation(
            error_type=str(entry.get("error_type", "ContractViolation")),
            message=str(entry.get("message", "")),
            path=str(entry.get("path", "")),
            method=str(entry.get("method", "GET")).upper(),
            status_code=entry.get("status_code"),
            curl_command=entry.get("curl_command"),
            schema_path=entry.get("schema_path"),
            details=dict(entry.get("details", {}))
        )
