"""Memory search and packing: `brain recall "<query>"`.

Why this shape:

- Few items, or none. Retrieving one memory beat retrieving four in the
  ReasoningBank study, and planted-memory attacks succeeded 6% of the time at
  three retrieved items but 38% at ten (docs/research/round2/01 section 3.3).
  So the default is at most 3 items in 300 tokens. When even the best match
  covers less than ``recall.floor`` of the query the answer is silence, and
  a further item is shown only when it covers ``recall.companion`` of what
  the best match covers: a strong hit does not bring weak ones along.
- The owner writes and dictates in Spanish and every item is English, so the
  query is first reduced to units of meaning: dictation fillers and function
  words are dropped and a Spanish term becomes the English word the items use
  (engine/glossary.py). English requests pass through unchanged.
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
  only). An owner-stated item gets the best multiplier any other hit earned,
  never less than 1, so learning never ranks a lesson above what the owner
  said (I-08) and a learning state that holds nothing changes nothing.
- The pack is chosen by greedy maximisation of a monotone submodular coverage
  objective, gain per token, under the token budget, so a near-duplicate of a
  packed item buys almost nothing. An owner standing instruction is seated
  first only when it covers ``recall.standing_coverage`` of the query; one
  that shares a stray word competes like any item.
- What is not trusted says so before its text: a lesson from the project's
  own files is "(project lesson)", a fact that was only read is "(read at
  <host>, not a rule)", and a candidate is "(unconfirmed)". A candidate is
  never packed with the trusted items: the best one that matches the query
  (two units and ``recall.unconfirmed_coverage`` of it, and no shown item
  covers more) gets one extra slot when the budget has room, so a noted
  lesson can be seen, followed and earn evidence.
- Facts whose ``valid_to`` has passed were superseded; they stay on disk as
  history and are never shown.
- Every call from a managed project appends the ids shown and a hash of the
  query to ``.brain/log/recall.jsonl``: credit can only go to items that were
  actually injected (``shown_ids`` reads it back).
"""
from __future__ import annotations

import heapq
import json
import math
import re
import sqlite3
import unicodedata
from pathlib import Path
from urllib.parse import urlsplit

from . import common as c
from . import glossary
from . import items as it

DEFAULT_K = 3
DEFAULT_BUDGET = 300
# Tunables, group "recall" of memory/ml_config.json. These fallbacks are the
# shipped values (a test keeps the two equal), so a brain without the file
# runs what production runs.
DEFAULT_FLOOR = 0.20      # the best match must cover this share of the query, or the answer is silence
COMPANION = 0.5           # a further item must cover this fraction of what the best match covers
MIN_UNITS = 1             # 2: silence unless some item shares two units with a query of two or more
STANDING_COVERAGE = 0.4   # an owner standing instruction is seated first only from this coverage up
UNCONFIRMED_COVERAGE = 0.5  # a candidate needs this coverage for the one labelled slot
UNCONFIRMED_UNITS = 2     # and must share this many units of the query
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


def query_units(query: str) -> list[tuple[str, ...]]:
    """The topic of a query as units of meaning, in query order: one tuple of
    words per word that is kept. Stop-words, dictation fillers and Spanish
    function words are dropped; a Spanish term becomes the English word memory
    uses, or two alternatives that count as one unit (engine/glossary.py)."""
    return glossary.units(re.findall(r"[a-z0-9]+", _fold(query or "")), STOP)


def query_words(query: str) -> list[str]:
    """Distinct words to search for, in query order. FTS5 stems these itself;
    the Python path stems them with ``porter``."""
    return list(dict.fromkeys(w for unit in query_units(query) for w in unit))


def query_terms(query: str) -> list[str]:
    """Distinct stemmed query terms."""
    return list(dict.fromkeys(porter(w) for w in query_words(query)))


def _stem_units(query: str) -> list[tuple[str, ...]]:
    """The query's units as stems: what coverage and packing count."""
    return list(dict.fromkeys(tuple(dict.fromkeys(porter(w) for w in unit)) for unit in query_units(query)))


def _alts(unit) -> tuple[str, ...]:
    return unit if isinstance(unit, tuple) else (unit,)


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


