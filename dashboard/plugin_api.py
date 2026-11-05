"""Rung REST routes, mounted by Hermes under /api/plugins/rung/. A thin wrapper over rung_engine.api."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from rung_engine import api as _api  # noqa: E402
from rung_engine.host import service  # noqa: E402

router = APIRouter()


def _notify(rev: int) -> None:
    try:
        from hermes_cli.plugin_events import broadcast_plugin_event
        broadcast_plugin_event("rung", "changed", {"rev": rev})
    except Exception:
        pass


async def _dispatch(request: Request, path: str):
    import asyncio
    body = None
    if request.method in ("POST", "PUT", "PATCH"):
        try:
            body = await request.json()
        except Exception:
            body = {}
    else:
        body = dict(request.query_params)
    svc = service()
    before = svc.engine.rev()
    status, data = await asyncio.to_thread(_api.handle, svc, request.method, path, body)
    after = svc.engine.rev()
    if after != before:
        _notify(after)
    return JSONResponse(data, status_code=status)


@router.get("/{path:path}")
async def get_any(request: Request, path: str = ""):
    return await _dispatch(request, path)


@router.post("/{path:path}")
async def post_any(request: Request, path: str = ""):
    return await _dispatch(request, path)
