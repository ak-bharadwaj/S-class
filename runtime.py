#!/usr/bin/env python3
import os
import sys
import json
import uuid
import argparse
from datetime import datetime

# Local Paths configuration
PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
WORKFLOW_FILE = os.path.join(PLUGIN_DIR, "workflow.json")
EVENTS_FILE = os.path.join(PLUGIN_DIR, "events.json")
CAPABILITIES_FILE = os.path.join(PLUGIN_DIR, "capabilities.json")
SCHEMA_FILE = os.path.join(PLUGIN_DIR, "state_schema.json")

# State path configuration
STATE_DIR = os.path.join(os.getcwd(), ".agents")
STATE_FILE = os.path.join(STATE_DIR, "orchestration_state.json")

def load_json(path):
    if not os.path.exists(path):
        print(f"Error: Required file not found: {path}", file=sys.stderr)
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def init_state():
    if os.path.exists(STATE_FILE):
        print(f"State file already exists at {STATE_FILE}. Skipping initialization.")
        return
    
    state = {
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
    
    write_json(STATE_FILE, state)
    print(f"Initialized shared orchestration state: {STATE_FILE}")

def get_state():
    if not os.path.exists(STATE_FILE):
        print("Error: State file not initialized. Run 'init' first.", file=sys.stderr)
        sys.exit(1)
    return load_json(STATE_FILE)

def dispatch_event(event_name):
    state = get_state()
    workflow = load_json(WORKFLOW_FILE)
    events = load_json(EVENTS_FILE)
    
    current_state = state["currentPhase"]
    
    # Check if event exists
    event_meta = next((e for e in events if e["event"] == event_name), None)
    if not event_meta:
        print(f"Error: Event '{event_name}' is not registered in events.json", file=sys.stderr)
        sys.exit(1)
        
    # Validate transition in FSM
    workflow_state = workflow["states"].get(current_state, {})
    valid_transitions = workflow_state.get("transitions", {})
    
    if event_name not in valid_transitions:
        print(f"Error: Transition '{event_name}' is invalid from current state '{current_state}'", file=sys.stderr)
        sys.exit(1)
        
    next_state = valid_transitions[event_name]
    
    # Update State
    state["currentPhase"] = next_state
    state["activeEvent"] = event_name
    
    # Increment debate or tasks version trackers if transition gates pass
    if event_name == "spec_approved":
        state["currentSpecVersion"] += 1
    if event_name == "tasks_ready":
        state["currentTaskVersion"] += 1
    if event_name == "debate_failed":
        state["currentDebateVersion"] += 1
    if event_name == "qa_failed":
        state["retryCount"] += 1
        
    # Log Decision Transition
    state["decisionLog"].append({
        "decision": f"Transition State to {next_state}",
        "reason": f"Fired event '{event_name}' from state '{current_state}'",
        "alternatives": list(valid_transitions.keys()),
        "confidence": 1.0,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "agent": "state_manager_runtime"
    })
    
    write_json(STATE_FILE, state)
    print(f"Transitioned state: {current_state} ──({event_name})──> {next_state}")

def show_status():
    state = get_state()
    print("=== S-Class FSM Execution State ===")
    print(f"Task ID:        {state['taskId']}")
    print(f"Current Phase:  {state['currentPhase']}")
    print(f"Active Event:   {state['activeEvent']}")
    print(f"Spec Version:   v{state['currentSpecVersion']}")
    print(f"Task Version:   v{state['currentTaskVersion']}")
    print(f"Retry Count:    {state['retryCount']}")
    print(f"Weighted Score: {state['confidenceMatrix']['weightedScore'] * 100}%")
    print("\n--- Active Tasks Queue ---")
    if not state["tasks"]:
        print("None")
    for t in state["tasks"]:
        print(f"[{t['status']}] {t['id']} (Owner: {t['owner']}) -> Targets: {t['targets']} [Acceptance: {t['acceptanceCriteria']}] (DependsOn: {t['dependsOn']})")
    print("\n--- Decision History Logs ---")
    for log in state["decisionLog"][-5:]:
        print(f"[{log['timestamp']}] ({log['agent']}): {log['decision']} - Reason: {log['reason']}")

def show_capabilities(agent_name):
    caps = load_json(CAPABILITIES_FILE)
    agent_caps = caps.get(agent_name)
    if not agent_caps:
        print(f"Error: Agent '{agent_name}' is not registered in capabilities.json", file=sys.stderr)
        sys.exit(1)
    print(f"=== Capabilities: {agent_name} ===")
    for cap, allowed in agent_caps.items():
        print(f" {cap}: {'Allowed' if allowed else 'Denied'}")

def update_task(task_id, status):
    state = get_state()
    task = next((t for t in state["tasks"] if t["id"] == task_id), None)
    if not task:
        print(f"Error: Task '{task_id}' not found.", file=sys.stderr)
        sys.exit(1)
        
    task["status"] = status
    
    # Check dependencies before starting task
    if status == "IN_PROGRESS":
        for dep in task["dependsOn"]:
            dep_task = next((t for t in state["tasks"] if t["id"] == dep), None)
            if dep_task and dep_task["status"] != "COMPLETED":
                print(f"Warning: Dependency task '{dep}' has status '{dep_task['status']}' (not COMPLETED). Proceed with caution.", file=sys.stderr)
                
    write_json(STATE_FILE, state)
    print(f"Updated Task '{task_id}' status to '{status}'")

def add_decision(decision, reason, agent, confidence, alts=[]):
    state = get_state()
    state["decisionLog"].append({
        "decision": decision,
        "reason": reason,
        "alternatives": alts,
        "confidence": float(confidence),
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "agent": agent
    })
    write_json(STATE_FILE, state)
    print(f"Durable Decision added by '{agent}': {decision}")

def main():
    parser = argparse.ArgumentParser(description="S-Class FSM Engine CLI Runtime")
    subparsers = parser.add_subparsers(dest="command", help="Available runtime operations")
    
    # Init command
    subparsers.add_parser("init", help="Initialize shared state orchestration_state.json")
    
    # Status command
    subparsers.add_parser("status", help="Print current state machine status details")
    
    # Dispatch command
    dispatch_parser = subparsers.add_parser("dispatch", help="Trigger FSM transition event")
    dispatch_parser.add_argument("event", type=str, help="Transition event name (e.g. triage_done)")
    
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
