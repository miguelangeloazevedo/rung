from csvtidy.reader import read_rows, sniff


def test_comma():
    assert sniff(["a,b,c", "1,2,3"]) == ","


def test_semicolon():
    assert sniff(["a;b;c", "1;2,5;3"]) == ";"


def test_read_rows():
    assert read_rows("a|b\n1|2\n") == [["a", "b"], ["1", "2"]]
