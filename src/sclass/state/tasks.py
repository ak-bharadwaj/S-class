"""
S-Class State: Task and Project Repository.
Provides transactional access to project, task, claim, and verification records.
"""

from __future__ import annotations
import json
import sqlite3
from typing import Optional, List, Dict, Any

from sclass.state.sqlite import SQLiteStateStore
from sclass.domain.project import Project, ProjectBoundary
from sclass.domain.task import Task, TaskState, TaskPriority
from sclass.domain.claim import Claim
from sclass.domain.verification import VerificationResult
from sclass.core.errors import StorageError


class StateRepository:
    """Repository pattern managing authoritative state persistence."""

    def __init__(self, workspace_dir: str):
        self.workspace_dir = workspace_dir
        self.store = SQLiteStateStore(workspace_dir)

    def save_project(self, project: Project) -> None:
        """Upserts project record."""
        query = """
        INSERT INTO projects (project_id, name, root_path, created_at, active_agent, current_goal, metadata_json)
        VALUES (:project_id, :name, :root_path, :created_at, :active_agent, :current_goal, :metadata_json)
        ON CONFLICT(project_id) DO UPDATE SET
            name = excluded.name,
            root_path = excluded.root_path,
            active_agent = excluded.active_agent,
            current_goal = excluded.current_goal,
            metadata_json = excluded.metadata_json;
        """
        data = {
            "project_id": project.project_id,
            "name": project.name,
            "root_path": project.boundary.root_path,
            "created_at": project.created_at,
            "active_agent": project.active_agent,
            "current_goal": project.current_goal,
            "metadata_json": json.dumps(project.metadata),
        }
        with self.store.get_connection() as conn:
            conn.execute(query, data)
            conn.commit()

    def get_project(self, project_id: str) -> Optional[Project]:
        """Retrieves project by ID."""
        query = "SELECT * FROM projects WHERE project_id = ?"
        with self.store.get_connection() as conn:
            row = conn.execute(query, (project_id,)).fetchone()
            if not row:
                return None
            return Project(
                project_id=row["project_id"],
                name=row["name"],
                boundary=ProjectBoundary(row["root_path"]),
                created_at=row["created_at"],
                active_agent=row["active_agent"],
                current_goal=row["current_goal"],
                metadata=json.loads(row["metadata_json"]),
            )

    def save_task(self, task: Task) -> None:
        """Upserts task record."""
        query = """
        INSERT INTO tasks (
            task_id, project_id, title, description, state, priority,
            depends_on_json, assigned_agent, claimed_evidence_id, verified_receipt_id,
            created_at, updated_at, completed_at, metadata_json
        )
        VALUES (
            :task_id, :project_id, :title, :description, :state, :priority,
            :depends_on_json, :assigned_agent, :claimed_evidence_id, :verified_receipt_id,
            :created_at, :updated_at, :completed_at, :metadata_json
        )
        ON CONFLICT(task_id) DO UPDATE SET
            title = excluded.title,
            description = excluded.description,
            state = excluded.state,
            priority = excluded.priority,
            depends_on_json = excluded.depends_on_json,
            assigned_agent = excluded.assigned_agent,
            claimed_evidence_id = excluded.claimed_evidence_id,
            verified_receipt_id = excluded.verified_receipt_id,
            updated_at = excluded.updated_at,
            completed_at = excluded.completed_at,
            metadata_json = excluded.metadata_json;
        """
        data = {
            "task_id": task.task_id,
            "project_id": task.project_id,
            "title": task.title,
            "description": task.description,
            "state": task.state.value,
            "priority": task.priority.value,
            "depends_on_json": json.dumps(task.depends_on),
            "assigned_agent": task.assigned_agent,
            "claimed_evidence_id": task.claimed_evidence_id,
            "verified_receipt_id": task.verified_receipt_id,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
            "completed_at": task.completed_at,
            "metadata_json": json.dumps(task.metadata),
        }
        with self.store.get_connection() as conn:
            conn.execute(query, data)
            conn.commit()

    def get_task(self, task_id: str) -> Optional[Task]:
        """Retrieves task by ID."""
        query = "SELECT * FROM tasks WHERE task_id = ?"
        with self.store.get_connection() as conn:
            row = conn.execute(query, (task_id,)).fetchone()
            if not row:
                return None
            return Task(
                task_id=row["task_id"],
                project_id=row["project_id"],
                title=row["title"],
                description=row["description"],
                state=TaskState(row["state"]),
                priority=TaskPriority(row["priority"]),
                depends_on=json.loads(row["depends_on_json"]),
                assigned_agent=row["assigned_agent"],
                claimed_evidence_id=row["claimed_evidence_id"],
                verified_receipt_id=row["verified_receipt_id"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                completed_at=row["completed_at"],
                metadata=json.loads(row["metadata_json"]),
            )

    def list_tasks(self, project_id: Optional[str] = None, state: Optional[TaskState] = None) -> List[Task]:
        """Lists tasks with optional filtering."""
        clauses = []
        params: List[Any] = []
        if project_id:
            clauses.append("project_id = ?")
            params.append(project_id)
        if state:
            clauses.append("state = ?")
            params.append(state.value)

        where_str = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        query = f"SELECT * FROM tasks {where_str} ORDER BY created_at ASC"

        with self.store.get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [
                Task(
                    task_id=r["task_id"],
                    project_id=r["project_id"],
                    title=r["title"],
                    description=r["description"],
                    state=TaskState(r["state"]),
                    priority=TaskPriority(r["priority"]),
                    depends_on=json.loads(r["depends_on_json"]),
                    assigned_agent=r["assigned_agent"],
                    claimed_evidence_id=r["claimed_evidence_id"],
                    verified_receipt_id=r["verified_receipt_id"],
                    created_at=r["created_at"],
                    updated_at=r["updated_at"],
                    completed_at=r["completed_at"],
                    metadata=json.loads(r["metadata_json"]),
                )
                for r in rows
            ]

    def save_claim(self, claim: Claim) -> None:
        """Upserts a claim."""
        query = """
        INSERT INTO claims (claim_id, task_id, statement, claim_type, verifier, target_files_json, created_at, metadata_json)
        VALUES (:claim_id, :task_id, :statement, :claim_type, :verifier, :target_files_json, :created_at, :metadata_json)
        ON CONFLICT(claim_id) DO UPDATE SET
            statement = excluded.statement,
            claim_type = excluded.claim_type,
            verifier = excluded.verifier,
            target_files_json = excluded.target_files_json,
            metadata_json = excluded.metadata_json;
        """
        data = {
            "claim_id": claim.claim_id,
            "task_id": claim.task_id,
            "statement": claim.statement,
            "claim_type": claim.claim_type,
            "verifier": claim.verifier,
            "target_files_json": json.dumps(list(claim.target_files)),
            "created_at": claim.created_at,
            "metadata_json": json.dumps(claim.metadata),
        }
        with self.store.get_connection() as conn:
            conn.execute(query, data)
            conn.commit()

    def get_claim(self, claim_id: str) -> Optional[Claim]:
        """Retrieves claim by ID."""
        query = "SELECT * FROM claims WHERE claim_id = ?"
        with self.store.get_connection() as conn:
            row = conn.execute(query, (claim_id,)).fetchone()
            if not row:
                return None
            return Claim(
                claim_id=row["claim_id"],
                task_id=row["task_id"],
                statement=row["statement"],
                claim_type=row["claim_type"],
                verifier=row["verifier"],
                target_files=tuple(json.loads(row["target_files_json"])),
                created_at=row["created_at"],
                metadata=json.loads(row["metadata_json"]),
            )

    def save_verification(self, result: VerificationResult) -> None:
        """Records a verification result."""
        import uuid
        query = """
        INSERT INTO verifications (
            verification_id, claim_id, receipt_id, status, reason,
            observed_exit_code, observed_files_json, passed_tests, failed_tests,
            verification_time, metadata_json
        )
        VALUES (
            :verification_id, :claim_id, :receipt_id, :status, :reason,
            :observed_exit_code, :observed_files_json, :passed_tests, :failed_tests,
            :verification_time, :metadata_json
        );
        """
        verif_time = (
            result.verification_event.verification_time
            if result.verification_event
            else json.dumps(result.to_dict().get("verification_time", ""))
        )
        data = {
            "verification_id": f"ver_{uuid.uuid4().hex[:10]}",
            "claim_id": result.claim_id,
            "receipt_id": result.receipt_id,
            "status": result.status,
            "reason": result.reason,
            "observed_exit_code": result.observed_exit_code,
            "observed_files_json": json.dumps(list(result.observed_files_changed)),
            "passed_tests": result.passed_tests,
            "failed_tests": result.failed_tests,
            "verification_time": verif_time,
            "metadata_json": json.dumps(result.metadata),
        }
        with self.store.get_connection() as conn:
            conn.execute(query, data)
            conn.commit()

    def get_verification(
        self,
        claim_id: Optional[str] = None,
        receipt_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Retrieves a verification record by claim_id and/or receipt_id."""
        clauses = []
        params = []
        if claim_id:
            clauses.append("claim_id = ?")
            params.append(claim_id)
        if receipt_id:
            clauses.append("receipt_id = ?")
            params.append(receipt_id)
        if not clauses:
            return None
        query = f"SELECT * FROM verifications WHERE {' AND '.join(clauses)} ORDER BY verification_time DESC LIMIT 1"
        with self.store.get_connection() as conn:
            row = conn.execute(query, params).fetchone()
            if not row:
                return None
            return dict(row)

    def list_verifications(
        self,
        claim_id: Optional[str] = None,
        receipt_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Lists verification records by claim_id and/or receipt_id."""
        clauses = []
        params = []
        if claim_id:
            clauses.append("claim_id = ?")
            params.append(claim_id)
        if receipt_id:
            clauses.append("receipt_id = ?")
            params.append(receipt_id)
        where_str = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        query = f"SELECT * FROM verifications {where_str} ORDER BY verification_time DESC"
        with self.store.get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]


    def save_recovery(self, record: Any) -> None:
        """Upserts a recovery record into the authoritative SQLite store."""
        query = """
        INSERT INTO recovery_records (
            recovery_id, task_id, affected_obligation_id, current_state,
            attempt_number, max_attempts, failure_classification, reason,
            affected_claim_id, affected_evidence_id, project_state_ref,
            parent_event_id, staleness_cause, created_at, updated_at,
            current_repair_obligation_json, resulting_verification_json,
            history_json, metadata_json
        )
        VALUES (
            :recovery_id, :task_id, :affected_obligation_id, :current_state,
            :attempt_number, :max_attempts, :failure_classification, :reason,
            :affected_claim_id, :affected_evidence_id, :project_state_ref,
            :parent_event_id, :staleness_cause, :created_at, :updated_at,
            :current_repair_obligation_json, :resulting_verification_json,
            :history_json, :metadata_json
        )
        ON CONFLICT(recovery_id) DO UPDATE SET
            current_state = excluded.current_state,
            attempt_number = excluded.attempt_number,
            max_attempts = excluded.max_attempts,
            failure_classification = excluded.failure_classification,
            reason = excluded.reason,
            affected_claim_id = excluded.affected_claim_id,
            affected_evidence_id = excluded.affected_evidence_id,
            project_state_ref = excluded.project_state_ref,
            parent_event_id = excluded.parent_event_id,
            staleness_cause = excluded.staleness_cause,
            updated_at = excluded.updated_at,
            current_repair_obligation_json = excluded.current_repair_obligation_json,
            resulting_verification_json = excluded.resulting_verification_json,
            history_json = excluded.history_json,
            metadata_json = excluded.metadata_json;
        """
        curr_ob_json = json.dumps(record.current_repair_obligation.to_dict()) if record.current_repair_obligation else None
        res_ver_json = json.dumps(record.resulting_verification) if record.resulting_verification else None
        data = {
            "recovery_id": record.recovery_id,
            "task_id": record.task_id,
            "affected_obligation_id": record.affected_obligation_id,
            "current_state": record.current_state.value if hasattr(record.current_state, "value") else str(record.current_state),
            "attempt_number": record.attempt_number,
            "max_attempts": record.max_attempts,
            "failure_classification": record.failure_classification,
            "reason": record.reason,
            "affected_claim_id": record.affected_claim_id,
            "affected_evidence_id": record.affected_evidence_id,
            "project_state_ref": record.project_state_ref,
            "parent_event_id": record.parent_event_id,
            "staleness_cause": record.staleness_cause,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
            "current_repair_obligation_json": curr_ob_json,
            "resulting_verification_json": res_ver_json,
            "history_json": json.dumps(list(record.history)),
            "metadata_json": json.dumps(dict(record.metadata)),
        }
        conn = self.store.get_connection()
        try:
            conn.execute(query, data)
            conn.commit()
        finally:
            conn.close()

    def get_recovery(self, recovery_id: str) -> Optional[Any]:
        """Retrieves a recovery record by recovery_id."""
        query = "SELECT * FROM recovery_records WHERE recovery_id = ?"
        conn = self.store.get_connection()
        try:
            row = conn.execute(query, (recovery_id,)).fetchone()
            if not row:
                return None
            return self._row_to_recovery_record(row)
        finally:
            conn.close()

    def list_recoveries(
        self,
        task_id: Optional[str] = None,
        affected_obligation_id: Optional[str] = None,
    ) -> List[Any]:
        """Lists recovery records with optional filtering."""
        clauses = []
        params: List[Any] = []
        if task_id:
            clauses.append("task_id = ?")
            params.append(task_id)
        if affected_obligation_id:
            clauses.append("affected_obligation_id = ?")
            params.append(affected_obligation_id)

        where_str = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        query = f"SELECT * FROM recovery_records {where_str} ORDER BY created_at ASC"
        conn = self.store.get_connection()
        try:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_recovery_record(r) for r in rows]
        finally:
            conn.close()

    def _row_to_recovery_record(self, row: Any) -> Any:
        """Converts an SQLite row to a RecoveryRecord."""
        from sclass.recovery.models import RecoveryRecord, RecoveryState, RepairObligation
        curr_ob = None
        if row["current_repair_obligation_json"]:
            curr_ob = RepairObligation.from_dict(json.loads(row["current_repair_obligation_json"]))

        res_ver = None
        if row["resulting_verification_json"]:
            res_ver = json.loads(row["resulting_verification_json"])

        return RecoveryRecord(
            recovery_id=row["recovery_id"],
            task_id=row["task_id"],
            affected_obligation_id=row["affected_obligation_id"],
            current_state=RecoveryState(row["current_state"]),
            attempt_number=int(row["attempt_number"]),
            max_attempts=int(row["max_attempts"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            failure_classification=row["failure_classification"],
            reason=row["reason"],
            parent_event_id=row["parent_event_id"],
            staleness_cause=row["staleness_cause"],
            affected_claim_id=row["affected_claim_id"],
            affected_evidence_id=row["affected_evidence_id"],
            project_state_ref=row["project_state_ref"],
            current_repair_obligation=curr_ob,
            history=json.loads(row["history_json"]) if row["history_json"] else [],
            resulting_verification=res_ver,
            metadata=json.loads(row["metadata_json"]) if row["metadata_json"] else {},
        )
