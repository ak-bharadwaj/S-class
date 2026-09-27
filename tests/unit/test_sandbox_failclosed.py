"""
Unit tests validating fail-closed boundary enforcement when sandbox provider is missing.
"""
import pytest

class SandboxUnavailableError(Exception):
    pass

class MockIsolationGate:
    def __init__(self, available_engines: list[str]):
        self.available_engines = set(available_engines)

    def execute_in_sandbox(self, engine: str, command: list[str]) -> int:
        if engine not in self.available_engines:
            raise SandboxUnavailableError(f"Requested isolation engine '{engine}' is unavailable.")
        return 0

def test_missing_container_engine_raises_sandbox_unavailable():
    gate = MockIsolationGate(available_engines=["bwrap"])
    with pytest.raises(SandboxUnavailableError) as exc_info:
        gate.execute_in_sandbox("runsc", ["echo", "test"])
    assert "runsc" in str(exc_info.value)

def test_available_engine_succeeds():
    gate = MockIsolationGate(available_engines=["bwrap"])
    assert gate.execute_in_sandbox("bwrap", ["echo", "test"]) == 0
