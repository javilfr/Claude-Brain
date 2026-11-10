"""Sizing and model routing: `brain route`.

Three pieces, each the cheapest method that is exact enough
(docs/research/04-algorithms.md sections 1.2, 2.1, 2.2):

- ``classify``: deterministic rules that size a request (0 answer, 1 small
  task, 2 project, 3 programme) and name its family and task class. Over-process
  is the main waste, so the rules lean low: a question or a small edit is
  never sized 2 or 3, and a doubt between two sizes resolves to the smaller.
- ``suggest``: the model and effort for a role, delegated to
  ``engine/mlearn.suggest_arm`` over ``stats/ml.json``: the role default from
  memory/models.json until enough checked outcomes exist, then hierarchical
  discounted Thompson sampling restricted to safe arms (I-10).
- ``assign``: one option per task maximising quality within a budget, solved
  exactly by dynamic programming (a multiple-choice knapsack). ``cheap_first``
  is the cascade rule: try the cheaper option first only when it pays.
"""
from __future__ import annotations

import json
import random
import re
import unicodedata

from . import common as c
from . import mlearn

TIER_NAMES = {0: "0 answer", 1: "1 small task", 2: "2 project", 3: "3 programme"}


# ---------------------------------------------------------------- text
def _fold(text: str) -> str:
    """Lower case without accents, so dictated 'rapido' equals 'rápido'."""
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", _fold(text))


def _close(a: str, b: str) -> bool:
    """Equal, or one edit apart (insert, delete, substitute or swap two
    neighbours) for words of five letters or more: dictation and typing slips."""
    if a == b:
        return True
    if min(len(a), len(b)) < 5 or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        diff = [i for i in range(len(a)) if a[i] != b[i]]
        return len(diff) == 1 or (len(diff) == 2 and diff[1] == diff[0] + 1
                                  and a[diff[0]] == b[diff[1]] and a[diff[1]] == b[diff[0]])
    short, long_ = (a, b) if len(a) < len(b) else (b, a)
    i = 0
    while i < len(short) and short[i] == long_[i]:
        i += 1
    return short[i:] == long_[i + 1:]


def _phrase_at(tokens: list[str], pos: int, phrase: tuple[str, ...]) -> bool:
    return pos + len(phrase) <= len(tokens) and all(_close(tokens[pos + k], w) for k, w in enumerate(phrase))


def _vocab(spec: str) -> list[tuple[str, ...]]:
    return [tuple(p.split()) for p in spec.split(",") if p.strip()]


def _hits(tokens: list[str], vocab: list[tuple[str, ...]]) -> list[tuple[str, ...]]:
    found = []
    for phrase in vocab:
        if any(_phrase_at(tokens, i, phrase) for i in range(len(tokens))):
            found.append(phrase)
    return found


# ---------------------------------------------------------------- vocabularies
FILLERS = set("ok okay vale please pls hey hi hola so bueno now ahora claude right alright then porfa favor por "
              "can could you puedes podrias lets let s just".split())

TRIGGERS = [  # (kind, phrases, how many words may follow the phrase; None = any)
    ("quick", _vocab("quick, rapido, rapida"), None),
    ("deep", _vocab("go deep, a fondo, deep dive"), None),
    ("new", _vocab("new project, nuevo proyecto"), None),
    ("learned", _vocab("what did you learn, what have you learned, what have you learnt, que has aprendido, que aprendiste"), 4),
    ("stop", _vocab("stop after this, para despues de esto, stop after"), 6),
    ("handover", _vocab("hand over, handover, new chat, nuevo chat, chat nuevo, pasa a un chat nuevo, prepara el relevo"), 6),
    ("revert", _vocab("go back, revert, roll back, rollback, vuelve atras, deshaz, revierte, vuelve a la version"), 8),
    ("status", _vocab("status, estado, where are we, como vamos, how are we doing, whats the status, what s the status, what is the status, cual es el estado"), 4),
    ("resume", _vocab("start running, keep going, carry on, continue, continua, continuar, sigue, seguimos, empieza"), 6),
    ("resume", _vocab("resume"), 2),
    ("setup", _vocab("set up, setup"), None),
]
SETUP_OK = set("this the project repo repository it here now el este proyecto repositorio todo everything".split())

