"""Memory search and packing: `brain recall "<query>"`.

Why this shape (docs/research/04-algorithms.md sections 1.1 and 3.1):

- Relevance comes from SQLite's built-in FTS5 index with BM25 ranking, built
  in memory from the item files each call (a fraction of a second, nothing
  committed, nothing installed). Class tags are weighted above the text. If
  this Python's SQLite lacks FTS5, a pure-Python BM25 gives the same kind of
  ranking so the command never breaks.
- Each hit is scored by relevance x confidence x recency x importance.
- The pack is chosen by greedy maximisation of a monotone submodular coverage
  objective, gain per token, under the token budget. Coverage is what makes
  near-duplicates cost-ineffective: an item whose words are already covered by
  a better item adds almost nothing, so the budget goes to new information.
  (MMR is not used: it has no approximation guarantee and over-fills.)
- Owner-stated standing instructions that match are seated first, so lessons
  can never crowd out what the owner said.
"""
from __future__ import annotations

import heapq
import json
import math
import sqlite3
import unicodedata
from pathlib import Path

from . import common as c
from . import items as it

IMPORTANCE = {1: 0.85, 2: 1.0, 3: 1.2}
TAG_WEIGHT = 2.0          # BM25 column weight for class tags (text is 1.0)
QUERY_UNIT_WEIGHT = 3.0   # a query word counts more than an incidental word
STANDING_FLOOR = 0.5      # minimum score of a matching owner standing instruction
REDUNDANT = 0.25          # an item adding < 25% of its standalone value is a near-duplicate
SUFFIXES = ("aciones", "iciones", "ciones", "ations", "ation", "ments", "ment", "ings", "ing", "ción", "cion",
            "edly", "ies", "ied", "es", "ed", "ly", "s")


# ---------------------------------------------------------------- text
def _fold(word: str) -> str:
    word = unicodedata.normalize("NFKD", word.lower())
    return "".join(ch for ch in word if not unicodedata.combining(ch))


def _stem(word: str) -> str:
    """Light suffix stripping so 'deploying' finds 'deployment' through a
    prefix query; the stem never drops below four letters."""
    for suf in SUFFIXES:
        suf = _fold(suf)
        if word.endswith(suf) and len(word) - len(suf) >= 4:
            return word[: -len(suf)]
    return word


def query_terms(query: str) -> list[tuple[str, bool]]:
    """(term, is_prefix) per distinct content word: words of four or more
    letters match as prefixes of their stem, shorter ones exactly."""
    out: dict[str, bool] = {}
    for w in c.words(query):
        w = _fold(w)
        for part in [p for p in "".join(ch if ch.isalnum() else " " for ch in w).split() if len(p) > 1]:
            if len(part) >= 4:
                out.setdefault(_stem(part), True)
            else:
                out.setdefault(part, False)
    return list(out.items())


def _doc_tokens(text: str) -> list[str]:
    return [p for w in c.words(text) for p in "".join(ch if ch.isalnum() else " " for ch in _fold(w)).split() if len(p) > 1]


def _matches(token: str, term: str, prefix: bool) -> bool:
    return token.startswith(term) if prefix else token == term


# ---------------------------------------------------------------- relevance
def _fts5_relevance(docs: list[tuple[str, str]], terms: list[tuple[str, bool]]) -> list[float]:
    """BM25 per document from an in-memory FTS5 table (higher is better)."""
    con = sqlite3.connect(":memory:")
    try:
        con.execute("CREATE VIRTUAL TABLE m USING fts5(body, tags, tokenize='unicode61 remove_diacritics 2')")
        con.executemany("INSERT INTO m(rowid, body, tags) VALUES (?, ?, ?)",
                        [(i + 1, body, tags) for i, (body, tags) in enumerate(docs)])
        match = " OR ".join(f'"{t}"' + ("*" if p else "") for t, p in terms)
        rows = con.execute(f"SELECT rowid, bm25(m, 1.0, {TAG_WEIGHT}) FROM m WHERE m MATCH ?", (match,)).fetchall()
    finally:
        con.close()
    rel = [0.0] * len(docs)
    for rowid, score in rows:
        rel[rowid - 1] = max(1e-9, -float(score))  # FTS5 bm25: lower (more negative) is better
    return rel


