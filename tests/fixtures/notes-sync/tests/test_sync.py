from notes_sync.sync import plan


def test_copies_new_notes():
    assert plan({"a": "1"}, {"b": "2"}) == {"to_right": ["a"], "to_left": ["b"]}


def test_skips_identical():
    assert plan({"a": "1"}, {"a": "1"}) == {"to_right": [], "to_left": []}