WH_WORDS = set("what whats why how which who when where que por como cual cuales cuanto cuanta cuantos donde "
               "cuando quien explain explica explicame".split())
POLITE = set("can could would will puedes podrias".split())
QWORDS = set("what whats why how which who when where can could does do did is are should would will explain "
             "tell difference que por como cual cuales cuanto cuanta cuantos donde cuando quien puedo puedes es hay "
             "deberia explica explicame sabes vale merece".split())
CREATE = _vocab(
    "build, create, make, design, redesign, develop, write, draft, translate, research, investigate, implement, "
    "generate, produce, prepare, compose, program, scaffold, construct, port, migrate, convert, scrape, "
    "automate, deploy, release, ship, publish, launch, analyse, analyze, audit, summarise, summarize, outline, "
    "compile, train, plan, organise, organize, map out, want, need, would like, set up, "
    "construye, construir, crea, crear, creame, haz, hazme, hacer, disena, disenar, desarrolla, escribe, escribir, "
    "redacta, traduce, traducir, investiga, implementa, genera, prepara, monta, programa, automatiza, despliega, "
    "publica, lanza, analiza, audita, resumir, migra, convierte, planifica, planea, organiza, quiero, necesito, "
    "me gustaria")
EDIT = _vocab(
    "add, fix, change, update, rename, rewrite, remove, delete, move, replace, tweak, adjust, bump, edit, correct, "
    "swap, shorten, increase, decrease, polish, reword, tidy, clean, debug, align, center, centre, hide, "
    "install, configure, push, instala, instalar, configura, "
    "anade, agrega, anadir, arregla, corrige, cambia, actualiza, renombra, reescribe, quita, elimina, borra, mueve, "
    "reemplaza, sustituye, ajusta, sube, pon, ponle, edita, limpia, acorta")
RESEARCH = _vocab("research, investigate, investiga, compare, compara, find out, averigua, sources, fuentes")
SMALL = _vocab(
    "typo, typos, field, column, button, colour, color, label, title, heading, paragraph, sentence, link, icon, "
    "font, margin, padding, chart, graph, caption, line, word, comment, string, variable, docstring, version, "
    "tooltip, placeholder, favicon, spacing, logo, image, photo, footer, emoji, date, text, copy, slide, cell, row, "
    "dropdown, toggle, checkbox, quote, citation, badge, border, shadow, message, one, single, small, tiny, little, "
    "minor, quick, errata, campo, columna, boton, etiqueta, titulo, parrafo, frase, enlace, icono, fuente, margen, "
    "grafico, linea, palabra, comentario, imagen, foto, fecha, texto, mensaje, celda, fila, diapositiva, cita, "
    "pequeno, pequena, solo")
BIG = _vocab(
    "app, apps, application, website, site, webapp, platform, system, report, pipeline, dashboard, api, backend, "
    "game, course, book, knowledge base, database, brochure, deck, presentation, essay, thesis, strategy, tool, "
    "bot, agent team, library, extension, plugin, curriculum, study, edition, newsletter, portfolio, store, shop, "
    "guide, handbook, assignment, rubric, tarea, rubrica, aplicacion, web, sitio, plataforma, sistema, informe, juego, curso, libro, guia, "
    "base de conocimiento, folleto, presentacion, ensayo, herramienta, estrategia, estudio, edicion, tienda, dossier, "
    "manual")
WHOLE = _vocab("whole, entire, all, every, complete, full, everything, todo, toda, todos, todas, entero, entera, "
               "completo, completa, from scratch, desde cero")
