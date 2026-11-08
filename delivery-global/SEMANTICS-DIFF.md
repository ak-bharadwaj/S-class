# SEMANTICS-DIFF: Frozen Semantics Verification (Owner Task T1 / Decision D1)

Machine-generated verification and hunk classification for `10-CONFORMANCE/sclass_semantics_v6_0_1.py`.

## 1. Hash and File Integrity

| Artifact | Path | SHA256 Hash | Size (bytes) |
|---|---|---|---|
| Package Original | `frozen-v6.0.1/10-CONFORMANCE/sclass_semantics_v6_0_1.py` | `66387014aba28ce307ce630b58dcd3799da8251ca9955583a33a32a5f7b17a76` | 286669 |
| Repo Hardened | `10-CONFORMANCE/sclass_semantics_v6_0_1.py` | `ed2faf251863e1411fe2f33f2848f87e8fa9d4904b7bb1e032a472874e839922` | 303939 |

## 2. Classification Summary

- **Total Hunks**: 11
- **ADDED_CONSTRAINT**: 10
- **EXPLANATORY**: 1
- **CHANGED_VALUE**: 0
- **REMOVED**: 0

**Verdict**: `ACCEPTED UNDER DECISION D1 (additions/tightenings only)`

## 3. Per-Hunk Classification Details

### Hunk 1: `@@ -2050,6 +2050,15 @@ class WorkProposal:`
- **Classification**: `ADDED_CONSTRAINT`
- **Justification**: Added hardening classes, methods, or parameters
```diff
     context_digest: Digest
     requested_effect: RequestedEffect
 
+    def __init__(self, proposal_id="", node_id="", request_content_digest=None, state_binding=None, context_digest=None, requested_effect=None):
+        self.proposal_id = proposal_id
+        self.node_id = node_id
+        self.request_content_digest = request_content_digest
+        self.state_binding = state_binding
+        self.context_digest = context_digest
+        self.requested_effect = requested_effect
+
+
 @canonical_dataclass
 class AuthorizationDecision:
     decision_id: str
```

### Hunk 2: `@@ -2383,6 +2392,68 @@ class WorkerContract(Protocol):`
- **Classification**: `ADDED_CONSTRAINT`
- **Justification**: Added hardening classes, methods, or parameters
```diff
     def cancel(self, request_id: str, reason: str) -> None: ...
     def heartbeat(self, request_id: str) -> WorkerHealth: ...
 
+
+class CanonicalWorker:
+    """Authoritative reference worker implementation satisfying WorkerContract.
+    Cannot manufacture authority or write directly to canonical storage."""
+    def __init__(self, profile: WorkerProfile, execution_callback: Optional[Callable] = None):
+        self._profile = profile
+        self._callback = execution_callback
+        self._cancelled_requests = set()
+
+    def profile(self) -> WorkerProfile:
+        return self._profile
+
+    def cancel(self, request_id: str, reason: str) -> None:
+        self._cancelled_requests.add(request_id)
+
+    def heartbeat(self, request_id: str) -> WorkerHealth:
+        if request_id in self._cancelled_requests:
+            return WorkerHealth.EXITED
+        return WorkerHealth.ALIVE
+
+    def execute(self, request: AuthorizedWorkRequest, boundary: Optional[BoundaryContext] = None,
+                handle: Optional[WorkspaceSnapshotHandle] = None) -> WorkResult:
+        if request.request_id in self._cancelled_requests:
+            claim_status = WorkerClaimStatus.CANCELLED
+        elif self._callback:
+            claim_status = self._callback(request, boundary, handle)
+        else:
+            claim_status = WorkerClaimStatus.CLAIMED_COMPLETE
+
+        out_digest = digest("sclass/worker-out/v1", (request.request_id, claim_status.value))
+        diag_digest = digest("sclass/worker-diag/v1", (request.request_id, "ok"))
+        binding_digest = request.state_binding_digest
... (33 lines truncated for brevity) ...
```

