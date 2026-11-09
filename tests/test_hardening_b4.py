"""Hardening round 4: one regression per defect found."""

from pathlib import Path

import os
import subprocess
import sys

import pytest

from rung_engine import RungError, api, hook
from rung_engine.claims import canonical_rid, rids_in
from rung_engine.service import Service
from support import seed
from test_hardening_b1 import _ai_spec, _decide, _todo, failing, tool  # noqa: F401  (fixtures)

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "desktop" / "src"


def _cli(store, *args):
    env = dict(os.environ, RUNG_STORE=str(store))
    return subprocess.run([sys.executable, "-m", "rung_engine.cli", *args], cwd=ROOT, env=env, capture_output=True,
                          text=True)


# ------------------------------------------------------------------ the done hook


def test_r4_a_store_gone_missing_is_unreadable_not_empty(failing, tool, tmp_path):
    e, _ = failing
    tool("rung_claim", {"spec": "S-2.1"})
    done = _todo(("t1", "Ship S-2.1", "completed"))
    assert hook.decide("todo_list", done, "sess-1", store=tmp_path / "moved.db") is None  # fail open
    assert _decide(e, "todo_list", done)  # judged once the store is back


@pytest.mark.parametrize("mark", ["\u034f", "\ufe0f", "\u115f", "\u180b", "\u3164"])
def test_r4_a_glyphless_character_inside_the_id_still_names_the_spec(failing, tool, mark):
    e, _ = failing
    tool("rung_claim", {"spec": "S-2.1"})
    assert _decide(e, "todo_list", _todo(("t1", f"Ship S-{mark}2.1", "completed")))
    assert canonical_rid(f"S{mark}-2.1") == "S-2.1"
    assert rids_in(f"Ship S-2{mark}.1") == ["S-2.1"]


def test_r4_a_malformed_report_is_left_to_the_tool(failing, tool):
    e, _ = failing
    tool("rung_claim", {"spec": "S-2.1"})
    assert _decide(e, "rung_report", {"spec": "S-2.1", "project": ["csvtidy"]}) is None
    assert _decide(e, "rung_report", {"spec": "S-2.1"})  # well formed: still blocked


# ------------------------------------------------------------------ ids at every door


@pytest.mark.parametrize("rid", ["s-2.1", " S 2.1 ", "S\u20112.1", "S\u200b-2.1"])
def test_r4_a_retired_need_is_read_only_under_every_id_form(failing, rid):
    e, _ = failing
    e.retire_need("csvtidy", "N-1", "dropped")
    with pytest.raises(RungError, match="retired"):
        e.claim("csvtidy", rid, "s1", "chat", "coder")
    with pytest.raises(RungError, match="retired"):
        e.set_allocation("csvtidy", rid, independent=True)


def test_r4_every_door_echoes_the_stored_id(failing):
    e, _ = failing
    assert e.suggest("csvtidy", "s-2.1")["spec"] == "S-2.1"
    assert e.check("csvtidy", " S 2.1 ")["id"] == "S-2.1"
    with pytest.raises(RungError) as x:
        e.report("csvtidy", "s-2.1", "nobody")
    assert "S-2.1" in str(x.value) and "s-2.1" not in str(x.value)


def test_r4_cli_release_names_the_stored_id(failing):
    e, _ = failing
    e.claim("csvtidy", "S-2.1", "s1", "chat", "coder")
    out = _cli(e.path, "--project", "csvtidy", "claims", "release", "s-2.1")
    assert out.returncode == 0, out.stderr
    assert out.stdout.startswith("S-2.1: released"), out.stdout


# ------------------------------------------------------------------ claims and carriers


def test_r4_an_independent_spec_is_not_reported_by_a_holder_who_wrote_a_test(failing, tool):
    e, restore = failing
    e.set_allocation("csvtidy", "S-2.1", independent=True)
    assert "error" not in tool("rung_claim", {"spec": "S-2.1"}, profile="writer")
    tool("rung_propose", {"parent": "S-2.1", "text": "Reads 2024-02-30 as an error"}, profile="writer")
    restore()
    e.run_test("csvtidy", "T-2.1a", carried_by="writer")
    out = tool("rung_report", {"spec": "S-2.1"}, profile="writer")
    assert "different profile from the author" in out.get("error", "") and "author of" in out["error"]
    assert any(c["status"] == "open" for c in e.claims("csvtidy"))


