"""UC39 The dock leads with the focused chat's task (decisions Round 24, B18): not bound, Bind to task with a
confirmation, then the task's outcome, state, one blocker and next action; the blocker opens its verification."""

import chatting as C
import harness as H
import test_uc25_dock as D
from support import seed


def test_dok01_dok02_dok03_dok04_dock_for_decisions(rung, csvtidy, page):
    e = rung.engine
    restore = seed.seed_failing(e, csvtidy)  # S-2.1 approved, T-2.1a failing now
    try:
        H.open_rung(page)
        C.use_profile(page, "coder")
        C.new_session(page)
        C.turn(page, "rung status", timeout=180)  # a stored chat, focused
        D.palette_dock(page, True)
        d = D.dock(page)

        # 1. No claim: the dock leads with this chat, not bound, the project's next task and Bind to task.
        chat = d.locator("[data-testid=dock-chat-body]")
        H.wait_until(lambda: chat.count() == 1 and chat.get_attribute("data-session"), msg=lambda: d.inner_text()[:400])
        first = d.evaluate("el => el.querySelector('.dk-body > section').getAttribute('data-testid')")
        assert first == "dock-chat", first
        H.wait_until(lambda: d.locator("[data-testid=dock-unbound]").count() == 1, msg=lambda: chat.inner_text())
        assert "Not bound" in chat.inner_text()
        nxt = e.home("csvtidy")["next"][0]["id"]  # the project's next task, the same one Home's Next leads with
        assert d.locator("[data-testid=dock-next]").get_attribute("title") == f"Next: {nxt}"
        assert d.locator("[data-testid=dock-ladder]").get_attribute("data-open") == "true"  # unbound: the ladder shows
        session = chat.get_attribute("data-session")

        # 2. Bind to task: the confirmation names the chat and the profile; Cancel stores nothing; Bind opens one claim.
        d.locator("[data-testid=dock-bind-open]").click()
        form = d.locator("[data-testid=dock-bind]")
        form.wait_for()
        assert form.locator("[data-testid=dock-bind-spec]").input_value() == nxt
        form.locator("[data-testid=dock-bind-spec]").select_option("S-2.1")
        facts = form.locator("[data-testid=dock-bind-facts]").inner_text()
        assert session in facts and "coder" in facts and "S-2.1" in facts, facts
        form.locator("[data-testid=dock-bind-cancel]").click()
        H.wait_until(lambda: form.count() == 0, msg="bind form closed")
        assert e.claims("csvtidy") == []
        d.locator("[data-testid=dock-bind-open]").click()
        form.locator("[data-testid=dock-bind-spec]").select_option("S-2.1")
        form.locator("[data-testid=dock-bind-confirm]").click()
        H.wait_until(lambda: len(e.claims("csvtidy")) == 1, msg="one claim")
        [cl] = e.claims("csvtidy")
        assert (cl["spec"], cl["session"], cl["profile"]) == ("S-2.1", session, "coder")

        # 3. The dock leads with S-2.1: outcome, state, one blocker, next action; the ladder is collapsed until opened.
        task = d.locator("[data-testid=dock-task]")
        H.wait_until(lambda: task.count() == 1, msg=lambda: chat.inner_text())
        assert e.rung("csvtidy", "S-2.1")["text"] in task.locator("[data-testid=dock-task-outcome]").inner_text()
        assert task.locator("[data-testid=dock-task-state]").inner_text() == "Failed"
        assert task.locator("[data-testid=dock-task-blocker]").count() == 1
        assert "T-2.1a" in task.locator("[data-testid=dock-task-blocker]").inner_text()
        assert task.locator("[data-testid=dock-task-next]").inner_text() == "Open failing test"
        ladder = d.locator("[data-testid=dock-ladder]")
        H.wait_until(lambda: ladder.get_attribute("data-open") == "false", msg="ladder collapsed")
        assert ladder.locator("[data-rung]").count() == 0
        ladder.locator("[data-testid=dock-ladder-toggle]").click()
        H.wait_until(lambda: ladder.locator("[data-rung=\"S-2.1\"]").count() == 1, msg="ladder opened")
        ladder.locator("[data-testid=dock-ladder-toggle]").click()
        H.evidence(page, 39)

        # The chat's own report is refused for the same reason: the binding is the agent's own claim.
        out = C.turn(page, "report rung S-2.1")
        assert "T-2.1a" in out and "claim it first" not in out, out

        # 4. The blocker opens S-2.1's verification section.
        task.locator("[data-testid=dock-task-blocker]").click()
        H.wait_view(page, "rung")
        sec = page.locator(".rung [data-testid=verification][data-focus=true]")
        sec.wait_for()
        assert sec.get_attribute("data-verification") == "failed"
        assert H.node(e, "csvtidy", "S-2.1")["verification"] == "failed"
        e.release_claim("csvtidy", "S-2.1")
        D.palette_dock(page, False)
    finally:
        restore()
