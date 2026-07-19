#!/usr/bin/env python3
import os
import sys
import json
import uuid
import time
import logging
import argparse
from datetime import datetime
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Optional, Any

# Local Paths configuration
PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
WORKFLOW_FILE = os.path.join(PLUGIN_DIR, "workflow.json")
EVENTS_FILE = os.path.join(PLUGIN_DIR, "events.json")
CAPABILITIES_FILE = os.path.join(PLUGIN_DIR, "capabilities.json")
SCHEMA_FILE = os.path.join(PLUGIN_DIR, "state_schema.json")

# State path configuration
STATE_DIR = os.path.join(os.getcwd(), ".agents")
STATE_FILE = os.path.join(STATE_DIR, "orchestration_state.json")
LOCK_FILE = os.path.join(STATE_DIR, "state.lock")
LOG_FILE = os.path.join(STATE_DIR, "orchestration.log")

# Setup Logging
os.makedirs(STATE_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(name)s) %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding="utf-8")
    ]
)
logger = logging.getLogger("sclass_runtime")

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
                break
            except FileExistsError:
                if time.time() - start_time > self.timeout:
                    logger.error(f"Concurrency Lock Timeout: Failed to acquire {self.lock_path}")
                    sys.exit(1)
                time.sleep(0.05)

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.fd is not None:
            os.close(self.fd)
            try:
                os.unlink(self.lock_path)
            except OSError:
                pass

# Dataclass models representing schemas
@dataclass
class Task:
    id: str
    owner: str
    targets: List[str]
    dependsOn: List[str]
    acceptanceCriteria: str
    priority: str
    status: str

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
    tasks: List[Task] = field(default_factory=list)
    decisionLog: List[Decision] = field(default_factory=list)

def load_json(path):
    if not os.path.exists(path):
        logger.error(f"Required configuration file missing: {path}")
        sys.exit(1)
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

def validate_state_types(state_dict: Dict[str, Any]):
    schema = load_json(SCHEMA_FILE)
    
    # Simple validation against schema properties
    properties = schema.get("properties", {})
    for key, val in state_dict.items():
        if key not in properties:
            logger.warning(f"Extraneous property in state: {key}")
            continue
            
        prop_schema = properties[key]
        expected_type = prop_schema.get("type")
        
        if expected_type == "string" and not isinstance(val, str) and val is not None:
            raise TypeError(f"Type validation failed: property '{key}' expected string, got {type(val)}")
        elif expected_type == "integer" and not isinstance(val, int):
            raise TypeError(f"Type validation failed: property '{key}' expected integer, got {type(val)}")
        elif expected_type == "number" and not isinstance(val, (int, float)):
            raise TypeError(f"Type validation failed: property '{key}' expected number, got {type(val)}")
        elif expected_type == "array" and not isinstance(val, list):
            raise TypeError(f"Type validation failed: property '{key}' expected array, got {type(val)}")
        elif expected_type == "object" and not isinstance(val, dict):
            raise TypeError(f"Type validation failed: property '{key}' expected object, got {type(val)}")

def init_state():
    with FileLock(LOCK_FILE):
        if os.path.exists(STATE_FILE):
            logger.info("State file already exists. Skipping initialization.")
            return
        
        state_dict = {
            "taskId": str(uuid.uuid4()),
            "currentPhase": "TRIAGE",
            "activeEvent": None,
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
                    "decision": "Initialize S-Class FSM Engine",
                    "reason": "Created baseline orchestration state file.",
                    "alternatives": [],
                    "confidence": 1.0,
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "agent": "dss_optimizer_v2"
                }
            ]
        }
        
        validate_state_types(state_dict)
        write_json_atomic(STATE_FILE, state_dict)
        logger.info(f"Initialized shared orchestration state: {STATE_FILE}")

