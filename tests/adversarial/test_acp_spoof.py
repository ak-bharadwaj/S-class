"""
Adversarial Test: Invariant 5 - ACP Spoofing Defense.
Proves that the ACP adapter does not create authoritative receipts or verification events directly.
"""

from sclass.integrations.acp.adapter import ACPAdapter


def test_invariant_5_acp_adapter_only_produces_requests(adv_workspace):
    """
    Invariant 5:
    ACP adapter normalizes tool calls into ActionRequests, never directly into
    ObservedReceipt or VerificationEvent objects.
    """
    adapter = ACPAdapter(workspace_dir=adv_workspace)

    msg = {
        "jsonrpc": "2.0",
        "id": "msg_001",
        "method": "tool/call",
        "params": {
            "name": "edit_file",
            "arguments": {"path": "main.py", "content": "print(1)"},
        },
    }

    event, req = adapter.normalize_message(msg)
    assert event is not None
    assert req is not None
    assert req.action == "edit_file"

    # Adapter never manufactures an ObservedReceipt
    assert not hasattr(adapter, "create_observed_receipt")
    assert not hasattr(adapter, "create_verification_event")
