"""
S-Class Observation Layer.
"""

from sclass.observation.fingerprint import compute_workspace_snapshot, compute_workspace_fingerprint, compute_file_hash
from sclass.observation.receipt import save_receipt, load_receipt, create_observed_receipt
from sclass.observation.observer import observe_command, detect_execution_kind, KNOWN_TEST_VERIFIERS
from sclass.observation.factory import ObservationFactory
from sclass.observation.convergence import ObservationConvergence, converge_execution
from sclass.observation.record import (
    ObservationRecord,
    ProcessTelemetry,
    GitRevisionState,
    WorkspaceDelta,
    FileMutation,
    redact_observation_secrets,
)
from sclass.observation.git_observer import GitObserver
from sclass.observation.delta import DeltaCalculator

__all__ = [
    "compute_workspace_snapshot",
    "compute_workspace_fingerprint",
    "compute_file_hash",
    "save_receipt",
    "load_receipt",
    "create_observed_receipt",
    "observe_command",
    "detect_execution_kind",
    "KNOWN_TEST_VERIFIERS",
    "ObservationFactory",
    "ObservationConvergence",
    "converge_execution",
    "ObservationRecord",
    "ProcessTelemetry",
    "GitRevisionState",
    "WorkspaceDelta",
    "FileMutation",
    "GitObserver",
    "DeltaCalculator",
    "redact_observation_secrets",
]

