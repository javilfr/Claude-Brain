"""Memory search and packing: `brain recall "<query>"`.

Why this shape:

- Few items, or none. Retrieving one memory beat retrieving four in the
  ReasoningBank study, and planted-memory attacks succeeded 6% of the time at
  three retrieved items but 38% at ten (docs/research/round2/01 section 3.3).
  So the default is at most 3 items in 300 tokens, and when even the best
  match covers little of the query the answer is silence.
- Relevance is SQLite's FTS5 BM25, built in memory from the item files on
  each call, with the design measured in docs/research/round2/04: the
  ``porter unicode61`` tokenizer, a stop-word-filtered OR query, and three
  weighted fields (text 1.0, class tags 0.5, id words 0.5). On 60 labelled
  queries it raised recall@5 from 0.744 to 0.803; aliases, prefix queries and
  dense vectors gave no held-out gain and are not used. When this Python's
  SQLite lacks FTS5, a pure-Python port of the same tokenizer and formula
  gives the same scores (tests compare them on the labelled set).
- Each hit is scored by relevance x confidence x recency x importance x the
  learned multiplier ``mlearn.item_score`` (credit from external outcomes
  only); owner-stated items always get the top multiplier, so learning never
  ranks a lesson above what the owner said (I-08).
- The pack is chosen by greedy maximisation of a monotone submodular coverage
  objective, gain per token, under the token budget, so a near-duplicate of a
  packed item buys almost nothing. Matching owner standing instructions are
  seated first.
- Facts whose ``valid_to`` has passed were superseded; they stay on disk as
  history and are never shown.
- Every call from a managed project appends the ids shown and a hash of the
  query to ``.brain/log/recall.jsonl``: credit can only go to items that were
  actually injected.
"""
from __future__ import annotations

import heapq
import json
import math
import re
import sqlite3
import unicodedata
from pathlib import Path

from . import common as c
from . import items as it

DEFAULT_K = 3
DEFAULT_BUDGET = 300
DEFAULT_FLOOR = 0.15      # tunable: memory/ml_config.json recall.floor
FIELD_WEIGHTS = (1.0, 0.5, 0.5)   # text, class tags, id words (round2/04)
IMPORTANCE = {1: 0.85, 2: 1.0, 3: 1.2}
QUERY_UNIT_WEIGHT = 3.0   # a query word counts more than an incidental word
STANDING_FLOOR = 0.5      # minimum score of a matching owner standing instruction
REDUNDANT = 0.25          # an item adding < 25% of its standalone value is a near-duplicate
TOP_MULTIPLIER = 1.3      # mlearn.item_score range is [0.7, 1.3]; owner-stated items get the top
# The measured query stop-list from round2/04 (English question words), plus
# the Spanish function words the owner may dictate.
STOP = frozenset(
    "a an the of to in on for and or is are be it its this that with at by from as can do does how what when which "
    "why i my me should not no we you your if so any all "
    "el la los las un una y o de del en que por para con es al lo se su".split())
ML_CONFIG = "memory/ml_config.json"
ML_STATE = "stats/ml.json"


# ---------------------------------------------------------------- tokenizer
def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if not unicodedata.combining(ch)).lower()


def _vowel(ch: str, y_is_vowel: bool) -> bool:
    return ch in "aeiou" or (y_is_vowel and ch == "y")


def _gobble_vc(w: str, prev_cons: bool) -> int:
    """Length of the first vowel-then-consonant run plus one, or 0."""
    cons = prev_cons
    i = 0
    while i < len(w):
        cons = not _vowel(w[i], cons)
        if not cons:
            break
        i += 1
    i += 1
    while i < len(w):
        cons = not _vowel(w[i], cons)
        if cons:
            return i + 1
        i += 1
    return 0


def _m_gt0(w: str) -> bool:
    return bool(_gobble_vc(w, False))


def _m_gt1(w: str) -> bool:
    n = _gobble_vc(w, False)
    return bool(n and _gobble_vc(w[n:], True))


