"""Repository map: the files that matter most, ranked by PageRank.

Why: an agent that reads a ranked one-line-per-file outline first opens the
right files instead of exploring by trial, and exploration is a large share of
tokens on any new task. This is the Aider idea without tree-sitter: Python is
parsed exactly with ``ast``; JS/TS with regular expressions; other text files
contribute references by mentioning file names. PageRank aggregates many edges,
so the occasional regex miss barely moves the ranking.

The result is cached by the content hashes of every file in the tree
(``engine/cache.py``), so an unchanged tree returns without re-parsing.
"""
from __future__ import annotations

import ast
import hashlib
import json
import math
import os
import re
from pathlib import Path

from . import cache
from . import common as c

VERSION = 1
# The extractor's own source is part of every cache key, so a code change
# can never serve a map computed by older code.
CODE_HASH = c.sha256_file(__file__)
MAX_BYTES = 400_000
SKIP_DIRS = {".git", "node_modules", "dist", "build", ".venv", "venv", "__pycache__",
             ".mypy_cache", ".pytest_cache", ".next", ".turbo"}
PY_EXT = {".py"}
JS_EXT = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".mts", ".cts"}
TEXT_EXT = {".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".cfg", ".ini", ".sh", ".html",
            ".css", ".scss", ".sql", ".rst", ".jsonl", ".env.example", ".xml", ".svg"}
DAMPING = 0.85

_JS_IMPORT = re.compile(r"""(?:\bimport\s[^'"]*?from\s*|\bimport\s*\(?\s*|\bexport\s[^'"]*?from\s*|\brequire\s*\(\s*)['"]([^'"\n]+)['"]""")
_JS_DEF = re.compile(
    r"^(?:export\s+)?(?:default\s+)?(?:declare\s+)?(?:abstract\s+)?(?:async\s+)?"
    r"(?:function\s*\*?\s*|class\s+|interface\s+|type\s+|enum\s+|const\s+|let\s+|var\s+)([A-Za-z_$][\w$]*)",
    re.MULTILINE)
_IDENT = re.compile(r"[A-Za-z_$][\w$]*")
_FILE_MENTION = re.compile(r"[\w./-]+\.[A-Za-z0-9]{1,5}")


# ---------------------------------------------------------------- walking
def _skip_dir(rel_dir: str, name: str) -> bool:
    return name in SKIP_DIRS or (name in ("cache", "log") and rel_dir.replace(os.sep, "/").endswith(".brain"))


def _git_listed(root: Path) -> set[str] | None:
    """Tracked and untracked-but-not-ignored files, when root is a git work
    tree; None otherwise. Generated files the project ignores stay out of the
    map (review item M8)."""
    import subprocess
    try:
        r = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "-co", "--exclude-standard"],
                           capture_output=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    return {p.decode("utf-8", "replace") for p in r.stdout.split(b"\0") if p}


def walk(root: Path) -> list[tuple[str, bytes]]:
    """(relative posix path, bytes) for every readable text file worth mapping."""
    out = []
    listed = _git_listed(root) if (Path(root) / ".git").exists() else None
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = os.path.relpath(dirpath, root)
        dirnames[:] = sorted(d for d in dirnames if not _skip_dir(rel_dir, d))
        for name in sorted(filenames):
            path = Path(dirpath) / name
            if listed is not None and path.relative_to(root).as_posix() not in listed:
                continue
            try:
                if path.is_symlink() or path.stat().st_size > MAX_BYTES:
                    continue
                data = path.read_bytes()
            except OSError:
                continue
            if b"\0" in data[:8192]:
                continue
            try:
                data.decode("utf-8")
            except UnicodeDecodeError:
                continue
            out.append((path.relative_to(root).as_posix(), data))
    return out


def _kind(rel: str) -> str:
    suffix = Path(rel).suffix.lower()
    if suffix in PY_EXT:
        return "py"
    if suffix in JS_EXT:
        return "js"
    return "text"


