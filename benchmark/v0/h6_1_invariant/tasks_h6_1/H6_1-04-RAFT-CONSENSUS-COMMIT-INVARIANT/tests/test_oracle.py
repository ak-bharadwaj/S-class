from target_module import RaftCommitGuard

def test_raft_basic():
    g = RaftCommitGuard(cluster_size=5)
    assert g.is_committed(replica_ack_count=3, entry_term=2, current_term=2) is True
    assert g.is_committed(replica_ack_count=2, entry_term=2, current_term=2) is False
