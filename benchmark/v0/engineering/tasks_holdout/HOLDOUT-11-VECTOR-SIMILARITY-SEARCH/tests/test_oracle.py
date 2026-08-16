from target_module import VectorSimilaritySearchIndex

def test_vector_search():
    idx = VectorSimilaritySearchIndex(dimension=3, metric='cosine')
    idx.insert('v1', [1.0, 0.0, 0.0])
    idx.insert('v2', [0.0, 1.0, 0.0])
    res = idx.search([0.9, 0.1, 0.0], top_k=1)
    assert len(res) == 1
    assert res[0][0] == 'v1'