def _python_relevance(docs: list[tuple[str, str]], terms: list[tuple[str, bool]]) -> list[float]:
    """FTS5's BM25 in pure Python (k1 1.2, b 0.75, per-column weights, and
    FTS5's rule that a term in more than half the documents gets IDF 1e-6)."""
    k1, b = 1.2, 0.75
    cols = [[_doc_tokens(body) for body, _ in docs], [_doc_tokens(tags) for _, tags in docs]]
    weights = [1.0, TAG_WEIGHT]
    n = len(docs)
    rel = [0.0] * n
    # FTS5 sums over columns with one IDF over the whole row.
    for t, p in terms:
        df = sum(1 for i in range(n) if any(_matches(tok, t, p) for col in cols for tok in col[i]))
        if df == 0:
            continue
        idf = math.log((n - df + 0.5) / (df + 0.5))
        idf = idf if idf > 0 else 1e-6
        for col, w in zip(cols, weights):
            avg = sum(len(d) for d in col) / n or 1.0
            for i, toks in enumerate(col):
                tf = sum(1 for tok in toks if _matches(tok, t, p))
                if tf:
                    rel[i] += w * idf * tf * (k1 + 1) / (tf + k1 * (1 - b + b * len(toks) / avg))
    return rel


def relevance(docs: list[tuple[str, str]], terms: list[tuple[str, bool]]) -> list[float]:
    if not docs or not terms:
        return [0.0] * len(docs)
    try:
        return _fts5_relevance(docs, terms)
    except sqlite3.Error:
        return _python_relevance(docs, terms)


# ---------------------------------------------------------------- scoring
def recency(item: dict) -> float:
    """1.0 if used or created within 30 days, falling linearly to 0.7 at a year."""
    d = min(c.days_since(item.get("last_used") or ""), c.days_since(item.get("created") or ""))
    if d <= 30:
        return 1.0
    return max(0.7, 1.0 - 0.3 * (d - 30) / (365 - 30))


def _is_standing(item: dict) -> bool:
    return item.get("type") == "standing" and item.get("trust") == "owner-stated"


def _in_scope(item: dict, family: str | None, from_project: bool) -> bool:
    scope = item.get("scope", "")
    if from_project:
        return True
    if scope == "global":
        return True
    if scope.startswith("family:"):
        return family is not None and scope == f"family:{family}"
    return False  # a 'project' item stored in the brain belongs to no project here


def _line(item: dict) -> str:
    return f"[{item['id']}] {item['text']}" + (" (probation)" if item.get("status") == "probation" else "")


