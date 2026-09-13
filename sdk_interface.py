"""
S-Class V12: Unified Public SDK & Embeddable Orchestration System (EoS) Contract
(sdk_interface.py)

Authoritative unified SDK wrapping all microkernel, Knowledge Graph, SDD,
guardrail, and cross-platform projection subsystems into a single programmatic interface.
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List

import runtime
from codebase_graph_db import CodebaseGraphDB
from ast_graph_extractor import ASTGraphExtractor
from graph_traversal import GraphTraversalEngine
from graph_rag import GraphRAGEngine
from skill_auto_loader import SkillAutoLoader, SkillDefinition
from rule_generator import PlatformRuleGenerator
from session_handoff import SessionHandoffEngine
from staleness_cascade import StalenessCascadeEngine
from codebase_kg_server import CodebaseKGServer
from sdd_pipeline import SDDPipeline
from delta_spec_manager import DeltaSpecManager
from artifact_dag import ArtifactDAG
from package_verifier import PackageVerifier
from secret_scanner import SecretScanner
from context_budget import ContextBudgetMonitor
from steering import SteeringEngine
from promise_protocol import PromiseProtocol
from resilience import ActionResilienceEngine
from observability import LocalAuditLogger
from app_quality_verifier import AppQualityVerifier
from accessibility_auditor import AccessibilityAuditor
from worktree_manager import WorktreeManager
from git_automation import GitAutomation

logger = logging.getLogger("sclass_sdk")


class SClassSDK:
    """
    Unified Public SDK for S-Class V12.
    Embeddable Orchestration System (EoS) for external AI coding agents.
    """

    def __init__(self, workspace_dir: Optional[str] = None):
        self.workspace_dir = os.path.abspath(workspace_dir or os.environ.get("SCLASS_WORKSPACE") or os.getcwd())
        os.environ["SCLASS_WORKSPACE"] = self.workspace_dir
        self.graph_db = CodebaseGraphDB(workspace_dir=self.workspace_dir)
        self.extractor = ASTGraphExtractor(graph_db=self.graph_db, workspace_dir=self.workspace_dir)
        self.traversal = GraphTraversalEngine(graph_db=self.graph_db)
        self.rag = GraphRAGEngine(graph_db=self.graph_db, traversal_engine=self.traversal)
        self.skill_loader = SkillAutoLoader(workspace_dir=self.workspace_dir)
        self.rule_gen = PlatformRuleGenerator(workspace_dir=self.workspace_dir, graph_db=self.graph_db)
        self.handoff_engine = SessionHandoffEngine(workspace_dir=self.workspace_dir, graph_db=self.graph_db)
        self.cascade = StalenessCascadeEngine(workspace_dir=self.workspace_dir, graph_db=self.graph_db)
        self.kg_server = CodebaseKGServer(workspace_dir=self.workspace_dir)
        self.resilience = ActionResilienceEngine()
        self.worktrees = WorktreeManager(repo_dir=self.workspace_dir)

    # 1. Microkernel & FSM Control
    def initialize_workspace(self, goal: str, profile: str = "full") -> Dict[str, Any]:
        """Initializes S-Class FSM state in the workspace."""
        runtime.initialize_state(self.workspace_dir, goal=goal, profile=profile)
        return self.get_fsm_state()

    def advance_phase(self) -> Dict[str, Any]:
        """Advances FSM state 1 step forward in the canonical sequence."""
        return runtime.FSMGoalSequenceRunner.advance_one_state(self.workspace_dir)

    def get_fsm_state(self) -> Dict[str, Any]:
        """Retrieves active FSM state."""
        try:
            state = runtime.get_state(self.workspace_dir)
            return {
                "initialized": True,
                "workspace": self.workspace_dir,
                "currentPhase": state.currentPhase,
                "goal": state.goal,
                "workflowProfile": state.workflowProfile,
                "tasksCount": len(state.tasks),
                "transitionCount": len(state.transitionHistory),
            }
        except (FileNotFoundError, Exception):
            return {
                "initialized": False,
                "workspace": self.workspace_dir,
                "currentPhase": "UNINITIALIZED",
                "goal": "",
                "workflowProfile": "unknown",
                "tasksCount": 0,
                "transitionCount": 0,
            }

    # 2. Knowledge Graph Operations
    def index_codebase(self, force_reindex: bool = False) -> Dict[str, Any]:
        """Indexes workspace files into the zero-infra SQLite Knowledge Graph."""
        return self.extractor.index_workspace(force_reindex=force_reindex)

    def query_graph(self, pattern: str = "", node_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Queries graph nodes."""
        res = self.kg_server.tool_graph_query(pattern=pattern, node_type=node_type)
        return res.get("nodes", [])

    def get_blast_radius(self, node_id: str, max_hops: int = 3) -> Dict[str, Any]:
        """Calculates blast radius and risk score for an entity."""
        return self.traversal.blast_radius(node_id, max_hops=max_hops)

    def semantic_search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Performs semantic vector search over codebase entities."""
        return self.rag.semantic_search(query, top_k=top_k)

    # 3. Dynamic Skills & Rule Projections
    def get_active_skills(self, current_phase: Optional[str] = None) -> List[SkillDefinition]:
        """Detects active skills matching current phase and workspace."""
        phase = current_phase or self.get_fsm_state().get("currentPhase")
        return self.skill_loader.detect_active_skills(current_phase=phase)

    def project_rules(self) -> Dict[str, str]:
        """Projects rules to Cursor, Claude Code, Codex CLI, and Gemini."""
        return self.rule_gen.generate_all_projections()

    # 4. Session Handoff & Staleness
    def create_session_handoff(self) -> Dict[str, Any]:
        """Serializes session handoff manifest and updates CONTINUE_HERE.md."""
        return self.handoff_engine.create_handoff_manifest()

    def invalidate_file(self, file_path: str) -> Dict[str, Any]:
        """Marks dependent claims STALE following a file edit."""
        return self.cascade.invalidate_for_file(file_path)

    # 5. Spec-Driven Development
    def create_sdd_pipeline(self, spec_id: str, version: str = "1.0.0") -> SDDPipeline:
        """Instantiates a new Spec-Driven Development pipeline."""
        return SDDPipeline(spec_id=spec_id, version=version)

    # 6. Multi-Tier Verification & Guardrails
    def verify_dom(self, html_content: str) -> Dict[str, Any]:
        """Audits DOM for blank screen, corruption tokens, and errors."""
        return AppQualityVerifier.verify_dom_html(html_content)

    def audit_accessibility(self, html_content: str) -> Dict[str, Any]:
        """Audits DOM for WCAG 2.1 AA compliance."""
        return AccessibilityAuditor.audit_html(html_content)

    def verify_package(self, package_name: str, ecosystem: str = "pypi") -> Dict[str, Any]:
        """Checks package legitimacy to block slopsquatting."""
        if ecosystem.lower() == "npm":
            return PackageVerifier.verify_npm_package(package_name)
        return PackageVerifier.verify_pypi_package(package_name)

    def scan_secrets(self, content: str) -> Dict[str, Any]:
        """Audits content for leaked API keys or credentials."""
        return SecretScanner.scan_text(content)

    def evaluate_token_budget(self, used_tokens: int) -> Dict[str, Any]:
        """Evaluates token window capacity and saturation levels."""
        return ContextBudgetMonitor.evaluate_budget(used_tokens=used_tokens)

    def read_steering(self) -> Optional[Dict[str, Any]]:
        """Reads active operator steering directives from STEERING.md."""
        return SteeringEngine.read_steering_directive(workspace_dir=self.workspace_dir)

    def parse_promise(self, text: str) -> List[Dict[str, Any]]:
        """Parses completion promise tags."""
        return PromiseProtocol.parse_promise_tags(text)

    def log_audit(self, event_type: str, message: str, payload: Optional[Dict] = None) -> Dict[str, Any]:
        """Records an entry in the local JSONL audit trace."""
        return LocalAuditLogger.log_event(event_type, message, payload, workspace_dir=self.workspace_dir)

    # 7. High-Level Slash Command Execution (/goal, /boost, /learn)
    def _audit_execution_provenance(self) -> Dict[str, Any]:
        """
        Epistemic Integrity Audit:
        Inspects whether the run relied on synthetic receipts (FSM_TEST_RUNNER / simulation mode)
        and whether actual production source code was generated on disk.
        Surfaces honest epistemic metadata to the top-level response.
        """
        qa_file = os.path.join(self.workspace_dir, ".agents", "qa_report.json")
        is_synthetic = False
        authority = "AGENT_VERIFIED"
        execution_mode = os.getenv("SCLASS_EXECUTION_MODE", "PRODUCTION")

        if os.path.exists(qa_file):
            try:
                qa_data = runtime.load_json(qa_file)
                prov = qa_data.get("provenance_metadata", {})
                if prov.get("synthetic") or prov.get("authority") == "FSM_TEST_RUNNER":
                    is_synthetic = True
                    authority = prov.get("authority", "FSM_TEST_RUNNER")
                    execution_mode = prov.get("mode", execution_mode)
            except Exception:
                pass
        elif execution_mode in ("TEST", "SIMULATION"):
            is_synthetic = True
            authority = "FSM_TEST_RUNNER"

        # Check for real source code files on disk (excluding metadata/scaffolding dirs)
        EXCLUDE_DIRS = {".agents", ".git", ".cursor", ".claude", "__pycache__", "node_modules", ".venv", "scratch"}
        source_files = []
        try:
            for root, dirs, files in os.walk(self.workspace_dir):
                dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
                for f in files:
                    ext = os.path.splitext(f)[1].lower()
                    if ext in (".py", ".ts", ".js", ".tsx", ".jsx", ".go", ".rs", ".java", ".c", ".cpp", ".cs", ".rb") and not f.startswith("test_"):
                        source_files.append(os.path.relpath(os.path.join(root, f), self.workspace_dir))
        except Exception:
            pass

        has_code = len(source_files) > 0
        warning = None

        if is_synthetic and not has_code:
            warning = (
                "EPISTEMIC CAVEAT: S-Class executed in SYNTHETIC SIMULATION mode (Authority: FSM_TEST_RUNNER). "
                "Architectural specifications and state transitions succeeded, but NO live coding agent credentials "
                "were attached, so NO production source code was written to disk."
            )
        elif is_synthetic:
            warning = (
                "EPISTEMIC CAVEAT: Source code was generated, but QA verification was performed using SYNTHETIC "
                "receipts under authority 'FSM_TEST_RUNNER'."
            )

        complexity_dec = ""
        complexity_tier = ""
        try:
            st = runtime.get_state(self.workspace_dir)
            complexity_dec = getattr(st, "complexityDecision", "")
            complexity_tier = getattr(st, "complexityTier", "")
        except Exception:
            pass

        return {
            "synthetic": is_synthetic,
            "authority": authority,
            "execution_mode": execution_mode,
            "code_generated": has_code,
            "source_files": source_files,
            "epistemic_warning": warning,
            "complexity_decision": complexity_dec,
            "complexity_tier": complexity_tier
        }

    def execute_goal(self, goal: str, profile: str = "full", max_steps: int = 25) -> Dict[str, Any]:
        """
        Executes autonomous /goal workflow:
        Initializes state with goal, projects rules, and runs sequence towards convergence.
        """
        self.initialize_workspace(goal=goal, profile=profile)
        self.project_rules()
        history = runtime.FSMGoalSequenceRunner.run_full_sequence(self.workspace_dir, max_steps=max_steps)
        curr = runtime.get_state(self.workspace_dir)
        self.create_session_handoff()

        prov = self._audit_execution_provenance()
        if curr.currentPhase == "DONE":
            if prov["synthetic"] and not prov["code_generated"]:
                status = "SIMULATED"
            elif prov["synthetic"]:
                status = "COMPLETED_SYNTHETIC"
            else:
                status = "COMPLETED"
        else:
            status = "IN_PROGRESS"

        complexity_dec = getattr(curr, "complexityDecision", "")
        complexity_tier = getattr(curr, "complexityTier", "")
        if not complexity_dec:
            try:
                from task_classifier import TaskClassifier
                tc = TaskClassifier.classify(curr.goal or goal, workspace_dir=self.workspace_dir)
                complexity_dec = tc.complexity_decision
                complexity_tier = tc.complexity_tier.value
            except Exception:
                pass

        res = {
            "mode": "goal",
            "workspace": self.workspace_dir,
            "status": status,
            "current_phase": curr.currentPhase,
            "goal": curr.goal,
            "complexity_tier": complexity_tier,
            "complexity_decision": complexity_dec,
            "synthetic": prov["synthetic"],
            "authority": prov["authority"],
            "execution_mode": prov["execution_mode"],
            "code_generated": prov["code_generated"],
            "source_files": prov["source_files"],
            "provenance": prov,
            "steps_executed": len(history),
            "history": history,
        }
        if prov["epistemic_warning"]:
            res["epistemic_warning"] = prov["epistemic_warning"]
        return res

    def execute_boost(self, goal_or_task: str, max_steps: int = 25) -> Dict[str, Any]:
        """
        Executes high-velocity /boost workflow:
        Optimizes execution profile, primes CKG indexing, engages full 8-subagent parallel swarm,
        and accelerates goal convergence.
        """
        index_res = self.index_codebase(force_reindex=False)
        self.initialize_workspace(goal=goal_or_task, profile="fast")
        self.project_rules()
        skills = self.get_active_skills()
        history = runtime.FSMGoalSequenceRunner.run_full_sequence(self.workspace_dir, max_steps=max_steps)
        curr = runtime.get_state(self.workspace_dir)
        self.create_session_handoff()

        prov = self._audit_execution_provenance()
        if curr.currentPhase == "DONE":
            if prov["synthetic"] and not prov["code_generated"]:
                status = "SIMULATED"
            elif prov["synthetic"]:
                status = "COMPLETED_SYNTHETIC"
            else:
                status = "COMPLETED"
        else:
            status = "IN_PROGRESS"

        complexity_dec = getattr(curr, "complexityDecision", "")
        complexity_tier = getattr(curr, "complexityTier", "")
        if not complexity_dec:
            try:
                from task_classifier import TaskClassifier
                tc = TaskClassifier.classify(curr.goal or goal_or_task, workspace_dir=self.workspace_dir)
                complexity_dec = tc.complexity_decision
                complexity_tier = tc.complexity_tier.value
            except Exception:
                pass

        res = {
            "mode": "boost",
            "workspace": self.workspace_dir,
            "status": status,
            "current_phase": curr.currentPhase,
            "goal": curr.goal,
            "complexity_tier": complexity_tier,
            "complexity_decision": complexity_dec,
            "skills_loaded": [s.name for s in skills],
            "nodes_indexed": index_res.get("nodes_indexed", 0),
            "synthetic": prov["synthetic"],
            "authority": prov["authority"],
            "execution_mode": prov["execution_mode"],
            "code_generated": prov["code_generated"],
            "source_files": prov["source_files"],
            "provenance": prov,
            "steps_executed": len(history),
            "history": history,
        }
        if prov["epistemic_warning"]:
            res["epistemic_warning"] = prov["epistemic_warning"]
        return res

    def execute_learn(
        self,
        pattern: Optional[str] = None,
        fix_description: Optional[str] = None,
        file_path: Optional[str] = None,
        solution_code: Optional[str] = None,
        promote_candidates: bool = True,
    ) -> Dict[str, Any]:
        """
        Executes automated /learn workflow:
        Captures bug fix patterns and architectural lessons into learning memory,
        promotes approved candidates into the Knowledge Base, and updates CKG.
        """
        from learning_engine import LearningEngine
        learned_record = None

        if pattern and fix_description:
            runtime.MemoryManager.learn_fix(
                pattern=pattern,
                fix_description=fix_description,
                file_path=file_path or "",
                solution_code=solution_code or "",
                workspace_dir=self.workspace_dir,
            )
            cand = LearningEngine.capture_candidate(
                category="architecture_patterns",
                title=f"Learned pattern: {pattern}",
                content=fix_description,
                tags=["learned", "fix"],
                confidence_score=0.95,
                workspace_dir=self.workspace_dir,
            )
            if promote_candidates and cand:
                LearningEngine.promote_candidate(cand.candidate_id, workspace_dir=self.workspace_dir)
            learned_record = {"pattern": pattern, "fix": fix_description}

        mem_file = os.path.join(self.workspace_dir, ".agents", "learning_memory.json")
        rules_list = []
        if os.path.exists(mem_file):
            try:
                with open(mem_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        rules_list = list(data.values())
                    elif isinstance(data, list):
                        rules_list = data
            except Exception:
                pass

        return {
            "mode": "learn",
            "workspace": self.workspace_dir,
            "learned_record": learned_record,
            "total_learned_rules": len(rules_list),
            "recent_rules": rules_list[-5:],
        }

    def execute_slash_command(self, command_str: str) -> Dict[str, Any]:
        """Universal parser and router for slash commands: /goal, /boost, /learn, /status, /advance, /grill, /doubt, /inquire."""
        cmd_clean = command_str.strip()
        parts = cmd_clean.split(maxsplit=1)
        verb = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if verb == "/goal":
            return self.execute_goal(goal=arg or "Autonomous Objective")
        elif verb == "/boost":
            return self.execute_boost(goal_or_task=arg or "Accelerated Task")
        elif verb == "/learn":
            return self.execute_learn(pattern=arg or None, fix_description="Automated learning capture" if arg else None)
        elif verb == "/status":
            return self.get_fsm_state()
        elif verb == "/advance":
            return self.advance_phase()
        elif verb == "/grill":
            from sclass_grill import SpecGrillerEngine
            from dataclasses import asdict
            report = SpecGrillerEngine.grill_specification(workspace_dir=self.workspace_dir)
            return asdict(report)
        elif verb in ("/doubt", "/inquire"):
            query = arg or ""
            nodes = self.query_graph(pattern=query)
            return {
                "query": query,
                "matching_symbols_count": len(nodes),
                "symbols": nodes[:10],
            }
        else:
            return {"error": f"Unknown slash command: '{verb}'. Supported: /goal, /boost, /learn, /status, /advance, /grill, /doubt, /inquire"}