def coverage(doc_terms: list[set[str]], units: list) -> list[float]:
    """Share of the query's information each document contains: the IDF-weighted
    fraction of query units present (a unit absent from memory weighs most).
    A unit is a stem, or a tuple of alternative stems of which one is enough.
    This is the normalised score the silence floor is compared with, because
    a BM25 score has no fixed scale."""
    n = len(doc_terms)
    units = [_alts(u) for u in units]
    has = [[any(t in d for t in u) for d in doc_terms] for u in units]
    weight = [math.log(1 + (n - sum(h) + 0.5) / (sum(h) + 0.5)) for h in has]
    total = sum(weight)
    return [sum(w for w, h in zip(weight, has) if h[i]) / total if total else 0.0 for i in range(n)]


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


def _in_scope(item: dict, family: str | None) -> bool:
    scope = item.get("scope", "")
    if item.get("_project"):  # loaded from the project's own files, so it is this project's
        return True
    if scope == "global":
        return True
    if scope.startswith("family:"):
        return family is not None and scope == f"family:{family}"
    return False  # a 'project' item stored in the brain belongs to no project here


def _read_at(item: dict) -> str:
    """The host an external fact was read at, for its mark. Only a plain host
    name is ever printed: the source is text somebody else wrote."""
    src = str(item.get("source") or "").strip()
    try:
        host = urlsplit(src if "//" in src else "//" + src).hostname or ""
    except ValueError:
        host = ""
    return host if re.fullmatch(r"[a-z0-9-]+(\.[a-z0-9-]+)+", host) and len(host) <= 60 else "an unnamed source"


def shown_text(item: dict) -> str:
    """An item's text as recall shows it: what is not trusted says so first."""
    marks = []
    if item.get("_project"):
        marks.append("(project lesson)")
    if item.get("status") == "candidate":
        marks.append("(unconfirmed)")
    if item.get("trust") == "external":
        marks.append(f"(read at {_read_at(item)}, not a rule)")
    return " ".join(marks + [item["text"]])


def line(hit: dict) -> str:
    """One recalled item as it is printed. ``hit`` is a result of ``recall``
    (its text already carries the marks) or a memory item."""
    text = hit["text"] if "label" in hit else shown_text(hit)
    return f"[{hit['id']}] {text}" + (" (probation)" if hit.get("status") == "probation" else "")


_line = line


def recall_config(brain_root: Path | str) -> dict:
    """The recall tunables: group ``recall`` of memory/ml_config.json over the inline fallbacks."""
    out = {"floor": DEFAULT_FLOOR, "companion": COMPANION, "min_units": MIN_UNITS,
           "standing_coverage": STANDING_COVERAGE, "unconfirmed_coverage": UNCONFIRMED_COVERAGE}
    cfg = c.read_json(Path(brain_root) / ML_CONFIG, {})
    group = cfg.get("recall") if isinstance(cfg, dict) else None
    for key in out:
        v = group.get(key) if isinstance(group, dict) else None
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            out[key] = float(v)
    return out


def floor_from_config(brain_root: Path) -> float:
    return recall_config(brain_root)["floor"]


def _config(root: Path, config: dict | None, floor: float | None) -> dict:
    cfg = {**recall_config(root), **(config or {})}
    if floor is not None:
        cfg["floor"] = floor
    if cfg["floor"] <= 0 and "companion" not in (config or {}):
        cfg["companion"] = 0.0
    return cfg


def item_multiplier(brain_root: Path):
    """A function item -> learned ranking multiplier. Uses ``mlearn.item_score``
    when that module and ``stats/ml.json`` exist; otherwise every item gets 1.0.
    For an owner-stated item it returns the cap: ``select`` gives such an item
    the best multiplier another hit earned, never less than 1 (I-08)."""
    from . import learn  # the one place tests inject a stand-in for mlearn
    state = c.read_json(Path(brain_root) / ML_STATE)
    ml = learn.mlearn_module(optional=True) if isinstance(state, dict) else None
    fn = getattr(ml, "item_score", None)

    def mult(item: dict) -> float:
        if fn is None:
            return 1.0
        if item.get("trust") == "owner-stated":
            return TOP_MULTIPLIER
        try:
            v = float(fn(state, item))
        except (TypeError, ValueError, KeyError):
            return 1.0
        return min(TOP_MULTIPLIER, max(0.0, v))
    return mult


