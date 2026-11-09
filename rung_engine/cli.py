"""`hermes rung ...`: the terminal door. Also runnable as `python -m rung_engine.cli` for scripts.

`hermes rung check S-2.1` is a goal gate: exit 0 only when the specification is verified now
(approved, nothing upstream stale, every required test's newest result is a pass recorded on the
project's code as it is now, with its approved test files unchanged). It is pure engine computation;
no model is called. `hermes rung recheck` runs every test whose pass no longer applies.
"""

from __future__ import annotations

import argparse
import json
import sys

from .core import RungError


def setup(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project", "-P", help="project name (default: the last opened project)")
    parser.add_argument("--json", action="store_true", help="print JSON")
    subs = parser.add_subparsers(dest="rung_command")
    c = subs.add_parser("check", help="exit 0 only when a specification is verified by its tests")
    c.add_argument("spec", nargs="?", help="specification id, for example S-2.1")
    c.add_argument("--all", action="store_true", help="check every approved specification of the project")
    subs.add_parser("status", help="tiles and the Needs you list")
    subs.add_parser("recheck", help="run again every command test whose pass was recorded on code that changed since")
    v = subs.add_parser("verify", help="the full verification result of a specification (state, blockers, next "
                                       "action), or of a need (complete, and every open requirement)")
    v.add_argument("spec", help="a specification id (S-2.1) or a need id (N-1)")
    ms = subs.add_parser("milestone", help="integration milestones: list them, or one milestone's verdict (exit 0 "
                                          "only when verified)")
    ms.add_argument("milestone", nargs="?", help="milestone id, for example M-1")
    ms.add_argument("--run", action="store_true", help="run its command checks first, on the code as it is now")
    ms.add_argument("--export", action="store_true", help="also write its report to Rung's exports folder")
    en = subs.add_parser("enforcement", help="whether the done hook enforces claims for a chat session "
                                             "(enforced, unbound or degraded); verification is a separate fact")
    en.add_argument("session", nargs="?", default="", help="Hermes session id")
    pr = subs.add_parser("projects", help="list projects")
    pr.add_argument("--archived", action="store_true", help="list the archived projects instead")
    t = subs.add_parser("tree", help="print the ladder")
    t.add_argument("--retired", action="store_true", help="list the retired needs instead")
    r = subs.add_parser("run", help="run the command tests of a specification now")
    r.add_argument("spec")
    s = subs.add_parser("send", help="start a supervised develop run for a specification")
    s.add_argument("spec")
    s.add_argument("--profile")
    w = subs.add_parser("where", help="print the store path")
    w.set_defaults()
    subs.add_parser("doctor", help="check the install, the store and every project folder")
    d = subs.add_parser("demo", help="the sample project")
    d.add_argument("action", choices=["reset"], help="reset: recreate the sample project only")
    a = subs.add_parser("archive", help="archive a project (read only until restored)")
    a.add_argument("name")
    a = subs.add_parser("restore", help="restore an archived project")
    a.add_argument("name")
    rt = subs.add_parser("retire", help="retire a need with a reason")
    rt.add_argument("need")
    rt.add_argument("--reason", required=True)
    ro = subs.add_parser("readout", help="print a need's results and evidence as markdown")
    ro.add_argument("need")
    ro.add_argument("--export", action="store_true", help="also write it to Rung's exports folder")
    cl = subs.add_parser("claims", help="list open claims; claims release <SPEC> lets go of one")
    cl.add_argument("action", nargs="?", choices=["release"], help="release: close the open claim on a specification")
    cl.add_argument("spec", nargs="?", help="specification id, for example S-2.1")
    cl.add_argument("--all", action="store_true", help="also list reported and released claims")
    parser.set_defaults(func=main)


def _project(svc, args) -> str:
    name = getattr(args, "project", None) or svc.engine.current_project()
    if not name:
        raise RungError("no project yet: create one in the Rung pane", code="not_found", status=404)
    return name


def _print_tree(nodes, depth=0, out=None):
    out = out if out is not None else []
    for n in nodes:
        mark = n.get("coverage") or n.get("result") or ""
        out.append(f"{'  ' * depth}{n['id']:8} {n['status']:9} {mark:10} {n['text']}")
        _print_tree(n.get("children", []), depth + 1, out)
    return out


def _say(args, data, text: str) -> None:
    """One result: JSON with --json, else the text line. Every command goes through here."""
    print(json.dumps(data, indent=2) if getattr(args, "json", False) else text)


def main(args) -> int:
    from .host import service, store_path
    cmd = getattr(args, "rung_command", None)
    if cmd == "where":
        _say(args, {"store": str(store_path())}, str(store_path()))
        return 0
    if cmd == "doctor":
        from .doctor import render, run_checks
        from .host import hermes_bin
        checks = run_checks(store_path(), hermes_bin())
        print(json.dumps(checks, indent=2) if getattr(args, "json", False) else render(checks))
        return 0 if all(c["ok"] for c in checks) else 1
    svc = service()
    e = svc.engine
    try:
        if cmd == "check":
            project = _project(svc, args)
            if args.all:
                res = e.check_all(project)
                if args.json:
                    print(json.dumps(res, indent=2))
                else:
                    for r in res["results"]:
                        line = f"{r['id']}: {'verified' if r['ok'] else 'blocked'}"
                        if not r["ok"]:
                            line += " by " + "; ".join(r["blockers"])
                        print(line)
                    print(f"rung check --all: {'PASS' if res['ok'] else 'FAIL'}")
                return 0 if res["ok"] else 1
            if not args.spec:
                print("usage: hermes rung check <SPEC> | --all", file=sys.stderr)
                return 2
            res = e.check(project, args.spec)
            if args.json:
                print(json.dumps(res, indent=2))
            elif res["ok"]:
                print(f"{args.spec}: verified, every gating test passes")
            else:
                print(f"{args.spec}: blocked by " + "; ".join(res["blockers"]))
            return 0 if res["ok"] else 1
        if cmd == "verify":
            project = _project(svc, args)
            if e.rung(project, args.spec)["kind"] == "need":
                res = e.need_completeness(project, args.spec, fresh=True)
                lines = [f"{res['need']}: {'complete' if res['complete'] else 'not complete'}"]
                lines += [f"  {o['code']:22} {o['text']}" for o in res["open"]]
                lines += [f"  {'out_of_scope':22} {o['rung']}: {o['reason']}" for o in res["out_of_scope"]]
                _say(args, res, "\n".join(lines))
                return 0 if res["complete"] else 1
            res = e.verification(project, args.spec, fresh=True)
            lines = [f"{res['spec']}: {res['verification']} "
                     f"({res['required_checks']['satisfied']} of {res['required_checks']['total']} required checks)"]
            lines += [f"  {b['code']:22} {b['text']}" for b in res["blockers"]]
            if res["next_action"]:
                lines.append(f"  next: {res['next_action']['kind']}"
                             + (f" {res['next_action'].get('test') or res['next_action'].get('rung')}"
                                if res['next_action'].get('test') or res['next_action'].get('rung') else ""))
            _say(args, res, "\n".join(lines))
            return 0 if res["ok"] else 1
        if cmd == "recheck":
            project = _project(svc, args)
            rows = e.recheck(project)
            _say(args, [{"test": r["test"], "n": r["n"], "status": r["status"]} for r in rows],
                 "\n".join(f"{r['test']} #{r['n']}: {r['status']}" for r in rows) or f"{project}: nothing out of date")
            return 0 if all(r["status"] == "pass" for r in rows) else 1
        if cmd == "enforcement":
            from pathlib import Path

            from .hook import status
            st = status(args.session, Path(e.path))
            lines = [f"{st['session'] or '(no session)'}: {st['enforcement']}" + (f" ({st['reason']})" if st["reason"] else "")]
            lines += [f"  {c['project']} {c['spec']}: " + ("verified" if c["verified"] else "blocked: " + "; ".join(c["blockers"]))
                      for c in st["claims"]]
            _say(args, st, "\n".join(lines))
            return 0 if st["enforcement"] != "degraded" else 1
        if cmd == "milestone":
            project = _project(svc, args)
            if not args.milestone:
                rows = e.milestones(project)
                _say(args, rows, "\n".join(f"{m['id']:6} {m['state']:20} {m['title']}" for m in rows)
                     or f"{project}: no milestones")
                return 0
            if args.run:
                for r in e.run_milestone(project, args.milestone):
                    if not args.json:
                        print(f"{r['check']} #{r['n']}: {r['status']}" + (f" ({r['reason']})" if r["reason"] else ""))
            v = e.milestone(project, args.milestone)
            lines = [f"{v['id']}: {v['state']} on code {v['basis']} "
                     f"({sum(s['ok'] for s in v['scope'])} of {len(v['scope'])} included specifications verified)"]
            lines += [f"  {b['code']:22} {b['text']}" for b in v["blockers"]]
            if v["next_action"]:
                na = v["next_action"]
                lines.append(f"  next: {na['kind']}" + (f" {na.get('check') or na.get('rung')}"
                                                       if na.get("check") or na.get("rung") else ""))
            if args.export:
                lines.append(f"  report: {e.export_milestone(project, args.milestone)['path']}")
            _say(args, v, "\n".join(lines))
            return 0 if v["ok"] else 1
        if cmd == "projects":
            archived = getattr(args, "archived", False)
            rows = e.projects(archived=archived)
            if args.json:
                print(json.dumps(rows, indent=2))
                return 0
            if not rows:
                print("no archived projects" if archived else
                      "no projects: create one in the Rung pane, or run hermes rung demo reset")
            for p in rows:
                s = p["stats"]
                print(f"{p['name']}: needs you {s['needs_you']}, running {s['running']}, stale {s['stale']}, "
                      f"checks satisfied {s['covered']} of {s['requirements']}")
            return 0
        if cmd == "tree":
            project = _project(svc, args)
            nodes = e.tree(project, retired=getattr(args, "retired", False))
            _say(args, nodes, "\n".join(_print_tree(nodes)))
            return 0
        if cmd == "run":
            project = _project(svc, args)
            ok, results = True, []
            for t in e.command_tests(project, args.spec):
                r = e.run_test(project, t["id"], carried_by="engine")
                ok = ok and r["status"] == "pass"
                results.append({"test": t["id"], "n": r["n"], "status": r["status"], "exit_code": r["exit_code"]})
                if not args.json:
                    print(f"{t['id']} #{r['n']}: {r['status']} (exit {r['exit_code']})")
            if args.json:
                print(json.dumps({"spec": args.spec, "ok": ok, "executions": results}, indent=2))
            return 0 if ok else 1
        if cmd == "send":
            project = _project(svc, args)
            run = svc.send(project, args.spec, profile=args.profile)
            _say(args, run, f"run {run['id']} started for {args.spec} with {run['profile']}")
            return 0
        if cmd == "claims":
            project = _project(svc, args)
            if args.action == "release":
                if not args.spec:
                    print("usage: hermes rung claims release <SPEC>", file=sys.stderr)
                    return 2
                rows = e.release_claim(project, args.spec)
                from .claims import canonical_rid
                _say(args, rows, f"{canonical_rid(args.spec)}: released " + ", ".join(f"{r['chat']} ({r['profile']})" for r in rows))
                return 0
            rows = e.claims(project, open_only=not args.all)
            lines = [f"{c['spec']:8} {c['status']:9} {c['profile']:12} {c['chat']}"
                     + (f"  proof {', '.join(c['proof'])}" if c["proof"] else "") for c in rows]
            _say(args, rows, "\n".join(lines) if lines else f"{project}: no {'claims' if args.all else 'open claims'}")
            return 0
        if cmd == "demo":
            p = e.reset_sample()
            _say(args, {"project": p["name"], "folder": p["folder"]}, f"sample project reset: {p['folder']}")
            return 0
        if cmd == "archive":
            e.archive_project(args.name)
            _say(args, {"project": args.name, "archived": True}, f"{args.name}: archived")
            return 0
        if cmd == "restore":
            e.restore_project(args.name)
            _say(args, {"project": args.name, "archived": False}, f"{args.name}: restored")
            return 0
        if cmd == "retire":
            project = _project(svc, args)
            e.retire_need(project, args.need, args.reason)
            _say(args, {"project": project, "need": args.need, "retired": True}, f"{args.need}: retired")
            return 0
        if cmd == "readout":
            project = _project(svc, args)
            if args.export:
                out = e.export_readout(project, args.need)
                md, path = out["markdown"], out["path"]
            else:
                md, path = e.readout_markdown(project, args.need), None
            if args.json:
                print(json.dumps({"project": project, "need": args.need, "markdown": md,
                                  **({"path": str(path)} if path else {})}, indent=2))
            else:
                print(md, end="")
                if path:
                    print(f"written to {path}", file=sys.stderr)
            return 0
        project = _project(svc, args)
        t = e.tiles(project)
        if args.json:
            print(json.dumps({"tiles": t, "needs_you": e.needs_you(project)}, indent=2))
            return 0
        print(f"{project}: needs you {t['needs_you']}, running {t['running']}, stale {t['stale']}, "
              f"failing {t['failing']}, checks satisfied {t['covered']} of {t['requirements']}")
        for item in e.needs_you(project):
            print(f"  {item['type']:9} {item['id']:8} {item['text']}")
        return 0
    except RungError as exc:
        if getattr(args, "json", False):
            print(json.dumps({"error": str(exc), "code": exc.code}, indent=2))
        else:
            print(f"rung: {exc}", file=sys.stderr)
        return 2


def run(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="rung")
    setup(ap)
    args = ap.parse_args(argv)
    return main(args)


if __name__ == "__main__":
    sys.exit(run())
