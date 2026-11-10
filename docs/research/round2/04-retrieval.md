# 04 Retrieval: does Claude Brain need anything beyond FTS5 BM25?

Viewpoint: retrieval engineer, prove it by running. Date 2026-11-10. Python 3.13, SQLite 3.53.1.

## Verdict (short)
1. ADOPT NOW: keep FTS5 BM25, but switch the tokenizer to `porter unicode61`, drop stopwords from the query, and index three weighted columns (text 1.0, class tags 0.5, id words 0.5). Measured: recall@5 0.744 -> 0.803 and MRR 0.822 -> 0.876 on 60 queries; 0.06 ms/query; zero installs.
2. DO NOT add dense embeddings at this corpus size (141 items). model2vec cost 8 s install, 30-130 MB disk, 3-5 s model load per process, and did not beat BM25 reliably: fusion helped MRR on one query set and hurt it on the other.
3. DO NOT add RM3 feedback or tag boosting: no gain. Alias table: gain on the set it was tuned on, zero on held-out (overfit). Keep as an optional file fed by real failed recalls.
4. Revisit dense when the corpus passes about 1,500-2,000 items, or when `brain recall` logs show vocabulary-gap misses (see "When dense wins").

## Corpus and method
Corpus: 141 items (memory/facts 18, memory/items 42, owner 22, playbooks 59), read-only from /home/user/Claude-Brain. Text = `text`; tags = `class`.
Golden set (my labels, from reading the items): `/tmp/claude-0/-home-user/ad24da2f-7dc0-51cf-aa28-dee6f5e57a4f/scratchpad/r2-4/golden.jsonl` (40 queries, tuning set) and `.../r2-4/held.jsonl` (20 queries, written AFTER the alias table was frozen, so held-out). Fields: query, relevant [ids]. Most queries have 2-4 relevant ids, so recall@5 is "fraction of relevant ids in top 5" and is capped by how many sibling items I counted as relevant. hit@5 = at least one relevant item in top 5.
Caveat, stated plainly: I wrote queries after reading items, so they are more lexical than a real future session. n=60 is small: one query flips recall by about 0.017-0.025. Differences under 0.03 are noise. Scripts: bm.py, imp.py, dense.py, miss.py, gen.py in r2-4/.

## Numbers
All 60 queries pooled (golden 40 + held-out 20), recall@5 / MRR / hit@5:

| Config | recall@5 | MRR | hit@5 |
|---|---|---|---|
| FTS5 unicode61, text only | 0.744 | 0.822 | 0.933 |
| unicode61 + fields (1/.5/.5) | 0.756 | 0.830 | 0.917 |
| porter, text only | 0.794 | 0.860 | 0.967 |
| porter + fields (1/.5/.5) **(recommended)** | 0.803 | 0.876 | 0.967 |
| porter + fields (1/.3/1) | 0.811 | 0.876 | 0.967 |
| + alias table | 0.831 | 0.896 | 0.967 |
| + RM3-style feedback (3 docs) | 0.803 | 0.879 | 0.967 |
| + tag boost x1.3 per matching class | 0.817 | 0.868 | 0.967 |

Prefix queries (`word*`) on golden 40: recall 0.708 -> 0.708, MRR 0.831 -> 0.811 (unicode61 + fields): no help, slightly worse. Porter subsumes most of what prefixes offered.

