"""A deterministic OpenAI-compatible chat endpoint for end-to-end tests. Standard library only.

It stands in for the chat model of the isolated test Hermes home, so an "ordinary Hermes chat"
can call Rung tools without any paid model. Rules, on the last user message:

- "Propose requirement under N-1: <text>"   -> a rung_propose tool call
- "Run rung tests for S-2.1"                -> a rung_run_tests tool call
- anything after a tool result               -> a short summary of the result
- title requests                             -> the first words of the user message
- goal judge requests                        -> {"done": true, ...}
- "claim rung S-2.1" / "report rung S-2.1"   -> rung_claim / rung_report
- "todo add t1: <text>" / "todo finish t2: <text>" -> todo_list, pending / completed (merge)
- "todo done t1"                             -> todo_list completing t1 by id only (empty content)
- "todo show", "kanban complete", "rung status" -> todo_list read, kanban_complete, rung_status
- a user message containing "slowly"         -> "Working on it." after 8 seconds
- anything else                              -> "OK."

    python tests/e2e/stub_model.py --port 18765
"""

from __future__ import annotations

import argparse
import json
import re
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LOG: list[dict] = []
SLOW_SECONDS = 8


def _text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(p.get("text", "") for p in content if isinstance(p, dict))
    return ""


def _call(tools: set, name: str, args: dict) -> dict | None:
    """Call a tool directly when it is listed, or through Hermes's deferred-tool bridge
    (tool_search keeps plugin tools behind tool_call when the tool list is long)."""
    if name in tools:
        return {"tool": name, "args": args}
    if "tool_call" in tools:
        return {"tool": "tool_call", "args": {"calls": [{"name": name, "arguments": args}]}}
    return None


def decide(body: dict) -> dict:
    msgs = body.get("messages") or []
    tools = {t.get("function", {}).get("name") for t in body.get("tools") or []}
    system = " ".join(_text(m.get("content")) for m in msgs if m.get("role") == "system").lower()
    users = [m for m in msgs if m.get("role") == "user"]
    last_user = _text(users[-1].get("content")) if users else ""
    last = msgs[-1] if msgs else {}
    if last.get("role") == "tool":
        return {"text": "Done: " + _text(last.get("content"))[:300]}
    low = last_user.lower()
    if "title" in system and not tools:
        words = re.sub(r"[^\w\s:-]", " ", last_user).split()
        return {"text": " ".join(words[:6]) or "Chat"}
    if ("judge" in system or "goal" in system and "verdict" in system) and not tools:
        return {"text": json.dumps({"done": True, "reason": "gates pass"})}
    m = re.search(r"propose requirement under ([A-Z]-\d+(?:\.\d+)?)\s*:\s*(.+)", last_user, re.I | re.S)
    if m:
        call = _call(tools, "rung_propose", {"parent": m.group(1), "text": m.group(2).strip().splitlines()[0]})
        if call:
            return call
    m = re.search(r"run rung tests for (S-\d+\.\d+)", last_user, re.I)
    if m:
        call = _call(tools, "rung_run_tests", {"spec": m.group(1)})
        if call:
            return call
    # Stage 3: claims, report, and the completion calls the done hook watches.
    m = re.search(r"\b(claim|report) rung (S-\d+\.\d+)", last_user, re.I)
    if m:
        call = _call(tools, "rung_" + m.group(1).lower(), {"spec": m.group(2)})
        if call:
            return call
    m = re.search(r"\btodo (add|finish) (\w+): (.+)", last_user, re.I)
    if m:
        status = "pending" if m.group(1).lower() == "add" else "completed"
        call = _call(tools, "todo_list", {"todos": [{"id": m.group(2), "content": m.group(3).strip().splitlines()[0],
                                                     "status": status}], "merge": True})
        if call:
            return call
    m = re.search(r"\btodo done (\w+)\b", last_user, re.I)
    if m:
        call = _call(tools, "todo_list", {"todos": [{"id": m.group(1), "content": "", "status": "completed"}], "merge": True})
        if call:
            return call
    if re.search(r"\btodo show\b", low):
        call = _call(tools, "todo_list", {})
        if call:
            return call
    if re.search(r"\bkanban complete\b", low):
        call = _call(tools, "kanban_complete", {"summary": "Finished the date parsing work"})
        if call:
            return call
    if re.search(r"\brung status\b", low):
        call = _call(tools, "rung_status", {})
        if call:
            return call
    if "slowly" in low:
        # A goal turn that takes a while, so a goal control (`/goal gate add`) can arrive mid-turn.
        time.sleep(SLOW_SECONDS)
        return {"text": "Working on it."}
    if "goal" in low or "gate" in low:
        return {"text": "Working on it."}
    return {"text": "OK."}


def completion(body: dict) -> dict:
    d = decide(body)
    msg = {"role": "assistant", "content": d.get("text", "")}
    finish = "stop"
    if "tool" in d:
        msg = {"role": "assistant", "content": "", "tool_calls": [{
            "id": "call_" + uuid.uuid4().hex[:12], "type": "function",
            "function": {"name": d["tool"], "arguments": json.dumps(d["args"])}}]}
        finish = "tool_calls"
    LOG.append({"t": time.time(), "decision": d})
    return {"id": "chatcmpl-" + uuid.uuid4().hex[:12], "object": "chat.completion", "created": int(time.time()),
            "model": body.get("model", "rung-stub"),
            "choices": [{"index": 0, "message": msg, "finish_reason": finish}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _json(self, code, obj):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.rstrip("/").endswith("/models"):
            return self._json(200, {"object": "list", "data": [
                {"id": "rung-stub", "object": "model", "owned_by": "rung", "context_length": 200000}]})
        if self.path.rstrip("/").endswith("/count"):
            return self._json(200, {"count": len(LOG)})
        if self.path.rstrip("/").endswith("/log"):
            return self._json(200, LOG[-50:])
        return self._json(200, {"ok": True})

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            body = {}
        if not self.path.rstrip("/").endswith("/chat/completions"):
            return self._json(404, {"error": {"message": "not found"}})
        res = completion(body)
        if not body.get("stream"):
            return self._json(200, res)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()
        msg = res["choices"][0]["message"]
        base = {"id": res["id"], "object": "chat.completion.chunk", "created": res["created"], "model": res["model"]}
        delta = {"role": "assistant", "content": msg.get("content") or ""}
        if msg.get("tool_calls"):
            delta["tool_calls"] = [{"index": 0, **tc} for tc in msg["tool_calls"]]
        chunks = [{**base, "choices": [{"index": 0, "delta": delta, "finish_reason": None}]},
                  {**base, "choices": [{"index": 0, "delta": {}, "finish_reason": res["choices"][0]["finish_reason"]}],
                   "usage": res["usage"]}]
        for c in chunks:
            self.wfile.write(f"data: {json.dumps(c)}\n\n".encode())
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()
        self.close_connection = True


def serve(port: int) -> ThreadingHTTPServer:
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=18765)
    a = ap.parse_args()
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    print(f"rung stub model on http://127.0.0.1:{a.port}/v1", flush=True)
    srv.serve_forever()
