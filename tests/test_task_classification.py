import os
import json
import pytest
import tempfile
import shutil
from task_classifier import TaskClassifier, TaskDomain, TaskClassification
from spec_synthesis import SpecSynthesisEngine
from verifier import EvidenceVerifier, VerificationError
import runtime

def test_task_classification_domains():
    algo = TaskClassifier.classify("implement a rate limiter using a sliding window algorithm")
    assert algo.domain == TaskDomain.ALGORITHM
    assert algo.requires_frontend_ui is False
    assert algo.requires_visual_qa is False
    assert algo.primary_verification == "unit_tests"

    cli = TaskClassifier.classify("build a CLI command line tool to parse log files")
    assert cli.domain == TaskDomain.CLI
    assert cli.requires_frontend_ui is False
    assert cli.requires_visual_qa is False

    lib = TaskClassifier.classify("create a python math calculation library")
    assert lib.domain == TaskDomain.LIBRARY
    assert lib.requires_frontend_ui is False
    assert lib.requires_visual_qa is False

    web = TaskClassifier.classify("build an e-commerce dashboard with shopping cart and checkout")
    assert web.domain in [TaskDomain.FULLSTACK, TaskDomain.FRONTEND]
    assert web.requires_frontend_ui is True
    assert web.requires_visual_qa is True

def test_spec_synthesis_algorithm_scoping():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = SpecSynthesisEngine()
        spec = engine.run_synthesis("implement a rate limiter using a sliding window algorithm", workspace_dir=tmpdir)
        
        # Must produce domain-focused algorithmic requirements, NOT 400+ CRUD components
        all_reqs = []
        for req_list in spec.requirements.values():
            if isinstance(req_list, list):
                all_reqs.extend(req_list)
        
        assert 3 <= len(all_reqs) <= 10
        # Check that page spreads are empty
        assert spec.page_spreads == {}
        # Check that archetypes are non-web
        assert spec.archetypes == ["library"]
        # Check out of scope
        assert any("Frontend web pages" in o for o in spec.scope_boundaries.get("out_of_scope", []))

def test_verifier_adaptive_qa_backend_success():
    with tempfile.TemporaryDirectory() as tmpdir:
        state_dir = os.path.join(tmpdir, ".agents")
        os.makedirs(state_dir, exist_ok=True)

        # Set up state with requiresFrontendUi=False
        state_data = {
            "taskId": "task-test-algo",
            "currentPhase": "QA",
            "activeEvent": None,
            "workflowProfile": "core",
            "taskDomain": "algorithm",
            "requiresFrontendUi": False,
            "planRationale": "test",
            "goal": "implement a rate limiter using a sliding window algorithm",
            "currentSpecVersion": 1,
            "currentDebateVersion": 0,
            "currentTaskVersion": 0,
            "retryCount": 0,
            "confidenceMatrix": {"weightedScore": 1.0, "votes": {}},
            "tasks": [],
            "decisionLog": [],
            "transitionHistory": []
        }
        with open(os.path.join(state_dir, "orchestration_state.json"), "w", encoding="utf-8") as f:
            json.dump(state_data, f)

        # Write valid qa_report.json
        with open(os.path.join(state_dir, "qa_report.json"), "w", encoding="utf-8") as f:
            json.dump({
                "overall_passed": True,
                "total_tests": 10,
                "passed_tests": 10,
                "failed_tests": 0,
                "assertions_verified": 25,
                "task_domain": "ALGORITHM"
            }, f)

        # Write test file with real assertion
        tests_dir = os.path.join(tmpdir, "tests")
        os.makedirs(tests_dir, exist_ok=True)
        with open(os.path.join(tests_dir, "test_limiter.py"), "w", encoding="utf-8") as f:
            f.write("def test_window():\n    assert True\n")

        # QA phase must pass without any screenshot receipts!
        v = EvidenceVerifier()
        receipt = v.verify_phase("QA", workspace_dir=tmpdir, allow_soft=False)
        assert receipt.phase == "QA"
        assert receipt.passed is True
        assert len(receipt.errors) == 0

