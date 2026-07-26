#!/usr/bin/env python3
import os
import sys
import json
import uuid
import time
import logging
from datetime import datetime, timezone
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Optional, Any

# Local Paths configuration
PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
WORKFLOW_FILE = os.path.join(PLUGIN_DIR, "workflow.json")
EVENTS_FILE = os.path.join(PLUGIN_DIR, "events.json")
CAPABILITIES_FILE = os.path.join(PLUGIN_DIR, "capabilities.json")
SCHEMA_FILE = os.path.join(PLUGIN_DIR, "state_schema.json")

# Setup Logging
logger = logging.getLogger("sclass_runtime")

@dataclass
class Task:
    id: str
    owner: str
    targets: List[str]
    dependsOn: List[str]
    acceptanceCriteria: str
    priority: str
    status: str
    confidence: float = 1.0
    criticality: int = 5
    sandboxBranch: Optional[str] = None

@dataclass
class Decision:
    decision: str
    reason: str
    alternatives: List[str]
    confidence: float
    timestamp: str
    agent: str

@dataclass
class ConfidenceMatrix:
    weightedScore: float
    votes: Dict[str, float] = field(default_factory=dict)

@dataclass
class State:
    taskId: str
    currentPhase: str
    activeEvent: Optional[str]
    currentSpecVersion: int
    currentDebateVersion: int
    currentTaskVersion: int
    retryCount: int
    confidenceMatrix: ConfidenceMatrix
    workflowProfile: str = "full"
    planRationale: str = ""
    tasks: List[Task] = field(default_factory=list)
    decisionLog: List[Decision] = field(default_factory=list)
    transitionHistory: List[Dict[str, Any]] = field(default_factory=list)

def _process_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        try:
            import ctypes
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if handle:
                kernel32.CloseHandle(handle)
                return True
            return False
        except Exception:
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

class FileLock:
    def __init__(self, lock_path: str, timeout: float = 10.0):
        self.lock_path = lock_path
        self.timeout = timeout
        self.fd = None

    def __enter__(self):
        start_time = time.time()
        while True:
            try:
                self.fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(self.fd, str(os.getpid()).encode())
                break
            except FileExistsError:
                # Lock exists: audit PID for staleness
                try:
                    with open(self.lock_path, "r", encoding="utf-8") as f:
                        pid_str = f.read().strip()
                    if pid_str.isdigit():
                        pid = int(pid_str)
                        if not _process_exists(pid):
                            logger.warning(f"Stale lock detected for dead PID {pid}. Cleaning up lock file.")
                            try:
                                os.unlink(self.lock_path)
                            except OSError:
                                pass
                            continue
                except Exception:
                    pass

                if time.time() - start_time > self.timeout:
                    raise TimeoutError(f"Concurrency Lock Timeout: Failed to acquire {self.lock_path}")
                time.sleep(0.05)

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.fd is not None:
            try:
                os.close(self.fd)
            except OSError:
                pass
            try:
                os.unlink(self.lock_path)
            except OSError:
                pass

class ResourceAwareScheduler:
    """Resource-aware OS task scheduler checking concurrency limits before dispatch."""
    MAX_CONCURRENT_BUILDERS = 4

    @staticmethod
    def can_dispatch_task(active_builder_count: int) -> bool:
        return active_builder_count < ResourceAwareScheduler.MAX_CONCURRENT_BUILDERS


class ContextBudgetOptimizer:
    """Prunes LLM context payload to only required task target files and boundaries."""
    MAX_CONTEXT_FILES = 5

    @staticmethod
    def optimize_context(task_targets: List[str]) -> List[str]:
        return task_targets[:ContextBudgetOptimizer.MAX_CONTEXT_FILES]


def _resolve_paths(workspace_dir: Optional[str] = None) -> tuple:
    cwd = workspace_dir if workspace_dir else os.getcwd()
    state_dir = os.path.join(cwd, ".agents")
    state_file = os.path.join(state_dir, "orchestration_state.json")
    lock_file = os.path.join(state_dir, "state.lock")
    config_file = os.path.join(cwd, "sclass.config.json")
    return state_dir, state_file, lock_file, config_file

def load_json(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Required configuration file missing: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def write_json_atomic(path, data):
    tmp_path = path + ".tmp"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, path)

