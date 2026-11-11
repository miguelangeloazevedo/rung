"""Project settings names the variables a project's commands receive; nothing else is inherited (catalog
review of 3928b7ae)."""

import harness as H
from support import seed


def test_project_settings_saves_environment_variables(rung, csvtidy, page):
    e = rung.engine
    seed.seed_csvtidy(e, csvtidy)
    e.open_project("csvtidy")
    H.open_rung(page)
    H.wait_view(page, "home")
    page.evaluate("window.__rungNavigate('project-settings')")
    H.wait_view(page, "project-settings")
    box = page.locator(".rung [data-testid=project-settings] input[name=env_vars]")
    box.wait_for()
    assert box.input_value() == ""
    box.fill("not-a-name")
    page.locator(".rung [data-testid=save-project]").click()
    H.wait_until(lambda: box.get_attribute("aria-invalid") == "true", msg="the bad name is not marked")
    assert e.project("csvtidy")["env_vars"] == []
    box.fill("DATABASE_URL, API_BASE")
    page.locator(".rung [data-testid=save-project]").click()
    H.wait_until(lambda: e.project("csvtidy")["env_vars"] == ["DATABASE_URL", "API_BASE"],
                 msg=lambda: f"stored {e.project('csvtidy')['env_vars']}")
    H.wait_until(lambda: box.input_value() == "DATABASE_URL API_BASE", msg=lambda: box.input_value())
    H.wait_until(lambda: "env vars" in page.locator(".rung [data-testid=project-history]").inner_text(),
                 msg="no history line")