def test_verifier_strict_qa_web_fails_without_screenshots():
    with tempfile.TemporaryDirectory() as tmpdir:
        state_dir = os.path.join(tmpdir, ".agents")
        os.makedirs(state_dir, exist_ok=True)

        # Set up state with requiresFrontendUi=True
        state_data = {
            "taskId": "task-test-web",
            "currentPhase": "QA",
            "activeEvent": None,
            "workflowProfile": "full",
            "taskDomain": "fullstack",
            "requiresFrontendUi": True,
            "planRationale": "test",
            "goal": "build an e-commerce dashboard with login",
            "currentSpecVersion": 1,
            "currentDebateVersion": 0,
            "currentTaskVersion": 0,
            "retryCount": 0,
            "confidenceMatrix": {"weightedScore": 1.0, "votes": {}},
            "tasks": [],
            "decisionLog": [],
            "transitionHistory": []
        }
        with open(os.path.join(state_dir, "orchestration_state.json"), "w", encoding="utf-8") as f:
            json.dump(state_data, f)

        # Create frontend dir to simulate web project
        os.makedirs(os.path.join(tmpdir, "frontend"), exist_ok=True)

        v = EvidenceVerifier()
        receipt = v.verify_phase("QA", workspace_dir=tmpdir, allow_soft=False)
        assert receipt.passed is False
        assert any("QA verification failed" in err for err in receipt.errors)
        assert any("visual screenshot receipts missing" in err for err in receipt.errors)

        with pytest.raises(VerificationError) as exc_info:
            runtime.dispatch_event("qa_passed", workspace_dir=tmpdir, enforce_evidence=True)
        assert "QA verification failed" in str(exc_info.value)

def test_verifier_design_phase_adaptive():
    with tempfile.TemporaryDirectory() as tmpdir:
        state_dir = os.path.join(tmpdir, ".agents")
        os.makedirs(state_dir, exist_ok=True)

        # Non-UI state
        state_data = {
            "taskId": "task-test-design",
            "currentPhase": "DESIGN",
            "activeEvent": None,
            "workflowProfile": "core",
            "taskDomain": "algorithm",
            "requiresFrontendUi": False,
            "planRationale": "test",
            "goal": "implement a rate limiter using a sliding window algorithm",
            "currentSpecVersion": 1,
            "currentDebateVersion": 0,
            "currentTaskVersion": 0,
            "retryCount": 0,
            "confidenceMatrix": {"weightedScore": 1.0, "votes": {}},
            "tasks": [],
            "decisionLog": [],
            "transitionHistory": []
        }
        with open(os.path.join(state_dir, "orchestration_state.json"), "w", encoding="utf-8") as f:
            json.dump(state_data, f)

        # design_blueprint with algorithm_spec (no db_schema or frontend_layout)
        with open(os.path.join(state_dir, "design_blueprint.json"), "w", encoding="utf-8") as f:
            json.dump({
                "phase": "DESIGN",
                "blueprint_status": "APPROVED",
                "algorithm_spec": {
                    "algorithm": "Sliding Window",
                    "time_complexity": "O(1)"
                }
            }, f)

        # grill_report
        with open(os.path.join(state_dir, "grill_report.json"), "w", encoding="utf-8") as f:
            json.dump({"overall_passed": True, "critical_defects_found": 0}, f)

        # DESIGN phase must pass without role_interaction_matrix.json or frontend_layout!
        v = EvidenceVerifier()
        receipt = v.verify_phase("DESIGN", workspace_dir=tmpdir)
        assert receipt.phase == "DESIGN"

def test_runtime_initialization_algorithm_domain():
    with tempfile.TemporaryDirectory() as tmpdir:
        runtime.initialize_state(
            goal="implement a rate limiter using a sliding window algorithm",
            workspace_dir=tmpdir
        )
        st = runtime.get_state(workspace_dir=tmpdir)
        assert st.taskDomain == "algorithm"
        assert st.requiresFrontendUi is False

def test_fsm_goal_sequence_algorithm_reaches_done():
    with tempfile.TemporaryDirectory() as tmpdir:
        runtime.initialize_state(
            tmpdir,
            goal="implement a rate limiter using a sliding window algorithm",
            profile="full"
        )
        
        history = runtime.FSMGoalSequenceRunner.run_full_sequence(tmpdir, max_steps=25)
        assert len(history) > 0
        final_st = runtime.get_state(workspace_dir=tmpdir)
        assert final_st.currentPhase == "DONE"
        assert final_st.taskDomain == "algorithm"
        assert final_st.requiresFrontendUi is False