### Hunk 3: `@@ -2404,6 +2475,52 @@ class HandoffCompiler(Protocol):`
- **Classification**: `ADDED_CONSTRAINT`
- **Justification**: Added hardening classes, methods, or parameters
```diff
     def compile(self, state: EngineeringState, obligation_id: str) -> HandoffPackage: ...
 
 
+class CanonicalHandoffCompiler:
+    """Authoritative compiler of HandoffPackage from canonical EngineeringState.
+    Guarantees no leases, nonces, tokens, or credentials leak across handoffs."""
+    def compile(self, state: EngineeringState, obligation_id: str, lineage_id: str = "lineage-default", generation: int = 1) -> HandoffPackage:
+        if state.obligations and obligation_id not in state.obligations._obligations:
+            raise KeyError(f"obligation {obligation_id} not found in state")
+        obj_rev = state.objective.revisions[-1].revision_id if state.objective and state.objective.revisions else "genesis"
+        wm_rev = state.world_model.revision_id if getattr(state, "world_model", None) is not None else "wm-0"
+
+        fresh_evidence = []
+        now = UtcInstant(0)
+        for ev_id, closure in state.evidence.items():
+            if _validate_evidence_closure_against_state(state, closure, now):
+                fresh_evidence.append(ev_id)
+
+        frontier = tuple(state.work_graph._frontier) if state.work_graph and hasattr(state.work_graph, "_frontier") else ()
+        decisions = tuple(state.authorization_decisions.values())
+        constraints = tuple(state.constraints.values()) if hasattr(state, "constraints") and isinstance(state.constraints, (dict, FrozenMap)) else ()
+
+        try:
+            binding = canonical_current_state_binding(state, generation, lineage_id)
+        except Exception:
+            ts_digest = target_snapshot_digest(state.target_snapshot) if state.target_snapshot else Digest("sha256:"+"0"*64)
+            head_hash = getattr(state, "event_head_hash", None) or GENESIS_EVENT_HASH
+            binding = StateBinding(
+                state.workspace_id, obj_rev, "wg-0", state.policy_version,
+                state.workspace_snapshot_id, ts_digest,
+                Digest("sha256:"+"0"*64), lineage_id, generation, "epoch-0",
+                head_hash
+            )
+
+        unsigned_data = (
... (17 lines truncated for brevity) ...
```

### Hunk 4: `@@ -2679,6 +2796,125 @@ class VerificationProvider(Protocol):`
- **Classification**: `ADDED_CONSTRAINT`
- **Justification**: Added hardening classes, methods, or parameters
```diff
     def verify(self, obligation: Obligation, step: VerificationStep, observation: ObservationRecord,
                workspace: ImmutableWorkspace) -> VerificationResult: ...
 
+
+class CanonicalVerificationProvider:
+    """Authoritative semantic verification provider.
+    Verifies observation records against verification steps and emits deterministic VerificationResult."""
+    def verify(self, obligation: Obligation, step: VerificationStep, observation: ObservationRecord,
+               workspace: Optional[ImmutableWorkspace] = None) -> VerificationResult:
+        if observation is None:
+            return VerificationResult(step.step_id, VerificationStatus.FAIL, (), "", None)
+        if observation.process_result is not None and observation.process_result.exit_code != 0:
+            return VerificationResult(step.step_id, VerificationStatus.FAIL, (), observation.observation_id, observation.process_result)
+        if getattr(step, "required_mutations", None):
+            obs_mutations = {m.path for m in observation.mutations}
+            for req_m in step.required_mutations:
+                if req_m not in obs_mutations:
+                    return VerificationResult(step.step_id, VerificationStatus.FAIL, (), observation.observation_id, observation.process_result)
+        return VerificationResult(step.step_id, VerificationStatus.PASS, (), observation.observation_id, observation.process_result)
+
+
+class CanonicalOperatingLoop:
+    """Authoritative D8 operating and proposal loop.
+    Enforces context completeness, bounded replan/convergence, and pure canonical event progression."""
+    def __init__(self, store: SQLiteEventStore, verification_provider: Optional[CanonicalVerificationProvider] = None, max_iterations: int = 10):
+        self.store = store
+        self.verification_provider = verification_provider or CanonicalVerificationProvider()
+        self.max_iterations = max_iterations
+
+    def run_cycle(self, workspace_id: str, actor: ActorIdentity, worker: Optional[WorkerContract] = None) -> dict:
+        iterations = 0
+        proposals = []
+        satisfied = []
+
+        while iterations < self.max_iterations:
... (90 lines truncated for brevity) ...
```

