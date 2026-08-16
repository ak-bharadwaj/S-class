import os
import json
import time
import logging
from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime, timezone, timedelta

@dataclass
class GCReport:
    stale_locks_removed: int = 0
    expired_states_removed: int = 0
    orphaned_screenshots_removed: int = 0
    expired_memory_entries_pruned: int = 0
    total_bytes_freed: int = 0
    errors: List[str] = field(default_factory=list)

def run_gc(workspace_dir: str, state_max_age_days: int = 7, memory_max_age_days: int = 30) -> GCReport:
    report = GCReport()
    agents_dir = os.path.join(workspace_dir, ".agents")
    if not os.path.isdir(agents_dir):
        return report

    now = datetime.now(timezone.utc)
    
    # 1. Stale locks
    lock_file = os.path.join(agents_dir, "state.lock")
    if os.path.exists(lock_file):
        try:
            from file_lock import FileLock, _process_exists
            is_stale = False
            lock = FileLock(lock_file, timeout=0.1)
            try:
                with lock:
                    # We hold the OS kernel lock! Check if owner PID is dead or status is released.
                    try:
                        with open(lock_file, "r") as f:
                            data = json.load(f)
                        pid = data.get("pid")
                        status = data.get("status")
                        if (pid and not _process_exists(pid)) or status == "released":
                            is_stale = True
                    except Exception:
                        is_stale = True

                    if is_stale:
                        size = os.path.getsize(lock_file)
                        report.stale_locks_removed += 1
                        report.total_bytes_freed += size
            except TimeoutError:
                # Active process holds the kernel lock on state.lock - preserve lock intact.
                pass

            if is_stale and os.path.exists(lock_file):
                try:
                    os.remove(lock_file)
                except OSError:
                    pass
        except Exception as e:
            report.errors.append(f"Error checking lock file: {e}")

    # 2. Expired states
    state_file = os.path.join(agents_dir, "orchestration_state.json")
    if os.path.exists(state_file):
        try:
            mtime = os.path.getmtime(state_file)
            mtime_dt = datetime.fromtimestamp(mtime, tz=timezone.utc)
            if (now - mtime_dt).days > state_max_age_days:
                size = os.path.getsize(state_file)
                os.remove(state_file)
                report.expired_states_removed += 1
                report.total_bytes_freed += size
        except Exception as e:
            report.errors.append(f"Error removing state file: {e}")

    # 3. Orphaned screenshots
    screenshots_dir = os.path.join(agents_dir, "qa_screenshots")
    if os.path.isdir(screenshots_dir):
        try:
            for fname in os.listdir(screenshots_dir):
                fpath = os.path.join(screenshots_dir, fname)
                if os.path.isfile(fpath):
                    mtime = os.path.getmtime(fpath)
                    mtime_dt = datetime.fromtimestamp(mtime, tz=timezone.utc)
                    if (now - mtime_dt).days > state_max_age_days:
                        size = os.path.getsize(fpath)
                        os.remove(fpath)
                        report.orphaned_screenshots_removed += 1
                        report.total_bytes_freed += size
        except Exception as e:
            report.errors.append(f"Error removing screenshots: {e}")

    # 4. Expired memory entries
    memory_file = os.path.join(agents_dir, "learning_memory.json")
    if os.path.exists(memory_file):
        try:
            size_before = os.path.getsize(memory_file)
            with open(memory_file, "r") as f:
                memory_data = json.load(f)
            
            if isinstance(memory_data, list):
                new_memory_data = []
                for entry in memory_data:
                    entry_time_str = entry.get("timestamp")
                    if entry_time_str:
                        try:
                            entry_time = datetime.fromisoformat(entry_time_str)
                            if entry_time.tzinfo is None:
                                entry_time = entry_time.replace(tzinfo=timezone.utc)
                            if (now - entry_time).days <= memory_max_age_days:
                                new_memory_data.append(entry)
                            else:
                                report.expired_memory_entries_pruned += 1
                        except ValueError:
                            new_memory_data.append(entry)
                    else:
                        new_memory_data.append(entry)
                
                if report.expired_memory_entries_pruned > 0:
                    with open(memory_file, "w") as f:
                        json.dump(new_memory_data, f, indent=2)
                    size_after = os.path.getsize(memory_file)
                    report.total_bytes_freed += max(0, size_before - size_after)
        except Exception as e:
            report.errors.append(f"Error pruning memory file: {e}")

    return report
