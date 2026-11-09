"""Stage 5 documents: the design notes for SYS-14 to SYS-16 and the roadmap of what is still open."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECTIONS = ["## Problem", "## Boundary", "## Proposed model", "## Dependencies", "## Acceptance criteria",
            "## Not claimed until built"]


def test_dsn01_design_notes_for_sys14_to_sys16():
    for name in ("sys-14-multi-repository.md", "sys-15-team-authority.md", "sys-16-operational-readiness.md"):
        text = (ROOT / "docs" / "design" / name).read_text()
        assert text.startswith("# SYS-1"), name
        assert "nothing here is built" in text, name
        for s in SECTIONS:
            body = text.split(s, 1)
            assert len(body) == 2, (name, s)
            assert body[1].strip().split("\n## ")[0].strip(), (name, s)  # the section says something


def test_rdm01_roadmap_lists_open_items_with_dependency_and_criterion():
    text = (ROOT / "docs" / "roadmap.md").read_text()
    rows = [r for r in text.splitlines() if r.startswith("| ") and not r.startswith("| ID") and "---" not in r]
    assert rows
    for r in rows:
        cells = [c.strip() for c in r.strip("|").split("|")]
        assert len(cells) == 4, r
        ident, item, dep, done = cells
        assert re.fullmatch(r"(B\d{2}|SYS-\d{2}|R\d{2}|U\d{2})(, (B\d{2}|SYS-\d{2}|R\d{2}|U\d{2}))*", ident), r
        assert item and dep and done, r
    built = (ROOT / "docs" / "verification.md").read_text()
    for n in range(1, 17):
        sys_id = f"SYS-{n:02d}"
        assert sys_id in text or sys_id in built, sys_id
