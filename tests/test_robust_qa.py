import os
import sys
import json
import pytest
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from verifier import EvidenceVerifier, VerificationError
import runtime

# Valid mock PNG headers with unique tags in the first 4096 bytes
VALID_PNG_CONTENT_DESKTOP = b'\x89PNG\r\n\x1a\n' + b'desktop' + b'\x00' * 11000
VALID_PNG_CONTENT_MOBILE = b'\x89PNG\r\n\x1a\n' + b'mobile_' + b'\x00' * 11000

@pytest.fixture
def qa_workspace(tmp_path):
    workspace = str(tmp_path)
    runtime.initialize_state(workspace_dir=workspace)
    state_dir = os.path.join(workspace, ".agents")
    screenshots_dir = os.path.join(state_dir, "screenshots")
    os.makedirs(screenshots_dir, exist_ok=True)
    
    # Create frontend dir to activate strict checks
    os.makedirs(os.path.join(workspace, "frontend"), exist_ok=True)
    
    # Create valid desktop and mobile screenshots with distinct hashes
    with open(os.path.join(screenshots_dir, "dashboard_desktop.png"), "wb") as f:
        f.write(VALID_PNG_CONTENT_DESKTOP)
    with open(os.path.join(screenshots_dir, "dashboard_mobile.png"), "wb") as f:
        f.write(VALID_PNG_CONTENT_MOBILE)
        
    # Create clean console audit with real message count
    with open(os.path.join(state_dir, "console_audit.json"), "w", encoding="utf-8") as f:
        json.dump({"errorCount": 0, "totalMessageCount": 15, "errors": []}, f)
        
    # Create clean network audit with totalRequestCount
    with open(os.path.join(state_dir, "network_audit.json"), "w", encoding="utf-8") as f:
        json.dump({"failedCount": 0, "totalRequestCount": 20, "failedRequests": []}, f)
        
    # Create clean interaction receipts with multi-role, route protection redirect, and distinct URLs
    with open(os.path.join(state_dir, "interaction_receipts.json"), "w", encoding="utf-8") as f:
        json.dump({
            "interactions": [
                {
                    "action": "navigate",
                    "role": "student",
                    "url": "http://localhost:3000/dashboard",
                    "authAttempt": "unauthenticated",
                    "finalUrl": "http://localhost:3000/login",
                    "status": "200"
                },
                {
                    "action": "click",
                    "role": "student",
                    "url": "http://localhost:3000/dashboard",
                    "status": "200"
                },
                {
                    "action": "fill",
                    "role": "faculty",
                    "url": "http://localhost:3000/profile",
                    "status": "200"
                }
            ]
        }, f)
        
    # Create DOM snapshots
    snapshots_dir = os.path.join(state_dir, "snapshots")
    os.makedirs(snapshots_dir, exist_ok=True)
    with open(os.path.join(snapshots_dir, "dashboard_snapshot.txt"), "w", encoding="utf-8") as f:
        f.write("Fully clean dashboard layout showing metrics and visual graphs")

    # Create clean Lighthouse receipt
    with open(os.path.join(state_dir, "lighthouse_audit.json"), "w", encoding="utf-8") as f:
        json.dump({"accessibility": 95, "seo": 90, "best-practices": 95}, f)
        
    # Create clean User Flow Receipts
    with open(os.path.join(state_dir, "user_flow_receipts.json"), "w", encoding="utf-8") as f:
        json.dump({
            "flows": [
                {
                    "flow_id": "create_student_flow",
                    "input_rendered_on_screen": True,
                    "passed": True
                }
            ]
        }, f)

    return workspace, state_dir

def test_robust_qa_verification_success(qa_workspace):
    workspace, _ = qa_workspace
    res = EvidenceVerifier.verify_phase("QA", workspace_dir=workspace, allow_soft=False)
    assert res.passed is True
    assert len(res.errors) == 0

def test_robust_qa_fails_on_console_errors(qa_workspace):
    workspace, state_dir = qa_workspace
    
    with open(os.path.join(state_dir, "console_audit.json"), "w", encoding="utf-8") as f:
        json.dump({
            "errorCount": 1,
            "totalMessageCount": 15,
            "errors": [{"message": "Uncaught TypeError: Cannot read properties of undefined (reading 'map')"}]
        }, f)
        
    res = EvidenceVerifier.verify_phase("QA", workspace_dir=workspace, allow_soft=False)
    assert res.passed is False
    assert any("Browser Console Error detected" in err for err in res.errors)

def test_robust_qa_fails_on_network_errors(qa_workspace):
    workspace, state_dir = qa_workspace
    
    with open(os.path.join(state_dir, "network_audit.json"), "w", encoding="utf-8") as f:
        json.dump({
            "failedCount": 1,
            "failedRequests": [{"url": "http://localhost:3000/api/users", "status": 500}]
        }, f)
        
    res = EvidenceVerifier.verify_phase("QA", workspace_dir=workspace, allow_soft=False)
    assert res.passed is False
    assert any("Failed API Network Requests detected" in err for err in res.errors)

def test_robust_qa_fails_on_missing_mobile_viewport(qa_workspace):
    workspace, state_dir = qa_workspace
    
    mobile_ss = os.path.join(state_dir, "screenshots", "dashboard_mobile.png")
    if os.path.exists(mobile_ss):
        os.remove(mobile_ss)
        
    res = EvidenceVerifier.verify_phase("QA", workspace_dir=workspace, allow_soft=False)
    assert res.passed is False
    assert any("Missing mobile viewport test screenshot" in err for err in res.errors)

