"""UC23 Claim and report: a `coder` Hermes session claims S-2.1 with `rung_claim`, is refused by
`rung_report` while the check fails, reports once it passes; a person releases a claim in the pane."""

import harness as H
import chatting as C
from support import seed

S31 = "Count dropped rows and print the count to stderr"


def spec_view(page, rid):
    H.open_rung(page, fresh=False)
    page.evaluate(f"window.__rungNavigate('rung', {{rid: '{rid}'}})")
    H.wait_until(lambda: page.locator(".rung [data-testid=spec]").count() > 0, timeout=20, msg=f"{rid} view")
    return page.locator(".rung [data-testid=main]").first


def claim_rows(page):
    return page.evaluate("""() => [...document.querySelectorAll('.rung [data-testid=claims] [data-claim]')]
        .map(x => ({id: +x.getAttribute('data-claim'), status: x.getAttribute('data-status'), text: x.innerText}))""")


def test_clm01_clm02_clm03_clm04_clm10_claim_and_report(rung, csvtidy, page):
    e = rung.engine
    restore = seed.seed_failing(e, csvtidy)
    try:
        # Setup: a draft specification S-3.1 and a human-only S-1.1.
        e.approve_requirements("csvtidy", "N-1")
        e.write_spec("csvtidy", "R-3", S31, tags=["python"])
        assert e.rung("csvtidy", "S-3.1")["status"] == "draft"
        e.set_allocation("csvtidy", "S-1.1", human_only=True)
        approval = {k: e.rung("csvtidy", "S-2.1")[k] for k in ("approved_by", "approved_at", "version")}

        # 1. A coder session claims S-2.1.
        H.open_rung(page)
        C.use_profile(page, "coder")
        C.new_session(page)
        out = C.turn(page, "Please claim rung S-2.1 for me")
        assert '"claimed": "S-2.1"' in out, out
        first = C.route(page)
        [cl] = e.claims("csvtidy")
        assert cl["profile"] == "coder" and cl["status"] == "open"
        main = spec_view(page, "S-2.1")
        H.wait_until(lambda: len(claim_rows(page)) == 1, msg="the claim on S-2.1")
        row = claim_rows(page)[0]
        assert row["status"] == "open" and "coder" in row["text"] and cl["chat"][:20] in row["text"], row
        page.evaluate("window.__rungNavigate('home')")
        H.wait_view(page, "home")
        running = page.locator(".rung [data-testid=running-claim]")
        H.wait_until(lambda: running.count() == 1, msg="the claim under Running")
        txt = running.first.inner_text()
        assert "S-2.1" in txt and "coder" in txt and cl["chat"][:20] in txt and "blocked by T-2.1a" in txt, txt

        # 2. Refusals, each naming its reason; nothing stored.
        C.new_session(page)
        out = C.turn(page, "claim rung S-2.1 please")
        assert "held by" in out and cl["chat"][:20] in out, out
        out = C.turn(page, "now claim rung S-3.1")
        assert "S-3.1 is draft" in out, out
        out = C.turn(page, "and claim rung S-1.1")
        assert "S-1.1 is human only" in out, out
        second = C.route(page)
        assert len(e.claims("csvtidy", open_only=False)) == 1

        # 3. Report while T-2.1a fails: refused, naming it; the claim stays open.
        C.go(page, first)
        out = C.turn(page, "report rung S-2.1")
        assert "T-2.1a" in out and "S-2.1" in out, out
        assert e.claims("csvtidy")[0]["status"] == "open"
        spec_view(page, "S-2.1")
        H.wait_until(lambda: claim_rows(page)[0]["status"] == "open", msg="claim still open")

        # 4. The test passes, run from the pane; the report succeeds with the passing execution.
        restore()
        page.locator(".rung [data-testid=run-tests]").first.click()
        H.wait_until(lambda: e.check("csvtidy", "S-2.1")["ok"], timeout=60, msg="T-2.1a passes")
        n = e.executions("csvtidy", "T-2.1a")[0]["n"]
        C.go(page, first)
        out = C.turn(page, "report rung S-2.1")
        assert "reported" in out.lower() and "error" not in out.lower(), out
        spec_view(page, "S-2.1")
        H.wait_until(lambda: claim_rows(page) and claim_rows(page)[0]["status"] == "reported", msg="claim reported")
        assert f"#{n}" in claim_rows(page)[0]["text"], claim_rows(page)
        assert {k: e.rung("csvtidy", "S-2.1")[k] for k in ("approved_by", "approved_at", "version")} == approval

        # 5. A new claim from the second session, released in the pane.
        C.go(page, second)
        out = C.turn(page, "claim rung S-2.1 again")
        assert '"claimed": "S-2.1"' in out, out
        spec_view(page, "S-2.1")
        H.wait_until(lambda: any(r["status"] == "open" for r in claim_rows(page)), msg="the second claim")
        page.locator(".rung [data-testid=release-claim]").first.click()
        H.wait_until(lambda: [r["status"] for r in claim_rows(page)] == ["released", "reported"],
                     msg=f"released: {claim_rows(page)}")
        assert not e.claims("csvtidy")

        # 6. S-2.1 with its claim history.
        page.locator(".rung [data-testid=claims]").first.scroll_into_view_if_needed()
        H.evidence(page, 23)
    finally:
        restore()
        C.use_profile(page, "default")
