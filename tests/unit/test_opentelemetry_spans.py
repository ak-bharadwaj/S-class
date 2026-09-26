"""
Unit tests validating OpenTelemetry span attribute standards for Layer E.
"""
import pytest
import hashlib
import json

def format_span(action_id: str, task_id: str, agent_id: str, exit_code: int, stdout: str) -> dict:
    stdout_digest = hashlib.sha256(stdout.encode("utf-8")).hexdigest()
    return {
        "name": "sclass.action",
        "attributes": {
            "sclass.action.id": action_id,
            "sclass.task.id": task_id,
            "sclass.agent.id": agent_id,
            "sclass.exit_code": exit_code,
            "sclass.stdout_digest": stdout_digest,
        }
    }

def test_span_attributes_presence():
    span = format_span("act-101", "task-500", "codex-01", 0, "All tests passed\n")
    attrs = span["attributes"]
    assert attrs["sclass.action.id"] == "act-101"
    assert attrs["sclass.task.id"] == "task-500"
    assert attrs["sclass.agent.id"] == "codex-01"
    assert attrs["sclass.exit_code"] == 0
    assert len(attrs["sclass.stdout_digest"]) == 64

def test_span_stdout_digest_deterministic():
    s1 = format_span("act-1", "task-1", "agent-1", 0, "sample output")
    s2 = format_span("act-2", "task-1", "agent-1", 0, "sample output")
    assert s1["attributes"]["sclass.stdout_digest"] == s2["attributes"]["sclass.stdout_digest"]
