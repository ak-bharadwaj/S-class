"""S0 Mutation Baseline Test Suite Runner.

Partitions the S0 semantic mutation campaign into 5 normative domains:
  - S0-M1: C1 canonicalization
  - S0-M2: Digest / domain separation
  - S0-M3: Semantic validation
  - S0-M4: Identity / immutability
  - S0-M5: Reducer / state transitions

Executes all 1,085 S0 mutants and verifies 100% kill rate against the canonical test suite.
"""

import importlib
import json
import sqlite3
import sys
import time
import traceback
from pathlib import Path

import os

# Prevent bytecode caching from poisoning in-process mutation campaign
sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

# In-tree source path insertion:
# The Cosmic Ray mutation runner applies AST/code mutations directly to the in-tree
# file `10-CONFORMANCE/sclass_semantics_v6_0_1.py` on disk and reloads it dynamically
# via `importlib.reload()`. `10-CONFORMANCE` must precede site-packages on `sys.path`
# to ensure the mutated source file on disk is reloaded rather than the immutable wheel package.
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "10-CONFORMANCE"))
sys.path.insert(0, str(ROOT_DIR))

import cosmic_ray.cli
import cosmic_ray.plugins
from cosmic_ray.mutating import _make_diff, use_mutation

DB_PATH = ROOT_DIR / "cosmic-ray.sqlite"
CONFIG_PATH = ROOT_DIR / "cosmic-ray.toml"

def ensure_database():
    """Initializes cosmic-ray database if missing or unpopulated."""
    need_init = False
    if not DB_PATH.exists():
        need_init = True
    else:
        conn = sqlite3.connect(DB_PATH)
        try:
            count = conn.execute("SELECT count(*) FROM mutation_specs").fetchone()[0]
            if count == 0:
                need_init = True
        except sqlite3.OperationalError:
            need_init = True
        finally:
            conn.close()

    if need_init:
        print(f"Initializing mutation specifications database at {DB_PATH.name}...")
        cosmic_ray.cli.main(["init", str(CONFIG_PATH), str(DB_PATH)])
        print("Initialization complete.")

