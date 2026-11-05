import pytest

from rung_engine import RungError


def test_create_project_stores_exact_values(engine, tmp_path):
    p = engine.create_project("csvtidy", str(tmp_path), "pytest", ["coder"])
    assert p["name"] == "csvtidy"
    assert p["folder"] == str(tmp_path)
    assert p["test_command"] == "pytest"
    assert p["profiles"] == ["coder"]
    assert engine.current_project() == "csvtidy"
    assert len(engine.projects()) == 1


@pytest.mark.parametrize("field", ["folder", "test_command", "profiles"])
def test_prj02_create_project_names_the_missing_field(engine, tmp_path, field):
    """Only the folder is required; a value that cannot be filled in is refused on its own field."""
    args = {"name": "x", "folder": str(tmp_path), "test_command": "pytest", "profiles": ["coder"]}
    args[field] = [] if field == "profiles" else ""
    with pytest.raises(RungError) as exc:
        engine.create_project(**args)
    assert exc.value.field == field
    assert engine.projects() == []


def test_duplicate_project_refused(engine, tmp_path):
    engine.create_project("a", str(tmp_path), "pytest", ["coder"])
    with pytest.raises(RungError):
        engine.create_project("a", str(tmp_path), "pytest", ["coder"])


def test_picker_numbers_match_state(seeded):
    rows = {p["name"]: p["stats"] for p in seeded.projects()}
    assert rows["csvtidy"]["requirements"] == 3
    assert rows["csvtidy"]["covered"] == 2  # R-1 and R-2 pass, R-3 draft
    assert rows["notes-sync"]["covered"] == 2
    assert rows["notes-sync"]["needs_you"] == 0
    seeded.open_project("notes-sync")
    assert seeded.current_project() == "notes-sync"


def test_projects_are_isolated(seeded):
    a = seeded.tree("csvtidy")
    b = seeded.tree("notes-sync")
    assert [n["text"] for n in a] != [n["text"] for n in b]
    assert seeded.rung("notes-sync", "R-1")["text"] == "Copy notes that exist on one side only"
