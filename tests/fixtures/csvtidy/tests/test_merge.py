from csvtidy.merge import merge


A = [["id", "name"], ["1", "Ada"], ["2", "Bo"], ["3", "Cy"]]
B = [["id", "city"], ["1", "Ghent"], ["3", "Lyon"], ["4", "Oslo"]]


def test_join_key():
    rows, _ = merge(A, B, key="id")
    assert rows[0] == ["id", "name", "city"]
    assert rows[1:] == [["1", "Ada", "Ghent"], ["3", "Cy", "Lyon"]]


def test_unmatched():
    _, unmatched = merge(A, B, key="id")
    assert unmatched == {"first": ["2"], "second": ["4"]}