def _validate_schema_value(value: Any, schema: Dict[str, Any], path: str = ""):
    expected_type = schema.get("type")
    
    if isinstance(expected_type, list):
        valid = False
        for t in expected_type:
            try:
                _validate_schema_value(value, {"type": t}, path)
                valid = True
                break
            except TypeError:
                pass
        if not valid:
            raise TypeError(f"Type validation failed at '{path}': expected one of {expected_type}, got {type(value)}")
        return

    if expected_type == "null":
        if value is not None:
            raise TypeError(f"Type validation failed at '{path}': expected null, got {type(value)}")
    elif expected_type == "string":
        if not isinstance(value, str):
            raise TypeError(f"Type validation failed at '{path}': expected string, got {type(value)}")
    elif expected_type == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError(f"Type validation failed at '{path}': expected integer, got {type(value)}")
    elif expected_type == "number":
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise TypeError(f"Type validation failed at '{path}': expected number, got {type(value)}")
    elif expected_type == "array":
        if not isinstance(value, list):
            raise TypeError(f"Type validation failed at '{path}': expected array, got {type(value)}")
        items_schema = schema.get("items")
        if items_schema:
            for idx, item in enumerate(value):
                _validate_schema_value(item, items_schema, f"{path}[{idx}]")
    elif expected_type == "object":
        if not isinstance(value, dict):
            raise TypeError(f"Type validation failed at '{path}': expected object, got {type(value)}")
        properties = schema.get("properties", {})
        for prop_key, prop_val in value.items():
            if prop_key in properties:
                _validate_schema_value(prop_val, properties[prop_key], f"{path}.{prop_key}")

def validate_state_types(state_dict: Dict[str, Any]):
    schema = load_json(SCHEMA_FILE)
    _validate_schema_value(state_dict, schema)

def _execute_side_effects(state: State, side_effects: List[str]):
    for effect in side_effects:
        if effect == "incrementSpecVersion":
            state.currentSpecVersion += 1
        elif effect == "incrementTaskVersion":
            state.currentTaskVersion += 1
        elif effect == "incrementDebateVersion":
            state.currentDebateVersion += 1
        elif effect == "incrementRetryCount":
            state.retryCount += 1
        elif effect == "resetRetryCount":
            state.retryCount = 0

# === Public Library APIs ===

