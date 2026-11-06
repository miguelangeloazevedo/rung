"""UC25 The docked pane: the Rung dock beside a chat in PANES_AREA, with the full page closed. Needs you,
Running (develop runs and claims, live), the current need's ladder with a picker that follows the
full page, `Open Rung`, empty states, keyboard and contrast, the full page's status colours and labels."""

import time

import pytest

import a11y
import chatting as C
import harness as H
from support import seed

DOCK = "[data-testid=rung-dock]"


def palette_dock(page, want: bool) -> None:
    """Turn the dock on or off the way a person does: the command palette (⌘K), `Rung dock`."""
    if dock_open(page) == want:
        return
    page.keyboard.press("Meta+K")
    box = page.get_by_role("dialog").locator("input").first
    box.wait_for(timeout=10000)
    box.click()  # focused before typing: keys sent while the palette opens can land elsewhere
    page.keyboard.type("Rung dock")  # typed, so the palette filters and highlights the entry
    sel = page.locator("[role=option][aria-selected=true]").filter(has_text="Rung dock")
    try:
        H.wait_until(lambda: sel.count() == 1, timeout=10, msg="Rung dock highlighted")
    except AssertionError as exc:
        opts = page.locator("[role=option]").all_inner_texts()[:8]
        raise AssertionError(f"{exc}: input {box.input_value()!r}, options {opts!r}") from exc
    page.keyboard.press("Enter")
    H.wait_until(lambda: dock_open(page) == want, timeout=15, msg=f"dock {'open' if want else 'closed'}")


def dock_open(page) -> bool:
    return page.locator(DOCK).count() > 0 and page.locator(DOCK).first.is_visible()


def dock(page):
    return page.locator(DOCK).first


def chat_route(page) -> None:
    page.evaluate("location.hash = '#/'")
    H.dismiss_toasts(page)
    page.locator(C.COMPOSER).first.wait_for(timeout=30000)


def full_page_closed(page) -> bool:
    return page.locator(".rung [data-rung-view]").count() == 0


def rungs(page, scope: str) -> dict:
    return page.evaluate("""(scope) => Object.fromEntries([...document.querySelectorAll(scope + ' [data-rung]')]
        .map(x => [x.getAttribute('data-rung'), [x.getAttribute('data-tone'), x.getAttribute('data-label')]]))""", scope)


