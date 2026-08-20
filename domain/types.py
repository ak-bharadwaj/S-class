"""Canonical Enums and Validation Constants for S-Class D1 Domain Kernel."""

from enum import Enum
import re


# ============================================================================
# Canonical ID Patterns
# ============================================================================

TASK_ID_PATTERN = re.compile(r"^TASK-[A-Za-z0-9_-]+$")
OBLIGATION_ID_PATTERN = re.compile(r"^OBL-[A-Za-z0-9_-]+$")
CLAIM_ID_PATTERN = re.compile(r"^CLM-[A-Za-z0-9_-]+$")
POLICY_ID_PATTERN = re.compile(r"^POL-[A-Za-z0-9_-]+$")
EXCEPTION_ID_PATTERN = re.compile(r"^EXC-[A-Za-z0-9_-]+$")
PROPOSAL_ID_PATTERN = re.compile(r"^PROP-[A-Za-z0-9_-]+$")
DECISION_ID_PATTERN = re.compile(r"^DEC-[A-Za-z0-9_-]+$")
EVIDENCE_ID_PATTERN = re.compile(r"^EV-[A-Za-z0-9_-]+$")
PLAN_ID_PATTERN = re.compile(r"^PLAN-[A-Za-z0-9_-]+$")
RECEIPT_ID_PATTERN = re.compile(r"^RCPT-[A-Za-z0-9_-]+$")
EVENT_ID_PATTERN = re.compile(r"^EVT-[A-Za-z0-9_-]+$")
WORKER_CONTEXT_ID_PATTERN = re.compile(r"^WCTX-[A-Za-z0-9_-]+$")
CONVERGENCE_REPORT_ID_PATTERN = re.compile(r"^CNV-[A-Za-z0-9_-]+$")

HEX_40_PATTERN = re.compile(r"^[0-9a-f]{40}$")
HEX_64_PATTERN = re.compile(r"^[0-9a-f]{64}$")
HEX_128_PATTERN = re.compile(r"^[0-9a-f]{128}$")


# ============================================================================
# Canonical Domain Enums
# ============================================================================

class ObligationCategory(str, Enum):
    CORRECTNESS_FUNCTIONAL = "CORRECTNESS_FUNCTIONAL"
    SECURITY_INTEGRITY = "SECURITY_INTEGRITY"
    PERFORMANCE_SCALE = "PERFORMANCE_SCALE"
    OPERATIONAL_SAFETY = "OPERATIONAL_SAFETY"
    REGRESSION_INVARIANCE = "REGRESSION_INVARIANCE"
    CONTRACT_CONFORMANCE = "CONTRACT_CONFORMANCE"
    ARCHITECTURAL_HEALTH = "ARCHITECTURAL_HEALTH"


class Criticality(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ObligationStatus(str, Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    SATISFIED = "SATISFIED"
    CONDITIONAL = "CONDITIONAL"
    BLOCKED = "BLOCKED"
    WAIVED = "WAIVED"


class ClaimTier(str, Enum):
    V0_OBSERVABLE = "V0_OBSERVABLE"
    V1_STRUCTURAL = "V1_STRUCTURAL"
    V2_BEHAVIORAL = "V2_BEHAVIORAL"
    V3_PROPERTY = "V3_PROPERTY"
    V4_ADVERSARIAL_EXPLORATORY = "V4_ADVERSARIAL_EXPLORATORY"


class TargetType(str, Enum):
    FILE = "FILE"
    FUNCTION = "FUNCTION"
    MODULE = "MODULE"
    ENDPOINT = "ENDPOINT"
    DATABASE_SCHEMA = "DATABASE_SCHEMA"
    CONFIGURATION = "CONFIGURATION"
    SYSTEM_BEHAVIOR = "SYSTEM_BEHAVIOR"


class ClaimStatus(str, Enum):
    UNSUPPORTED = "UNSUPPORTED"
    SUPPORTED = "SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    WAIVED = "WAIVED"


class PolicyScope(str, Enum):
    GLOBAL_ORGANIZATIONAL = "GLOBAL_ORGANIZATIONAL"
    PROJECT = "PROJECT"
    TASK = "TASK"
    OBLIGATION = "OBLIGATION"


class RuleType(str, Enum):
    REQUIRE_CAPABILITY = "REQUIRE_CAPABILITY"
    REQUIRE_TIER = "REQUIRE_TIER"
    REQUIRE_INDEPENDENT_PROVIDERS = "REQUIRE_INDEPENDENT_PROVIDERS"
    NO_CONFLICTS = "NO_CONFLICTS"
    FORBID_SYNTHETIC = "FORBID_SYNTHETIC"
    MAX_STALENESS_COMMITS = "MAX_STALENESS_COMMITS"
    REQUIRE_MIN_TRIALS = "REQUIRE_MIN_TRIALS"
    REQUIRE_CODE_COVERAGE = "REQUIRE_CODE_COVERAGE"


class CombinatorType(str, Enum):
    ALL = "ALL"
    ANY = "ANY"
    AT_LEAST = "AT_LEAST"
    CONDITIONAL = "CONDITIONAL"


class EvidencePolarity(str, Enum):
    SUPPORTS = "SUPPORTS"
    REFUTES = "REFUTES"
    NEUTRAL = "NEUTRAL"


class EvidenceValidity(str, Enum):
    VALID = "VALID"
    STALE = "STALE"
    CONFLICTED = "CONFLICTED"
    INVALID_SIGNATURE = "INVALID_SIGNATURE"


class RawStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"
    INDETERMINATE = "INDETERMINATE"


class AssessmentVerdict(str, Enum):
    SATISFIED = "SATISFIED"
    REJECTED = "REJECTED"
    CONDITIONAL = "CONDITIONAL"


class EventType(str, Enum):
    TASK_CREATED = "TASK_CREATED"
    OBLIGATION_DERIVED = "OBLIGATION_DERIVED"
    CLAIM_REGISTERED = "CLAIM_REGISTERED"
    EVIDENCE_COLLECTED = "EVIDENCE_COLLECTED"
    ASSESSMENT_PRODUCED = "ASSESSMENT_PRODUCED"
    CONVERGENCE_EVALUATED = "CONVERGENCE_EVALUATED"
    TASK_ACCEPTED = "TASK_ACCEPTED"
    TASK_BLOCKED = "TASK_BLOCKED"


class DriftType(str, Enum):
    MISSING = "MISSING"
    PARTIAL = "PARTIAL"
    CONTRADICTORY = "CONTRADICTORY"
    UNREQUESTED = "UNREQUESTED"
    STALE = "STALE"