# ---------------------------------------------------------------- packing
def pack(cands: list[dict], terms: list[tuple[str, bool]], k: int, budget: int) -> list[dict]:
    """Lazy greedy (CELF) on F(S) = sum over units u of w_u * max_{i in S} s_i [u in i].

    Units are the query terms (weight 3) and the content words of the
    candidates (weight 1); s_i is the item's score. F is monotone submodular,
    so gain-per-token greedy with the best single item as a fallback carries
    the classical constant-factor guarantee under a knapsack budget. Seeded
    items (matching standing instructions) are placed first."""
    if not cands or k <= 0:
        return []
    units: list[dict[str, float]] = []
    for cd in cands:
        toks = set(cd["_tokens"])
        u = {f"w:{t}": 1.0 for t in toks}
        for t, p in terms:
            if any(_matches(tok, t, p) for tok in toks):
                u[f"q:{t}"] = QUERY_UNIT_WEIGHT
        units.append(u)
    covered: dict[str, float] = {}

    def gain(i: int) -> float:
        s = cands[i]["score"]
        return sum(w * max(0.0, s - covered.get(u, 0.0)) for u, w in units[i].items())

    alone = [gain(i) for i in range(len(cands))]
    chosen: list[int] = []
    used = 0

    def take(i: int) -> None:
        nonlocal used
        chosen.append(i)
        used += cands[i]["_cost"]
        for u in units[i]:
            covered[u] = max(covered.get(u, 0.0), cands[i]["score"])

    seeds = [i for i in range(len(cands)) if cands[i]["_seed"]]
    for i in sorted(seeds, key=lambda i: -cands[i]["score"])[: max(1, k // 2)]:
        if used + cands[i]["_cost"] <= budget:
            take(i)
    heap = [(-alone[i] / cands[i]["_cost"], i, -1) for i in range(len(cands)) if i not in chosen]
    heapq.heapify(heap)
    while heap and len(chosen) < k:
        neg, i, stamp = heapq.heappop(heap)
        if used + cands[i]["_cost"] > budget:
            continue
        if stamp != len(chosen):  # stale bound: recompute and push back (lazy evaluation)
            heapq.heappush(heap, (-gain(i) / cands[i]["_cost"], i, len(chosen)))
            continue
        g = -neg * cands[i]["_cost"]
        if g <= 1e-9 or g < REDUNDANT * alone[i]:
            continue  # nothing new, or mostly a restatement of what is packed
        take(i)
    if not seeds:
        fits = [i for i in range(len(cands)) if cands[i]["_cost"] <= budget]
        if fits:
            single = max(fits, key=lambda i: (alone[i], -i))
            if not chosen or alone[single] > _objective(chosen, cands, units):
                chosen = [single]
    return [cands[i] for i in chosen]


def _objective(chosen: list[int], cands: list[dict], units: list[dict[str, float]]) -> float:
    best: dict[str, tuple[float, float]] = {}
    for i in chosen:
        for u, w in units[i].items():
            if cands[i]["score"] > best.get(u, (0.0, 0.0))[0]:
                best[u] = (cands[i]["score"], w)
    return sum(s * w for s, w in best.values())


# ---------------------------------------------------------------- recall
def recall(query: str, family: str | None = None, k: int = 6, budget_tokens: int = 600,
           project: Path | str | None = None, brain_root: Path | str | None = None,
           include_candidates: bool = False) -> list[dict]:
    """The best set of memory items for a query, within ``k`` and the budget."""
    root = Path(brain_root or c.BRAIN_ROOT)
    proj = Path(project) if project else None
    project_files = {str(f) for f in it.project_item_files(proj)}
    pool = []
    for item in it.load_items(root, proj):
        if item.get("status") == "candidate" and not include_candidates:
            continue
        if _in_scope(item, family, item.get("_file") in project_files):
            pool.append(item)
    terms = query_terms(query)
    rel = relevance([(i["text"], " ".join(i.get("class", [])) + " " + i["id"].replace("-", " ")) for i in pool], terms)
    top = max(rel, default=0.0)
    cands = []
    for item, r in zip(pool, rel):
        if r <= 0:
            continue
        conf = item["_confidence"]
        # A matched item keeps at least 5% relevance: in a small memory BM25
        # gives a word found in most items an IDF near zero.
        score = max(0.05, r / top) * (0.5 + 0.5 * conf) * recency(item) * IMPORTANCE.get(item.get("importance", 2), 1.0)
        seed = _is_standing(item)
        if seed:
            score = max(score, STANDING_FLOOR)
        line = _line(item)
        cands.append({"id": item["id"], "text": item["text"], "type": item.get("type"), "scope": item.get("scope"),
                      "status": item.get("status"), "score": score, "confidence": conf,
                      "file": item.get("_file"), "_seed": seed, "_cost": max(1, c.est_tokens(line)),
                      "_tokens": _doc_tokens(item["text"] + " " + " ".join(item.get("class", [])))})
    cands.sort(key=lambda d: (-d["score"], d["id"]))
    chosen = pack(cands, terms, k, budget_tokens)
    chosen.sort(key=lambda d: (-d["score"], d["id"]))
    result = [{**{key: v for key, v in d.items() if not key.startswith("_")}, "score": round(d["score"], 4)}
              for d in chosen]
    if proj is not None:
        _log(proj, terms, result)
    return result


def _log(project: Path, terms: list, result: list[dict]) -> None:
    """Record which items were offered, so learning can later tell which were
    used. Only in a managed project's .brain/log, never inside the brain."""
    if not c.is_managed(project):
        return
    log = project.resolve() / ".brain" / "log" / "recall.jsonl"
    if log.is_relative_to(c.BRAIN_ROOT.resolve()):
        return
    try:
        c.append_jsonl(log, {"at": c.now_iso(), "session": c.session_id(), "words": len(terms),
                             "ids": [r["id"] for r in result]})
    except OSError:
        return


# ---------------------------------------------------------------- cli
def cmd_recall(args) -> int:
    proj = c.resolve_project(args.project)
    proj = proj if proj and c.is_managed(proj) else None
    family = args.family or (c.load_manifest(proj).get("family") if proj else None)
    res = recall(args.query, family=family, k=args.k, budget_tokens=args.budget, project=proj)
    if args.json:
        print(json.dumps(res, ensure_ascii=False))
        return 0
    if not res:
        print("nothing relevant in memory")
        return 0
    lines = [_line(r) for r in res]
    print("\n".join(lines))
    print(f"{len(res)} items, ~{sum(c.est_tokens(l) for l in lines)} tokens")
    return 0


def register(sub) -> None:
    p = sub.add_parser("recall", help="find and pack the memory items relevant to a task")
    p.add_argument("query")
    p.add_argument("--family", choices=it.FAMILIES)
    p.add_argument("--k", type=int, default=6)
    p.add_argument("--budget", type=int, default=600, help="token budget for the items")
    p.add_argument("--json", action="store_true")
    c.add_project_arg(p)
    p.set_defaults(func=cmd_recall)