def test_r4_tests_proposed_by_drafting_are_the_drafting_profiles(seeded, svc, monkeypatch):
    from test_flow import _specs_step
    e = _specs_step(svc)
    e.set_setting("drafting", {"kind": "stub", "delay": 0.0, "profile": "writer"})
    svc.set_authoring("csvtidy", "R-4", "ai", wait=True)
    svc.set_authoring("csvtidy", "R-5", "ai", wait=True)
    e.write_spec("csvtidy", "R-6", "Preserve column order from the first file")
    e.approve_drafted("csvtidy", "N-2")
    actors = []
    real = e.add_test
    monkeypatch.setattr(e, "add_test", lambda p, rid, f, actor=None: (actors.append(actor), real(p, rid, f, actor))[1])
    assert svc.propose_tests("csvtidy", "N-2")
    assert actors and {a.name for a in actors} == {"writer"}
    assert "writer" in e._authors(e._rung_row("csvtidy", "S-4.1"))


def test_r4_removing_a_profile_that_holds_a_claim_is_refused(failing):
    e, _ = failing
    e.claim("csvtidy", "S-2.1", "s1", "chat", "coder")
    profiles = [x for x in e.project("csvtidy")["profiles"] if x != "coder"] or ["writer"]
    with pytest.raises(RungError, match="coder holds the claim on S-2.1"):
        e.update_project("csvtidy", profiles=profiles)


@pytest.mark.parametrize("op", ["archive", "delete", "retire"])
def test_r4_busy_checks_run_inside_the_write(failing, op, monkeypatch):
    e, _ = failing
    seen = []
    real = e._refuse_while_busy
    monkeypatch.setattr(e, "_refuse_while_busy", lambda *a, **k: (seen.append(getattr(e, "_tx_depth", 0)), real(*a, **k))[1])
    {"archive": lambda: e.archive_project("csvtidy"),
     "delete": lambda: (e.archive_project("csvtidy"), e.delete_project("csvtidy", "csvtidy")),
     "retire": lambda: e.retire_need("csvtidy", "N-1", "dropped")}[op]()
    assert seen and all(d >= 1 for d in seen)


def test_r4_running_counts_open_claims_like_the_dock(failing):
    e, _ = failing
    before = e.tiles("csvtidy")["running"]
    e.claim("csvtidy", "S-2.1", "s1", "chat", "coder")
    assert e.tiles("csvtidy")["running"] == before + 1


# ------------------------------------------------------------------ REST


def test_r4_settings_tools_null_is_refused_not_ignored(seeded):
    svc = Service(seeded, inline_runs=True)
    st, out = api.handle(svc, "POST", "/settings", {"profiles": [{"name": "coder", "tools": None}]})
    assert st == 400 and out.get("field") == "tools"


def test_r4_defaults_with_a_non_text_folder_names_the_field(seeded):
    svc = Service(seeded, inline_runs=True)
    st, out = api.handle(svc, "POST", "/projects/defaults", {"folder": 5})
    assert st == 400 and out.get("field") == "folder" and "attribute" not in str(out)


def test_r4_a_negative_run_id_is_named_for_what_it_is(seeded):
    svc = Service(seeded, inline_runs=True)
    st, out = api.handle(svc, "POST", "/runs/-1/cancel", {})
    assert st == 400 and "0 or more" in out["detail"]


# ------------------------------------------------------------------ the pane


def _src(name):
    return (SRC / name).read_text()


def test_r4_a_released_spec_reads_released_on_its_page_as_in_the_ladder():
    det = _src("40-detail.js")
    assert "r.released ? h(Badge, { status: 'released' })" in det
    assert "r.released ? h(Badge, { status: 'covered' })" not in det


def test_r4_a_failed_draft_reads_draft_failed_in_dock_rail_and_page():
    dock, core, det = _src("70-dock.js"), _src("00-core.js"), _src("40-detail.js")
    assert "n.draft_state === 'failed') return 'draft failed'" in dock
    assert "node.draft_state === 'failed'" in core
    assert "status: 'draft_failed'" in det and "'data-testid': 'draft-error'" in det


def test_r4_an_untouched_output_limit_saves_as_stored():
    assert "s.output_limit_label == null ? s.output_limit" in _src("20-home.js")
