"""Component 5: Golden Vertical Slice (§12)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "20-RUNTIME"))
sys.path.insert(0, str(Path(__file__).parents[2] / "10-CONFORMANCE"))
sys.path.insert(0, str(Path(__file__).parents[2] / "src"))


from sclass.client import SClassClient


def test_golden_vertical_slice_end_to_end(tmp_path):
    # Setup authority DB
    db_path = str(tmp_path / "sclass.sqlite")
    client = SClassClient.connect(db_path)
    workspace = "default"

    # Step 1: Compile intent and submit
    intent = "Implement a TokenBucketRateLimiter with tests and type annotations"
    client.compile_and_submit_intent(intent, workspace)

    # Step 2: Run autonomous cycle (execute implementation node)
    client.run_autonomous_cycle(workspace, str(tmp_path))

    # Step 3: Verify obligations (execute verification plane)
    client.verify_obligations(workspace, str(tmp_path))

    # Step 4: Evaluate and release
    verdict = client.evaluate_and_release(workspace)

    assert str(verdict) == "ReleaseVerdict.READY"
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
    client.run_autonomous_cycle(workspace, str(tmp_path))

    # Step 3: Verify obligations (ruff + pytest)
    client.verify_obligations(workspace, str(tmp_path))

    # Step 4: Evaluate and release
    verdict = client.evaluate_and_release(workspace)

    assert str(verdict) == "ReleaseVerdict.READY"
    client.close()

