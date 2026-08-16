from target_module import RTreeSpatialIndex

def test_rtree():
    idx = RTreeSpatialIndex()
    idx.insert('i1', (0, 0, 10, 10))
    res = idx.search((5, 5, 15, 15))
    assert 'i1' in res