PROGRAMME = _vocab(
    "phases, phase, waves, wave, roadmap, milestones, multi week, multiweek, several weeks, several months, "
    "multi month, sprints, programme, "
    "end to end, entire platform, whole platform, fases, fase, oleadas, hoja de ruta, semanas, meses, hitos, "
    "plataforma completa, de principio a fin")
COMPLAINT = _vocab("broken, bug, bugs, crash, crashes, error, errors, wrong, missing, ugly, overlaps, overlap, cut off, "
                   "doesnt work, dont work, not working, dont load, doesnt load, wont load, not loading, too, roto, rota, falla, fallo, feo, fea, mal, falta, demasiado, "
                   "no funciona, no carga")

FAMILY_WORDS = {
    "language": _vocab("translate, translation, translated, traduce, traducir, traduccion, spanish, english, japanese, "
                       "espanol, ingles, japones, glossary, glosario, localise, localize, i18n, bilingual, bilingue"),
    "data": _vocab("data, datos, pipeline, csv, dataset, spreadsheet, excel, sql, etl, scrape, scraper, chart, graph, "
                   "plot, grafico, statistics, stats, analysis, analisis, analyse, analyze, analiza, quota, ingest, "
                   "table, tabla, metrics, sightings, observations, dashboard"),
    "operations": _vocab("cron, scheduled, automation, automate, automatiza, routine, rutina, backup, copia de seguridad, "
                         "install, instala, instalar, my computer, mi ordenador, ordenador, mac, laptop, pc, windows, "
                         "daily, weekly, every morning, every day, cada dia, cada semana, reminder, recordatorio"),
    "knowledge": _vocab("research, investiga, investigacion, report, informe, essay, ensayo, memo, strategy, estrategia, "
                        "legal, law, ley, contract, contrato, brochure, folleto, deck, slides, presentation, "
                        "presentacion, document, documento, pdf, docx, course, curso, lesson, leccion, book, libro, "
                        "summary, resumen, assignment, rubric, rubrica, audit, article, articulo, chapter, capitulo, "
                        "letter, carta, cv, knowledge, conocimiento, notes, apuntes, paragraph, parrafo, sources, "
                        "fuentes, thesis, tesis, compare, compara, essay"),
    "software": _vocab("app, apps, application, aplicacion, website, site, web, webapp, pwa, iphone, ios, android, api, "
                       "backend, frontend, code, bug, crash, deploy, vercel, react, button, boton, css, ui, screen, "
                       "pantalla, page, component, login, game, juego, minecraft, mod, repo, repository, branch, main, "
                       "typescript, javascript, html, database, server, extension, plugin, bot, agents, feature, field, fields, campo, "
                       "tests, dark mode, layout, font, python, cli, command line, script, scripts, program, programa, "
                       "codigo, library, package, function, unit tests, flask, django, fastapi, node, rust, golang, "
                       "java, kotlin, swift, service, microservice, endpoint, compiler, converter"),
}
FAMILY_ORDER = ("language", "data", "operations", "knowledge", "software")
CLASS_WORDS = [  # (family, class, words) checked in order; first hit wins
    ("data", "data.analysis", _vocab("chart, graph, plot, grafico, analyse, analyze, analysis, analisis, analiza, stats, statistics")),
    ("operations", "operations.local", _vocab("my computer, mi ordenador, ordenador, mac, laptop, pc, windows, install, instala, instalar, terminal")),
    ("knowledge", "knowledge.research", _vocab("research, investiga, investigacion, compare, compara, sources, fuentes, find out, legal, law, ley")),
    ("knowledge", "knowledge.audit", _vocab("audit, rubric, rubrica, assignment, grade, review against, audita")),
    ("knowledge", "knowledge.document", _vocab("deck, slides, brochure, folleto, pdf, docx, presentation, presentacion, letter, carta, cv")),
    ("software", "software.bugfix", COMPLAINT + _vocab("fix, arregla, debug, corrige")),
    ("software", "software.housekeeping", _vocab("clean up, cleanup, branches, gitignore, housekeeping, tidy, limpia")),
    ("software", "software.agents", _vocab("agent team, agents, subagents, agentes")),
    ("software", "software.ui", _vocab("design, redesign, colour, color, font, layout, css, button, spacing, polish, "
                                      "animation, dark mode, screen, icon, ui, looks, diseno, disena, boton, pantalla")),
]
CLASS_WORDS.append(("software", "software.release",
                    _vocab("deploy, release, push to main, ship, publish, vercel, despliega, publica, sube a main")))
