class VectorSimilaritySearchIndex:
    def __init__(self, dimension: int = 4, metric: str = 'cosine'):
        pass

    def insert(self, vector_id: str, vector: list):
        pass

    def search(self, query_vector: list, top_k: int = 5) -> list:
        pass