class MemoryManager:
    """Persistent learning memory with semantic search and shadow-first validation."""
    
    SCHEMA_VERSION = 2

    @staticmethod
    def get_memory_file(workspace_dir: Optional[str] = None) -> str:
        cwd = workspace_dir if workspace_dir else os.getcwd()
        return os.path.join(cwd, ".agents", "learning_memory.json")

    @staticmethod
    def _load_memory(workspace_dir: Optional[str] = None) -> Dict[str, Any]:
        memory_file = MemoryManager.get_memory_file(workspace_dir)
        default = {"version": MemoryManager.SCHEMA_VERSION, "fixes": []}
        if not os.path.exists(memory_file):
            return default
        try:
            with open(memory_file, "r", encoding="utf-8") as f:
                memory = json.load(f)
            # Auto-migrate v1 -> v2
            if "version" not in memory:
                memory["version"] = MemoryManager.SCHEMA_VERSION
            return memory
        except Exception as e:
            logger.error(f"Failed to read learning memory: {e}")
            return default

    @staticmethod
    def _save_memory(memory: Dict[str, Any], workspace_dir: Optional[str] = None) -> None:
        memory_file = MemoryManager.get_memory_file(workspace_dir)
        os.makedirs(os.path.dirname(memory_file), exist_ok=True)
        memory["version"] = MemoryManager.SCHEMA_VERSION
        write_json_atomic(memory_file, memory)

    @staticmethod
    def get_fix(error_msg: str, workspace_dir: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Exact substring match (legacy v1 behavior, kept for backward compat)."""
        memory = MemoryManager._load_memory(workspace_dir)
        for entry in memory.get("fixes", []):
            pattern = entry.get("pattern", "")
            if pattern and pattern.lower() in error_msg.lower():
                return entry
        return None

    @staticmethod
    def semantic_search(query: str, workspace_dir: Optional[str] = None, domain: Optional[str] = None, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search memory using TF-IDF cosine similarity with domain namespace isolation."""
        memory = MemoryManager._load_memory(workspace_dir)
        fixes = memory.get("fixes", [])
        if domain:
            fixes = [f for f in fixes if f.get("domain", "").lower() == domain.lower() or not f.get("domain")]
        if not fixes or not query.strip():
            return []
        
        # Build corpus from fix patterns + descriptions
        corpus_texts = []
        for fix in fixes:
            text = f"{fix.get('pattern', '')} {fix.get('fixDescription', '')}"
            corpus_texts.append(text)
        
        # Add query as the last document
        corpus_texts.append(query)
        
        try:
            # Lightweight TF-IDF with cosine similarity (no external API)
            # Using manual implementation to avoid hard scikit-learn dependency
            scores = MemoryManager._tfidf_cosine_scores(corpus_texts)
        except Exception as e:
            logger.error(f"Semantic search failed, falling back to substring: {e}")
            # Fallback to substring match
            result = MemoryManager.get_fix(query, workspace_dir)
            return [result] if result else []
        
        # Pair scores with fixes and sort descending
        scored_fixes = [(scores[i], fixes[i]) for i in range(len(fixes)) if scores[i] > 0.0]
        scored_fixes.sort(key=lambda x: x[0], reverse=True)
        
        return [fix for _, fix in scored_fixes[:top_k]]

    @staticmethod
    def _tfidf_cosine_scores(corpus: List[str]) -> List[float]:
        """Manual TF-IDF cosine similarity. Query is the last element in corpus."""
        import math
        from collections import Counter
        
        # Tokenize
        def tokenize(text: str) -> List[str]:
            return [w.lower().strip() for w in text.split() if len(w.strip()) > 1]
        
        tokenized = [tokenize(doc) for doc in corpus]
        
        # Build vocabulary
        vocab: Dict[str, int] = {}
        for tokens in tokenized:
            for token in set(tokens):
                vocab[token] = vocab.get(token, 0) + 1
        
        n_docs = len(corpus)
        
        # Compute TF-IDF vectors
        def tfidf_vector(tokens: List[str]) -> Dict[str, float]:
            tf = Counter(tokens)
            total = len(tokens) if tokens else 1
            vec: Dict[str, float] = {}
            for term, count in tf.items():
                tf_val = count / total
                df = vocab.get(term, 1)
                idf = math.log((n_docs + 1) / (df + 1)) + 1
                vec[term] = tf_val * idf
            return vec
        
        vectors = [tfidf_vector(t) for t in tokenized]
        query_vec = vectors[-1]  # Last is the query
        
        # Cosine similarity of each document vs query
        def cosine_sim(a: Dict[str, float], b: Dict[str, float]) -> float:
            common = set(a.keys()) & set(b.keys())
            if not common:
                return 0.0
            dot = sum(a[k] * b[k] for k in common)
            mag_a = math.sqrt(sum(v * v for v in a.values()))
            mag_b = math.sqrt(sum(v * v for v in b.values()))
            if mag_a == 0 or mag_b == 0:
                return 0.0
            return dot / (mag_a * mag_b)
        
        return [cosine_sim(vectors[i], query_vec) for i in range(len(corpus) - 1)]

    @staticmethod
    def learn_fix(pattern: str, fix_description: str, file_path: str, solution_code: str, workspace_dir: Optional[str] = None) -> None:
        """Record a new fix to the persistent learning memory."""
        memory = MemoryManager._load_memory(workspace_dir)
        
        # Prevent duplicates
        if not any(f.get("pattern") == pattern for f in memory.get("fixes", [])):
            memory.setdefault("fixes", []).append({
                "pattern": pattern,
                "fixDescription": fix_description,
                "filePath": file_path,
                "solutionCode": solution_code,
                "timestamp": datetime.now(timezone.utc).isoformat() + "Z"
            })
            MemoryManager._save_memory(memory, workspace_dir)
            logger.info(f"Learned new fix for pattern: {pattern}")

    @staticmethod
    def shadow_validate(pattern: str, proposed_fix: str, test_command: str = "python -m pytest", workspace_dir: Optional[str] = None) -> bool:
        """Shadow-first validation: only promote a fix if a test command exits 0.
        Returns True if the fix is safe to promote (tests pass), False otherwise.
        NOTE: This is a validation check only — it does NOT execute the fix.
        The caller is responsible for applying the fix before calling this."""
        import subprocess
        cwd = workspace_dir if workspace_dir else os.getcwd()
        try:
            result = subprocess.run(
                test_command.split(),
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=120
            )
            return result.returncode == 0
        except Exception as e:
            logger.warning(f"Shadow validation failed for '{pattern}': {e}")
            return False

def initialize_workspace_wizard(workspace_dir: Optional[str] = None) -> Dict[str, Any]:
    """Inspects the workspace and configures sclass.config.json automatically."""
    cwd = workspace_dir if workspace_dir else os.getcwd()
    _, _, _, config_file = _resolve_paths(workspace_dir)
    
    config = {
        "pipeline": "sclass-v5",
        "executionMode": "Closed Loop",
        "loopMode": "closed-loop",
        "projectType": "unknown",
        "topology": "hierarchical",
        "commands": {
            "devServer": "",
            "apiServer": "",
            "test": "",
            "dbMigration": ""
        }
    }
    
    # 1. Detect frontend Next.js / package.json
    frontend_path = os.path.join(cwd, "frontend")
    if os.path.exists(frontend_path) and os.path.exists(os.path.join(frontend_path, "package.json")):
        config["projectType"] = "full-stack-web"
        config["commands"]["devServer"] = "cd frontend && npm run dev"
        config["commands"]["test"] = "cd frontend && npm test"
    elif os.path.exists(os.path.join(cwd, "package.json")):
        config["projectType"] = "node-application"
        config["commands"]["devServer"] = "npm run dev"
        config["commands"]["test"] = "npm test"
        
    # 2. Detect backend FastAPI / Python
    backend_path = os.path.join(cwd, "backend")
    if os.path.exists(backend_path):
        is_full_stack = config["projectType"] == "full-stack-web"
        if config["projectType"] == "unknown":
            config["projectType"] = "python-backend"
        # Check uvicorn
        main_py = os.path.join(backend_path, "main.py")
        app_py = os.path.join(backend_path, "app.py")
        if os.path.exists(main_py):
            cmd = "python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"
        elif os.path.exists(app_py):
            cmd = "python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload"
        else:
            cmd = ""
            
        if cmd:
            if is_full_stack:
                config["commands"]["apiServer"] = cmd
            else:
                config["commands"]["devServer"] = cmd
            
        # Check pytest
        if os.path.exists(os.path.join(cwd, "tests")) or os.path.exists(os.path.join(backend_path, "tests")):
            config["commands"]["test"] = "python -m pytest"
            
        # Check migrations / prisma / alembic
        if os.path.exists(os.path.join(backend_path, "prisma")):
            config["commands"]["dbMigration"] = "npx prisma db push"
        elif os.path.exists(os.path.join(cwd, "alembic.ini")):
            config["commands"]["dbMigration"] = "alembic upgrade head"
            
    # Write config atomically
    write_json_atomic(config_file, config)
    logger.info(f"Workspace configuration generated automatically at {config_file}")
    return config

def initialize_state(workspace_dir: Optional[str] = None, goal: Optional[str] = None, profile: Optional[str] = None) -> None:
    """Initializes a new orchestration_state.json and generates a default sclass.config.json."""
    from planner import MetaPlanner, WorkflowProfile
    state_dir, state_file, lock_file, config_file = _resolve_paths(workspace_dir)
    os.makedirs(state_dir, exist_ok=True)
    
    # Auto-generate workspace config file if it doesn't exist
    if not os.path.exists(config_file):
        initialize_workspace_wizard(workspace_dir)
    
    # Classify goal into workflow plan if goal/profile provided
    plan = MetaPlanner.classify_goal(goal or "", profile)

    with FileLock(lock_file):
        if os.path.exists(state_file):
            return
        
        state_dict = {
            "taskId": str(uuid.uuid4()),
            "currentPhase": "TRIAGE",
            "activeEvent": None,
            "workflowProfile": plan.profile.value,
            "planRationale": plan.rationale,
            "currentSpecVersion": 1,
            "currentDebateVersion": 0,
            "currentTaskVersion": 0,
            "retryCount": 0,
            "confidenceMatrix": {
              "weightedScore": 0.0,
              "votes": {}
            },
            "tasks": [],
            "decisionLog": [
                {
                    "decision": f"Initialize S-Class FSM Engine ({plan.profile.value.upper()} Profile)",
                    "reason": plan.rationale,
                    "alternatives": [p.value for p in WorkflowProfile],
                    "confidence": 1.0,
                    "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
                    "agent": "meta_planner"
                }
            ],
            "transitionHistory": []
        }
        
        validate_state_types(state_dict)
        write_json_atomic(state_file, state_dict)

def get_state(workspace_dir: Optional[str] = None) -> State:
    """Loads and validates the current State dataclass object."""
    _, state_file, _, _ = _resolve_paths(workspace_dir)
    if not os.path.exists(state_file):
        raise FileNotFoundError("State file not initialized. Call initialize_state() first.")
    
    state_dict = load_json(state_file)
    validate_state_types(state_dict)
    
    tasks = [Task(**t) for t in state_dict.get("tasks", [])]
    decisions = [Decision(**d) for d in state_dict.get("decisionLog", [])]
    conf_matrix = ConfidenceMatrix(**state_dict["confidenceMatrix"])
    
    return State(
        taskId=state_dict["taskId"],
        currentPhase=state_dict["currentPhase"],
        activeEvent=state_dict["activeEvent"],
        workflowProfile=state_dict.get("workflowProfile", "full"),
        planRationale=state_dict.get("planRationale", ""),
        currentSpecVersion=state_dict["currentSpecVersion"],
        currentDebateVersion=state_dict["currentDebateVersion"],
        currentTaskVersion=state_dict["currentTaskVersion"],
        retryCount=state_dict["retryCount"],
        confidenceMatrix=conf_matrix,
        tasks=tasks,
        decisionLog=decisions,
        transitionHistory=state_dict.get("transitionHistory", [])
    )

def save_state(state: State, workspace_dir: Optional[str] = None) -> None:
    """Saves a State dataclass object back to orchestration_state.json atomically."""
    _, state_file, _, _ = _resolve_paths(workspace_dir)
    state_dict = asdict(state)
    validate_state_types(state_dict)
    write_json_atomic(state_file, state_dict)

def dispatch_event(event_name: str, workspace_dir: Optional[str] = None, enforce_evidence: bool = False) -> None:
    """Dispatches a transition event, updating FSM state and executing side effects."""
    from planner import MetaPlanner, WorkflowProfile
    from verifier import EvidenceVerifier, VerificationError
    from evaluation import SelfEvaluator, EvaluationAction
    from replay import TransitionRecord
    
    _, _, lock_file, config_file = _resolve_paths(workspace_dir)
    
    # Check if sclass.config.json enables strict evidence enforcement
    if not enforce_evidence and os.path.exists(config_file):
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            if cfg.get("enforceEvidence", False):
                enforce_evidence = True
        except Exception:
            pass

    with FileLock(lock_file):
        state = get_state(workspace_dir)
        raw_workflow = load_json(WORKFLOW_FILE)
        events = load_json(EVENTS_FILE)
        
        current_phase = state.currentPhase

        # 1. Evidence Verification Gate
        v_res = EvidenceVerifier.verify_phase(current_phase, workspace_dir, allow_soft=not enforce_evidence)
        if not v_res.passed:
            raise VerificationError(f"Cannot transition from state '{current_phase}': {'; '.join(v_res.errors)}")

        # 2. Continuous Self-Evaluation Gate
        weighted_conf = state.confidenceMatrix.weightedScore if state.confidenceMatrix else 1.0
        eval_res = SelfEvaluator.evaluate_phase(
            phase=current_phase,
            confidence_score=weighted_conf if weighted_conf > 0.0 else 1.0,
            retry_count=state.retryCount,
            current_profile=state.workflowProfile
        )

        if eval_res.action == EvaluationAction.PIVOT_PROFILE and eval_res.suggested_profile:
            logger.info(f"Self-Evaluation Pivoted profile: {state.workflowProfile} -> {eval_res.suggested_profile}")
            state.workflowProfile = eval_res.suggested_profile

        # Apply profile-specific transition overrides
        try:
            profile_enum = WorkflowProfile(state.workflowProfile)
        except ValueError:
            profile_enum = WorkflowProfile.FULL
            
        workflow = MetaPlanner.get_effective_workflow(raw_workflow, profile_enum)
        
        # Check event existence & load metadata
        event_meta = next((e for e in events if e["event"] == event_name), None)
        if not event_meta:
            raise ValueError(f"Event '{event_name}' is not registered in events.json")
            
        # Validate FSM State transition
        workflow_state = workflow["states"].get(current_phase, {})
        valid_transitions = workflow_state.get("transitions", {})
        
        if event_name not in valid_transitions:
            raise ValueError(f"Transition '{event_name}' is invalid from current state '{current_phase}' under '{state.workflowProfile}' profile")
            
        next_phase = valid_transitions[event_name]
        
        # Apply transition
        state.currentPhase = next_phase
        state.activeEvent = event_name
        
        # Execute side-effects
        side_effects = event_meta.get("sideEffects", [])
        _execute_side_effects(state, side_effects)
        
        ts_now = datetime.now(timezone.utc).isoformat() + "Z"

        # Log Decision Transition
        dec_entry = Decision(
            decision=f"Transition State to {next_phase}",
            reason=f"Fired event '{event_name}' from state '{current_phase}'",
            alternatives=list(valid_transitions.keys()),
            confidence=1.0,
            timestamp=ts_now,
            agent="state_manager_runtime"
        )
        state.decisionLog.append(dec_entry)

        # Guarantee #6: Record Immutable Transition Record for Deterministic Replay
        t_rec = TransitionRecord(
            stepIndex=len(state.transitionHistory) + 1,
            fromState=current_phase,
            toState=next_phase,
            eventFired=event_name,
            workflowProfile=state.workflowProfile,
            evidenceVerified=[asdict(art) for art in v_res.artifacts],
            decision=asdict(dec_entry),
            timestamp=ts_now,
            agent="state_manager_runtime"
        )
        state.transitionHistory.append(t_rec.to_dict())
        
        save_state(state, workspace_dir)

def reset_to_triage(workspace_dir: Optional[str] = None, new_goal: Optional[str] = None) -> None:
    """Resets the FSM state back to TRIAGE when user modifies requirements mid-flight."""
    from planner import MetaPlanner, WorkflowProfile
    from replay import TransitionRecord
    _, _, lock_file, _ = _resolve_paths(workspace_dir)
    
    with FileLock(lock_file):
        state = get_state(workspace_dir)
        old_phase = state.currentPhase
        
        # Classify new goal strategy if provided
        if new_goal:
            plan = MetaPlanner.classify_goal(new_goal)
            state.workflowProfile = plan.profile.value
            state.planRationale = plan.rationale
            
        state.currentPhase = "TRIAGE"
        state.activeEvent = "cancellation_requested"
        state.retryCount = 0
        
        ts_now = datetime.now(timezone.utc).isoformat() + "Z"
        
        dec_entry = Decision(
            decision="Reset FSM Workflow to TRIAGE",
            reason=f"User modified requirements mid-flight from state '{old_phase}'. Restarting strategy & planning.",
            alternatives=["continue_current_workflow"],
            confidence=1.0,
            timestamp=ts_now,
            agent="meta_planner"
        )
        state.decisionLog.append(dec_entry)
        
        t_rec = TransitionRecord(
            stepIndex=len(state.transitionHistory) + 1,
            fromState=old_phase,
            toState="TRIAGE",
            eventFired="cancellation_requested",
            workflowProfile=state.workflowProfile,
            evidenceVerified=[],
            decision=asdict(dec_entry),
            timestamp=ts_now,
            agent="meta_planner"
        )
        state.transitionHistory.append(t_rec.to_dict())
        
        save_state(state, workspace_dir)
        logger.info(f"FSM Reset: Requirements modified mid-flight in state '{old_phase}'. Workflow reset to TRIAGE.")

def update_task(task_id: str, status: str, workspace_dir: Optional[str] = None) -> None:
    """Updates the status of a specific task in the queue."""
    _, _, lock_file, _ = _resolve_paths(workspace_dir)
    
    with FileLock(lock_file):
        state = get_state(workspace_dir)
        task = next((t for t in state.tasks if t.id == task_id), None)
        if not task:
            raise KeyError(f"Task '{task_id}' not found.")
            
        task.status = status
        
        # Verify dependencies
        if status == "IN_PROGRESS":
            for dep in task.dependsOn:
                dep_task = next((t for t in state.tasks if t.id == dep), None)
                if dep_task and dep_task.status != "COMPLETED":
                    logger.warning(f"Dependency task '{dep}' status is '{dep_task.status}' (expected COMPLETED).")
                    
        save_state(state, workspace_dir)

def get_capabilities(agent_name: str) -> Dict[str, bool]:
    """Returns the capability permissions for a specified agent."""
    caps = load_json(CAPABILITIES_FILE)
    agent_caps = caps.get(agent_name)
    if not agent_caps:
        raise KeyError(f"Agent '{agent_name}' is not registered in capabilities.json")
    return agent_caps

def log_decision(decision: str, reason: str, agent: str, confidence: float, alts: Optional[List[str]] = None, workspace_dir: Optional[str] = None) -> None:
    """Appends a durable decision log entry."""
    _, _, lock_file, _ = _resolve_paths(workspace_dir)
    alts_list = alts if alts else []
    
    with FileLock(lock_file):
        state = get_state(workspace_dir)
        state.decisionLog.append(Decision(
            decision=decision,
            reason=reason,
            alternatives=alts_list,
            confidence=float(confidence),
            timestamp=datetime.now(timezone.utc).isoformat() + "Z",
            agent=agent
        ))
        save_state(state, workspace_dir)
