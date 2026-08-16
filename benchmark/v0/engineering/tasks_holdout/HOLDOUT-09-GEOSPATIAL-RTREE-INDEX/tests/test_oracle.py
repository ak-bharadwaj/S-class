from target_module import RTreeSpatialIndex

def test_rtree_insert_search():
    idx = RTreeSpatialIndex()
    idx.insert('item1', (0, 0, 10, 10))
    idx.insert('item2', (50, 50, 60, 60))
    res = idx.search((5, 5, 15, 15))
    assert 'item1' in res
    assert 'item2' not in res