def _m_eq1(w: str) -> bool:
    n = _gobble_vc(w, False)
    return bool(n and not _gobble_vc(w[n:], True))


def _ostar(w: str) -> bool:
    if not w or w[-1] in "wxy":
        return False
    mask, cons = 0, False
    for ch in w:
        cons = not _vowel(ch, cons)
        mask = (mask << 1) + int(cons)
    return (mask & 7) == 5


def _has_vowel(w: str) -> bool:
    return any(_vowel(ch, i > 0) for i, ch in enumerate(w))


def _m_gt1_st(w: str) -> bool:
    return bool(w) and w[-1] in "st" and _m_gt1(w)


# Steps 2-4 as SQLite generates them: the rules are grouped by the
# second-to-last letter, and within a group the first suffix that matches
# decides, whether or not its condition then holds.
_STEP2 = {"a": [("ational", "ate"), ("tional", "tion")], "c": [("enci", "ence"), ("anci", "ance")],
          "e": [("izer", "ize")], "g": [("logi", "log")],
          "l": [("bli", "ble"), ("alli", "al"), ("entli", "ent"), ("eli", "e"), ("ousli", "ous")],
          "o": [("ization", "ize"), ("ation", "ate"), ("ator", "ate")],
          "s": [("alism", "al"), ("iveness", "ive"), ("fulness", "ful"), ("ousness", "ous")],
          "t": [("aliti", "al"), ("iviti", "ive"), ("biliti", "ble")]}
_STEP3 = {"a": [("ical", "ic")], "s": [("ness", "")], "t": [("icate", "ic"), ("iciti", "ic")],
          "u": [("ful", "")], "v": [("ative", "")], "z": [("alize", "al")]}
_STEP4 = {"a": ["al"], "c": ["ance", "ence"], "e": ["er"], "i": ["ic"], "l": ["able", "ible"],
          "n": ["ant", "ement", "ment", "ent"], "o": ["ion", "ou"], "s": ["ism"], "t": ["ate", "iti"],
          "u": ["ous"], "v": ["ive"], "z": ["ize"]}


def _step(w: str, table: dict, cond) -> str:
    if len(w) < 2:
        return w
    for suf, rep in table.get(w[-2], []):
        if len(w) > len(suf) and w.endswith(suf):
            stem = w[: -len(suf)]
            return stem + rep if cond(stem) else w
    return w


def _step4(w: str) -> str:
    if len(w) < 2:
        return w
    for suf in _STEP4.get(w[-2], []):
        if len(w) > len(suf) and w.endswith(suf):
            stem = w[: -len(suf)]
            ok = _m_gt1_st(stem) if suf == "ion" else _m_gt1(stem)
            return stem if ok else w
    return w


def porter(w: str) -> str:
    """The Porter stemmer exactly as SQLite's FTS5 ``porter`` tokenizer applies
    it (ext/fts5/fts5_tokenize.c), so the pure-Python path and FTS5 index the
    same terms. Tokens under 3 or over 64 characters pass through."""
    if len(w) < 3 or len(w.encode("utf-8")) > 64:
        return w
    if w.endswith("s"):  # step 1a
        if (len(w) > 4 and w.endswith("sses")) or (len(w) > 3 and w.endswith("ies")):
            w = w[:-2]
        elif not w.endswith("ss"):
            w = w[:-1]
    one_b = False  # step 1b
    if len(w) > 3 and w.endswith("eed"):
        if _m_gt0(w[:-3]):
            w = w[:-1]
    elif len(w) > 2 and w.endswith("ed"):
        if _has_vowel(w[:-2]):
            w, one_b = w[:-2], True
    elif len(w) > 3 and w.endswith("ing"):
        if _has_vowel(w[:-3]):
            w, one_b = w[:-3], True
    if one_b:
        if len(w) > 2 and w[-2:] in ("at", "bl", "iz"):
            w += "e"
        elif len(w) >= 2 and not _vowel(w[-1], False) and w[-1] not in "lsz" and w[-1] == w[-2]:
            w = w[:-1]
        elif _m_eq1(w) and _ostar(w):
            w += "e"
    if w.endswith("y") and _has_vowel(w[:-1]):  # step 1c
        w = w[:-1] + "i"
    w = _step(w, _STEP2, _m_gt0)
    w = _step(w, _STEP3, _m_gt0)
    w = _step4(w)
    if w.endswith("e") and (_m_gt1(w[:-1]) or (_m_eq1(w[:-1]) and not _ostar(w[:-1]))):  # step 5a
        w = w[:-1]
    if len(w) > 1 and w.endswith("ll") and _m_gt1(w[:-1]):  # step 5b
        w = w[:-1]
    return w