# ---------------------------------------------------------------- packing
def pack(cands: list[dict], terms: list, k: int, budget: int) -> list[dict]:
    """Lazy greedy (CELF) on F(S) = sum over units u of w_u * max_{i in S} s_i [u in i].

    Units are the query units (weight 3; ``terms`` holds stems or tuples of
    alternative stems) and the content words of the candidates (weight 1);
    s_i is the item's score. F is monotone submodular,
    so gain-per-token greedy with the best single item as a fallback carries
    the classical constant-factor guarantee under a knapsack budget. Seeded
    items (matching standing instructions) are placed first."""
    if not cands or k <= 0:
        return []
    units: list[dict[str, float]] = []
    for cd in cands:
        toks = cd["_tokens"]
        u = {f"w:{t}": 1.0 for t in toks}
        for alts in map(_alts, terms):
            if any(t in toks for t in alts):
                u[f"q:{alts[0]}"] = QUERY_UNIT_WEIGHT
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
def _rank(query: str, pool: list[dict], floor: float, multiplier, standing_coverage: float,
          companion: float = 0.0, min_units: float = 1) -> tuple[list[dict], list]:
    """The items of ``pool`` that match ``query``, scored, best first, and the
    query's stem units. Nothing when the best match covers less than
    ``floor`` of the query, or when no item shares ``min_units`` units with
    it (as many as the query has, if fewer); no item that covers less than
    ``companion`` times what the best match covers."""
    words = query_words(query)
    units = _stem_units(query)
    pool = [i for i in pool if current(i)]
    if not pool or not words:
        return [], units
    rel = relevance([_fields(i) for i in pool], words)
    doc_terms = [_terms(i) for i in pool]
    cov = coverage(doc_terms, units)
    top = max(rel, default=0.0)
    mult = multiplier or (lambda _item: 1.0)
    hits = [(item, r, cv, dt, sum(1 for u in units if any(t in dt for t in u)))
            for item, r, cv, dt in zip(pool, rel, cov, doc_terms) if r > 0]
    best = max((h[2] for h in hits), default=0.0)
    if best < floor or max((h[4] for h in hits), default=0) < min(min_units, len(units)):
        return [], units
    hits = [h for h in hits if h[2] >= companion * best]
    learned = [mult(item) for item, *_ in hits]
    # I-08 without a live-state dependency: the owner's multiplier is the best
    # one learning gave any other hit, so nothing learned can overtake it and
    # an empty learning state leaves every score as it was.
    owner = max([1.0] + [m for (item, *_), m in zip(hits, learned) if item.get("trust") != "owner-stated"])
    cands = []
    for (item, r, cv, dt, shared), m in zip(hits, learned):
        conf = item["_confidence"]
        # A matched item keeps at least 5% relevance: in a small memory BM25
        # gives a word found in most items an IDF near zero.
        score = (max(0.05, r / top) * (0.5 + 0.5 * conf) * recency(item)
                 * IMPORTANCE.get(item.get("importance", 2), 1.0)
                 * (owner if item.get("trust") == "owner-stated" else m))
        seed = _is_standing(item) and cv >= standing_coverage
        if seed:
            score = max(score, STANDING_FLOOR)
        text = shown_text(item)
        cands.append({"id": item["id"], "text": text, "type": item.get("type"), "scope": item.get("scope"),
                      "status": item.get("status"), "score": score, "confidence": conf, "coverage": round(cv, 3),
                      "label": "unconfirmed" if item.get("status") == "candidate" else "",
                      "file": item.get("_file"), "_seed": seed, "_tokens": dt, "_hits": shared,
                      "_cost": max(1, c.est_tokens(line({"id": item["id"], "text": text, "label": "",
                                                         "status": item.get("status")})))})
    cands.sort(key=lambda d: (-d["score"], d["id"]))
    return cands, units


