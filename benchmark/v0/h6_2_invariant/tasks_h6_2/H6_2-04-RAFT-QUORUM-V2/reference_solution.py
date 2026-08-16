class RaftQuorumV2:
    def __init__(self, size=5): self.size = size
    def is_committed(self, ack: int, term: int, cur_term: int) -> bool:
        return ack > (self.size // 2) and term == cur_term
