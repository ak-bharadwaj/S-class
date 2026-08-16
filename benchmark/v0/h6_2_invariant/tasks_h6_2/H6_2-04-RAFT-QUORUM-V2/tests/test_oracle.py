from target_module import RaftQuorumV2
def test_raft_l1():
    q = RaftQuorumV2(5)
    assert q.is_committed(3, 2, 2) is True
    assert q.is_committed(2, 2, 2) is False