def test_dck01_dck02_dck03_dck04_dck05_dck06_dck07_dck08_dck10_docked_pane(rung, csvtidy, page):
    e = rung.engine
    seed.seed_merge(e, csvtidy, upto="develop")
    H.configure_stubs(e, csvtidy, worker_delay=2.5)
    e.open_project("csvtidy")
    H.open_rung(page)
    chat_route(page)
    assert full_page_closed(page)

    # 1. Open the dock beside a chat.
    palette_dock(page, True)
    d = dock(page)
    H.wait_until(lambda: d.locator("[data-testid=dock-project]").inner_text() == "csvtidy", msg="dock project")
    chip = page.locator("[data-testid=rung-status-chip]").first

    def counts():
        n = int(d.locator("[data-testid=dock-needs] [data-testid=dock-count]").inner_text())
        c = int("".join(ch for ch in chip.inner_text() if ch.isdigit()) or 0)
        return n, c
    H.wait_until(lambda: len(set(counts())) == 1, msg=f"dock count equals the chip: {counts()}")
    items = d.locator("[data-testid=dock-item]")
    assert items.count() == min(counts()[0], items.count()) and (items.count() > 0) == (counts()[0] > 0)
    assert d.locator("[data-testid=dock-running]").count() == 1
    H.wait_until(lambda: d.locator("[data-testid=dock-need]").input_value() in ("N-1", "N-2"), msg="a need picked")
    d.locator("[data-testid=dock-need]").select_option("N-1")
    assert set(rungs(page, DOCK)) >= {"R-1", "S-1.1", "T-1.1a", "R-2", "S-2.1"}

    # 2. Click a Needs you item: the full page opens on it. Open N-2 in the full page: the dock follows.
    if items.count():
        rid = items.first.get_attribute("data-item")
        items.first.click()
        page.locator(".rung [data-rung-view]").first.wait_for(timeout=20000)
        H.wait_until(lambda: rid in page.locator(".rung [data-testid=main]").first.inner_text(), msg=f"{rid} opened")
    page.evaluate("window.__rungNavigate('rung', {rid: 'N-2'})")
    H.wait_until(lambda: dock(page).locator("[data-testid=dock-need]").input_value() == "N-2", msg="dock follows N-2")
    assert "S-4.1" in rungs(page, DOCK)
    dock(page).locator("[data-testid=dock-need]").select_option("N-1")
    H.wait_until(lambda: "S-2.1" in rungs(page, DOCK) and "S-4.1" not in rungs(page, DOCK), msg="picker back to N-1")

    # 3. A develop run and a claim appear under Running without a reload; the run ends and leaves.
    page.evaluate("window.__rungNavigate('build', {need: 'N-2', step: 'develop'})")
    row = page.locator(".rung [data-testid=develop-table] [data-spec=\"S-4.1\"]")
    row.first.wait_for(timeout=20000)
    marker = page.evaluate("window.__rungMarker = Math.random()")
    H.button(page, "Send", row).click()
    H.wait_view(page, "run")
    e.claim("csvtidy", "S-2.1", "sess-dock", "Fix date parsing in csvtidy", "reviewer")
    chat_route(page)
    d = dock(page)
    H.wait_until(lambda: d.locator("[data-testid=dock-run]").count() == 1, timeout=20, msg="the run in the dock")
    H.wait_until(lambda: d.locator("[data-testid=dock-claim]").count() == 1, timeout=20, msg="the claim in the dock")
    run_txt = d.locator("[data-testid=dock-run]").first.inner_text()
    assert "S-4.1" in run_txt and "attempt" in run_txt, run_txt
    t0 = d.locator("[data-testid=dock-elapsed]").first.inner_text()
    H.wait_until(lambda: d.locator("[data-testid=dock-elapsed]").count() == 0
                 or d.locator("[data-testid=dock-elapsed]").first.inner_text() != t0, msg="elapsed ticks")
    assert "reviewer" in d.locator("[data-testid=dock-claim]").first.inner_text()
    H.wait_until(lambda: d.locator("[data-testid=dock-run]").count() == 0, timeout=120, msg="the run leaves Running")
    assert page.evaluate("window.__rungMarker") == marker, "the page reloaded"
    e.release_claim("csvtidy", "S-2.1")

    # 4. Collapse, switch session, reopen: still on csvtidy. Open Rung opens the full page home.
    palette_dock(page, False)
    C.new_session(page)
    palette_dock(page, True)
    H.wait_until(lambda: dock(page).locator("[data-testid=dock-project]").inner_text() == "csvtidy", msg="still csvtidy")
    dock(page).locator("[data-testid=dock-open]").click()
    H.wait_view(page, "home")
    assert page.locator(".rung [data-testid=project-name]").first.inner_text().strip() == "csvtidy"

    # 7. Status colours and labels of every rung in the dock equal those of the same rung on home.
    page.evaluate("window.__rungNavigate('rung', {rid: 'N-1'})")
    H.wait_until(lambda: dock(page).locator("[data-testid=dock-need]").input_value() == "N-1", msg="dock on N-1")
    time.sleep(1)
    in_dock = rungs(page, DOCK)
    on_home = rungs(page, ".rung [data-testid=rail]")
    shared = set(in_dock) & set(on_home)
    assert shared >= {"R-1", "S-1.1", "R-2", "S-2.1"}, (in_dock, on_home)
    assert {k: in_dock[k] for k in shared} == {k: on_home[k] for k in shared}

    # 8. The dock beside a chat with the full page closed.
    chat_route(page)
    assert full_page_closed(page) and dock_open(page)
    H.evidence(page, 25)

    # 6. Keyboard only: every dock control is reachable, focus is visible, names and contrast hold.
    page.locator(C.COMPOSER).first.click()
    want = dock(page).evaluate("el => el.querySelectorAll('button, select').length")
    seen, shown = set(), []
    for _ in range(200):
        page.keyboard.press("Tab")
        f = page.evaluate("""() => { const a = document.activeElement, dk = a && a.closest('[data-testid=rung-dock]');
            if (!dk) return null; const s = getComputedStyle(a);
            return {k: a.outerHTML.slice(0, 120), ring: s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0 || s.boxShadow !== 'none'} }""")
        if f:
            seen.add(f["k"])
            shown.append(f["ring"])
        if len(seen) >= want:
            break
    assert len(seen) >= want, f"reached {len(seen)} of {want} dock controls by Tab"
    assert all(shown), "focus visible on every dock control"
    assert not [x for x in a11y.unnamed_controls(page) if "dk" in str(x)]
    assert not a11y.contrast_failures(page)

    # 5. Empty states: notes-sync with nothing that needs you and nothing running; then no project.
    seed.seed_notes_sync(e, H.copy_fixture("notes-sync", rung.work))
    e.open_project("notes-sync")
    H.wait_until(lambda: dock(page).locator("[data-testid=dock-project]").inner_text() == "notes-sync", msg="notes-sync")
    empties = dock(page).locator("[data-testid=dock-empty]")
    H.wait_until(lambda: empties.count() >= 1, msg="empty sections")
    for i in range(empties.count()):
        assert empties.nth(i).locator("button").count() <= 1 and empties.nth(i).inner_text().strip()
    store2 = rung.tmp / "empty" / "rung.db"
    H.use_store(store2)
    H.reload(page)
    chat_route(page)
    H.wait_until(lambda: dock_open(page) and "No project" in dock(page).inner_text(), timeout=30, msg="no project")
    assert dock(page).locator("button").count() == 1 and dock(page).locator("button").inner_text().strip() == "Open Rung"
    H.use_store(rung.store)
    palette_dock(page, False)


