"""`hermes rung ...`: the terminal door. Also runnable as `python -m rung_engine.cli` for scripts.

`hermes rung check S-2.1` is a goal gate: exit 0 only when the specification is released
(approved, nothing upstream stale, every gating test has a counting pass since the last
upstream change). It is pure engine computation; no model is called.
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
    c = subs.add_parser("check", help="exit 0 only when a specification is released by its tests")
    c.add_argument("spec", nargs="?", help="specification id, for example S-2.1")
    c.add_argument("--all", action="store_true", help="check every approved specification of the project")
    subs.add_parser("status", help="tiles and the Needs you list")
    subs.add_parser("projects", help="list projects")
    t = subs.add_parser("tree", help="print the ladder")
    t.add_argument("--all-statuses", action="store_true")
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
    ro = subs.add_parser("readout", help="print a need's read-out as markdown")
    ro.add_argument("need")
    ro.add_argument("--export", action="store_true", help="also write it to Rung's exports folder")
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


def main(args) -> int:
    from .host import service, store_path
    cmd = getattr(args, "rung_command", None)
    if cmd == "where":
        print(store_path())
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
                        line = f"{r['id']}: {'released' if r['ok'] else 'blocked'}"
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
                print(f"{args.spec}: released, every gating test passes")
            else:
                print(f"{args.spec}: blocked by " + "; ".join(res["blockers"]))
            return 0 if res["ok"] else 1
        if cmd == "projects":
            rows = e.projects()
            if not rows and not args.json:
                print("no projects: create one in the Rung pane, or run hermes rung demo reset")
            if args.json:
                print(json.dumps(rows, indent=2))
            for p in rows:
                s = p["stats"]
                print(f"{p['name']}: needs you {s['needs_you']}, running {s['running']}, stale {s['stale']}, "
                      f"covered {s['covered']} of {s['requirements']}")
            return 0
        if cmd == "tree":
            project = _project(svc, args)
            print("\n".join(_print_tree(e.tree(project))))
            return 0
        if cmd == "run":
            project = _project(svc, args)
            ok = True
            for t in e.command_tests(project, args.spec):
                r = e.run_test(project, t["id"], carried_by="engine")
                ok = ok and r["status"] == "pass"
                print(f"{t['id']} #{r['n']}: {r['status']} (exit {r['exit_code']})")
            return 0 if ok else 1
        if cmd == "send":
            project = _project(svc, args)
            run = svc.send(project, args.spec, profile=args.profile)
            print(f"run {run['id']} started for {args.spec} with {run['profile']}")
            return 0
        if cmd == "demo":
            p = e.reset_sample()
            print(f"sample project reset: {p['folder']}")
            return 0
        if cmd == "archive":
            e.archive_project(args.name)
            print(f"{args.name}: archived")
            return 0
        if cmd == "restore":
            e.restore_project(args.name)
            print(f"{args.name}: restored")
            return 0
        if cmd == "retire":
            project = _project(svc, args)
            e.retire_need(project, args.need, args.reason)
            print(f"{args.need}: retired")
            return 0
        if cmd == "readout":
            project = _project(svc, args)
            if args.export:
                out = e.export_readout(project, args.need)
                print(out["markdown"], end="")
                print(f"written to {out['path']}", file=sys.stderr)
            else:
                print(e.readout_markdown(project, args.need), end="")
            return 0
        project = _project(svc, args)
        t = e.tiles(project)
        if args.json:
            print(json.dumps({"tiles": t, "needs_you": e.needs_you(project)}, indent=2))
            return 0
        print(f"{project}: needs you {t['needs_you']}, running {t['running']}, stale {t['stale']}, "
              f"failing {t['failing']}, covered {t['covered']} of {t['requirements']}")
        for item in e.needs_you(project):
            print(f"  {item['type']:9} {item['id']:8} {item['text']}")
        return 0
    except RungError as exc:
        print(f"rung: {exc}", file=sys.stderr)
        return 2


def run(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="rung")
    setup(ap)
    args = ap.parse_args(argv)
    return main(args)


if __name__ == "__main__":
    sys.exit(run())