def _terms(item: dict) -> set[str]:
    """The item's indexed terms, kept on the loaded item so a second query
    over the same list (the unconfirmed slot, a measurement) does not stem it again."""
    if "_terms" not in item:
        item["_terms"] = set(tokens(" ".join(_fields(item))))
    return item["_terms"]


def _public(d: dict) -> dict:
    return {**{key: v for key, v in d.items() if not key.startswith("_")}, "score": round(d["score"], 4)}


def select(query: str, pool: list[dict], k: int = DEFAULT_K, budget_tokens: int = DEFAULT_BUDGET,
           floor: float = DEFAULT_FLOOR, multiplier=None, standing_coverage: float = STANDING_COVERAGE,
           companion: float | None = None, min_units: float = MIN_UNITS) -> list[dict]:
    """Rank ``pool`` (items from ``items.load_items``) for ``query`` and pack
    the best ``k`` within the budget. A best match that covers less than
    ``floor`` of the query yields an empty list, and an item that covers less
    than ``companion`` of what the best match covers is left out. A floor of
    0 means no relevance cut at all: the companion cut is then off unless given."""
    if companion is None:
        companion = COMPANION if floor > 0 else 0.0
    cands, units = _rank(query, pool, floor, multiplier, standing_coverage, companion, min_units)
    chosen = pack(cands, units, k, budget_tokens)
    chosen.sort(key=lambda d: (-d["score"], d["id"]))
    return [_public(d) for d in chosen]


def _unconfirmed(query: str, pool: list[dict], waiting: list[dict], shown: list[dict], budget: int,
                 cfg: dict, multiplier) -> dict | None:
    """The one extra slot: the best candidate that matches the query and fits
    what is left of the budget. It never takes a trusted item's place, and it
    is not shown when a trusted item on the list covers more of the query."""
    room = budget - sum(c.est_tokens(line(x)) for x in shown)
    ranked, _units = _rank(query, pool + waiting, 0.0, multiplier, cfg["standing_coverage"])
    ids = {x["id"] for x in shown}
    least = max([cfg["unconfirmed_coverage"], cfg["floor"]] + [d["coverage"] for d in ranked if d["id"] in ids])
    for d in ranked:
        if d["status"] == "candidate" and d["_hits"] >= UNCONFIRMED_UNITS and d["coverage"] >= least and d["_cost"] <= room:
            return _public(d)
    return None


def recall(query: str, family: str | None = None, k: int = DEFAULT_K, budget_tokens: int = DEFAULT_BUDGET,
           project: Path | str | None = None, brain_root: Path | str | None = None,
           include_candidates: bool = False, floor: float | None = None, unconfirmed: bool = True,
           config: dict | None = None) -> list[dict]:
    """The best few memory items for a query, or none; logged when a project
    is given. At most ``k`` trusted items, then at most one item labelled
    ``unconfirmed``. ``config`` overrides the tunables of ``recall_config``;
    ``floor`` overrides the floor alone, and a floor of 0 turns the companion
    cut off too (the unfiltered ranking, for measurement and tests)."""
    root = Path(brain_root or c.BRAIN_ROOT)
    proj = Path(project) if project else None
    result = _answer(it.load_items(root, proj), query, family, k, budget_tokens, _config(root, config, floor),
                     item_multiplier(root), include_candidates, unconfirmed)
    if proj is not None:
        _log(proj, query, result)
    return result


def _answer(items: list[dict], query: str, family: str | None, k: int, budget_tokens: int, cfg: dict, mult,
            include_candidates: bool = False, unconfirmed: bool = True) -> list[dict]:
    """What ``recall`` returns for loaded ``items``: the trusted pack, then the unconfirmed slot."""
    pool, waiting = [], []
    for item in items:
        if item.get("awaiting_owner"):
            continue  # an owner claim not yet confirmed in his own words is never shown, not even as unconfirmed
        if _in_scope(item, family):
            (waiting if item.get("status") == "candidate" and not include_candidates else pool).append(item)
    result = select(query, pool, k, budget_tokens, cfg["floor"], mult, cfg["standing_coverage"], cfg["companion"],
                    cfg["min_units"])
    if unconfirmed and waiting:
        slot = _unconfirmed(query, pool, waiting, result, budget_tokens, cfg, mult)
        if slot:
            result.append(slot)
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
    row = {"at": c.now_iso(), "session": c.session_id(),
           "query_sha": c.sha256_text(" ".join(query.split()).lower())[:16], "ids": [r["id"] for r in result]}
    trial = [r["id"] for r in result if r.get("label") == "unconfirmed"]
    if trial:
        row["unconfirmed"] = trial
    try:
        c.append_jsonl(log, row)
    except OSError:
        return


