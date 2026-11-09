"""What a test result applies to: the code basis of a project and the files a test is judged by.

Standard library only, no model call. Two facts are computed here:

* the project basis: one digest over the content of the project's files (a walk that honours `.gitignore` files,
  without starting a process, so the read-only done hook computes the same value), minus generated and runtime
  files and anything listed in a `.rungignore` file. A result is current only while the basis it was recorded against is still the basis now.
* a test's protected files: the files its command names, the test modules it imports, a discovering runner's test
  files and the runner's configuration. A worker that changes any of them after a person approved the test does
  not get a counting result until a person accepts the change.

Both are integrity checks for cooperative local work, not a security boundary: a process with the same OS user can
change anything, Rung included.
"""

from __future__ import annotations

import fnmatch
import hashlib
import os
import re
import shlex
import threading
import time
from pathlib import Path

# Generated, cached or runtime output: never part of the basis.
EXCLUDE_DIRS = {".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv", ".tox", ".nox",
                ".pytest_cache", ".mypy_cache", ".ruff_cache", ".cache", ".idea", ".vscode", "dist", "build",
                ".next", ".parcel-cache", "coverage", "htmlcov", ".rung-stub", ".eggs"}
EXCLUDE_GLOBS = ("*.pyc", "*.pyo", "*.db", "*.db-journal", "*.db-wal", "*.db-shm", "*.sqlite", "*.sqlite3",
                 "*.log", ".DS_Store", "*.swp", "*~", ".coverage", "*.egg-info")
MAX_FILES = 20000
MAX_BYTES = 256 * 1024 * 1024

UNKNOWN = "unknown"

_lock = threading.Lock()
_file_cache: dict[str, tuple[int, int, str]] = {}  # abs path -> (size, mtime_ns, sha256)
_basis_cache: dict[str, tuple[float, str, int]] = {}  # root -> (computed at, basis, file count)
TTL = 1.0


def _ignored(rel: str, extra: list[str]) -> bool:
    parts = rel.split("/")
    if any(p in EXCLUDE_DIRS or p.endswith(".egg-info") for p in parts[:-1]):
        return True
    name = parts[-1]
    if any(fnmatch.fnmatch(name, g) for g in EXCLUDE_GLOBS):
        return True
    for pat in extra:
        pat = pat.rstrip("/")
        if fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(name, pat) or rel.startswith(pat + "/"):
            return True
    return False


def rungignore(root: Path) -> list[str]:
    try:
        lines = (root / ".rungignore").read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    return [ln.strip().lstrip("/") for ln in lines if ln.strip() and not ln.strip().startswith("#")]


def _gitignore(path: Path) -> list[tuple[bool, bool, bool, str]]:
    """(negate, dir_only, anchored, pattern) rules of one ignore file; [] when there is none."""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    rules = []
    for ln in lines:
        ln = ln.rstrip()
        if not ln or ln.startswith("#"):
            continue
        neg = ln.startswith("!")
        ln = ln[1:] if neg else ln
        dir_only = ln.endswith("/")
        ln = ln.rstrip("/")
        anchored = "/" in ln
        rules.append((neg, dir_only, anchored, ln.lstrip("/")))
    return rules


def _matches(rules, rel: str, is_dir: bool) -> bool | None:
    """Last matching rule wins, as git reads them: True ignored, False re-included, None no rule matched."""
    name = rel.rsplit("/", 1)[-1]
    hit = None
    for neg, dir_only, anchored, pat in rules:
        if dir_only and not is_dir:
            continue
        target = rel if anchored else name
        if fnmatch.fnmatch(target, pat) or (anchored and "**" in pat and fnmatch.fnmatch(rel, pat.replace("**/", ""))):
            hit = not neg
    return hit