Honest split on the alias table (hand-written after reading the golden set): golden 40 recall 0.792 -> 0.833, held-out 20 0.825 -> 0.825. So the alias gain is overfit. RM3: golden40 MRR +0.006, held-out MRR -0.03, recall 0: nothing. (Consistent with literature: PRF on small collections is unreliable; Lin 2019 notes early PRF failed on small collections, https://ar5iv.labs.arxiv.org/html/1904.08861. [snippet only])

Dense, model2vec 0.10.0, items embedded whole (they are short), cosine, k=60 RRF:

| Model | golden40 recall/MRR | held-out20 recall/MRR |
|---|---|---|
| BM25 porter+fields | 0.792 / 0.852 | 0.825 / 0.925 |
| potion-base-8M alone | 0.754 / 0.817 | 0.825 / 0.822 |
| potion-base-8M + BM25 (RRF) | 0.787 / 0.904 | 0.825 / 0.883 |
| potion-retrieval-32M alone | 0.729 / 0.838 | 0.850 / 0.854 |
| potion-retrieval-32M + BM25 (RRF) | 0.779 / 0.900 | 0.850 / 0.887 |
| 32M + BM25, BM25 weight 2 | 0.792 / 0.896 | 0.850 / 0.892 |

Reading: fusion lifts MRR on golden40 (+0.05) and lowers it on held-out (-0.04 to -0.03); recall essentially flat (+/-0.03, noise). Not a reliable win.

Cost of the dense option, measured:
- `python3 -m venv` + `pip install model2vec`: 7.9 s when the registry responded (my first attempt hung over 5 minutes and had to be killed; installs through the proxy can stall, so never put it on the session-start path). Venv 133 MB (numpy, tokenizers, huggingface-hub, jinja2...).
- Model download + first load: potion-base-8M 3.3 s, potion-retrieval-32M 5.0 s (includes download). Weights on disk about 29 MB and about 129 MB (my estimate from 32.3M float32 params; blobs total 153 MB for both).
- Encode all 141 items: 9 ms. Query: 0.2 ms. So runtime is trivial; install and load are the cost.
- Per-process load of 3-5 s on every `brain recall` call is worse than BM25's 0.06 ms by five orders of magnitude, unless a cache file of vectors plus a stored model is kept; the model still needs numpy.

Failure analysis (miss.py): of 21 queries where BM25 top 5 missed some relevant id, the first-relevant item was almost always found; misses were secondary siblings (e.g. query "scheduled job needs to be safe to rerun" finds ops-run-twice, misses ops-dry-run). Dense recovered a different sibling in about half of these and no sibling in several others (e.g. "where does most of the money go in a session" -> fact-cost-shape missed by both: needs "cost/cache writes/output" synonyms). Cheap alternative for siblings: the existing greedy coverage packing plus a "same class tag" neighbour pull; untested.

## Literature and threads (what the sources say)
- Static embeddings (Hugging Face blog, https://huggingface.co/blog/static-embeddings): about 62x CPU speed vs all-MiniLM-L6-v2 (107,419 vs 1,739 sentences/s, my division of the table), about 89.5% of its NanoBEIR NDCG@10 (0.5032 vs 0.5623). English-only retrieval model; multilingual one not meant for retrieval. Self-reported by the authors.
- potion-retrieval-32M card (https://huggingface.co/minishlab/potion-retrieval-32M): MTEB retrieval 35.06 vs 42.92 MiniLM-L6 (82%); static-retrieval-mrl-en-v1 34.95; 32.3M params; English; MIT. Vendor numbers; no independent benchmark found.
- Grep vs vectors: "Is Grep All You Need? How Agent Harnesses Reshape Agentic Search" (arXiv 2605.15184, May 2026, https://arxiv.org/abs/2605.15184): on LongMemEval (116 questions) with Claude Code/Codex/Gemini CLI harnesses, secondary summaries say grep often beats vector retrieval and vector degrades as irrelevant context is injected; authors say harness and tool-calling style dominate. [I read only summaries, numbers unverified.] Claude Code's creator reportedly said agentic search "works better" than their early RAG [secondary reports, unverified original]. Augment's SWE-bench note: grep and find sufficed (https://jxnl.co/writing/2025/09/11/why-grep-beat-embeddings-in-our-swe-bench-agent-lessons-from-augment/) [not opened].
- Not tested, judged too heavy: SPLADE-style learned sparse (needs a BERT forward pass per doc and query, torch-class install), ColBERT late interaction (multi-vector index), cross-encoder rerankers (tens of MB plus onnxruntime; at 141 items the first-stage already finds the first relevant item in 96.7% of queries, so reranking has little headroom). BM25F-style field weighting is what FTS5 `bm25(t,0,w1,w2,w3)` already provides; BM25+ is a long-document fix and irrelevant for 20-60 word items.

## Recommended recall design
1. Index: FTS5 table with columns text, cls (class tags), idt (id split on hyphens), `tokenize='porter unicode61'`, rebuilt in memory from the JSONL files at call time (0 ms at this size; no stale index, no extra file in git).
2. Query: lowercase, alnum tokens, drop stopwords, quote each token, join with OR, rank `bm25(t,0,1.0,0.5,0.5)`. Quoting prevents FTS syntax errors from punctuation in questions.
3. Pack: existing greedy coverage under a token budget on the top 10.
4. Log every recall (query, returned ids, whether the item was later cited/used). Two fields suffice; this is the data to decide on dense and to grow aliases from real misses.
5. Keep golden.jsonl + held.jsonl in the repo as `tests/recall/` and run in the existing check; threshold recall@5 >= 0.78, MRR >= 0.85 on pooled 60 (current 0.803 / 0.876); add every real failed recall as a new query.
6. Spanish: the corpus is English now. FTS5 has no Spanish stemmer; if Spanish items arrive, add a stripper (below) applied identically to index text and query, because porter is English-only.

TRY BEHIND A MEASUREMENT: alias table (`.brain/aliases.json`), only entries born from a logged failed recall, kept only if held-out recall does not drop. Dense static embeddings when any trigger fires: corpus > ~1,500 items; or >= 10% of logged recalls show a relevant item cited that BM25 had not returned while sharing no query word; or Spanish/English mixed queries over one store (use potion-multilingual-128M only for similarity, not retrieval, per the blog; so test first). Then use potion-base-8M (smallest, 29 MB) with cached vectors in a .npy/JSON file, RRF k=60 with BM25 weight 2, and pip install in a lazily created venv, never at session start.

AVOID: always-on dense at 141 items (cost without reliable gain); RM3 (no gain, extra queries); tag boost (noise); SPLADE/ColBERT/cross-encoder (install weight, no headroom); chunking items (they are already one idea each).

## Code that won (port-ready)
Saved at /tmp/claude-0/-home-user/ad24da2f-7dc0-51cf-aa28-dee6f5e57a4f/scratchpad/r2-4/recall_port.py. Core:

```python
import re, sqlite3
STOP = set("a an the of to in on for and or is are be it its this that with at by from as can do does how what when which why i my me should not no we you your if so any all".split())
def words(t): return [w for w in re.findall(r"[a-z0-9]+", t.lower()) if w not in STOP]
def build(items, db=":memory:"):
    c = sqlite3.connect(db)
    c.execute("create virtual table if not exists t using fts5(id unindexed,text,cls,idt,tokenize='porter unicode61')")
    c.executemany("insert into t values(?,?,?,?)",
        [(i["id"], i["text"], " ".join(i.get("class", [])), i["id"].replace("-", " ")) for i in items])
    return c
def recall(c, query, k=5, aliases=None):
    ws = words(query)
    for w in list(ws): ws += (aliases or {}).get(w, "").split()
    ws = list(dict.fromkeys(ws))
    if not ws: return []
    m = " OR ".join('"%s"' % w for w in ws)
    return [r[0] for r in c.execute(
        "select id from t where t match ? order by bm25(t,0,1.0,0.5,0.5) limit ?", (m, k))]
```
Optional Spanish/English stripper for a non-porter path (untested on Spanish data, no Spanish items exist):
```python
SUF = ('aciones','acion','mente','ando','iendo','ments','ment','ings','ing','ies','ed','es','s')
def stem2(w):
    for s in SUF:
        if w.endswith(s) and len(w)-len(s) >= 4: return w[:-len(s)]
    return w
```

## Evidence files
Scripts and logs: /tmp/claude-0/-home-user/ad24da2f-7dc0-51cf-aa28-dee6f5e57a4f/scratchpad/r2-4/ (bm.py baseline, imp.py improvements, dense.py, miss.py, gen.py, pip.log, venv/, hf/).
Golden sets: .../r2-4/golden.jsonl (40), .../r2-4/held.jsonl (20).
