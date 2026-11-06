"""UC24 The done hook: while a claimed specification fails `rung check`, Rung's `pre_tool_call` hook
blocks the claiming session's completion calls (todo items naming it, by content or by an id that
named it earlier, `kanban_complete`, `rung_report`), deterministically and without a model call."""

import harness as H
import chatting as C
from support import seed

BLOCK = "Blocked by Rung"


def blocked(out: str) -> bool:
    return BLOCK in out and "S-2.1" in out and "T-2.1a" in out


def todo_state(page) -> str:
    out = C.turn(page, "todo show")
    return out


def test_clm05_clm06_clm07_clm08_done_hook(rung, csvtidy, page):
    e = rung.engine
    restore = seed.seed_failing(e, csvtidy)
    try:
        H.open_rung(page)
        C.use_profile(page, "coder")
        C.new_session(page)
        assert '"claimed": "S-2.1"' in C.turn(page, "claim rung S-2.1")
        session = C.route(page)

        # 1. Four completion calls, each blocked, naming S-2.1 and the blocking rung.
        out = C.turn(page, "todo add t1: Finish S-2.1 date parsing")
        assert BLOCK not in out and '"pending": 1' in out, out
        calls = C.model_calls()
        turns = 0
        out = C.turn(page, "todo done t1")                     # by id only (CLM-06)
        turns += 1
        assert blocked(out), out
        out = C.turn(page, "todo finish t2: Ship S-2.1 date parsing")  # content names S-2.1 (CLM-05)
        turns += 1
        assert blocked(out), out
        out = C.turn(page, "kanban complete")
        turns += 1
        assert blocked(out), out
        out = C.turn(page, "report rung S-2.1")
        turns += 1
        assert blocked(out), out
        out = todo_state(page)
        turns += 1
        assert '"id": "t1"' in out and '"status": "pending"' in out and '"completed": 0' in out, out
        # 5. No model call by the hook: two completions per turn (the tool call and the reply), nothing else.
        assert C.model_calls() - calls == 2 * turns

        # 2. Calls that declare nothing done go through.
        out = C.turn(page, "todo finish t3: Tidy the README wording")
        assert BLOCK not in out and '"completed": 1' in out, out
        out = C.turn(page, "rung status")
        assert BLOCK not in out and "error" not in out.lower() and "csvtidy" in out, out

        # 3. A session without a claim completes a todo naming S-2.1: not blocked (CLM-08).
        C.new_session(page)
        out = C.turn(page, "todo finish t9: Finish S-2.1 date parsing")
        assert BLOCK not in out and '"completed": 1' in out, out

        # 4. The command test passes: the same calls go through (CLM-07).
        restore()
        e.run_test("csvtidy", "T-2.1a", carried_by="coder")
        assert e.check("csvtidy", "S-2.1")["ok"]
        C.go(page, session)
        out = C.turn(page, "todo done t1")
        assert BLOCK not in out and '"completed"' in out, out
        out = C.turn(page, "todo finish t2: Ship S-2.1 date parsing")
        assert BLOCK not in out, out
        out = C.turn(page, "kanban complete")
        assert BLOCK not in out, out
        out = C.turn(page, "report rung S-2.1")
        assert BLOCK not in out and '"reported": "S-2.1"' in out, out
        assert e.claims("csvtidy", open_only=False)[0]["status"] == "reported"

        # 6. The transcript with a blocked call next to the pane: show an earlier blocked turn and the dock.
        page.evaluate("window.__rungDock(true)")
        page.locator("[data-testid=rung-dock]").first.wait_for(timeout=20000)
        page.get_by_text(BLOCK, exact=False).first.scroll_into_view_if_needed()
        H.evidence(page, 24)
    finally:
        restore()
        try:
            page.evaluate("window.__rungDock && window.__rungDock(false)")
        except Exception:
            pass
        C.use_profile(page, "default")
