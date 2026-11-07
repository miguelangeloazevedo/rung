"""Result lines (NAV-11) are named once, in the RESULTS table of desktop/src/00-core.js.

A view that adds its own line after post() gives the same action a second name, or lays a second sentence
over the first. Only an action made of several posts names itself, and it posts quietly.
"""
import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "desktop" / "src"

# the only lines a view may write itself: a batch, and a bot job cancelled because its view went away
ALLOWED_NOTIFY = {"45-bot.js": 2}
ALLOWED_FINISH_NOTICE = {"30-build.js": 1}


def _calls(pattern):
    found = {}
    for f in sorted(SRC.glob("*.js")):
        if f.name == "00-core.js":
            continue
        n = len(re.findall(pattern, f.read_text()))
        if n:
            found[f.name] = n
    return found


def test_views_do_not_name_results_themselves():
    assert _calls(r"\bnotify\(") == ALLOWED_NOTIFY


def test_only_a_batch_names_itself_through_finish():
    assert _calls(r"\bfinish\([^,()]+, [^,()]+, [`'\"]") == ALLOWED_FINISH_NOTICE


def test_a_batch_posts_quietly():
    build = (SRC / "30-build.js").read_text()
    send_all = build[build.index("const sendAll"):build.index("const body", build.index("const sendAll"))]
    assert "{ quiet: true }" in send_all


def test_each_row_returns_a_line_or_lets_the_search_go_on():
    core = (SRC / "00-core.js").read_text()
    assert "const line = m && f(m, body, data); if (line) return line" in core
    rows = re.findall(r"^\s*\[/(.+?)/, ", core[core.index("const RESULTS"):core.index("function resultLine")], re.M)
    assert len(rows) == len(set(rows)), "a path has two rows"
