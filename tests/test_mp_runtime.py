import os
import sys
import shutil
import multiprocessing
import runtime

def mp_decision_worker(workspace, iters, worker_idx, err_list):
    for i in range(iters):
        try:
            runtime.log_decision(
                decision=f"dec_p{worker_idx}_{i}",
                reason=f"reason_p{worker_idx}_{i}",
                agent=f"agent_p{worker_idx}",
                confidence=0.9,
                workspace_dir=workspace
            )
        except Exception as e:
            err_list.append(f"Worker {worker_idx} error: {e}")

def test_mp_runtime_decisions(lock_type="FileLock"):
    ws = os.path.abspath(f"test_runtime_mp_{lock_type}")
    if os.path.exists(ws):
        shutil.rmtree(ws)
    os.makedirs(ws)

    state = runtime.initialize_state(workspace_dir=ws, goal="mp test")
    init_decisions = len(state.decisionLog)

    if lock_type == "NativeLock":
        from file_lock import NativeLock
        runtime.FileLock = NativeLock

    num_procs = 4
    iters = 10
    mgr = multiprocessing.Manager()
    err_list = mgr.list()

    procs = []
    for p_idx in range(num_procs):
        p = multiprocessing.Process(target=mp_decision_worker, args=(ws, iters, p_idx, err_list))
        procs.append(p)
        p.start()

    for p in procs:
        p.join()

    final_state = runtime.get_state(ws)
    actual = len(final_state.decisionLog) - init_decisions
    expected = num_procs * iters
    print(f"[{lock_type}] Actual: {actual}/{expected}, Errors: {len(err_list)}")

    shutil.rmtree(ws)
    assert actual == expected

if __name__ == "__main__":
    fl_ok = test_mp_runtime_decisions("FileLock")
    nl_ok = test_mp_runtime_decisions("NativeLock")
    print("Multi-process Runtime Results: FileLock:", fl_ok, "NativeLock:", nl_ok)
