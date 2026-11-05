#!/usr/bin/env python3
"""Build desktop/plugin.js from desktop/src/*.js. Standard library only.

The pane is written with a small Tailwind-like utility vocabulary (the prototype's own class
names, with its hex colours replaced by Rung tokens such as `text-fg` or `bg-needs/10`). This
script collects every class the sources use, generates scoped CSS for exactly those classes
(under `.rung`), and inlines it into the single file the Desktop loads. Unknown utility-looking
classes fail the build, so a typo cannot silently drop a style.

    python3 scripts/build_desktop.py          # writes desktop/plugin.js
    python3 scripts/build_desktop.py --check  # exit 1 if desktop/plugin.js is out of date
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "desktop" / "src"
OUT = ROOT / "desktop" / "plugin.js"

COLORS = {
    "fg": "var(--r-fg)", "fg2": "var(--r-fg2)", "muted": "var(--r-muted)", "dim": "var(--r-dim)",
    "card": "var(--r-card)", "line": "var(--r-line)", "line2": "var(--r-line2)", "well": "var(--r-well)",
    "btn": "var(--r-btn)", "btnh": "var(--r-btnh)", "page": "var(--r-page)",
    "needs": "var(--r-needs)", "pass": "var(--r-pass)", "fail": "var(--r-fail)", "stale": "var(--r-stale)",
    "draft": "var(--r-draft)", "on-needs": "var(--r-on-needs)", "on-pass": "var(--r-on-pass)",
    "transparent": "transparent", "current": "currentColor",
}
SPACE = {"0": "0px", "px": "1px", "0.5": "2px", "1": "4px", "1.5": "6px", "2": "8px", "2.5": "10px", "3": "12px",
         "3.5": "14px", "4": "16px", "5": "20px", "6": "24px", "7": "28px", "8": "32px", "9": "36px", "10": "40px",
         "11": "44px", "12": "48px", "14": "56px", "16": "64px", "20": "80px", "24": "96px", "28": "112px",
         "32": "128px", "36": "144px", "40": "160px", "48": "192px", "56": "224px", "64": "256px", "72": "288px",
         "80": "320px", "96": "384px"}
FONT = {"xs": ("12px", "16px"), "sm": ("14px", "20px"), "base": ("16px", "24px"), "lg": ("18px", "28px"),
        "xl": ("20px", "28px"), "2xl": ("24px", "32px"), "3xl": ("30px", "36px")}
WEIGHT = {"normal": 400, "medium": 500, "semibold": 600, "bold": 700}
TRACK = {"tight": "-0.025em", "tighter": "-0.05em", "wide": "0.025em", "wider": "0.05em", "widest": "0.1em",
         "normal": "0"}
LEAD = {"none": "1", "tight": "1.25", "snug": "1.375", "normal": "1.5", "relaxed": "1.625", "loose": "2"}
MAXW = {"md": "28rem", "lg": "32rem", "xl": "36rem", "2xl": "42rem", "3xl": "48rem", "none": "none"}
STATIC = {
    "flex": "display:flex", "inline-flex": "display:inline-flex", "grid": "display:grid", "block": "display:block",
    "inline-block": "display:inline-block", "inline": "display:inline", "hidden": "display:none",
    "contents": "display:contents",
    "flex-col": "flex-direction:column", "flex-row": "flex-direction:row", "flex-wrap": "flex-wrap:wrap",
    "flex-1": "flex:1 1 0%", "flex-none": "flex:none", "shrink-0": "flex-shrink:0", "grow": "flex-grow:1",
    "items-center": "align-items:center", "items-start": "align-items:flex-start", "items-end": "align-items:flex-end",
    "items-baseline": "align-items:baseline", "items-stretch": "align-items:stretch",
    "justify-between": "justify-content:space-between", "justify-center": "justify-content:center",
    "justify-end": "justify-content:flex-end", "justify-start": "justify-content:flex-start",
    "self-start": "align-self:flex-start", "self-center": "align-self:center", "self-end": "align-self:flex-end",
    "w-full": "width:100%", "h-full": "height:100%", "min-w-0": "min-width:0", "min-h-0": "min-height:0",
    "w-auto": "width:auto", "mx-auto": "margin-left:auto;margin-right:auto", "ml-auto": "margin-left:auto",
    "rounded": "border-radius:4px", "rounded-md": "border-radius:6px", "rounded-lg": "border-radius:8px",
    "rounded-full": "border-radius:9999px", "rounded-none": "border-radius:0",
    "border": "border-width:1px;border-style:solid", "border-2": "border-width:2px;border-style:solid",
    "border-t": "border-top-width:1px;border-top-style:solid", "border-b": "border-bottom-width:1px;border-bottom-style:solid",
    "border-l": "border-left-width:1px;border-left-style:solid", "border-r": "border-right-width:1px;border-right-style:solid",
    "border-l-2": "border-left-width:2px;border-left-style:solid", "border-l-[3px]": "border-left-width:3px;border-left-style:solid",
    "border-dashed": "border-style:dashed", "border-0": "border-width:0",
    "uppercase": "text-transform:uppercase", "italic": "font-style:italic", "line-through": "text-decoration:line-through",
    "underline": "text-decoration:underline", "no-underline": "text-decoration:none",
    "truncate": "overflow:hidden;text-overflow:ellipsis;white-space:nowrap", "whitespace-nowrap": "white-space:nowrap",
    "whitespace-pre-wrap": "white-space:pre-wrap", "whitespace-pre": "white-space:pre", "break-all": "word-break:break-all",
    "text-left": "text-align:left", "text-right": "text-align:right", "text-center": "text-align:center",
    "mono": "font-family:var(--dt-font-mono, ui-monospace, monospace)",
    "font-mono": "font-family:var(--dt-font-mono, ui-monospace, monospace)",
    "overflow-hidden": "overflow:hidden", "overflow-y-auto": "overflow-y:auto", "overflow-x-auto": "overflow-x:auto",
    "overflow-auto": "overflow:auto", "cursor-pointer": "cursor:pointer", "cursor-default": "cursor:default",
    "cursor-not-allowed": "cursor:not-allowed", "select-none": "user-select:none", "resize-none": "resize:none",
    "resize-y": "resize:vertical", "outline-none": "outline:none", "pointer-events-none": "pointer-events:none",
    "relative": "position:relative", "absolute": "position:absolute", "sticky": "position:sticky",
    "inset-0": "inset:0", "top-0": "top:0", "bottom-0": "bottom:0", "left-0": "left:0", "right-0": "right:0",
    "z-10": "z-index:10", "table-fixed": "table-layout:fixed", "border-collapse": "border-collapse:collapse",
    "animate-pulse": "animation:rung-pulse 2s cubic-bezier(.4,0,.6,1) infinite",
    "animate-spin": "animation:rung-spin 1s linear infinite",
    "transition-colors": "transition:color .15s,background-color .15s,border-color .15s",
    "list-none": "list-style:none", "leading-tight": "line-height:1.25",
    "divide-y": "", "tabular-nums": "font-variant-numeric:tabular-nums", "appearance-none": "appearance:none",
    "font-sans": "font-family:var(--dt-font-sans, system-ui, sans-serif)",
    "w-fit": "width:fit-content", "shadow-2xl": "box-shadow:0 25px 50px -12px rgba(0,0,0,.5)", "z-50": "z-index:50",
    "inset-y-0": "top:0;bottom:0", "fixed": "position:fixed", "wrap-anywhere": "overflow-wrap:anywhere",
}
VARIANTS = {"hover": ":hover", "focus": ":focus", "disabled": ":disabled", "focus-within": ":focus-within",
            "placeholder": "::placeholder"}


def length(v: str) -> str | None:
    if v in SPACE:
        return SPACE[v]
    if re.fullmatch(r"\d+(\.5)?", v):
        return f"{float(v) * 0.25:g}rem"
    m = re.fullmatch(r"\[(-?[\d.]+(?:px|rem|em|%|vh|vw|ch))\]", v)
    if m:
        return m.group(1)
    if re.fullmatch(r"\d+/\d+", v):
        a, b = v.split("/")
        return f"{int(a) / int(b) * 100:.4f}%"
    return None


def color(v: str) -> str | None:
    base, _, alpha = v.partition("/")
    c = COLORS.get(base)
    if c is None:
        return None
    if alpha:
        return f"color-mix(in srgb, {c} {int(alpha)}%, transparent)"
    return c


def rule(cls: str) -> str | None:
    """Declarations for one bare utility (no variant), or None when unknown."""
    if cls in STATIC:
        return STATIC[cls]
    m = re.fullmatch(r"(-?)(p|px|py|pt|pb|pl|pr|m|mx|my|mt|mb|ml|mr)-(.+)", cls)
    if m:
        neg, k, v = m.groups()
        L = length(v)
        if L is None:
            return None
        if neg:
            L = f"-{L}"
        side = {"p": ["padding"], "px": ["padding-left", "padding-right"], "py": ["padding-top", "padding-bottom"],
                "pt": ["padding-top"], "pb": ["padding-bottom"], "pl": ["padding-left"], "pr": ["padding-right"],
                "m": ["margin"], "mx": ["margin-left", "margin-right"], "my": ["margin-top", "margin-bottom"],
                "mt": ["margin-top"], "mb": ["margin-bottom"], "ml": ["margin-left"], "mr": ["margin-right"]}[k]
        return ";".join(f"{s}:{L}" for s in side)
    m = re.fullmatch(r"gap(-x|-y)?-(.+)", cls)
    if m:
        L = length(m.group(2))
        if L is None:
            return None
        return {None: f"gap:{L}", "-x": f"column-gap:{L}", "-y": f"row-gap:{L}"}[m.group(1)]
    m = re.fullmatch(r"(w|h|min-w|min-h|max-w|max-h)-(.+)", cls)
    if m:
        k, v = m.groups()
        prop = {"w": "width", "h": "height", "min-w": "min-width", "min-h": "min-height", "max-w": "max-width",
                "max-h": "max-height"}[k]
        if k == "max-w" and v in MAXW:
            return f"max-width:{MAXW[v]}"
        L = length(v)
        return f"{prop}:{L}" if L else None
    m = re.fullmatch(r"grid-cols-(\d+)", cls)
    if m:
        return f"grid-template-columns:repeat({m.group(1)},minmax(0,1fr))"
    m = re.fullmatch(r"grid-cols-\[(.+)\]", cls)
    if m:
        return "grid-template-columns:" + m.group(1).replace("_", " ")
    m = re.fullmatch(r"col-span-(\d+)", cls)
    if m:
        return f"grid-column:span {m.group(1)} / span {m.group(1)}"
    m = re.fullmatch(r"text-(xs|sm|base|lg|xl|2xl|3xl)", cls)
    if m:
        s, lh = FONT[m.group(1)]
        return f"font-size:{s};line-height:{lh}"
    m = re.fullmatch(r"text-\[(\d+(?:\.\d+)?px)\]", cls)
    if m:
        return f"font-size:{m.group(1)}"
    m = re.fullmatch(r"font-(normal|medium|semibold|bold)", cls)
    if m:
        return f"font-weight:{WEIGHT[m.group(1)]}"
    m = re.fullmatch(r"tracking-(\w+)", cls)
    if m and m.group(1) in TRACK:
        return f"letter-spacing:{TRACK[m.group(1)]}"
    m = re.fullmatch(r"leading-(\w+|\[.+\])", cls)
    if m:
        v = m.group(1)
        if v in LEAD:
            return f"line-height:{LEAD[v]}"
        if v.startswith("["):
            return f"line-height:{v[1:-1]}"
        if v in SPACE:
            return f"line-height:{SPACE[v]}"
    m = re.fullmatch(r"rounded-\[(\d+px)\]", cls)
    if m:
        return f"border-radius:{m.group(1)}"
    m = re.fullmatch(r"opacity-(\d+)", cls)
    if m:
        return f"opacity:{int(m.group(1)) / 100}"
    m = re.fullmatch(r"(bg|text|border|border-l|border-t|border-b|divide|ring|placeholder|accent|decoration)-(.+)", cls)
    if m:
        k, v = m.groups()
        c = color(v)
        if c is None:
            return None
        return {"bg": f"background-color:{c}", "text": f"color:{c}", "border": f"border-color:{c}",
                "border-l": f"border-left-color:{c}", "border-t": f"border-top-color:{c}",
                "border-b": f"border-bottom-color:{c}", "divide": f"--r-divide:{c}",
                "ring": f"box-shadow:0 0 0 1px {c}", "placeholder": f"--r-ph:{c}", "accent": f"accent-color:{c}",
                "decoration": f"text-decoration-color:{c}"}[k]
    m = re.fullmatch(r"space-y-(.+)", cls)
    if m and length(m.group(1)):
        return f"--r-space-y:{length(m.group(1))}"
    return None


def esc(cls: str) -> str:
    return re.sub(r"([^a-zA-Z0-9_-])", r"\\\1", cls)


def css_for(classes: set[str]) -> tuple[str, list[str]]:
    out, unknown = [], []
    for cls in sorted(classes):
        variant, _, bare = cls.rpartition(":")
        if variant and variant not in VARIANTS:
            unknown.append(cls)
            continue
        decl = rule(bare)
        if decl is None:
            unknown.append(cls)
            continue
        if not decl:
            continue
        sel = f".rung .{esc(cls)}"
        if variant == "placeholder":
            out.append(f".rung .{esc(cls)}::placeholder{{{decl.replace('--r-ph:', 'color:')}}}")
            continue
        if variant:
            sel += VARIANTS[variant]
        if bare.startswith("divide-") and bare != "divide-y":
            out.append(f".rung .{esc(cls)}>*+*{{border-color:{decl.split(':', 1)[1]}}}")
            continue
        if bare.startswith("space-y-"):
            out.append(f".rung .{esc(cls)}>*+*{{margin-top:{decl.split(':', 1)[1]}}}")
            continue
        out.append(f"{sel}{{{decl}}}")
    out.append(".rung .divide-y>*+*{border-top-width:1px;border-top-style:solid}")
    return "\n".join(out), unknown


UTILITY_HINT = re.compile(r"^(?:[a-z-]+:)?-?(?:p[xytblr]?|m[xytblr]?|gap|w|h|min-w|max-w|text|bg|border|font|tracking|"
                          r"leading|rounded|flex|items|justify|grid|col|opacity|divide|space)(?:-|$)")


def collect(sources: str) -> set[str]:
    classes = set()
    for m in re.finditer(r"(?:className|cls)\s*:\s*(['`\"])(.*?)\1", sources, re.S):
        for c in re.split(r"\s+", m.group(2)):
            if c and "${" not in c and "}" not in c:
                classes.add(c)
    for m in re.finditer(r"\bh\(\s*'[a-z0-9]+'\s*,\s*'([^']*)'", sources):
        classes.update(c for c in m.group(1).split() if c)
    for m in re.finditer(r"\bcx\(([^)]*)\)", sources):
        for s in re.finditer(r"'([^']*)'", m.group(1)):
            classes.update(c for c in s.group(1).split() if c)
    for m in re.finditer(r"/\*cls\*/\s*'([^']*)'", sources):
        classes.update(c for c in m.group(1).split() if c)
    for m in re.finditer(r"//\s*safelist:(.*)", sources):
        classes.update(c for c in m.group(1).split() if c)
    # Any other string literal made only of known utilities (badge tables, tone maps).
    for m in re.finditer(r"'([a-z][^'\n]*)'", sources):
        toks = m.group(1).split()
        if toks and all(_known(t) for t in toks) and any(not t.isalpha() or t in STATIC for t in toks):
            classes.update(toks)
    return classes


def _known(tok: str) -> bool:
    variant, _, bare = tok.rpartition(":")
    if variant and variant not in VARIANTS:
        return False
    return rule(bare) is not None


def build() -> str:
    parts = [p.read_text() for p in sorted(SRC.glob("*.js"))]
    js = "\n".join(parts)
    classes = collect(js)
    css, unknown = css_for(classes)
    unknown = [u for u in unknown if UTILITY_HINT.match(u)]
    if unknown:
        raise SystemExit("unknown utility classes: " + ", ".join(sorted(unknown)))
    header = "// GENERATED by scripts/build_desktop.py from desktop/src/*.js. Edit the sources, then rebuild.\n"
    return header + js.replace("/*__RUNG_CSS__*/''", "`" + css.replace("\\", "\\\\").replace("`", "\\`") + "`")


def main() -> int:
    out = build()
    if "--check" in sys.argv:
        if not OUT.exists() or OUT.read_text() != out:
            print("desktop/plugin.js is out of date: run scripts/build_desktop.py")
            return 1
        return 0
    OUT.write_text(out)
    print(f"wrote {OUT.relative_to(ROOT)} ({len(out)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
