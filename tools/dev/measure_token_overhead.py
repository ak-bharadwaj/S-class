"""Tooling to measure token savings in minimal projection contexts."""
def calculate_token_reduction(raw_context_len: int, projected_len: int) -> float:
    if raw_context_len == 0:
        return 0.0
    return ((raw_context_len - projected_len) / raw_context_len) * 100.0

if __name__ == "__main__":
    reduction = calculate_token_reduction(50000, 800)
    print(f"Token reduction: {reduction:.2f}% (98.4% achieved)")
