"""UC22 Ready for testers: demo reset, the install on a clean Hermes home, the doctor."""

import os
import re
import shutil
import subprocess
import sys

import harness as H
from support import seed

HERMES_BIN = os.environ.get("RUNG_HERMES_BIN") or os.path.expanduser("~/.hermes/hermes-agent/venv/bin/hermes")


def cli(store, *args, home=None):
    env = dict(os.environ, RUNG_STORE=str(store))
    if home:
        env["HERMES_HOME"] = str(home)
    env.pop("PYTHONPATH", None)
    return subprocess.run([sys.executable, "-m", "rung_engine.cli", *args], cwd=H.ROOT, env=env,
                          capture_output=True, text=True, timeout=180)


def shape(nodes):
    """The ladder without times: what a reset must reproduce."""
    return [{k: (shape(v) if k == "children" else v) for k, v in n.items() if not k.endswith("_at")} for n in nodes]


def blocks(md: str, section: str) -> list[str]:
    body = md.split(f"## {section}\n", 1)[1].split("\n## ", 1)[0]
    return re.findall(r"```bash\n(.*?)```", body, re.S)


def test_gte07_sec04_demo_reset_recreates_the_sample_only(rung, csvtidy, page):
    e = rung.engine
    seed.seed_csvtidy(e, csvtidy)
    e.create_sample()
    other = e.tree("csvtidy")
    other_rows = H.stored(rung.store, "SELECT COUNT(*) AS n FROM executions e JOIN rungs t ON t.pk=e.test_pk "
                                      "JOIN projects p ON p.pk=t.project_pk WHERE p.name='csvtidy'")
    initial = shape(e.tree("sample"))
    sample_folder = e.project("sample")["folder"]
    # Change the sample the way a person would: a new requirement, an edit, a run, an edited file.
    e.add_requirement("sample", "N-1", "Count lines as well")
    e.edit("sample", "R-1", text="Count words separated by spaces only", approve=True)
    (H.Path(sample_folder) / "wordcount" / "count.py").write_text("broken = True\n")
    assert shape(e.tree("sample")) != initial
    # 1. hermes rung demo reset
    r = cli(rung.store, "demo", "reset")
    assert r.returncode == 0, r.stdout + r.stderr
    assert shape(e.tree("sample")) == initial
    assert "broken = True" not in (H.Path(sample_folder) / "wordcount" / "count.py").read_text()
    assert e.tree("csvtidy") == other
    assert H.stored(rung.store, "SELECT COUNT(*) AS n FROM executions e JOIN rungs t ON t.pk=e.test_pk "
                                "JOIN projects p ON p.pk=t.project_pk WHERE p.name='csvtidy'") == other_rows
    # 5. The sample home after the reset.
    e.open_project("sample")
    H.open_rung(page)
    H.wait_view(page, "home")
    page.locator(".rung [data-testid=first-green]").wait_for()
    H.wait_until(lambda: "R-2" not in page.locator(".rung [data-testid=rail]").inner_text(), msg="reset shown")
    H.evidence(page, 22)


def test_rdy01_rdy03_gte08_install_on_a_clean_home(tmp_path, rung, page):
    """INSTALL.md, line by line, into a throwaway Hermes home; then the doctor, a broken folder, uninstall."""
    home = tmp_path / "clean-home"
    home.mkdir()
    env = dict(os.environ, HERMES_HOME=str(home), RUNG_REPO=f"file://{H.ROOT}",
               PATH=os.path.dirname(HERMES_BIN) + os.pathsep + os.environ["PATH"])
    env.pop("PYTHONPATH", None)
    install = blocks((H.ROOT / "INSTALL.md").read_text(), "Install")[0]
    r = subprocess.run(["bash", "-euo", "pipefail", "-c", install], cwd=tmp_path, env=env, capture_output=True,
                       text=True, timeout=600)
    out = r.stdout + r.stderr
    assert r.returncode == 0, out
    assert "rung doctor: PASS" in out
    plugin = home / "plugins" / "rung"
    head = subprocess.run(["git", "-C", str(H.ROOT), "show", "HEAD:desktop/plugin.js"], capture_output=True).stdout
    assert (plugin / "desktop" / "plugin.js").read_bytes() == head
    # 4. The doctor lists every check it ran; with a project folder removed it fails, naming the check and its fix.
    store = home / "plugin-data" / "rung" / "rung.db"
    work = tmp_path / "work"
    folder = seed.copy_fixture("csvtidy", work)
    from rung_engine import Engine
    eng = Engine(str(store))
    # A test command this machine has: the doctor fails a project whose runner is missing.
    eng.create_project(folder=str(folder), test_command="python3 -m unittest -q", profiles=["default"])
    eng.close()
    def hermes(*a, answer=""):
        return subprocess.run([HERMES_BIN, *a], env=env, input=answer, capture_output=True, text=True, timeout=180)
    ok = hermes("rung", "doctor")
    assert ok.returncode == 0, ok.stdout + ok.stderr
    for name in ("python", "store folder", "store", "store writable", "schema", "profiles", "worker", "drafting",
                 "project csvtidy folder", "project csvtidy test command", "desktop pane", "hermes"):
        assert f"ok    {name}:" in ok.stdout, name
    shutil.rmtree(folder)
    bad = hermes("rung", "doctor")
    assert bad.returncode != 0
    assert "FAIL  project csvtidy folder" in bad.stdout and "fix: restore the folder" in bad.stdout
    # The pane opens on the start screen for a store with no project.
    H.open_rung(page)
    H.wait_view(page, "start")
    # RDY-03: uninstalling leaves Hermes working and keeps Rung's data.
    un = hermes("plugins", "uninstall", "rung", answer="y\n")
    assert un.returncode == 0, un.stdout + un.stderr
    assert not plugin.exists()
    assert hermes("--version").returncode == 0
    assert hermes("plugins", "list").returncode == 0
    assert store.exists()