def _raw_tokens(text: str) -> list[str]:
    """unicode61 tokens: runs of letters and digits, lower-cased, accents removed."""
    return "".join(ch if ch.isalnum() else " " for ch in _fold(text or "")).split()


def tokens(text: str) -> list[str]:
    """Indexed terms of a text, as FTS5 ``porter unicode61`` produces them."""
    return [porter(t) for t in _raw_tokens(text)]


def query_words(query: str) -> list[str]:
    """Distinct query words, lower-cased, stop-words removed, in query order.
    FTS5 stems these itself; the Python path stems them with ``porter``."""
    return list(dict.fromkeys(w for w in re.findall(r"[a-z0-9]+", _fold(query or "")) if w not in STOP))


def query_terms(query: str) -> list[str]:
    """Distinct stemmed query terms: the units for coverage and packing."""
    return list(dict.fromkeys(porter(w) for w in query_words(query)))


# ---------------------------------------------------------------- relevance
def _fields(item: dict) -> tuple[str, str, str]:
    return item.get("text", ""), " ".join(item.get("class") or []), str(item.get("id", "")).replace("-", " ")


def _fts5_relevance(docs: list[tuple[str, str, str]], words: list[str]) -> list[float]:
    """BM25 per document from an in-memory FTS5 table (higher is better)."""
    con = sqlite3.connect(":memory:")
    try:
        con.execute("CREATE VIRTUAL TABLE m USING fts5(body, tags, idt, tokenize='porter unicode61')")
        con.executemany("INSERT INTO m(rowid, body, tags, idt) VALUES (?, ?, ?, ?)",
                        [(i + 1, *d) for i, d in enumerate(docs)])
        # Each term is quoted, so punctuation in a question is never FTS syntax.
        match = " OR ".join(f'"{w}"' for w in words)
        w = ", ".join(str(x) for x in FIELD_WEIGHTS)
        rows = con.execute(f"SELECT rowid, bm25(m, {w}) FROM m WHERE m MATCH ?", (match,)).fetchall()
    finally:
        con.close()
    rel = [0.0] * len(docs)
    for rowid, score in rows:
        rel[rowid - 1] = max(1e-9, -float(score))  # FTS5 bm25: lower (more negative) is better
    return rel


def _python_relevance(docs: list[tuple[str, str, str]], words: list[str]) -> list[float]:
    """FTS5's ``bm25()`` in pure Python (ext/fts5/fts5_aux.c): per phrase, the
    column-weighted term frequency f = sum_c w_c * tf_c goes into
    idf * f * (k1 + 1) / (f + k1 * (1 - b + b * D / avgD)) with k1 1.2, b 0.75,
    D the whole row's token count and avgD its mean; a phrase in more than
    half the rows gets IDF 1e-6. Like FTS5, two query words with the same stem
    count as two phrases."""
    k1, b = 1.2, 0.75
    rows = [[tokens(field) for field in d] for d in docs]
    n = len(docs)
    size = [sum(len(f) for f in row) for row in rows]
    avg = sum(size) / n or 1.0
    rel = [0.0] * n
    for t in (porter(w) for w in words):
        df = sum(1 for row in rows if any(t in f for f in row))
        if df == 0:
            continue
        idf = math.log((n - df + 0.5) / (df + 0.5))
        idf = idf if idf > 0 else 1e-6
        for i, row in enumerate(rows):
            f = sum(w * field.count(t) for w, field in zip(FIELD_WEIGHTS, row))
            if f:
                rel[i] += idf * f * (k1 + 1) / (f + k1 * (1 - b + b * size[i] / avg))
    return rel


