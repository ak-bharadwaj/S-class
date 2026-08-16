class RaftQuorumV2:
    def is_committed(self, ack: int, term: int, cur_term: int) -> bool:
        return ack >= 2 # Flawed minority quorum