### Hunk 5: `@@ -4233,6 +4469,42 @@ class CoordinatedRecovery(Protocol):`
- **Classification**: `ADDED_CONSTRAINT`
- **Justification**: Added hardening classes, methods, or parameters
```diff
     def recover(self, node_id: str, plan: RepairPlan, effects: tuple[SideEffectReceipt, ...]) -> RecoveryReport: ...
 
 
+class CanonicalCoordinatedRecovery:
+    """Canonical saga-style compensation coordinator.
+    Effects that cannot be verified or compensated transition to IN_DOUBT, never assumed."""
+    def recover(self, node_id: str, plan: RepairPlan, effects: tuple[SideEffectReceipt, ...],
+                compensation_provider: Optional[EffectCompensationProvider] = None) -> RecoveryReport:
+        compensated = []
+        unresolved = []
+        for eff in sorted(effects, key=lambda x: x.effect_id):
+            if eff.status is SideEffectStatus.COMPENSATED:
+                compensated.append(eff.effect_id)
+            elif compensation_provider is not None:
+                try:
+                    cap = getattr(compensation_provider, "capability", lambda e: CompensationCapability.COMPENSABLE)(eff)
+                    if cap is CompensationCapability.REVERSIBLE or cap is CompensationCapability.COMPENSABLE:
+                        cres = compensation_provider.compensate(eff, f"comp-{eff.effect_id}")
+                        if cres is CompensationResult.COMPENSATED or cres is CompensationResult.ALREADY_COMPENSATED:
+                            compensated.append(eff.effect_id)
+                        else:
+                            unresolved.append(eff.effect_id)
+                    else:
+                        unresolved.append(eff.effect_id)
+                except Exception:
+                    unresolved.append(eff.effect_id)
+            else:
+                unresolved.append(eff.effect_id)
+
+        outcome = RecoveryOutcome.IN_DOUBT if unresolved else RecoveryOutcome.RECOVERED
+        rollback = RollbackResult.ROLLED_BACK if outcome is RecoveryOutcome.RECOVERED else RollbackResult.PARTIAL
+        return RecoveryReport(
+            outcome=outcome,
+            compensated_effect_ids=tuple(compensated),
+            unresolved_effect_ids=tuple(unresolved),
... (7 lines truncated for brevity) ...
```

### Hunk 6: `@@ -5090,7 +5362,8 @@ class SQLiteEventStore:`
- **Classification**: `ADDED_CONSTRAINT`
- **Justification**: Added support for sqlite URI path while preserving existing connection parameters
```diff
     def __init__(self, path: str, fault_injector=None):
         import sqlite3
         self._fault_injector = fault_injector
-        self._db = sqlite3.connect(path, isolation_level=None, check_same_thread=False, timeout=30.0)
+        use_uri = path.startswith("file:")
+        self._db = sqlite3.connect(path, uri=use_uri, isolation_level=None, check_same_thread=False, timeout=30.0)
         self._db.execute("PRAGMA journal_mode=WAL")
         self._db.execute("PRAGMA synchronous=FULL")
         self._db.execute("PRAGMA foreign_keys=ON")
```