def relevance(docs: list[tuple[str, str, str]], words: list[str]) -> list[float]:
    """BM25 of each (text, tags, id words) document for the query words."""
    if not docs or not words:
        return [0.0] * len(docs)
    try:
        return _fts5_relevance(docs, words)
    except sqlite3.Error:
        return _python_relevance(docs, words)


def coverage(doc_terms: list[set[str]], terms: list[str]) -> list[float]:
    """Share of the query's information each document contains: the IDF-weighted
    fraction of query terms present (a term absent from memory weighs most).
    This is the normalised score the silence floor is compared with, because
    a BM25 score has no fixed scale."""
    n = len(doc_terms)
    weight = {t: math.log(1 + (n - df + 0.5) / (df + 0.5))
              for t in terms for df in [sum(1 for d in doc_terms if t in d)]}
    total = sum(weight.values())
    return [sum(weight[t] for t in terms if t in d) / total if total else 0.0 for d in doc_terms]


# ---------------------------------------------------------------- scoring
def recency(item: dict) -> float:
    """1.0 if used or created within 30 days, falling linearly to 0.7 at a year."""
    d = min(c.days_since(item.get("last_used") or ""), c.days_since(item.get("created") or ""))
    if d <= 30:
        return 1.0
    return max(0.7, 1.0 - 0.3 * (d - 30) / (365 - 30))


def current(item: dict, day: str | None = None) -> bool:
    """False for an item outside its validity window: superseded (``valid_to``
    reached; the end date is exclusive) or not yet valid (``valid_from`` later)."""
    day = day or c.today()
    vt, vf = str(item.get("valid_to") or ""), str(item.get("valid_from") or "")
    return not (vt and vt[:10] <= day) and not (vf and vf[:10] > day)


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


def floor_from_config(brain_root: Path) -> float:
    cfg = c.read_json(Path(brain_root) / ML_CONFIG, {}) or {}
    v = (cfg.get("recall") or {}).get("floor", DEFAULT_FLOOR) if isinstance(cfg, dict) else DEFAULT_FLOOR
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else DEFAULT_FLOOR


def item_multiplier(brain_root: Path):
    """A function item -> learned ranking multiplier. Uses ``mlearn.item_score``
    when that module and ``stats/ml.json`` exist; otherwise every item gets 1.0.
    Owner-stated items always get the top multiplier (I-08)."""
    from . import learn  # the one place tests inject a stand-in for mlearn
    state = c.read_json(Path(brain_root) / ML_STATE)
    ml = learn.mlearn_module(optional=True) if isinstance(state, dict) else None
    fn = getattr(ml, "item_score", None)

    def mult(item: dict) -> float:
        if item.get("trust") == "owner-stated":
            return TOP_MULTIPLIER
        if fn is None:
            return 1.0
        try:
            v = float(fn(state, item))
        except (TypeError, ValueError, KeyError):
            return 1.0
        return min(TOP_MULTIPLIER, max(0.0, v))
    return mult