RELEASE_VERBS = _vocab("deploy, release, ship, publish, launch, despliega, publica, lanza")
OBJECT_FAMILY = [(p, fam) for fam, spec in (
    ("software", "app, apps, application, aplicacion, website, site, webapp, web, platform, plataforma, sitio, api, "
                 "backend, game, juego, extension, plugin, bot, store, shop, tienda, tool, herramienta, cli, "
                 "command line, script, program, programa, library, package, service, converter"),
    ("knowledge", "report, informe, essay, ensayo, book, libro, brochure, folleto, deck, presentation, presentacion, "
                  "course, curso, guide, guia, handbook, manual, knowledge base, base de conocimiento, thesis, "
                  "strategy, estrategia, study, estudio, newsletter, dossier, assignment, rubric, tarea, letter, carta"),
    ("data", "pipeline, dashboard, database, dataset, spreadsheet"),
) for p in _vocab(spec)]
DEFAULT_CLASS = {"software": "software.feature", "data": "data.pipeline", "knowledge": "knowledge.longform",
                 "language": "language.translate", "operations": "operations.routine"}


# ---------------------------------------------------------------- classify
def _first_object_family(tokens: list[str]) -> str | None:
    """Family of the first deliverable named after the first action verb: in
    'make a learning app from the book' the app, not the book, is the work."""
    verbs = CREATE + EDIT
    start = next((i for i in range(len(tokens)) if any(_phrase_at(tokens, i, v) for v in verbs)), 0)
    for i in range(start, len(tokens)):
        for phrase, fam in OBJECT_FAMILY:
            if _phrase_at(tokens, i, phrase):
                return fam
    return None


def _family_score(tokens: list[str], vocab: list[tuple[str, ...]]) -> float:
    """One point per word matched exactly, half a point per word matched only
    within one edit: 'tests' must not count as fully as 'tesis' (thesis)."""
    score = 0.0
    for phrase in vocab:
        exact = any(tuple(tokens[i:i + len(phrase)]) == phrase for i in range(len(tokens)))
        if exact:
            score += 1.0
        elif any(_phrase_at(tokens, i, phrase) for i in range(len(tokens))):
            score += 0.5
    return score


def _family(tokens: list[str], manifest: dict) -> str:
    scores = {f: _family_score(tokens, FAMILY_WORDS[f]) for f in FAMILY_ORDER}
    if _hits(tokens, _vocab("translate, traduce, traducir")):
        scores["language"] += 2
    obj = _first_object_family(tokens)
    if obj:
        scores[obj] += 1.5
    best = max(FAMILY_ORDER, key=lambda f: (scores[f], f == manifest.get("family"), -FAMILY_ORDER.index(f)))
    if scores[best] > 0:
        return best
    return manifest.get("family") if manifest.get("family") in FAMILY_ORDER else "software"


def _task_class(tokens: list[str], family: str) -> str:
    for fam, cls, words in CLASS_WORDS:
        if fam == family and _hits(tokens, words):
            return cls
    return DEFAULT_CLASS[family]


def _question_kind(raw: str, tokens: list[str]) -> str | None:
    """'wh' for what/why/how/qué/cómo questions (answered even when they name
    a verb: 'how do I fix this?' asks for an explanation), 'polite' for
    can you/puedes requests (really a task when a verb follows), 'yesno' for
    other questions, None for statements."""
    first = tokens[0] if tokens else ""
    if first in WH_WORDS:
        return "wh"
    if first in POLITE and (first in ("puedes", "podrias") or (len(tokens) > 1 and tokens[1] in ("you", "u"))):
        return "polite"
    s = raw.strip()
    if s.endswith("?") or s.startswith("¿") or first in QWORDS:
        return "yesno"
    return None