def shown_ids(project: Path | str, session: str | None = None) -> set[str]:
    """The ids recall showed in this project during a session (default: this
    one), from the injection log: the only items that session can credit."""
    sid = session or c.session_id()
    rows = c.read_jsonl(Path(project) / ".brain" / "log" / "recall.jsonl")
    return {i for row in rows if row.get("session") == sid for i in row.get("ids") or [] if isinstance(i, str)}


# ---------------------------------------------------------------- measurement
def evaluate(queries: list[dict], brain_root: Path | str | None = None, k: int = DEFAULT_K,
             budget_tokens: int = DEFAULT_BUDGET, floor: float | None = None, whole_pool: bool = False,
             config: dict | None = None) -> dict:
    """Recall quality on labelled queries ``{query, relevant, [family]}`` over
    the items under ``brain_root``. By default each query runs the production
    path (``recall`` with the family its relevant items belong to, and the
    tunables of ``config`` or of that root). ``whole_pool`` ranks every scope
    at once with no learned multiplier: the pinned ranking regression.
    Returns n, recall and mrr (means over the queries that have an answer),
    precision (relevant share of everything shown), items and tokens per
    query, and silent (queries that returned nothing)."""
    root = Path(brain_root or c.BRAIN_ROOT)
    cfg = _config(root, config, floor)
    pool = it.load_items(root)
    mult = item_multiplier(root)
    scope = {i["id"]: i.get("scope", "") for i in pool}
    rec = mrr = 0.0
    answerable = shown = hit = spent = silent = 0
    for q in queries:
        rel = set(q.get("relevant") or [])
        if whole_pool:
            got = select(q["query"], pool, k, budget_tokens, cfg["floor"], None, cfg["standing_coverage"],
                         cfg["companion"], cfg["min_units"])
        else:
            fams = [scope[x].split(":", 1)[1] for x in q.get("relevant") or [] if scope.get(x, "").startswith("family:")]
            family = q.get("family") or (max(fams, key=lambda f: (fams.count(f), -fams.index(f))) if fams else None)
            got = _answer(pool, q["query"], family, k, budget_tokens, cfg, mult)
        ids = [x["id"] for x in got]
        shown += len(ids)
        silent += not ids
        spent += sum(c.est_tokens(line(x)) for x in got)
        hit += len(rel & set(ids))
        if rel:
            answerable += 1
            rec += len(rel & set(ids)) / len(rel)
            mrr += next((1 / (i + 1) for i, x in enumerate(ids) if x in rel), 0.0)
    n = len(queries)
    mean = lambda total, count: round(total / count, 6) if count else 0.0
    return {"n": n, "recall": mean(rec, answerable), "mrr": mean(mrr, answerable), "precision": mean(hit, shown),
            "items": mean(shown, n), "tokens": mean(spent, n), "silent": silent}


# ---------------------------------------------------------------- cli
def cmd_recall(args) -> int:
    proj = c.resolve_project(args.project)
    proj = proj if proj and c.is_managed(proj) else None
    family = args.family or (c.load_manifest(proj).get("family") if proj else None)
    res = recall(args.query, family=family, k=args.k, budget_tokens=args.budget, project=proj)
    if args.json:
        print(json.dumps(res, ensure_ascii=False))
        return 0
    lines = [line(r) for r in res]
    if lines:
        print("\n".join(lines))
        print(f"{len(res)} items, ~{sum(c.est_tokens(l) for l in lines)} tokens")
    else:
        print("nothing relevant in memory")
    refused = it.project_refusals(proj) if proj else []
    if refused:
        print(f"ignored {len(refused)} project item(s) that claim owner authority or a type a project cannot hold; "
              "run: brain items check")
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
