"""
Real Agent Matrix: OpenCode / CodeSandbox Platform Adapter Tests.
Verifies OpenCode interactions:
- connection handshake
- actions authorization
- tools
- events
- claims
- handoff
"""

from sclass.integrations.opencode.adapter import OpenCodeAdapter
from sclass.domain.claim import Claim


def test_opencode_complete_matrix(tmp_path):
    adapter = OpenCodeAdapter(workspace_dir=str(tmp_path), mode="enforce")

    # 1. Connection
    conn = adapter.connect()
    assert conn["status"] == "connected"
    assert adapter.connected

    # 2. Actions
    act_allow = adapter.on_action("create_file", "index.js", {"content": "console.log('hi');"})
    assert act_allow.is_allowed

    act_deny = adapter.on_action("delete_file", ".sclass/trust/key.pem", {})
    assert act_deny.is_denied

    # 3. Tools
    tool_allow = adapter.on_tool("npm_install", {"package": "lodash"})
    assert tool_allow.is_allowed

    # 4. Events
    ev_res = adapter.on_event("sandbox_started", {"sandbox_id": "sbx-99"})
    assert ev_res["status"] == "recorded"

    # 5. Claims
    claim = Claim(
        claim_id="opencode_claim",
        task_id="opencode_task",
        statement="Tests pass",
        claim_type="test_pass",
    )
    import sys
    from sclass.trust.ledger import LocalLedger
    from sclass.observation.observer import observe_command

    test_file = tmp_path / "test_opencode_pass.py"
    test_file.write_text("def test_opencode_ok(): assert True\n", encoding="utf-8")
    ledger = LocalLedger(str(tmp_path))
    receipt = observe_command(f'"{sys.executable}" -m pytest "{test_file}" -q', workspace_dir=str(tmp_path), ledger=ledger)

    verdict = adapter.evaluate_claim(claim, receipt)
    assert verdict.is_accepted


    # 6. Handoff
    pkg = adapter.create_handoff("opencode_project", next_action="Review pull request")
    assert pkg.next_action == "Review pull request"