def _content(raw: str, tokens: list[str], manifest: dict) -> dict:
    """Size a request that is not a command phrase."""
    family = _family(tokens, manifest)
    create, edit = _hits(tokens, CREATE), _hits(tokens, EDIT)
    small, big, whole = _hits(tokens, SMALL), _hits(tokens, BIG), _hits(tokens, WHOLE)
    programme = _hits(tokens, PROGRAMME)
    acts = bool(create or edit)
    q = _question_kind(raw, tokens)
    if q == "wh" or (q == "yesno" and not acts):
        return {"tier": 0, "family": family, "task_class": "answer", "reason": "a question"}
    cls = _task_class(tokens, family)
    if cls == "software.release" and big and _hits(tokens, CREATE) != _hits(tokens, RELEASE_VERBS):
        cls = DEFAULT_CLASS["software"]  # 'build an app ... deployed on Vercel' is a feature build
    deliverables = {" ".join(p) for p in big}
    joins = sum(1 for w in tokens if w in ("and", "y", "plus")) + raw.count(",") + raw.count("+")
    several = len(deliverables) >= 3 and joins >= 2
    if acts and (programme or several or (create and _hits(tokens, _vocab("everything, entire platform")))):
        why = "multi-phase language" if programme else "several deliverables" if several else "everything"
        return {"tier": 3, "family": family, "task_class": cls, "reason": why}
    if create:
        if (big or whole or _hits(tokens, RESEARCH)) and not (small and not big and not whole):
            return {"tier": 2, "family": family, "task_class": cls, "reason": "builds a whole deliverable"}
        if small:
            return {"tier": 1, "family": family, "task_class": cls, "reason": "one small piece"}
        return {"tier": 1, "family": family, "task_class": cls,
                "reason": "unsure between 1 and 2; chose 1, move up if it grows"}
    if edit:
        if whole and not small:
            return {"tier": 2, "family": family, "task_class": cls, "reason": "a change across a whole deliverable"}
        return {"tier": 1, "family": family, "task_class": cls, "reason": "a bounded edit"}
    if _hits(tokens, COMPLAINT):
        fam = family if family != "knowledge" else (manifest.get("family") or "software")
        return {"tier": 1, "family": fam, "task_class": _task_class(tokens, fam) if fam != "software" else "software.bugfix",
                "reason": "reports a problem to fix"}
    return {"tier": 0, "family": family, "task_class": "answer", "reason": "no task verb; answer or acknowledge"}


def _trigger(tokens: list[str]) -> tuple[str, list[str]] | None:
    pos = 0
    while pos < len(tokens) and tokens[pos] in FILLERS:
        pos += 1
    for kind, phrases, max_rest in TRIGGERS:
        for phrase in phrases:
            starts = {pos, 0}
            if kind in ("handover", "revert", "stop", "learned"):  # '..., go back' at the end
                starts.add(len(tokens) - len(phrase))
            for start in sorted(s for s in starts if s >= 0):
                if _phrase_at(tokens, start, phrase):
                    rest = tokens[start + len(phrase):]
                    if kind == "setup" and any(w not in SETUP_OK and w not in FILLERS for w in rest):
                        continue
                    if max_rest is not None and len(rest) > max_rest:
                        continue
                    return kind, rest
    return None


