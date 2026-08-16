class DistributedCacheInvalidator:
    def __init__(self):
        pass

    def set(self, key: str, value: str, version: int, ttl_sec: int = 60) -> bool:
        pass

    def get(self, key: str):
        pass

    def invalidate(self, key: str, version: int) -> bool:
        pass