def get_state_obj() -> State:
    if not os.path.exists(STATE_FILE):
        logger.error("State file not initialized. Run 'init' first.")
        sys.exit(1)
    
    state_dict = load_json(STATE_FILE)
    validate_state_types(state_dict)
    
    tasks = [Task(**t) for t in state_dict.get("tasks", [])]
    decisions = [Decision(**d) for d in state_dict.get("decisionLog", [])]
    conf_matrix = ConfidenceMatrix(**state_dict["confidenceMatrix"])
    
    return State(
        taskId=state_dict["taskId"],
        currentPhase=state_dict["currentPhase"],
        activeEvent=state_dict["activeEvent"],
        currentSpecVersion=state_dict["currentSpecVersion"],
        currentDebateVersion=state_dict["currentDebateVersion"],
        currentTaskVersion=state_dict["currentTaskVersion"],
        retryCount=state_dict["retryCount"],
        confidenceMatrix=conf_matrix,
        tasks=tasks,
        decisionLog=decisions
    )

def save_state_obj(state: State):
    state_dict = asdict(state)
    validate_state_types(state_dict)
    write_json_atomic(STATE_FILE, state_dict)

def execute_side_effects(state: State, side_effects: List[str]):
    for effect in side_effects:
        if effect == "incrementSpecVersion":
            state.currentSpecVersion += 1
            logger.info("Executing SideEffect: Incremented Spec Version")
        elif effect == "incrementTaskVersion":
            state.currentTaskVersion += 1
            logger.info("Executing SideEffect: Incremented Task Version")
        elif effect == "incrementDebateVersion":
            state.currentDebateVersion += 1
            logger.info("Executing SideEffect: Incremented Debate Version")
        elif effect == "incrementRetryCount":
            state.retryCount += 1
            logger.info("Executing SideEffect: Incremented Retry Count")
        elif effect == "resetRetryCount":
            state.retryCount = 0
            logger.info("Executing SideEffect: Reset Retry Count")
        else:
            logger.warning(f"Unknown side effect declared in event metadata: {effect}")

def dispatch_event(event_name):
    with FileLock(LOCK_FILE):
        state = get_state_obj()
        workflow = load_json(WORKFLOW_FILE)
        events = load_json(EVENTS_FILE)
        
        current_phase = state.currentPhase
        
        # Check event existence & load metadata
        event_meta = next((e for e in events if e["event"] == event_name), None)
        if not event_meta:
            logger.error(f"Event '{event_name}' is not registered in events.json")
            sys.exit(1)
            
        # Validate FSM State transition
        workflow_state = workflow["states"].get(current_phase, {})
        valid_transitions = workflow_state.get("transitions", {})
        
        if event_name not in valid_transitions:
            logger.error(f"FSM Veto: Transition '{event_name}' is invalid from current state '{current_phase}'")
            sys.exit(1)
            
        next_phase = valid_transitions[event_name]
        
        # Apply transition
        state.currentPhase = next_phase
        state.activeEvent = event_name
        
        # Execute metadata side-effects
        side_effects = event_meta.get("sideEffects", [])
        execute_side_effects(state, side_effects)
        
        # Log Decision Transition
        state.decisionLog.append(Decision(
            decision=f"Transition State to {next_phase}",
            reason=f"Fired event '{event_name}' from state '{current_phase}'",
            alternatives=list(valid_transitions.keys()),
            confidence=1.0,
            timestamp=datetime.utcnow().isoformat() + "Z",
            agent="state_manager_runtime"
        ))
        
        save_state_obj(state)
        logger.info(f"Transitioned state: {current_phase} ──({event_name})──> {next_phase}")

def show_status():
    state = get_state_obj()
    print("=== S-Class FSM Execution State ===")
    print(f"Task ID:        {state.taskId}")
    print(f"Current Phase:  {state.currentPhase}")
    print(f"Active Event:   {state.activeEvent}")
    print(f"Spec Version:   v{state.currentSpecVersion}")
    print(f"Task Version:   v{state.currentTaskVersion}")
    print(f"Retry Count:    {state.retryCount}")
    print(f"Weighted Score: {state.confidenceMatrix.weightedScore * 100}%")
    print("\n--- Active Tasks Queue ---")
    if not state.tasks:
        print("None")
    for t in state.tasks:
        print(f"[{t.status}] {t.id} (Owner: {t.owner}) -> Targets: {t.targets} [Acceptance: {t.acceptanceCriteria}] (DependsOn: {t.dependsOn})")
    print("\n--- Decision History Logs ---")
    for log in state.decisionLog[-5:]:
        print(f"[{log.timestamp}] ({log.agent}): {log.decision} - Reason: {log.reason}")