def classify(request: str, manifest: dict | None = None) -> dict:
    """{tier, family, task_class, reason} for a request in English or Spanish."""
    manifest = manifest or {}
    raw = request or ""
    tokens = _tokens(raw)
    recorded = manifest.get("tier", manifest.get("size", 2))
    recorded = recorded if isinstance(recorded, int) and 0 <= recorded <= 3 else 2
    fam_default = manifest.get("family") if manifest.get("family") in FAMILY_ORDER else None
    trig = _trigger(tokens)
    if trig:
        kind, rest = trig
        rest_raw = " ".join(rest) + ("?" if raw.strip().endswith("?") else "")
        fixed = {
            "resume": (recorded, "resume", f"resume at the recorded size {recorded}"),
            "setup": (recorded, "resume", f"set up: resume at the recorded size {recorded}"),
            "status": (0, "status", "status request"),
            "learned": (0, "learned", "asks what was learned"),
            "stop": (0, "stop", "finish the current item, then stop"),
            "handover": (1, "handover", "hand over to a new chat"),
            "revert": (1, "revert", "restore the last good version"),
        }
        if kind in fixed:
            tier, cls, why = fixed[kind]
            return {"tier": tier, "family": fam_default or _family(rest, manifest), "task_class": cls, "reason": why}
        inner = _content(rest_raw, rest, manifest) if rest else {
            "tier": 0, "family": fam_default or "software", "task_class": "answer", "reason": "empty request"}
        if kind == "quick":
            inner["tier"] = min(inner["tier"], 1)
            inner["reason"] = "'quick:' caps the size at 1; " + inner["reason"]
        elif kind == "deep":
            if inner["tier"] == 0:
                inner.update(tier=1, task_class="knowledge.research", family=inner["family"])
            inner["reason"] = "'go deep:' allows a researched answer; " + inner["reason"]
        elif kind == "new":
            inner["tier"] = 3 if inner["tier"] == 3 else 2
            if inner["task_class"] == "answer":
                inner["task_class"] = DEFAULT_CLASS[inner["family"]]
            inner["reason"] = "new project; " + inner["reason"]
        return inner
    return _content(raw, tokens, manifest)


# ---------------------------------------------------------------- suggest
def suggest(task_class: str, role: str = "lead", family: str = "software", risk: str | None = "standard",
            tier: int | None = 1, has_check: bool = False, state: dict | None = None, cfg: dict | None = None,
            seed: int | None = None) -> dict:
    """{model, effort, explored, propensity, basis} for a role on a task.

    All learning lives in engine/mlearn.py; this wrapper only supplies the
    stored state and config and a seeded generator, so a seed reproduces the
    choice (I-13). Without a verifying check the answer is the role default."""
    cfg = cfg if cfg is not None else mlearn.config()
    state = state if state is not None else mlearn.load()
    return mlearn.suggest_arm(state, cfg, task_class, family, role, risk, tier, has_check, random.Random(seed))


def cheap_first(p_cheap: float, c_cheap: float, c_verify: float, c_strong: float) -> bool:
    """Cascade rule: trying the cheap option, checking it, and escalating on
    failure costs c_cheap + c_verify + (1 - p) c_strong in expectation; that
    beats going straight to the strong option when p > (c_cheap + c_verify) / c_strong."""
    if c_strong <= 0:
        return False
    return p_cheap > (c_cheap + c_verify) / c_strong