# ---------------------------------------------------------------- packing
def pack(cands: list[dict], terms: list[str], k: int, budget: int) -> list[dict]:
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
        toks = cd["_tokens"]
        u = {f"w:{t}": 1.0 for t in toks}
        for t in terms:
            if t in toks:
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
def select(query: str, pool: list[dict], k: int = DEFAULT_K, budget_tokens: int = DEFAULT_BUDGET,
           floor: float = DEFAULT_FLOOR, multiplier=None) -> list[dict]:
    """Rank ``pool`` (items from ``items.load_items``) for ``query`` and pack
    the best ``k`` within the budget. Items covering less than ``floor`` of
    the query are dropped, so a weak best match yields an empty list."""
    words = query_words(query)
    terms = query_terms(query)
    pool = [i for i in pool if current(i)]
    if not pool or not words:
        return []
    rel = relevance([_fields(i) for i in pool], words)
    doc_terms = [set(tokens(" ".join(_fields(i)))) for i in pool]
    cov = coverage(doc_terms, terms)
    top = max(rel, default=0.0)
    mult = multiplier or (lambda _item: 1.0)
    cands = []
    for item, r, cv, dt in zip(pool, rel, cov, doc_terms):
        if r <= 0 or cv < floor:
            continue
        conf = item["_confidence"]
        # A matched item keeps at least 5% relevance: in a small memory BM25
        # gives a word found in most items an IDF near zero.
        score = (max(0.05, r / top) * (0.5 + 0.5 * conf) * recency(item)
                 * IMPORTANCE.get(item.get("importance", 2), 1.0) * mult(item))
        seed = _is_standing(item)
        if seed:
            score = max(score, STANDING_FLOOR)
        cands.append({"id": item["id"], "text": item["text"], "type": item.get("type"), "scope": item.get("scope"),
                      "status": item.get("status"), "score": score, "confidence": conf,
                      "file": item.get("_file"), "_seed": seed, "_cost": max(1, c.est_tokens(_line(item))),
                      "_tokens": dt})
    cands.sort(key=lambda d: (-d["score"], d["id"]))
    chosen = pack(cands, terms, k, budget_tokens)
    chosen.sort(key=lambda d: (-d["score"], d["id"]))
    return [{**{key: v for key, v in d.items() if not key.startswith("_")}, "score": round(d["score"], 4)}
            for d in chosen]


def recall(query: str, family: str | None = None, k: int = DEFAULT_K, budget_tokens: int = DEFAULT_BUDGET,
           project: Path | str | None = None, brain_root: Path | str | None = None,
           include_candidates: bool = False, floor: float | None = None) -> list[dict]:
    """The best few memory items for a query, or none; logged when a project is given."""
    root = Path(brain_root or c.BRAIN_ROOT)
    proj = Path(project) if project else None
    project_files = {str(f) for f in it.project_item_files(proj)}
    pool = []
    for item in it.load_items(root, proj):
        if item.get("status") == "candidate" and not include_candidates:
            continue
        if _in_scope(item, family, item.get("_file") in project_files):
            pool.append(item)
    result = select(query, pool, k, budget_tokens, floor_from_config(root) if floor is None else floor,
                    item_multiplier(root))
    if proj is not None:
        _log(proj, query, result)
    return result


def _log(project: Path, query: str, result: list[dict]) -> None:
    """The injection log: which items were shown for which query (as a hash),
    so credit can only go to items that were actually offered. Only in a
    managed project's .brain/log, never inside the brain."""
    if not c.is_managed(project):
        return
    log = project.resolve() / ".brain" / "log" / "recall.jsonl"
    if log.is_relative_to(c.BRAIN_ROOT.resolve()):
        return
    try:
        c.append_jsonl(log, {"at": c.now_iso(), "session": c.session_id(),
                             "query_sha": c.sha256_text(" ".join(query.split()).lower())[:16],
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
    p = sub.add_parser("recall", help="find and pack the few memory items relevant to a task")
    p.add_argument("query")
    p.add_argument("--family", choices=it.FAMILIES)
    p.add_argument("--k", type=int, default=DEFAULT_K)
    p.add_argument("--budget", type=int, default=DEFAULT_BUDGET, help="token budget for the items")
    p.add_argument("--json", action="store_true")
    c.add_project_arg(p)
    p.set_defaults(func=cmd_recall)
