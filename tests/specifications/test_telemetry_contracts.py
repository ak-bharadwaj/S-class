"""Test telemetry span contracts."""
import pytest
from sclass.contracts.telemetry_contracts import SpanDefinition

def test_span_definition_attributes():
    span = SpanDefinition(
        name="sclass.action.execute",
        trace_id="trace-001",
        span_id="span-001",
        parent_span_id=None,
        start_time_ns=1000000,
        end_time_ns=2000000,
        attributes={"sclass.exit_code": 0},
        status_code="OK"
    )
    assert span.name == "sclass.action.execute"
    assert span.attributes["sclass.exit_code"] == 0