def _walk(root: Path, extra: list[str]) -> list[str] | None:
    """The project's files without starting a process: .gitignore files (root, nested and .git/info/exclude) are
    read the way git reads them for the common patterns, so the done hook can compute the same basis read only."""
    is_git = (root / ".git").exists()
    base_rules = (_gitignore(root / ".git" / "info" / "exclude") if is_git else []) + _gitignore(root / ".gitignore")
    files: list[str] = []
    stack = [(root, "", base_rules)]
    while stack:
        d, prefix, rules = stack.pop()
        try:
            entries = sorted(os.scandir(d), key=lambda x: x.name)
        except OSError:
            continue
        local = rules
        if prefix:
            nested = _gitignore(d / ".gitignore")
            if nested:  # nested rules are relative to their own folder
                local = rules + [(n, do, a, (prefix + "/" + p) if a else p) for n, do, a, p in nested]
        for ent in entries:
            rel = f"{prefix}/{ent.name}" if prefix else ent.name
            try:
                is_dir = ent.is_dir(follow_symlinks=False)
            except OSError:
                continue
            if is_dir:
                if ent.name in EXCLUDE_DIRS or ent.name.endswith(".egg-info") or _matches(local, rel, True):
                    continue
                stack.append((Path(ent.path), rel, local))
                continue
            if _matches(local, rel, False) or _ignored(rel, extra):
                continue
            files.append(rel)
            if len(files) > MAX_FILES:
                return None
    return files


def project_files(root: Path) -> list[str] | None:
    """Every file in the basis, relative and sorted; None when there are more than MAX_FILES."""
    root = Path(root)
    files = _walk(root, rungignore(root))
    return None if files is None else sorted(set(files))


def file_sha(path: Path) -> str | None:
    """Content digest of one file, cached by size and modification time. None when it does not exist."""
    try:
        st = path.stat()
    except OSError:
        return None
    if not path.is_file():
        return None
    key = str(path)
    with _lock:
        hit = _file_cache.get(key)
    if hit and hit[0] == st.st_size and hit[1] == st.st_mtime_ns:
        return hit[2]
    h = hashlib.sha256()
    try:
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
    except OSError:
        return None
    digest = h.hexdigest()
    with _lock:
        _file_cache[key] = (st.st_size, st.st_mtime_ns, digest)
    return digest


def manifest(root) -> dict | None:
    """{relative path: content digest} for every file in the basis; None when unreadable or too large."""
    root = Path(root).expanduser()
    if not root.is_dir():
        return None
    files = project_files(root)
    if files is None:
        return None
    out, total = {}, 0
    for rel in files:
        p = root / rel
        try:
            total += p.stat().st_size
        except OSError:
            continue
        if total > MAX_BYTES:
            return None
        sha = file_sha(p)
        if sha is not None:
            out[rel] = sha
    return out


def digest(m: dict | None) -> str:
    if m is None:
        return UNKNOWN
    h = hashlib.sha256()
    for rel in sorted(m):
        h.update(rel.encode("utf-8", "replace") + b"\0" + m[rel].encode() + b"\n")
    return "sha256:" + h.hexdigest()


def modified(before: dict | None, after: dict | None) -> list[str]:
    """Files that existed before and were changed or deleted by the time of `after`. A file created in between is
    output (a test writing its own artifact), not a change to the code under test."""
    if before is None or after is None:
        return []
    return sorted(f for f, sha in before.items() if after.get(f) != sha)


def basis(root, fresh: bool = False) -> str:
    """`sha256:<hex>` over the project's files, or `unknown` when the folder is missing or too large to read whole."""
    root = Path(root).expanduser()
    key = str(root)
    if not fresh:
        with _lock:
            hit = _basis_cache.get(key)
        if hit and time.monotonic() - hit[0] < TTL:
            return hit[1]
    result = digest(manifest(root))
    with _lock:
        _basis_cache[key] = (time.monotonic(), result, 0)
    return result


def forget(root=None) -> None:
    with _lock:
        if root is None:
            _basis_cache.clear()
        else:
            _basis_cache.pop(str(Path(root).expanduser()), None)


# ---------------------------------------------------------------------------------------------- protected files

TEST_GLOBS = ("test_*.py", "*_test.py", "conftest.py", "*.test.js", "*.test.ts", "*.test.jsx", "*.test.tsx",
              "*.spec.js", "*.spec.ts", "*.spec.jsx", "*.spec.tsx", "*_test.go", "*_spec.rb")
TEST_DIRS = {"tests", "test", "__tests__", "spec"}
RUNNER_CONFIG = ("pytest.ini", "tox.ini", "conftest.py", "jest.config.js", "jest.config.ts", "vitest.config.ts",
                 "vitest.config.js", ".mocharc.json", ".mocharc.js", "phpunit.xml")
