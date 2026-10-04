# Cgroup v2 Subtree Delegation & Resource Containment

## 1. Zero Privilege Escalation Invariant

S-Class runtime processes operate under the principle of least privilege. **S-Class never escalates privileges itself: there is zero invocation of `sudo`, `setuid`, or root capabilities inside the runtime.**

To enforce resource ceilings (§8.6, §18) including:
- Memory limits (`memory.max`)
- Swap containment (`memory.swap.max`)
- Process count ceilings (`pids.max`)
- CPU time quotas (`cpu.max`)
- Guaranteed process-tree termination (`cgroup.kill` and cgroup membership tracking)

the host deployer must provide a **delegated cgroup v2 subtree** writable by the unprivileged S-Class service user.

---

## 2. Deployer / System Administrator Setup

The host deployer establishes the delegated hierarchy prior to starting the S-Class service:

```bash
# 1. Create the delegated S-Class cgroup v2 subtree
sudo mkdir -p /sys/fs/cgroup/sclass

# 2. Grant ownership to the unprivileged service user
sudo chown -R $SERVICE_USER:$SERVICE_USER /sys/fs/cgroup/sclass

# 3. Enable subtree controllers in root and delegated hierarchy
echo "+memory +pids +cpu" | sudo tee /sys/fs/cgroup/cgroup.subtree_control || true
echo "+memory +pids +cpu" | sudo tee /sys/fs/cgroup/sclass/cgroup.subtree_control || true
```

---

## 3. Runtime Subtree Discovery and Lifecycle

1. **Subtree Path Discovery**:
   - `LinuxExecutionBoundary` checks if an explicit `cgroup_root` argument is provided to its constructor.
   - If not specified, it probes for the default delegated subtree `/sys/fs/cgroup/sclass`.
   - If `/sys/fs/cgroup/sclass` does not exist, it falls back to `/sys/fs/cgroup`.
2. **Hierarchy Validation**:
   - `_assert_cgroup_v2()` verifies that cgroup v2 controllers are available and that the delegated root directory is writable (`os.access(self.cgroup_root, os.W_OK)`).
   - If unwritable or controllers are missing, S-Class immediately raises `BoundaryUnavailable` fail-closed before any subprocess is executed.
3. **Leaf Allocation**:
   - For each authorized execution lease, S-Class creates a unique transient leaf cgroup:
     `/sys/fs/cgroup/sclass/sclass-<pid>-<token>`
   - It populates `memory.max`, `pids.max`, and `cpu.max` in accordance with the authorized `ResourceBudget`.
   - The worker process PID is bound to `cgroup.procs`.
4. **Cleanup and Teardown**:
   - Upon process completion, timeout, or boundary exit, all descendant processes within the cgroup are terminated with `SIGKILL` (via `cgroup.kill` and process table scanning).
   - Once all processes exit, S-Class safely removes the transient leaf directory.