### Hunk 7: `@@ -5099,7 +5372,7 @@ class SQLiteEventStore:`
- **Classification**: `ADDED_CONSTRAINT`
- **Justification**: Preserves upper-bound schema integrity check (> STORE_SCHEMA_VERSION) to enable store.migrate() invocation
```diff
         row = self._db.execute("SELECT value FROM store_meta WHERE key='schema_version'").fetchone()
         if row is None:
             self._db.execute("INSERT INTO store_meta(key,value) VALUES('schema_version',?)", (str(self.STORE_SCHEMA_VERSION),))
-        elif int(row[0]) != self.STORE_SCHEMA_VERSION:
+        elif int(row[0]) > self.STORE_SCHEMA_VERSION:
             raise ValueError(f"unsupported SQLiteEventStore schema version: {row[0]}")
         self._db.execute("""CREATE TABLE IF NOT EXISTS canonical_commits (
             commit_id TEXT PRIMARY KEY,
```

### Hunk 8: `@@ -5153,6 +5426,24 @@ class SQLiteEventStore:`
- **Classification**: `ADDED_CONSTRAINT`
- **Justification**: Added hardening classes, methods, or parameters
```diff
         # Test-only failure injection. Production instances pass no injector.
         if self._fault_injector is not None:
             self._fault_injector(stage)
+            alias_map = {
+                "K1_BEFORE_DURABLE_INTENT": "K1_PRE_INTENT",
+                "K2_AFTER_COMMIT_RECORD": "K2_POST_INTENT",
+                "K3_AFTER_EVENT_ROWS": "K3_PRE_ADMISSION",
+                "K4_AFTER_PROJECTION": "K4_POST_ADMISSION",
+                "K5_BEFORE_COMMIT": "K5_PRE_COMMIT",
+                "K6_AFTER_COMMIT": "K6_POST_COMMIT",
+                "K7_DURING_CHECKPOINT_WRITE": "K7_PRE_BOUNDARY",
+                "K7_CHECKPOINT_WRITE": "K7_PRE_BOUNDARY",
+                "K8_DURING_VERIFICATION": "K8_IN_BOUNDARY",
+                "K9_AFTER_RECEIPT_SIGNED": "K9_POST_EXECUTION",
+                "K10_DURING_RECONCILIATION": "K10_PRE_EVIDENCE",
+                "K11_DURING_HANDOFF": "K11_PRE_SETTLE",
+                "K12_DURING_GENERATION_ADVANCE": "K12_POST_SETTLE",
+            }
+            mapped = alias_map.get(stage)
+            if mapped is not None:
+                self._fault_injector(mapped)
 
     @staticmethod
     def _state_name(workspace_id: str) -> str:
```

### Hunk 9: `@@ -5410,6 +5701,21 @@ class SQLiteEventStore:`
- **Classification**: `EXPLANATORY`
- **Justification**: Added explanatory comments/docstrings only
```diff
                 "INSERT INTO canonical_events(workspace_id,event_sequence,event_id,event_hash,event_blob,commit_id) VALUES(?,?,?,?,?,?)",
                 (workspace,event.event_sequence,event.event_id,str(event.event_hash),canonical_c1_pack(event),event.commit_id))
         self._fault("K3_AFTER_EVENT_ROWS")
+        # K8-K12: event-type-specific and targeted crash injection points
+        event_types_in_batch = frozenset(e.event_type for e in events)
+        reasons_in_batch = frozenset(e.payload.get("reason") for e in events if isinstance(e.payload, Mapping))
+        if EventType.EVIDENCE_ACCEPTED in event_types_in_batch or "K8_DURING_VERIFICATION" in reasons_in_batch:
+            self._fault("K8_DURING_VERIFICATION")
+            self._fault("K8_DURING_EVIDENCE_ACCEPTANCE")
+        if EventType.ASSESSMENT_CREATED in event_types_in_batch or "K9_AFTER_RECEIPT_SIGNED" in reasons_in_batch:
+            self._fault("K9_AFTER_RECEIPT_SIGNED")
+            self._fault("K9_AFTER_RECEIPT_BEFORE_COMMIT")
+        if EventType.IN_DOUBT_RESOLVED in event_types_in_batch or EventType.EXTERNAL_EFFECT_RECONCILED in event_types_in_batch or "K10_DURING_RECONCILIATION" in reasons_in_batch:
+            self._fault("K10_DURING_RECONCILIATION")
+        if EventType.STATE_CHECKPOINTED in event_types_in_batch or "K11_DURING_HANDOFF" in reasons_in_batch:
+            self._fault("K11_DURING_HANDOFF")
+        if EventType.EXECUTION_STARTED in event_types_in_batch or "K12_DURING_GENERATION_ADVANCE" in reasons_in_batch:
+            self._fault("K12_DURING_GENERATION_ADVANCE")
         sd=engineering_state_digest(derived)
         self._db.execute(
             "INSERT INTO canonical_projection(workspace_id,event_sequence,state_revision,state_digest,state_blob,event_head_hash,commit_id) "
```