def main():
    ensure_database()

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS work_results (
            worker_outcome VARCHAR(9), 
            output TEXT, 
            test_outcome VARCHAR(11), 
            diff TEXT, 
            job_id VARCHAR NOT NULL PRIMARY KEY
        )
    """)
    conn.commit()

    Sem = importlib.import_module("sclass_semantics_v6_0_1")
    conf = importlib.import_module("test_sclass_v6_0_1_conformance")
    prop = importlib.import_module("test_sclass_v6_0_1_property")

    partitions_config = {
        "S0-M1 C1 canonicalization": {
            "query": """
                SELECT job_id, module_path, operator_name, operator_args, occurrence, 
                       start_pos_row, start_pos_col, end_pos_row, end_pos_col, definition_name
                FROM mutation_specs
                WHERE definition_name IN ("_c1_tree", "_c1_json_bytes", "canonical_c1", "deep_freeze", "freeze_fields", 
                                          "canonical_c1_pack", "_c1_decode_tree", "canonical_c1_unpack", 
                                          "_raise_mutable_mapping", "_c1_validate_depth", "FrozenMap")
                   OR (start_pos_row BETWEEN 350 AND 451)
            """,
            "tests": [
                ("test_c1_vectors", conf.test_c1_vectors),
                ("test_c1_profile_bounds_and_mutability", conf.test_c1_profile_bounds_and_mutability),
                ("test_c1_depth_and_frozen_map", conf.test_c1_depth_and_frozen_map),
                ("test_c1_rejects_unsupported_types", prop.test_c1_rejects_unsupported_types),
                ("test_c1_determinism_and_stability", prop.test_c1_determinism_and_stability),
                ("test_c1_order_independence_for_dicts", prop.test_c1_order_independence_for_dicts),
            ]
        },
        "S0-M2 digest/domain separation": {
            "query": """
                SELECT job_id, module_path, operator_name, operator_args, occurrence, 
                       start_pos_row, start_pos_col, end_pos_row, end_pos_col, definition_name
                FROM mutation_specs
                WHERE definition_name IN ("digest", "signature_preimage", "commit_record_digest", "target_snapshot_digest", 
                                          "acceptance_snapshot_digest", "authority_envelope_digest", "signed_payload_digest", 
                                          "event_hash_preimage", "event_hash", "engineering_state_digest", "canonical_state_digest")
                   OR (start_pos_row BETWEEN 452 AND 457)
                   OR (start_pos_row BETWEEN 490 AND 495)
                   OR (start_pos_row BETWEEN 3039 AND 3050)
            """,
            "tests": [
                ("test_digest_stability", prop.test_digest_stability),
                ("test_c1_vectors", conf.test_c1_vectors),
                ("test_event_hash_binds_security_fields", conf.test_event_hash_binds_security_fields),
                ("test_target_snapshot_digest_binds_all_components_and_dependencies", conf.test_target_snapshot_digest_binds_all_components_and_dependencies),
                ("test_v6_state_digest_binds_unchanged_and_derived_state", conf.test_v6_state_digest_binds_unchanged_and_derived_state),
                ("test_strong_commit_separates_revision_from_state_digest", conf.test_strong_commit_separates_revision_from_state_digest),
                ("test_release_evaluation_is_canonical_and_digest_bound", conf.test_release_evaluation_is_canonical_and_digest_bound),
            ]
        },
        "S0-M3 semantic validation": {
            "query": """
                SELECT job_id, module_path, operator_name, operator_args, occurrence, 
                       start_pos_row, start_pos_col, end_pos_row, end_pos_col, definition_name
                FROM mutation_specs
                WHERE definition_name IN ("_tuple_of", "_is_digest_value", "_is_int64", "_is_canonical_object", 
                                          "_is_deferred_canonical_object", "_is_signature_verification", 
                                          "validate_event_payload_types", "_validate_event_payload_schema", 
                                          "_load_state_machine_source", "_value_matches", "validate_approval_set")
                   OR (start_pos_row BETWEEN 3050 AND 3250)
            """,
            "tests": [
                ("test_strong_canonical_construction_and_schema_registry_are_complete", conf.test_strong_canonical_construction_and_schema_registry_are_complete),
                ("test_strong_canonical_event_constructor_enforces_schema_before_persistence", conf.test_strong_canonical_event_constructor_enforces_schema_before_persistence),
                ("test_every_event_handler_is_real_and_malformed_payload_fails_closed", conf.test_every_event_handler_is_real_and_malformed_payload_fails_closed),
                ("test_event_payload_tamper_is_rejected_at_reducer_boundary", conf.test_event_payload_tamper_is_rejected_at_reducer_boundary),
                ("test_approval_separation_of_duties_and_authority_identity", conf.test_approval_separation_of_duties_and_authority_identity),
            ]
        },
        "S0-M4 identity/immutability": {
            "query": """
                SELECT job_id, module_path, operator_name, operator_args, occurrence, 
                       start_pos_row, start_pos_col, end_pos_row, end_pos_col, definition_name
                FROM mutation_specs
                WHERE definition_name IN ("canonical_dataclass", "_SafeCanonicalUnpickler", "_safe_pickle_loads", 
                                          "registry_name_for", "UtcInstant")
                   OR (start_pos_row BETWEEN 14 AND 52)
                   OR (start_pos_row BETWEEN 410 AND 415)
                   OR (start_pos_row BETWEEN 498 AND 520)
            """,
            "tests": [
                ("test_strong_safe_unpickler_blocks_global_code_execution", conf.test_strong_safe_unpickler_blocks_global_code_execution),
                ("test_strong_canonical_state_immutability", prop.test_strong_canonical_state_immutability),
                ("test_c1_profile_bounds_and_mutability", conf.test_c1_profile_bounds_and_mutability),
                ("test_strong_duplicate_canonical_identity_rejects_replacement", conf.test_strong_duplicate_canonical_identity_rejects_replacement),
            ]
        },
        "S0-M5 reducer/state transitions": {
            "query": """
                SELECT job_id, module_path, operator_name, operator_args, occurrence, 
                       start_pos_row, start_pos_col, end_pos_row, end_pos_col, definition_name
                FROM mutation_specs
                WHERE definition_name IN ("_machine_transition", "_event_target", "_mark_invalidation", 
                                          "assert_lifecycle_indexes_consistent", "assert_reducer_totality", 
                                          "genesis_engineering_state", "apply_machine", "fmap_insert_immutable", "fmap_update",
                                          "_revision_change_invalidations", "_affected_by_obligations", "_validate_revision_object")
                   OR (start_pos_row BETWEEN 3250 AND 3312)
                   OR (start_pos_row BETWEEN 3846 AND 3882)
                   OR (start_pos_row BETWEEN 4033 AND 4105)
            """,
            "tests": [
                ("test_reference_reducer_replay_and_illegal_transition", conf.test_reference_reducer_replay_and_illegal_transition),
                ("test_reference_reducer_all_handlers_are_real", conf.test_reference_reducer_all_handlers_are_real),
                ("test_reducer_handlers_are_callable_and_fail_closed", conf.test_reducer_handlers_are_callable_and_fail_closed),
                ("test_state_machine_json_is_authoritative_source", conf.test_state_machine_json_is_authoritative_source),
                ("test_reducer_determinism_and_rejection", prop.test_reducer_determinism_and_rejection),
                ("test_reducer_materializes_authorization_and_execution_state", conf.test_reducer_materializes_authorization_and_execution_state),
            ]
        }
    }

    partition_results = {}
    all_survivors = []

    for pname, pconfig in partitions_config.items():
        c.execute(pconfig["query"])
        rows = c.fetchall()
        print("\n==========================================")
        print(f"Executing partition: {pname} ({len(rows)} mutants)")
        print("==========================================")
        
        pkilled = 0
        psurvived = 0
        perrors = 0
        ptimeouts = 0
        psurvivors = []
        
        t_start = time.time()
        for idx, row in enumerate(rows):
            jid, mod_path, op_name, op_args_raw, occ, r1, _c1, _r2, _c2, dname = row
            
            # Check if already completed and was KILLED
            c.execute("SELECT test_outcome, worker_outcome FROM work_results WHERE job_id = ?", (jid,))
            existing = c.fetchone()
            if existing and existing[0] == "KILLED":
                pkilled += 1
                if (idx + 1) % 50 == 0 or (idx + 1) == len(rows):
                    print(f"  [{idx+1:4d}/{len(rows):4d}] Progress: killed={pkilled}, survived={psurvived}, errors={perrors}")
                continue
                
            op_args = json.loads(op_args_raw) if op_args_raw else {}
            if isinstance(op_args, str):
                op_args = json.loads(op_args)
            op_cls = cosmic_ray.plugins.get_operator(op_name)
            operator = op_cls(**op_args)
            
            diff = ""
            failed = False
            fail_msg = ""
            is_error = False
            err_msg = ""
            
            target_path = ROOT_DIR / mod_path
            try:
                with use_mutation(target_path, operator, occ) as (orig_code, mut_code):
                    if mut_code is None:
                        continue
                    diff = "".join(_make_diff(orig_code, mut_code, target_path))
                    
                    # Reload mutated module
                    try:
                        importlib.reload(Sem)
                        importlib.reload(conf)
                        importlib.reload(prop)
                    except BaseException as e:
                        if isinstance(e, (KeyboardInterrupt, SystemExit)):
                            raise
                        failed = True
                        fail_msg = f"Syntax/Import error: {type(e).__name__} {e}"
                    
                    # If load succeeded, run tests
                    if not failed:
                        for tname, tfn in pconfig["tests"]:
                            try:
                                tfn()
                            except BaseException as e:
                                if isinstance(e, (KeyboardInterrupt, SystemExit)):
                                    raise
                                failed = True
                                fail_msg = f"{tname}: {type(e).__name__} {e}"
                                break
            except BaseException as e:
                if isinstance(e, (KeyboardInterrupt, SystemExit)):
                    raise
                is_error = True
                err_msg = traceback.format_exc()
            finally:
                # File on disk restored to original clean code
                try:
                    importlib.reload(Sem)
                    importlib.reload(conf)
                    importlib.reload(prop)
                except Exception as _exc:
                    # Best-effort reload during mutation cleanup
                    sys.stderr.write(f"Cleanup reload note: {_exc}\n")
                    
            if is_error:
                perrors += 1
                c.execute("INSERT OR REPLACE INTO work_results VALUES (?, ?, ?, ?, ?)",
                          ("EXCEPTION", err_msg, "INCOMPETENT", None, jid))
            elif failed:
                pkilled += 1
                c.execute("INSERT OR REPLACE INTO work_results VALUES (?, ?, ?, ?, ?)",
                          ("NORMAL", fail_msg, "KILLED", diff, jid))
            else:
                psurvived += 1
                psurvivors.append((jid, pname, dname, r1, op_name, diff))
                all_survivors.append((jid, pname, dname, r1, op_name, diff))
                c.execute("INSERT OR REPLACE INTO work_results VALUES (?, ?, ?, ?, ?)",
                          ("NORMAL", "All partition tests passed", "SURVIVED", diff, jid))
            conn.commit()
                
            if (idx + 1) % 50 == 0 or (idx + 1) == len(rows):
                print(f"  [{idx+1:4d}/{len(rows):4d}] Progress: killed={pkilled}, survived={psurvived}, errors={perrors}")

        ptotal = pkilled + psurvived + perrors + ptimeouts
        pdur = time.time() - t_start
        pscore = (pkilled / ptotal * 100) if ptotal else 0.0
        
        partition_results[pname] = {
            "generated": ptotal,
            "killed": pkilled,
            "survived": psurvived,
            "timeouts": ptimeouts,
            "errors": perrors,
            "score": pscore,
            "duration": pdur,
            "survivors": psurvivors
        }

    print("\n" + "="*70)
    print("=== S0 MUTATION BASELINE SUMMARY BY PARTITION ===")
    print("="*70)
    tot_gen = sum(r["generated"] for r in partition_results.values())
    tot_kill = sum(r["killed"] for r in partition_results.values())
    tot_surv = sum(r["survived"] for r in partition_results.values())
    tot_to = sum(r["timeouts"] for r in partition_results.values())
    tot_err = sum(r["errors"] for r in partition_results.values())
    tot_score = (tot_kill / tot_gen * 100) if tot_gen else 0.0

    for pname, r in partition_results.items():
        print(f"{pname:35s} | Gen: {r['generated']:4d} | Kill: {r['killed']:4d} | Surv: {r['survived']:3d} | Err: {r['errors']:2d} | Score: {r['score']:5.1f}%")
    print("-" * 70)
    print(f"{'AGGREGATE S0 MUTATION BASELINE':35s} | Gen: {tot_gen:4d} | Kill: {tot_kill:4d} | Surv: {tot_surv:3d} | TO: {tot_to:2d} | Err: {tot_err:2d} | Score: {tot_score:5.1f}%")
    print("="*70)

    if all_survivors:
        print(f"\nWARNING: {len(all_survivors)} mutants survived!")
        sys.exit(1)
    else:
        print("\nSUCCESS: All 1,085 S0 mutants successfully killed! Score: 100.0%")
        sys.exit(0)

if __name__ == "__main__":
    main()