@pytest.mark.parametrize("theme", [("github", "light")], ids=lambda t: "-".join(t))
def test_dck08_dck09_dock_light_theme_widths_and_large_project(rung, csvtidy, theme):
    e = rung.engine
    seed.seed_large(e, rung.work, name="bigladder", text=lambda kind, i: (
        f"{kind} {i} " + "with a long wording that will not fit in the narrow dock " * 2))
    e.open_project("bigladder")
    with H.desktop(theme=theme) as page:
        H.open_rung(page)
        H.wait_view(page, "home")
        page.locator(".rung [data-testid=rail] [data-rung]").first.wait_for(timeout=30000)
        chat_route(page)
        H.wait_until(lambda: page.evaluate("typeof window.__rungDock === 'function'"), msg="Rung registered")
        # The project's data is loaded (the full page fetched it); the dock renders it within a second.
        t0 = time.time()
        page.evaluate("window.__rungDock(true)")
        page.locator(DOCK + " [data-rung]").first.wait_for(timeout=20000)
        took = time.time() - t0
        assert took < 1.0, f"dock rendered a 500-rung project in {took:.2f}s"
        # A glance: the first items, then how many more, opening the full page.
        n = len(e.needs_you("bigladder"))
        assert n > 8
        H.wait_until(lambda: page.locator(DOCK + " [data-testid=dock-item]").count() == 8, msg="eight Needs you rows")
        assert page.locator(DOCK + " [data-testid=dock-more]").inner_text().strip() == f"{n - 8} more"
        # contrast and names on a light theme
        assert not a11y.contrast_failures(page)
        for width in (237, 288, 360):
            page.evaluate("""(w) => { const d = document.querySelector('[data-testid=rung-dock]');
                let p = d; while (p && p.parentElement && !p.parentElement.matches('body')) {
                  if (getComputedStyle(p).width && p.getBoundingClientRect().width > w + 4 && p !== d) break; p = p.parentElement }
                d.style.width = w + 'px' }""", width)
            time.sleep(0.3)
            over = page.evaluate("""() => { const d = document.querySelector('[data-testid=rung-dock]'), r = d.getBoundingClientRect();
                return [...d.querySelectorAll('*')].filter(x => { const b = x.getBoundingClientRect();
                  return b.width && (b.right > r.right + 0.5 || b.left < r.left - 0.5) && !x.closest('select') }).map(x => x.outerHTML.slice(0, 80)) }""")
            assert not over, f"{width}px: {over[:3]}"
            cut = page.evaluate("""() => [...document.querySelectorAll('[data-testid=rung-dock] .truncate')]
                .filter(x => x.scrollWidth > x.clientWidth + 1 && !x.getAttribute('title')).map(x => x.innerText.slice(0, 40))""")
            assert not cut, f"{width}px truncated without a title: {cut[:3]}"
        page.evaluate("document.querySelector('[data-testid=rung-dock]').style.width = ''")
        page.evaluate("window.__rungDock(false)")