def test_robust_qa_fails_on_missing_route_protection_test(qa_workspace):
    workspace, state_dir = qa_workspace
    
    with open(os.path.join(state_dir, "interaction_receipts.json"), "w", encoding="utf-8") as f:
        json.dump({
            "interactions": [
                {
                    "action": "click",
                    "role": "student",
                    "url": "http://localhost:3000/dashboard",
                    "status": "200"
                },
                {
                    "action": "fill",
                    "role": "faculty",
                    "url": "http://localhost:3000/profile",
                    "status": "200"
                }
            ]
        }, f)
        
    res = EvidenceVerifier.verify_phase("QA", workspace_dir=workspace, allow_soft=False)
    assert res.passed is False
    assert any("Unauthenticated Route Protection test missing" in err for err in res.errors)

def test_robust_qa_fails_on_dom_sanity_defect(qa_workspace):
    workspace, state_dir = qa_workspace
    
    snapshots_dir = os.path.join(state_dir, "snapshots")
    with open(os.path.join(snapshots_dir, "dashboard_snapshot.txt"), "w", encoding="utf-8") as f:
        f.write("Some html output with undefined property value inside container")
        
    res = EvidenceVerifier.verify_phase("QA", workspace_dir=workspace, allow_soft=False)
    assert res.passed is False
    assert any("Rendered HTML/DOM Visual Fidelity error" in err for err in res.errors)

def test_robust_qa_fails_on_stale_screenshots(qa_workspace):
    workspace, state_dir = qa_workspace
    
    # Touch orchestration_state.json to make screenshots older than FSM session state
    state_file = os.path.join(state_dir, "orchestration_state.json")
    
    # Set screenshots to have been modified 10 minutes ago
    ten_mins_ago = time.time() - 600
    for ss in ["dashboard_desktop.png", "dashboard_mobile.png"]:
        os.utime(os.path.join(state_dir, "screenshots", ss), (ten_mins_ago, ten_mins_ago))
        
    # Touch state_file to current time
    os.utime(state_file, None)
    
    res = EvidenceVerifier.verify_phase("QA", workspace_dir=workspace, allow_soft=False)
    assert res.passed is False
    assert any("Stale screenshots from a previous build cycle detected" in err for err in res.errors)

def test_robust_qa_fails_on_missing_lighthouse_receipt(qa_workspace):
    workspace, state_dir = qa_workspace
    
    lh_file = os.path.join(state_dir, "lighthouse_audit.json")
    if os.path.exists(lh_file):
        os.remove(lh_file)
        
    res = EvidenceVerifier.verify_phase("QA", workspace_dir=workspace, allow_soft=False)
    assert res.passed is False
    assert any("Missing Lighthouse Audit Receipt" in err for err in res.errors)

def test_robust_qa_fails_on_low_lighthouse_score(qa_workspace):
    workspace, state_dir = qa_workspace
    
    # Set accessibility score to 40
    with open(os.path.join(state_dir, "lighthouse_audit.json"), "w", encoding="utf-8") as f:
        json.dump({"accessibility": 40}, f)
        
    res = EvidenceVerifier.verify_phase("QA", workspace_dir=workspace, allow_soft=False)
    assert res.passed is False
    assert any("Lighthouse Accessibility score too low" in err for err in res.errors)

def test_robust_qa_fails_on_fabricated_console_log(qa_workspace):
    workspace, state_dir = qa_workspace
    
    # Set totalMessageCount to 0
    with open(os.path.join(state_dir, "console_audit.json"), "w", encoding="utf-8") as f:
        json.dump({"errorCount": 0, "totalMessageCount": 0, "errors": []}, f)
        
    res = EvidenceVerifier.verify_phase("QA", workspace_dir=workspace, allow_soft=False)
    assert res.passed is False
    assert any("Fabricated console logs (totalMessageCount = 0) detected" in err for err in res.errors)

def test_robust_qa_fails_on_duplicate_screenshots(qa_workspace):
    workspace, state_dir = qa_workspace
    
    # Overwrite mobile screenshot with desktop screenshot content to simulate duplication
    with open(os.path.join(state_dir, "screenshots", "dashboard_mobile.png"), "wb") as f:
        f.write(VALID_PNG_CONTENT_DESKTOP)
        
    res = EvidenceVerifier.verify_phase("QA", workspace_dir=workspace, allow_soft=False)
    assert res.passed is False
    assert any("Identical/Duplicate screenshots found" in err for err in res.errors)

def test_robust_qa_fails_on_fabricated_network_logs(qa_workspace):
    workspace, state_dir = qa_workspace
    
    # Set totalRequestCount to 0
    with open(os.path.join(state_dir, "network_audit.json"), "w", encoding="utf-8") as f:
        json.dump({"failedCount": 0, "totalRequestCount": 0, "failedRequests": []}, f)
        
    res = EvidenceVerifier.verify_phase("QA", workspace_dir=workspace, allow_soft=False)
    assert res.passed is False
    assert any("Fabricated network logs (totalRequestCount = 0) detected" in err for err in res.errors)

def test_robust_qa_fails_on_invalid_receipt_schema(qa_workspace):
    workspace, state_dir = qa_workspace
    
    # Write invalid format to interaction receipts
    with open(os.path.join(state_dir, "interaction_receipts.json"), "w", encoding="utf-8") as f:
        f.write("{invalid json content}")
        
    res = EvidenceVerifier.verify_phase("QA", workspace_dir=workspace, allow_soft=False)
    assert res.passed is False
    assert any("Malformed interaction receipts file" in err for err in res.errors)
