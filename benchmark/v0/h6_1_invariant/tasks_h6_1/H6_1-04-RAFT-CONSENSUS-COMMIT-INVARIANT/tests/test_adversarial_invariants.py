from target_module import RaftCommitGuard

def test_raft_adversarial_probes():
    g = RaftCommitGuard(cluster_size=5)
    # Probe 1: Term mismatch commit attempt (stale leader term)
    assert g.is_committed(replica_ack_count=5, entry_term=1, current_term=2) is False
    # Probe 2: Split vote tie (2 acks in size 5 cluster)
    assert g.is_committed(replica_ack_count=2, entry_term=2, current_term=2) is False
    # Probe 3: Zero acks
    assert g.is_committed(replica_ack_count=0, entry_term=2, current_term=2) is False