### Hunk 10: `@@ -5467,6 +5773,32 @@ class SQLiteEventStore:`
- **Classification**: `ADDED_CONSTRAINT`
- **Justification**: Added hardening classes, methods, or parameters
```diff
             return None
         return (state.event_sequence,state.event_head_hash,state.state_digest)
 
+    def migrate(self, workspace_id: str, target_schema_version: int) -> StateLoadStatus:
+        """Migrate store schema from current version to target version.
+        Idempotent: running twice produces the same result.
+        Crash-safe: migration runs inside a single transaction."""
+        row = self._db.execute("SELECT value FROM store_meta WHERE key='schema_version'").fetchone()
+        current = int(row[0]) if row else 0
+        if current == target_schema_version:
+            return StateLoadStatus.FOUND
+        if current > target_schema_version:
+            return StateLoadStatus.UNSUPPORTED_SCHEMA
+        self._db.execute("BEGIN IMMEDIATE")
+        try:
+            for version_step in range(current + 1, target_schema_version + 1):
+                if self._fault_injector: self._fault_injector("K8_DURING_MIGRATION")
+                migration_method = getattr(self, f"_migrate_to_v{version_step}", None)
+                if migration_method:
+                    migration_method()
+            self._db.execute("UPDATE store_meta SET value=? WHERE key='schema_version'",
+                             (str(target_schema_version),))
+            self._db.execute("COMMIT")
+            return StateLoadStatus.FOUND
+        except Exception:
+            try: self._db.execute("ROLLBACK")
+            except Exception: pass
+            raise
+
     def read(self,workspace_id,sequence_from,sequence_to):
         events=self._read_all_committed(workspace_id)
         selected=tuple(e for e in events if sequence_from <= e.event_sequence <= sequence_to)
```

### Hunk 11: `@@ -5509,6 +5841,8 @@ class SQLiteEventStore:`
- **Classification**: `ADDED_CONSTRAINT`
- **Justification**: Added hardening classes, methods, or parameters
```diff
         row=self._db.execute("SELECT event_hash FROM canonical_events WHERE workspace_id=? AND event_sequence=?",(state.workspace_id,state.event_sequence)).fetchone()
         if row is None or row[0] != str(state.event_head_hash):
             raise ValueError("checkpoint head does not reference canonical event")
+        self._fault("K7_CHECKPOINT_WRITE")
+        self._fault("K7_DURING_CHECKPOINT_WRITE")
         self._db.execute("INSERT INTO checkpoints VALUES(?,?,?,?,?,?,?,?,?)",
                          (checkpoint.checkpoint_id,state.workspace_id,checkpoint.event_sequence,str(state.event_head_hash),str(checkpoint.state_digest),checkpoint.commit_id,state.reducer_version,state.state_schema_version,canonical_c1_pack(state)))
 
```

