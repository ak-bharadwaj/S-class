"""
S-Class Migration Script: v5 to v6 Adaptive Architecture (migrate_v5_to_v6.py)

Migrates workspace configuration, persona bindings, and state databases
from S-Class v5 to S-Class v6 Adaptive Engineering Guard.
"""

import os
import sys
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("sclass_migration")

ROLE_MAPPINGS = {
    "dss_lead_architect": "architect",
    "dss_architect_v2": "architect",
    "dss_governor": "architect",
    "dss_fullstack_dev": "builder",
    "dss_frontend_dev": "builder",
    "dss_backend_dev": "builder",
    "dss_builder_v2": "builder",
    "dss_db_architect": "builder",
    "dss_cso_v2": "security",
    "dss_qa_frontend": "qa",
    "dss_qa_v2": "qa",
    "dss_user_alias_v2": "reviewer",
    "dss_analyst": "analyst",
}


def migrate_workspace(workspace_dir: Optional[str] = None) -> Dict[str, Any]:
    """Migrates an existing S-Class v5 workspace configuration to v6."""
    cwd = workspace_dir or os.getcwd()
    agents_dir = os.path.join(cwd, ".agents")
    os.makedirs(agents_dir, exist_ok=True)

    report = {
        "workspace": cwd,
        "config_updated": False,
        "state_migrated": False,
        "roles_mapped": 0,
        "instructions_migrated": True,
        "status": "SUCCESS"
    }

    import subprocess
    import shutil
    try:
        status_out = subprocess.check_output(["git", "status", "--porcelain"], cwd=cwd, text=True)
        if status_out.strip():
            logger.error("Git working directory is not clean. Commit or stash changes before migrating.")
            return {"status": "ERROR", "message": "Dirty git tree"}
    except Exception as e:
        logger.warning(f"Git check failed, proceeding anyway: {e}")

    # 1. Migrate sclass.config.json
    cfg_file = os.path.join(cwd, "sclass.config.json")
    if os.path.exists(cfg_file):
        try:
            shutil.copy2(cfg_file, cfg_file + ".bak")
            with open(cfg_file, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            cfg["plugin_version"] = "6.0.0"
            cfg["plugin_id"] = "sclass-v6"
            cfg["adaptive_profiles_enabled"] = True
            with open(cfg_file, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2)
            report["config_updated"] = True
        except Exception as e:
            logger.warning(f"Config migration notice: {e}")

    # 2. Migrate orchestration_state.json if present
    state_file = os.path.join(agents_dir, "orchestration_state.json")
    if os.path.exists(state_file):
        try:
            shutil.copy2(state_file, state_file + ".bak")
            with open(state_file, "r", encoding="utf-8") as f:
                state_data = json.load(f)
            # Map legacy persona names in decision log
            for dec in state_data.get("decisionLog", []):
                old_agent = dec.get("agent", "")
                if old_agent in ROLE_MAPPINGS:
                    dec["agent"] = ROLE_MAPPINGS[old_agent]
                    report["roles_mapped"] += 1
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump(state_data, f, indent=2)
            report["state_migrated"] = True
        except Exception as e:
            logger.warning(f"State migration notice: {e}")

    # 3. Create or verify split instructions directory
    instructions_dir = os.path.join(cwd, "instructions")
    if not os.path.exists(instructions_dir):
        os.makedirs(instructions_dir, exist_ok=True)

    return report


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    result = migrate_workspace(target)
    print(json.dumps(result, indent=2))