# An option's argument never looks like a path, so `pytest -q tests/test_api.py` names one file, not the suite.
DISCOVERING = re.compile(r"(^|[\s;&|(])(pytest|py\.test)(\s+-[\w-]+(\s+(?![^\s;&|)]*(/|\.py\b|::))[^\s;&|)-]\S*)?)*"
                         r"\s*($|[;&|)])|"
                         r"-m\s+(pytest|unittest)(\s+(discover|-[\w-]+))*\s*($|[;&|)])|"
                         r"\b(npm|pnpm|yarn)\s+(run\s+)?test\b|\bgo\s+test\b|\bcargo\s+test\b|\bjest\b|\bvitest\b|"
                         r"\bmocha\b|\brspec\b|\bphpunit\b")
_MODULE = re.compile(r"(?:-m\s+|from\s+|import\s+)([A-Za-z_][\w.]*)")


def _is_test_path(rel: str) -> bool:
    parts = rel.split("/")
    return any(p in TEST_DIRS for p in parts[:-1]) or any(fnmatch.fnmatch(parts[-1], g) for g in TEST_GLOBS)


def _tokens(command: str) -> list[str]:
    try:
        return shlex.split(command, comments=False, posix=True)
    except ValueError:
        return command.split()


def protected_files(command: str, folder: Path, root: Path) -> list[str]:
    """The files a command test is judged by, relative to the project root. Names a file the command refers to
    even before it exists, so a worker creating it is a change too."""
    root, folder = Path(root).expanduser(), Path(folder).expanduser()
    try:
        rroot = root.resolve()
    except OSError:
        return []
    out: set[str] = set()

    def add(p: Path, must_exist: bool = False):
        try:
            rp = p.resolve()
        except OSError:
            return
        if not rp.is_relative_to(rroot):
            return
        rel = rp.relative_to(rroot).as_posix()
        if rel in ("", "."):
            return
        if rp.is_dir():
            files = project_files(rp) or []
            for f in files:
                if _is_test_path(f) or rp != rroot:
                    out.add(f"{rel}/{f}")
            return
        if must_exist and not rp.is_file():
            return
        if not any(part in EXCLUDE_DIRS for part in Path(rel).parts):
            out.add(rel)

    for tok in _tokens(command or ""):
        tok = tok.split("::", 1)[0]
        if not tok or tok.startswith("-") or "=" in tok and not tok.startswith(("./", "/")):
            continue
        looks = "/" in tok or re.search(r"\.(py|js|ts|jsx|tsx|mjs|cjs|sh|rb|go|json|ya?ml|toml|ini|cfg|txt|csv)$", tok)
        if looks:
            add(folder / tok)
    for mod in _MODULE.findall(command or ""):
        rel = mod.replace(".", "/")
        for cand in (folder / f"{rel}.py", folder / rel / "__init__.py"):
            r = cand.resolve().relative_to(rroot).as_posix() if cand.resolve().is_relative_to(rroot) else None
            if r and cand.is_file() and _is_test_path(r):
                add(cand, must_exist=True)
    if DISCOVERING.search(command or ""):
        for f in project_files(root) or []:
            if _is_test_path(f):
                out.add(f)
    for f in RUNNER_CONFIG:
        if (root / f).is_file():
            out.add(f)
        if folder != root and (folder / f).is_file():
            add(folder / f, must_exist=True)
    return sorted(out)


def digest_files(root: Path, files: list[str]) -> dict:
    root = Path(root).expanduser()
    return {f: file_sha(root / f) for f in files}


def changed(baseline: dict, current: dict) -> list[dict]:
    """Protected files that differ from the approved baseline: changed, created or deleted."""
    out = []
    for f in sorted(set(baseline) | set(current)):
        before, after = baseline.get(f), current.get(f)
        if before == after:
            continue
        kind = "created" if before is None else "deleted" if after is None else "changed"
        out.append({"path": f, "change": kind})
    return out


def short(b: str | None) -> str:
    if not b:
        return ""
    if b.startswith("sha256:"):
        return b[7:19]
    return b
