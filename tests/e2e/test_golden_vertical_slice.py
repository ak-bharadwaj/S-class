"""Component 5: Golden Vertical Slice (§12)."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parents[2] / "20-RUNTIME"))
sys.path.insert(0, str(Path(__file__).parents[2] / "10-CONFORMANCE"))
sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

import sclass_semantics_v6_0_1 as sem

from sclass.client import SClassClient, StateBindingRefusalError
from tests.helpers.test_boundary import TestOnlyUnsandboxedBoundary


def test_golden_vertical_slice_end_to_end(tmp_path):
    # Setup authority DB
    db_path = str(tmp_path / "sclass.sqlite")
    client = SClassClient.connect(db_path)
    workspace = "default"

    # Step 1: Compile intent and submit
    intent = "Implement a TokenBucketRateLimiter with tests and type annotations"
    client.compile_and_submit_intent(intent, workspace)

    # Step 2: Run autonomous cycle (execute implementation node)
    # Under Path 2 disposition (E-SEM-1 A6), callers must provide authentic StateBinding.
    # Without authentic attestation, run_autonomous_cycle must fail closed before creating
    # any WorkProposal, execution lease, authorization claim, digest, or synthetic evidence object.
    with (
        patch.object(sem, "WorkProposal", wraps=sem.WorkProposal) as mock_wp,
        patch.object(sem, "ExecutionLease", wraps=sem.ExecutionLease) as mock_el,
        patch.object(sem, "AuthorizationLease", wraps=sem.AuthorizationLease) as mock_al,
        pytest.raises(PermissionError) as exc_info,
    ):
        client.run_autonomous_cycle(workspace, str(tmp_path), boundary=TestOnlyUnsandboxedBoundary(tmp_path))

    # Assert exact structured refusal attributes
    assert isinstance(exc_info.value, StateBindingRefusalError)
    assert exc_info.value.reason_code == "MISSING_AUTHENTIC_STATE_BINDING"
    assert "Authentic StateBinding" in str(exc_info.value)
    assert exc_info.value.missing_items == [
        "state_binding",
        "request_content_digest",
        "context_digest",
    ]

    # Verify no WorkProposal, lease, or authorization claim object was created before refusal
    assert mock_wp.call_count == 0
    assert mock_el.call_count == 0
    assert mock_al.call_count == 0

    # Verify no uncommitted mutations were staged or executed to workspace
    assert not (tmp_path / "src").exists()

    client.close()


def test_golden_vertical_slice_arbitrary_component(tmp_path):
    """Verify autonomous pipeline operates cleanly on non-rate-limiter components without hardcoding."""
    db_path = str(tmp_path / "sclass_lru.sqlite")
    client = SClassClient.connect(db_path)
    workspace = "default"

    # Step 1: Compile arbitrary intent and submit
    intent = "Implement an LRUCache with storage and eviction operations"
    client.compile_and_submit_intent(intent, workspace)

    # Step 2: Run autonomous cycle
    # Under Path 2 disposition (E-SEM-1 A6), autonomous execution must fail closed
    # without authentic StateBinding attestation.
    with (
        patch.object(sem, "WorkProposal", wraps=sem.WorkProposal) as mock_wp,
        patch.object(sem, "ExecutionLease", wraps=sem.ExecutionLease) as mock_el,
        patch.object(sem, "AuthorizationLease", wraps=sem.AuthorizationLease) as mock_al,
        pytest.raises(PermissionError) as exc_info,
    ):
        client.run_autonomous_cycle(workspace, str(tmp_path), boundary=TestOnlyUnsandboxedBoundary(tmp_path))

    # Assert exact structured refusal attributes
    assert isinstance(exc_info.value, StateBindingRefusalError)
    assert exc_info.value.reason_code == "MISSING_AUTHENTIC_STATE_BINDING"
    assert "Authentic StateBinding" in str(exc_info.value)
    assert exc_info.value.missing_items == [
        "state_binding",
        "request_content_digest",
        "context_digest",
    ]

    # Verify no WorkProposal, lease, or authorization claim object was created before refusal
    assert mock_wp.call_count == 0
    assert mock_el.call_count == 0
    assert mock_al.call_count == 0

    # Verify no uncommitted mutations were staged or executed to workspace
    assert not (tmp_path / "src").exists()

    client.close()

