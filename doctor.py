import os
import json
import sys
from dataclasses import dataclass
from typing import List

@dataclass
class DoctorCheck:
    name: str
    status: str  # PASS | FAIL | WARN
    message: str

@dataclass 
class DoctorReport:
    checks: List[DoctorCheck]
    overall_status: str  # HEALTHY | DEGRADED | BROKEN

def check_python_version() -> DoctorCheck:
    if sys.version_info >= (3, 10):
        return DoctorCheck("Python Version", "PASS", f"Python >= 3.10 ({sys.version.split()[0]})")
    return DoctorCheck("Python Version", "FAIL", f"Python < 3.10 ({sys.version.split()[0]})")

def check_state_file_integrity(workspace_dir: str) -> DoctorCheck:
    state_file = os.path.join(workspace_dir, ".agents", "orchestration_state.json")
    if not os.path.exists(state_file):
        return DoctorCheck("State File", "WARN", "Missing orchestration_state.json")
    try:
        with open(state_file, "r") as f:
            json.load(f)
        return DoctorCheck("State File", "PASS", "Valid JSON")
    except Exception as e:
        return DoctorCheck("State File", "FAIL", f"Corrupt JSON: {e}")

def check_memory_file_integrity(workspace_dir: str) -> DoctorCheck:
    memory_file = os.path.join(workspace_dir, ".agents", "learning_memory.json")
    if not os.path.exists(memory_file):
        return DoctorCheck("Memory File", "WARN", "Missing learning_memory.json")
    try:
        with open(memory_file, "r") as f:
            json.load(f)
        return DoctorCheck("Memory File", "PASS", "Valid JSON")
    except Exception as e:
        return DoctorCheck("Memory File", "FAIL", f"Corrupt JSON: {e}")

def check_lock_file_clean(workspace_dir: str) -> DoctorCheck:
    lock_file = os.path.join(workspace_dir, ".agents", "state.lock")
    if os.path.exists(lock_file):
        try:
            with open(lock_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
            
            pid = None
            if content.isdigit():
                pid = int(content)
            elif content.startswith("{"):
                try:
                    data = json.loads(content)
                    if isinstance(data, dict):
                        pid = data.get("pid")
                except Exception:
                    pass

            if pid is not None:
                from runtime import _process_exists
                if not _process_exists(int(pid)):
                    return DoctorCheck("Lock File", "WARN", f"Stale lock file detected (PID {pid} is dead)")
                else:
                    return DoctorCheck("Lock File", "PASS", f"Lock file is active (PID {pid} is alive)")
            return DoctorCheck("Lock File", "WARN", "Lock file exists but has no valid PID")
        except Exception as e:
            return DoctorCheck("Lock File", "WARN", f"Lock file exists but cannot be read: {e}")
    return DoctorCheck("Lock File", "PASS", "No lock file")

def check_config_exists(workspace_dir: str) -> DoctorCheck:
    config_file = os.path.join(workspace_dir, "sclass.config.json")
    if os.path.exists(config_file):
        return DoctorCheck("Config File", "PASS", "sclass.config.json exists")
    return DoctorCheck("Config File", "WARN", "Missing sclass.config.json")

def run_doctor(workspace_dir: str) -> DoctorReport:
    from sclass_doctor import SClassProactiveDoctor

    checks = [
        check_python_version(),
        check_state_file_integrity(workspace_dir),
        check_memory_file_integrity(workspace_dir),
        check_lock_file_clean(workspace_dir),
        check_config_exists(workspace_dir)
    ]
    
    try:
        sclass_audit = SClassProactiveDoctor.audit_workspace(workspace_dir)
        for audit_name, audit_data in sclass_audit.get("audits", {}).items():
            st = audit_data.get("status", "PASSED")
            msg = audit_data.get("message", f"Status: {st}")
            if "missing" in audit_data:
                msg = f"Missing: {', '.join(audit_data['missing'])}"
            elif "count" in audit_data:
                msg = f"{msg} (count: {audit_data['count']})"
            st_mapped = "WARN" if st == "FAILED" else ("PASS" if st == "PASSED" else "WARN")
            checks.append(DoctorCheck(
                name=f"S-Class {audit_name.replace('_', ' ').title()}",
                status=st_mapped,
                message=msg
            ))
    except Exception as ex:
        checks.append(DoctorCheck("S-Class Proactive Audit", "WARN", f"Audit warning: {ex}"))

    statuses = [c.status for c in checks]
    if "FAIL" in statuses:
        overall = "BROKEN"
    elif "WARN" in statuses:
        overall = "DEGRADED"
    else:
        overall = "HEALTHY"
        
    return DoctorReport(checks=checks, overall_status=overall)