# ---------------------------------------------------------------- extraction
def _py_extract(text: str) -> tuple[list[str], dict[str, int], list[tuple[int, str]]]:
    """(definitions, referenced names with counts, imports as (level, module))."""
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return [], {}, []
    defs: list[str] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defs.append(node.name)
            if isinstance(node, ast.ClassDef):
                defs += [f"{node.name}.{m.name}" for m in node.body
                         if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and not m.name.startswith("__")]
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            defs += [t.id for t in targets if isinstance(t, ast.Name) and t.id.isupper()]
    refs: dict[str, int] = {}
    imports: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            refs[node.id] = refs.get(node.id, 0) + 1
        elif isinstance(node, ast.Attribute):
            refs[node.attr] = refs.get(node.attr, 0) + 1
        elif isinstance(node, ast.Import):
            imports += [(0, a.name) for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            imports.append((node.level, base))
            for a in node.names:
                imports.append((node.level, f"{base}.{a.name}" if base else a.name))
                refs[a.name] = refs.get(a.name, 0) + 1
    return defs, refs, imports


def _js_extract(text: str) -> tuple[list[str], dict[str, int], list[str]]:
    defs = list(dict.fromkeys(_JS_DEF.findall(text)))
    refs: dict[str, int] = {}
    for w in _IDENT.findall(text):
        refs[w] = refs.get(w, 0) + 1
    for d in defs:  # a definition is not a reference to itself
        refs[d] = refs.get(d, 1) - 1
    return defs, refs, _JS_IMPORT.findall(text)


# ---------------------------------------------------------------- resolution
def _py_module_index(paths: list[str]) -> dict[str, str]:
    """Dotted module name -> file, including every suffix of the name so that
    imports work whether the package root is the repo root or a sub-folder."""
    index: dict[str, str] = {}
    for rel in paths:
        if not rel.endswith(".py"):
            continue
        parts = rel[:-3].split("/")
        if parts[-1] == "__init__":
            parts = parts[:-1]
        for i in range(len(parts)):
            index.setdefault(".".join(parts[i:]), rel)
    return index


def _resolve_py(rel: str, level: int, module: str, index: dict[str, str]) -> str | None:
    if level:
        pkg = rel.split("/")[:-1]
        pkg = pkg[: len(pkg) - (level - 1)] if level > 1 else pkg
        name = ".".join(pkg + ([module] if module else []))
        return index.get(name)
    return index.get(module)


def _resolve_js(rel: str, spec: str, files: set[str]) -> str | None:
    if not spec.startswith("."):
        return None
    base = os.path.normpath(os.path.join(os.path.dirname(rel), spec)).replace(os.sep, "/")
    candidates = [base] + [base + e for e in sorted(JS_EXT)] + [f"{base}/index{e}" for e in sorted(JS_EXT)]
    stem, ext = os.path.splitext(base)
    if ext in (".js", ".mjs", ".cjs"):  # TS sources imported with a .js suffix
        candidates += [stem + e for e in (".ts", ".tsx", ".mts", ".cts")]
    return next((cand for cand in candidates if cand in files), None)


# ---------------------------------------------------------------- graph
def build_graph(files: list[tuple[str, bytes]]) -> tuple[dict[str, dict[str, float]], dict[str, list[str]], dict[str, dict[str, int]]]:
    """Weighted edges A -> B (A depends on B), definitions per file, and per
    definition the number of other files that reference it."""
    paths = [p for p, _ in files]
    file_set = set(paths)
    by_base: dict[str, list[str]] = {}
    for p in paths:
        by_base.setdefault(p.rsplit("/", 1)[-1], []).append(p)
    py_index = _py_module_index(paths)
    defs: dict[str, list[str]] = {}
    refs: dict[str, dict[str, int]] = {}
    edges: dict[str, dict[str, float]] = {p: {} for p in paths}

    def link(a: str, b: str | None, w: float) -> None:
        if b and b != a:
            edges[a][b] = edges[a].get(b, 0.0) + w

    for rel, data in files:
        text = data.decode("utf-8")
        kind = _kind(rel)
        if kind == "py":
            d, r, imports = _py_extract(text)
            for level, module in imports:
                link(rel, _resolve_py(rel, level, module, py_index), 1.0)
        elif kind == "js":
            d, r, specs = _js_extract(text)
            for spec in specs:
                link(rel, _resolve_js(rel, spec, file_set), 1.0)
        else:
            d, r = [], {}
            for mention in set(_FILE_MENTION.findall(text)):
                mention = mention.strip("./")
                if mention in file_set:
                    link(rel, mention, 1.0)
                else:
                    for target in by_base.get(mention.rsplit("/", 1)[-1], [])[:3]:
                        link(rel, target, 0.5)
        defs[rel] = d
        refs[rel] = r

    definers: dict[str, list[str]] = {}
    for rel, names in defs.items():
        for name in names:
            definers.setdefault(name.rsplit(".", 1)[-1], []).append(rel)
    n_files = max(1, len(paths))
    inbound: dict[str, dict[str, int]] = {rel: {} for rel in paths}
    for rel, counts in refs.items():
        for name, count in counts.items():
            owners = definers.get(name)
            if not owners or count <= 0 or len(name) < 3:
                continue
            # Rare names carry the signal; names defined everywhere (get, run) do not.
            idf = math.log(1 + n_files / len(owners))
            for owner in owners:
                if owner == rel:
                    continue
                link(rel, owner, math.sqrt(count) * idf / len(owners))
                for full in defs[owner]:
                    if full.rsplit(".", 1)[-1] == name:
                        inbound[owner][full] = inbound[owner].get(full, 0) + 1
    return edges, defs, inbound


def pagerank(edges: dict[str, dict[str, float]], iterations: int = 100, tol: float = 1e-10) -> dict[str, float]:
    """Power iteration with damping 0.85; a file with no outgoing edges spreads
    its rank uniformly (the standard dangling-node fix)."""
    nodes = sorted(edges)
    n = len(nodes)
    if n == 0:
        return {}
    rank = {v: 1.0 / n for v in nodes}
    out_sum = {v: sum(edges[v].values()) for v in nodes}
    for _ in range(iterations):
        dangling = sum(rank[v] for v in nodes if out_sum[v] <= 0)
        base = (1 - DAMPING) / n + DAMPING * dangling / n
        new = {v: base for v in nodes}
        for v in nodes:
            if out_sum[v] > 0:
                share = DAMPING * rank[v] / out_sum[v]
                for target, w in edges[v].items():
                    new[target] += share * w
        delta = sum(abs(new[v] - rank[v]) for v in nodes)
        rank = new
        if delta < tol:
            break
    return rank


def build_map(root: Path | str, cache_dir: Path | str | None = None, use_cache: bool = True) -> dict:
    """Ranked files with their most-referenced symbols, cached by tree content."""
    root = Path(root)
    files = walk(root)
    k = cache.key("repomap", VERSION, CODE_HASH, sorted((p, hashlib.sha256(d).hexdigest()) for p, d in files))
    if use_cache:
        hit = cache.get(k, cache_dir)
        if hit is not None:
            hit["cached"] = True
            return hit
    edges, defs, inbound = build_graph(files)
    rank = pagerank(edges)
    ranked = []
    for rel in sorted(rank, key=lambda p: (-rank[p], p)):
        # Referenced symbols first; unreferenced private helpers are noise.
        shown = [s for s in defs[rel] if inbound[rel].get(s, 0) or not s.rsplit(".", 1)[-1].startswith("_")]
        symbols = sorted(shown, key=lambda s: (-inbound[rel].get(s, 0), defs[rel].index(s)))
        ranked.append({"path": rel, "rank": round(rank[rel], 6), "symbols": symbols[:5],
                       "refs": sum(inbound[rel].values())})
    result = {"files": ranked, "edges": sum(len(v) for v in edges.values()), "cached": False}
    if use_cache:
        cache.put(k, result, cache_dir)
    return result


def render(result: dict, top: int = 25, budget: int = 800) -> list[str]:
    """One line per file, highest rank first, stopping at ``top`` or the budget."""
    files = result["files"]
    if not files:
        return ["map: no source files found"]
    lines: list[str] = []
    used = 0
    for f in files[:top]:
        line = f["path"] + (": " + ", ".join(f["symbols"]) if f["symbols"] else "")
        cost = c.est_tokens(line) + 1
        if lines and used + cost > budget:
            break
        lines.append(line)
        used += cost
    lines.append(f"map: {len(lines)} of {len(files)} files, {result['edges']} links, ~{used} tokens"
                 + (" (cached)" if result.get("cached") else ""))
    return lines


# ---------------------------------------------------------------- cli
def _cache_dir_for(path: Path, explicit_project: str | None) -> Path:
    if explicit_project:
        return cache.default_dir(Path(explicit_project))
    for p in (path, *path.parents):
        if c.is_managed(p):
            return cache.default_dir(p)
    return cache.default_dir(None)


def cmd_map(args) -> int:
    root = Path(args.path).expanduser().resolve()
    if not root.is_dir():
        print(f"map: not a directory: {args.path}")
        return 2
    result = build_map(root, _cache_dir_for(root, args.project))
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
        return 0
    print("\n".join(render(result, args.top, args.budget)))
    return 0


def register(sub) -> None:
    p = sub.add_parser("map", help="ranked outline of a source tree (PageRank over references)")
    p.add_argument("path", nargs="?", default=".")
    p.add_argument("--top", type=int, default=12)
    p.add_argument("--budget", type=int, default=800, help="token budget for the printed map")
    p.add_argument("--json", action="store_true")
    c.add_project_arg(p)
    p.set_defaults(func=cmd_map)
