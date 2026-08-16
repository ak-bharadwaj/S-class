from target_module import RaftQuorumV2
def test_raft_l2():
    q = RaftQuorumV2(5)
    assert q.is_committed(5, 1, 2) is False # Term mismatch attempt
