"""
Unit Tests for S-Class CLI Commands.
Covers:
- sclass init
- sclass status
- sclass doctor
- sclass task create
- sclass map
- sclass impact
- sclass handoff
"""

import os
import io
import contextlib
import pytest

from sclass.cli.main import (
    build_parser,
    cmd_init,
    cmd_status,
    cmd_doctor,
    cmd_task_create,
    cmd_map,
    cmd_impact,
    cmd_handoff,
)


@pytest.fixture
def workspace(tmp_path):
    ws = tmp_path / "cli_ws"
    ws.mkdir(parents=True, exist_ok=True)
    # Create sample file for map and impact
    (ws / "sample.py").write_text("class MyService:\n    def execute(self):\n        pass\n", encoding="utf-8")
    return str(ws)


def test_cli_init_status_doctor(workspace):
    parser = build_parser()

    # 1. sclass init
    args_init = parser.parse_args(["init", "-w", workspace])
    assert cmd_init(args_init) == 0

    # 2. sclass status
    args_status = parser.parse_args(["status", "-w", workspace])
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert cmd_status(args_status) == 0
    status_out = buf.getvalue()
    assert "S-Class Control Plane Status" in status_out
    assert "OK (Chain Valid)" in status_out

    # 3. sclass doctor
    args_doctor = parser.parse_args(["doctor", "-w", workspace])
    buf_doc = io.StringIO()
    with contextlib.redirect_stdout(buf_doc):
        assert cmd_doctor(args_doctor) == 0
    doc_out = buf_doc.getvalue()
    assert "[PASSED]" in doc_out

    # 4. sclass status --json
    parser.add_argument("--json", action="store_true") # ensure json arg works or pass to parser
    args_status_json = parser.parse_args(["status", "-w", workspace])
    setattr(args_status_json, "json", True)
    buf_json = io.StringIO()
    with contextlib.redirect_stdout(buf_json):
        assert cmd_status(args_status_json) == 0
    import json
    parsed_status = json.loads(buf_json.getvalue())
    assert parsed_status["ledger_valid"] is True

    # 5. sclass daemon --once
    from sclass.cli.main import cmd_daemon
    args_daemon = parser.parse_args(["daemon", "--once", "-w", workspace])
    buf_daemon = io.StringIO()
    with contextlib.redirect_stdout(buf_daemon):
        assert cmd_daemon(args_daemon) == 0
    assert "Health tick complete" in buf_daemon.getvalue()
    # Check IPC file was written
    ipc_file = os.path.join(workspace, ".sclass", "daemon", "ipc.json")
    assert os.path.exists(ipc_file)
    with open(ipc_file, "r", encoding="utf-8") as f:
        ipc_data = json.load(f)
    assert ipc_data["status"] == "healthy"



def test_cli_task_and_handoff(workspace):
    parser = build_parser()
    cmd_init(parser.parse_args(["init", "-w", workspace]))

    # Create task
    args_task = parser.parse_args(["task", "create", "Build Token Bucket", "-d", "Rate limiting module", "-w", workspace])
    assert cmd_task_create(args_task) == 0

    # Handoff markdown
    args_handoff = parser.parse_args(["handoff", "-w", workspace, "--next", "Implement leaky bucket fallback"])
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert cmd_handoff(args_handoff) == 0
    handoff_out = buf.getvalue()
    assert "S-Class Project Handoff" in handoff_out
    assert "Implement leaky bucket fallback" in handoff_out


def test_cli_map_and_impact(workspace):
    parser = build_parser()

    # Map
    args_map = parser.parse_args(["map", "-w", workspace, "--max-files", "5"])
    buf_map = io.StringIO()
    with contextlib.redirect_stdout(buf_map):
        assert cmd_map(args_map) == 0
    map_out = buf_map.getvalue()
    assert "Codebase Symbol Map" in map_out
    assert "MyService" in map_out

    # Impact
    args_impact = parser.parse_args(["impact", "MyService", "-w", workspace])
    buf_imp = io.StringIO()
    with contextlib.redirect_stdout(buf_imp):
        assert cmd_impact(args_impact) == 0
    imp_out = buf_imp.getvalue()
    assert "Target: MyService" in imp_out
