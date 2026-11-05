"""Rung: a design-control ladder for Hermes. Registration only; the engine lives in rung_engine/."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from rung_engine import cli as _cli  # noqa: E402
from rung_engine import tools as _tools  # noqa: E402


def register(ctx):
    _tools.PROFILE["name"] = getattr(ctx, "profile_name", "") or ""
    for schema in _tools.SCHEMAS:
        ctx.register_tool(name=schema["name"], toolset="rung", schema=schema,
                          handler=_tools.HANDLERS[schema["name"]], emoji="🪜")
    ctx.register_cli_command(name="rung", help="Rung design-control ladder (check, status, tree, run, send)",
                             setup_fn=_cli.setup, handler_fn=_cli.main)
    ctx.register_command("rung", handler=_tools.slash, description="Rung: what needs you; /rung check <SPEC>",
                         args_hint="[check <SPEC>|--all]")
    skills = _ROOT / "skills"
    if skills.is_dir():
        for child in sorted(skills.iterdir()):
            md = child / "SKILL.md"
            if child.is_dir() and md.exists():
                ctx.register_skill(child.name, md)
