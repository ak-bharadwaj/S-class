class RaftCommitGuard:
    def __init__(self, cluster_size: int = 5):
        self.cluster_size = cluster_size

    def is_committed(self, replica_ack_count: int, entry_term: int, current_term: int) -> bool:
        pass