# ---------------------------------------------------------------- assign
def assign(tasks: list[dict] | None, budget: int | None) -> dict:
    """Exact multiple-choice knapsack: one option per task, maximum total
    quality with total cost within budget.

    Dynamic programming over the Pareto front of (cost, quality) states: after
    each task only states that no other state beats on both cost and quality
    are kept. This is exact like the classic table over every budget unit, but
    its size follows the number of distinct useful totals rather than the
    budget, so token-sized budgets stay fast. When even the cheapest option of
    every task exceeds the budget, that cheapest assignment is returned with
    ``feasible`` false."""
    if not isinstance(tasks, list) or not tasks:
        raise ValueError('needs a non-empty "tasks" list')
    if not isinstance(budget, int) or isinstance(budget, bool) or budget < 0:
        raise ValueError("budget must be a non-negative integer")
    ids = []
    for pos, t in enumerate(tasks):
        opts = t.get("options") if isinstance(t, dict) else None
        tid = str(t.get("id", f"task-{pos + 1}")) if isinstance(t, dict) else f"task-{pos + 1}"
        if not isinstance(opts, list) or not opts:
            raise ValueError(f"task {tid} has no options")
        for o in opts:
            cost, q = o.get("cost"), o.get("quality")
            if not isinstance(cost, int) or isinstance(cost, bool) or cost < 0:
                raise ValueError(f"task {tid}: cost must be a non-negative integer")
            if not isinstance(q, (int, float)) or isinstance(q, bool):
                raise ValueError(f"task {tid}: quality must be a number")
        if tid in ids:
            raise ValueError(f"duplicate task id {tid}")
        ids.append(tid)
    # front: list of (cost, quality, back-pointer) sorted by cost; layers keep pointers.
    layers: list[list[tuple[int, float, int, int]]] = []
    front: list[tuple[int, float, int, int]] = [(0, 0.0, -1, -1)]
    for t in tasks:
        cand = []
        for si, (cost, q, _, _) in enumerate(front):
            for oi, o in enumerate(t["options"]):
                nc = cost + o["cost"]
                if nc <= budget:
                    cand.append((nc, q + float(o["quality"]), si, oi))
        cand.sort(key=lambda s: (s[0], -s[1], s[2], s[3]))
        pruned: list[tuple[int, float, int, int]] = []
        for s in cand:
            if not pruned or s[1] > pruned[-1][1] + 1e-12:
                pruned.append(s)
        layers.append(pruned)
        front = pruned
        if not front:
            break
    if not front:
        choice = {tid: dict(min(t["options"], key=lambda o: (o["cost"], -o["quality"])))
                  for tid, t in zip(ids, tasks)}
        return {"choice": choice, "cost": sum(o["cost"] for o in choice.values()),
                "quality": round(sum(float(o["quality"]) for o in choice.values()), 6), "feasible": False}
    picks = [0] * len(tasks)
    si = len(front) - 1  # highest quality, and the cheapest at that quality
    for layer in range(len(tasks) - 1, -1, -1):
        _, _, prev, oi = layers[layer][si]
        picks[layer] = oi
        si = prev
    choice = {tid: dict(t["options"][picks[k]]) for k, (tid, t) in enumerate(zip(ids, tasks))}
    return {"choice": choice, "cost": front[-1][0], "quality": round(front[-1][1], 6), "feasible": True}


# ---------------------------------------------------------------- cli
def lead_role(result: dict) -> str:
    """Deep lead for programmes and for a new project's architecture; the
    ordinary lead otherwise."""
    return "deep-lead" if result["tier"] == 3 else "lead"


def cmd_route(args) -> int:
    proj = c.resolve_project(args.project)
    manifest = c.load_manifest(proj) if proj and c.is_managed(proj) else {}
    res = classify(args.request, manifest)
    role = lead_role(res)
    sug = suggest(res["task_class"], role, res["family"], args.risk, res["tier"], args.check, seed=args.seed)
    res.update(role=role, **sug)
    if args.json:
        print(json.dumps(res, ensure_ascii=False))
        return 0
    kind = f"exploration, p={sug['propensity']}" if sug["explored"] else "not an exploration"
    print(f"size {TIER_NAMES[res['tier']]} | {res['family']} | {res['task_class']} | {role}: {sug['model']} {sug['effort']}")
    print(f"why: {res['reason']}; model basis: {sug['basis']}; {kind}")
    return 0


def register(sub) -> None:
    p = sub.add_parser("route", help="size a request and suggest the lead model and effort")
    p.add_argument("request")
    p.add_argument("--seed", type=int, help="seed for the Thompson draw (reproducible)")
    p.add_argument("--risk", choices=("trivial", "standard", "high"), default="standard",
                   help="high (release, security, migration, data deletion) never tries a cheaper model")
    p.add_argument("--check", action="store_true", help="the task has a verifying check (needed to try a cheaper model)")
    p.add_argument("--json", action="store_true")
    c.add_project_arg(p)
    p.set_defaults(func=cmd_route)