def show_capabilities(agent_name):
    caps = load_json(CAPABILITIES_FILE)
    agent_caps = caps.get(agent_name)
    if not agent_caps:
        logger.error(f"Agent '{agent_name}' is not registered in capabilities.json")
        sys.exit(1)
    print(f"=== Capabilities: {agent_name} ===")
    for cap, allowed in agent_caps.items():
        print(f" {cap}: {'Allowed' if allowed else 'Denied'}")

def update_task(task_id, status):
    with FileLock(LOCK_FILE):
        state = get_state_obj()
        task = next((t for t in state.tasks if t.id == task_id), None)
        if not task:
            logger.error(f"Task '{task_id}' not found.")
            sys.exit(1)
            
        task.status = status
        
        # Verify dependencies before starting task
        if status == "IN_PROGRESS":
            for dep in task.dependsOn:
                dep_task = next((t for t in state.tasks if t.id == dep), None)
                if dep_task and dep_task.status != "COMPLETED":
                    logger.warning(f"Dependency task '{dep}' has status '{dep_task.status}' (not COMPLETED). Proceed with caution.")
                    
        save_state_obj(state)
        logger.info(f"Updated Task '{task_id}' status to '{status}'")

def add_decision(decision, reason, agent, confidence, alts=[]):
    with FileLock(LOCK_FILE):
        state = get_state_obj()
        state.decisionLog.append(Decision(
            decision=decision,
            reason=reason,
            alternatives=alts,
            confidence=float(confidence),
            timestamp=datetime.utcnow().isoformat() + "Z",
            agent=agent
        ))
        save_state_obj(state)
        logger.info(f"Durable Decision added by '{agent}': {decision}")

def main():
    parser = argparse.ArgumentParser(description="S-Class FSM Engine CLI Runtime")
    subparsers = parser.add_subparsers(dest="command", help="Available runtime operations")
    
    # Init command
    subparsers.add_parser("init", help="Initialize shared state orchestration_state.json")
    
    # Status command
    subparsers.add_parser("status", help="Print current state machine status details")
    
    # Dispatch command
    dispatch_parser = subparsers.add_parser("dispatch", help="Trigger FSM transition event")
    dispatch_parser.add_argument("event", type=str, help="Transition event name")
    
    # Capabilities command
    caps_parser = subparsers.add_parser("capabilities", help="Audits permission matrix of an agent")
    caps_parser.add_argument("agent", type=str, help="Agent name")
    
    # Task update command
    task_parser = subparsers.add_parser("task", help="Updates task execution status")
    task_parser.add_argument("id", type=str, help="Task ID (e.g. T1)")
    task_parser.add_argument("status", type=str, choices=["PENDING", "IN_PROGRESS", "COMPLETED", "FAILED"], help="Target status")
    
    # Decision log command
    dec_parser = subparsers.add_parser("decision", help="Appends durable decision log")
    dec_parser.add_argument("decision", type=str, help="Decision detail")
    dec_parser.add_argument("reason", type=str, help="Rationale for selection")
    dec_parser.add_argument("agent", type=str, help="Author agent")
    dec_parser.add_argument("confidence", type=float, help="Confidence value (0-1)")
    dec_parser.add_argument("--alts", nargs="*", default=[], help="Alternative options evaluated")
    
    args = parser.parse_args()
    
    if args.command == "init":
        init_state()
    elif args.command == "status":
        show_status()
    elif args.command == "dispatch":
        dispatch_event(args.event)
    elif args.command == "capabilities":
        show_capabilities(args.agent)
    elif args.command == "task":
        update_task(args.id, args.status)
    elif args.command == "decision":
        add_decision(args.decision, args.reason, args.agent, args.confidence, args.alts)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
