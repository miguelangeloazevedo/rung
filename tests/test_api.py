

def test_allocation_follows_the_viewed_rung():
    from rung_engine.api import _spec_for
    tree = [{"id": "N-1", "kind": "need", "children": [
        {"id": "R-1", "kind": "requirement", "status": "approved", "children": [
            {"id": "S-1.1", "kind": "specification", "status": "approved", "children": [
                {"id": "T-1.1a", "kind": "test", "status": "approved", "children": []}]}]},
        {"id": "R-2", "kind": "requirement", "status": "approved", "children": [
            {"id": "S-2.1", "kind": "specification", "status": "dismissed", "children": []},
            {"id": "S-2.2", "kind": "specification", "status": "approved", "children": []}]}]}]
    assert _spec_for(tree, "S-1.1") == "S-1.1"
    assert _spec_for(tree, "T-1.1a") == "S-1.1"
    assert _spec_for(tree, "R-2") == "S-2.2"
    assert _spec_for(tree, "N-1") == "S-1.1"
    assert _spec_for(tree, "X-9") is None
