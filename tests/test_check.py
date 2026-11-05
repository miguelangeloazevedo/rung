import subprocess

from rung_engine import drafting


def test_check_never_calls_a_model(seeded, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("model call during check")

    monkeypatch.setattr(drafting.StubDrafter, "derive_spec", boom)
    monkeypatch.setattr(drafting.ProfileDrafter, "_ask", boom)
    real = subprocess.Popen

    def guarded(argv, *a, **k):
        if argv and "hermes" in str(argv[0]):
            raise AssertionError("hermes launched during check")
        return real(argv, *a, **k)

    monkeypatch.setattr(subprocess, "Popen", guarded)
    assert seeded.check("csvtidy", "S-2.1")["ok"]
    assert seeded.check_all("csvtidy")["ok"]


def test_check_all_false_when_any_fails(seeded):
    seeded.edit("csvtidy", "R-1", text="Detect the delimiter automatically, including pipes", approve=True)
    res = seeded.check_all("csvtidy")
    assert not res["ok"]
    assert [r["id"] for r in res["results"] if not r["ok"]] == ["S-1.1"]
