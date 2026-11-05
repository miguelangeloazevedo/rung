from rung_engine import Actor

from test_flow import _new_need


def test_need_edit_makes_requirements_stale(seeded, svc):
    e = seeded
    _new_need(svc)
    e.add_requirement("csvtidy", "N-2", "Keep the first file\'s column order")
    e.approve_requirements("csvtidy", "N-2")
    before = e.tiles("csvtidy")["needs_you"]
    e.edit("csvtidy", "N-2", text="Merge two or more CSV exports by a shared key", approve=True)
    for r in ("R-4", "R-5", "R-6"):
        assert e.rung("csvtidy", r)["status"] == "stale"
    assert e.tiles("csvtidy")["needs_you"] == before + 3
    ch = e.changes("csvtidy", "N-2")[0]
    assert ch["before"] == "Merge two CSV exports by a shared key"
    assert ch["after"] == "Merge two or more CSV exports by a shared key"
    assert ch["stale"] == ["R-4", "R-5", "R-6"]
    assert [h["text"] for h in e.history("csvtidy", "N-2")] == [
        "Merge two CSV exports by a shared key", "Merge two or more CSV exports by a shared key"]
    for r in ("R-4", "R-5", "R-6"):
        e.approve("csvtidy", r)
    assert e.tiles("csvtidy")["needs_you"] == before


def test_upstream_change_invalidates_passes(seeded, svc):
    e = seeded
    assert e.check("csvtidy", "S-2.1")["ok"]
    assert e.coverage("csvtidy", "R-2") == "covered"
    n0 = e.tiles("csvtidy")["needs_you"]
    e.edit("csvtidy", "R-2", text="Normalise every date to ISO 8601, keeping the time when present", approve=True)
    assert e.rung("csvtidy", "S-2.1")["status"] == "stale"
    assert e.rung("csvtidy", "T-2.1a")["status"] == "stale"
    assert e.rung("csvtidy", "T-2.1b")["status"] == "approved"  # never run: nothing to invalidate
    ex = e.executions("csvtidy", "T-2.1a")
    assert ex[0]["status"] == "pass" and not ex[0]["counts"] and ex[0]["invalidated"]
    assert e.coverage("csvtidy", "R-2") == "stale"
    assert e.tiles("csvtidy")["needs_you"] == n0 + 1
    item = [i for i in e.needs_you("csvtidy") if i["type"] == "stale"][0]
    assert item["id"] == "S-2.1"
    assert item["change"]["before"] == "Normalise every date to ISO 8601"
    assert set(item["change"]["stale"]) == {"S-2.1", "T-2.1a"}
    chk = e.check("csvtidy", "S-2.1")
    assert not chk["ok"] and any("S-2.1 is stale" in b for b in chk["blockers"])
    e.approve("csvtidy", "S-2.1")
    assert e.tiles("csvtidy")["needs_you"] == n0
    assert e.rung("csvtidy", "T-2.1a")["status"] == "approved"
    chk = e.check("csvtidy", "S-2.1")
    assert not chk["ok"] and any("has not passed since" in b for b in chk["blockers"])
    assert e.coverage("csvtidy", "R-2") != "covered"
    e.run_test("csvtidy", "T-2.1a")
    assert e.check("csvtidy", "S-2.1")["ok"]
    assert e.coverage("csvtidy", "R-2") == "covered"
    assert e.check_all("csvtidy")["ok"]


def test_proposals(seeded):
    e = seeded
    n0 = e.tiles("csvtidy")["needs_you"]
    p = e.propose("csvtidy", "N-1", "requirement", "Accept a two-digit year only with --century", proposer="coder",
                  source_chat="Fix date parsing in csvtidy")
    assert p["status"] == "proposed" and p["id"] == "R-4"
    items = [i for i in e.needs_you("csvtidy") if i["type"] == "proposed"]
    assert items[0]["proposer"] == "coder" and items[0]["source_chat"] == "Fix date parsing in csvtidy"
    assert e.tiles("csvtidy")["needs_you"] == n0 + 1
    try:
        e.approve("csvtidy", "R-4", Actor("agent", "coder"))
        raise AssertionError("agent approved")
    except Exception as exc:
        assert "human" in str(exc)
    e.approve("csvtidy", "R-4")
    assert e.rung("csvtidy", "R-4")["status"] == "approved"
    q = e.propose("csvtidy", "N-1", "requirement", "Guess the encoding", proposer="coder", source_chat="x")
    e.dismiss("csvtidy", q["id"])
    assert all(r["text"] != "Guess the encoding" for n in e.tree("csvtidy") for r in n["children"])
    assert e.tiles("csvtidy")["needs_you"] == n0
