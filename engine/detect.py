"""Find the project beside the brain and print a short orientation.

``boot`` replaces the start-of-session reading list. An earlier setup spent an
estimated 35,000-50,000 tokens reading six documents before doing anything;
this prints at most fifteen lines.

Boot makes one bounded fetch of the project's branch heads (decision D-17):
a new chat starts on a new branch cut from the default branch, so the last
chat's checkpoint is on another branch and has to be looked for.
"""
from __future__ import annotations

from pathlib import Path

from . import common as c
from . import state as st_mod

BOOT_LIMIT = 1500  # bytes
BOOT_LINES = 15


def classify(path: Path) -> str:
    if c.is_managed(path):
        return "managed"
    if c.is_empty_repo(path):
        return "empty"
    return "unmanaged"


def detect(brain_root: Path | None = None, named: str | None = None) -> dict:
    """Decide the working mode from the folders beside the brain."""
    root = Path(brain_root or c.BRAIN_ROOT)
    sibs = [(p, classify(p)) for p in c.sibling_dirs(root)]
    # Only repositories count as candidate projects; stray folders are ignored.
    sibs = [(p, k) for p, k in sibs if k == "managed" or (p / ".git").exists()]
    out: dict = {"brain": str(root), "siblings": [{"path": str(p), "kind": k} for p, k in sibs], "project": None}
    managed = [p for p, k in sibs if k == "managed"]
    if named:
        hit = [p for p, _ in sibs if p.name.lower() == named.lower() or named.lower() in p.name.lower()]
        if len(hit) == 1:
            sibs = [(hit[0], classify(hit[0]))]
            managed = [p for p, k in sibs if k == "managed"]
    if not sibs:
        out["mode"] = "brain-only"
        return out
    if len(managed) > 1:
        # Most recently checkpointed wins; the caller is told there was a choice.
        managed.sort(key=lambda p: st_mod.read_state(p).get("updated", ""), reverse=True)
        out.update(mode="choose", project=str(managed[0]), others=[p.name for p in managed[1:]])
        return out
    if len(managed) == 1:
        proj = managed[0]
        ver = c.load_manifest(proj).get("contract")
        out["project"] = str(proj)
        if isinstance(ver, int) and ver > c.CONTRACT_VERSION:
            out["mode"] = "stale-brain"
        elif isinstance(ver, int) and ver < c.CONTRACT_VERSION:
            out["mode"] = "migrate"
        else:
            out["mode"] = "work"
        return out
    if len(sibs) == 1:
        out["project"] = str(sibs[0][0])
        out["mode"] = "bootstrap" if sibs[0][1] == "empty" else "adopt"
        return out
    out["mode"] = "choose"
    out["others"] = [p.name for p, _ in sibs]
    return out


MODE_HELP = {
    "brain-only": "no project attached: answer, maintain or learn; to build, attach a project repository",
    "bootstrap": "empty project: on 'New project: …' run `brain init <path> --family F --title T`",
    "adopt": "existing codebase without a contract: `brain adopt <path> --survey` first, then `brain adopt <path>`",
    "migrate": "project is on an older contract: run `brain migrate`",
    "stale-brain": "project uses a newer contract than this brain: write nothing to .brain/; tell the owner the brain needs updating",
    "choose": "several projects attached: use the one the owner named",
    "work": "",
}


def clip_bytes(text: str, limit: int) -> str:
    """One line of at most ``limit`` bytes (the boot cap is in bytes, and
    Spanish text is longer in bytes than in characters)."""
    text = " ".join(str(text).split())
    if len(text.encode()) <= limit:
        return text
    return text.encode()[: max(0, limit - 3)].decode("utf-8", "ignore").rstrip() + "…"


def fit(lines: list[tuple[int, str]], limit: int = BOOT_LIMIT, max_lines: int = BOOT_LINES) -> list[str]:
    """Keep the lines that fit the byte and line caps, lowest priority number
    first, in their original order; a line that does not fit is skipped, never
    the ones after it. When anything was left out, the last line says so."""
    def choose(room: int, count: int) -> list[bool]:
        keep = [False] * len(lines)
        size = n = 0
        for pri in sorted({p for p, _ in lines}):
            for i, (p, l) in enumerate(lines):
                need = len(l.encode()) + 1
                if p == pri and size + need <= room and n < count:
                    keep[i], size, n = True, size + need, n + 1
        return keep
    keep = choose(limit, max_lines)
    if not all(keep):
        keep = choose(limit - 48, max_lines - 1)   # room for the notice
    out = [l for (_, l), k in zip(lines, keep) if k]
    left = len(lines) - len(out)
    return out + ([f"… {left} more line(s) left out: brain resume"] if left else [])


def _without_trigger(request: str) -> str:
    """The request without its trigger phrase ("Go deep:", "Quick:"), so recall
    matches the subject and not the trigger word."""
    try:
        from . import route
        trig = route._trigger(route._tokens(request))
        return " ".join(trig[1]) if trig else request
    except Exception:
        return request


def boot_lines(request: str | None = None, brain_root: Path | None = None, named: str | None = None) -> list[str]:
    """The orientation, as (priority, line) pairs cut to the caps by priority:
    0 = mode, project, PROBLEM, WARNING and a newer checkpoint elsewhere;
    1 = the position; 2 = notes and the other project; 3 = recall and news."""
    root = Path(brain_root or c.BRAIN_ROOT)
    d = detect(root, named)
    mode = d["mode"]
    proj = Path(d["project"]) if d.get("project") else None
    managed = bool(proj and c.is_managed(proj))
    lines: list[tuple[int, str]] = []

    def add(pri: int, line: str, limit: int = 220) -> None:
        if line:
            lines.append((pri, clip_bytes(line, limit)))
    newer: list[dict] = []
    if proj and mode != "stale-brain":
        try:  # the last chat's state is usually on another branch; one bounded fetch
            newer = st_mod.newer_checkpoints(proj)
        except Exception:
            newer = []
    hint = MODE_HELP.get(mode, "")
    if newer and mode in ("bootstrap", "adopt"):
        hint = "this checkout has no contract, but a branch on the remote does"
    add(0, f"brain: {root.name} · mode: {mode}" + (f" · {hint}" if hint else ""))
    family = None
    st = None
    view = None
    working = managed and mode in ("work", "choose", "migrate") and not c.manifest_problem(proj)
    if managed and c.manifest_problem(proj):
        add(0, f"project: {c.clip(proj.name, 40)} · PROBLEM: {c.manifest_problem(proj)}", 260)
    elif working:
        m, st = c.load_manifest(proj), st_mod.read_state(proj)
        family = m.get("family")
        meta = m.get("project") if isinstance(m.get("project"), dict) else {}
        add(0, f"project: {c.clip(proj.name, 40)} · {c.clip(str(meta.get('title', '')), 60)} · family {family} · contract v{m.get('contract')} · stage {st.get('stage') or m.get('stage')}")
        view = dict(m)
        if st.get("tier", "").isdigit() and 0 <= int(st["tier"]) <= 3:
            view["tier"] = int(st["tier"])   # the checkpointed size wins over the manifest's first one
        problem = st_mod.state_problem(proj)
        if problem:
            add(0, "PROBLEM: " + problem, 240)
        if not newer:   # with a newer checkpoint elsewhere, this position is stale: adopt first
            add(1, f"item: {c.clip(st.get('item') or 'none', 160)} · last done: {c.clip(st.get('last_done') or 'none', 90)}", 280)
            if st["next_list"]:
                add(1, "next: " + "; ".join(st["next_list"]), 310)
            if st.get("blockers") and st["blockers"] != "none":
                add(1, f"blockers: {st['blockers']}", 190)
            if st.get("notes"):
                add(2, "notes: " + st_mod.notes_tail(st["notes"], 200), 250)
            rq, needs = st_mod.req_counts(proj), st_mod.open_needs(proj)
            rel = m.get("release") if isinstance(m.get("release"), dict) else {}
            if rq.get("broken"):
                add(0, "PROBLEM: .brain/requirements.jsonl has an unreadable line; run `brain req check` and repair it first")
            add(1, f"requirements: {rq['done']}/{rq['total']} done, {rq['open']} open · needs owner: {len(needs)} · release: {rel.get('rule', 'none')}")
            add(1, st_mod.owner_marks(proj), 240)
            warn = st_mod.lease_warning(st)
            if warn:
                add(0, "WARNING: " + warn)
        if d.get("others"):
            add(2, "also attached: " + c.clip(", ".join(d["others"]), 120) + " (using the most recently active)")
    elif proj:
        add(0, f"project folder: {c.clip(proj.name, 60)}")
    elif d.get("others"):
        add(1, "attached: " + c.clip(", ".join(d["others"]), 160))
    if newer:
        n = newer[0]
        add(0, f"newer checkpoint on {n['ref']} ({n['updated'][:16].replace('T', ' ')}, item: {c.clip(n['item'] or 'none', 70)}): "
               "run `brain resume --adopt` before anything else" + (f" (+{len(newer) - 1} more branch(es))" if len(newer) > 1 else ""), 260)
    models = c.read_json(root / "memory" / "models.json", {}) or {}
    age = c.days_since(models.get("verified_on", ""))
    if age > int(models.get("recheck_days", 90)):
        add(3, f"note: model facts were verified {age} days ago; re-check memory/models.json before relying on prices or model names")
    if mode == "brain-only":
        for l in brain_work_lines(root):
            add(1, l)
    for l in session_start_lines(root, proj if working and mode in ("work", "choose") and not newer else None):
        add(2 if l.startswith("earlier session") else 3, l)
    add(3, learning_line(root), 240)
    if request:
        tier = cls = None
        try:
            from . import route
            r = route.classify(request, view if view is not None else (c.load_manifest(proj) if managed else None))
            names = {0: "0 answer", 1: "1 small task", 2: "2 project", 3: "3 programme"}
            add(1, f"size: {names.get(r['tier'], r['tier'])} · {r.get('family') or family or '-'} · {r.get('task_class', '-')} · {c.clip(r.get('reason', ''), 90)}", 180)
            family = family or r.get("family")
            tier, cls = r["tier"], r.get("task_class")
        except Exception:  # routing is optional at boot; never block orientation
            pass
        if tier != 0 and cls not in ("handover", "status", "learned", "stop") and not newer:
            if cls == "resume":
                # A bare "Continue" says nothing about the work: recall on what is recorded.
                query = " ".join(x for x in ([st.get("item"), *st["next_list"], st.get("blockers")] if st else []) if x and x != "none")
            else:
                query = _without_trigger(request)
            try:
                if query.strip():
                    from . import recall
                    hits = recall.recall(query, family=family, k=3, budget_tokens=260,
                                         project=proj if working else None, brain_root=root)
                    for h in hits:
                        add(3, f"recall [{h['id']}] {c.clip(h['text'], 170)}", 200)
            except Exception:
                pass
    return fit(lines)


def ticket_lines(root: Path) -> list[str]:
    """The brain's own open tickets, in one line (none when there are none)."""
    data = c.read_json(root / "docs" / "plan" / "tickets.json", {}) or {}
    tickets = [t for t in data.get("tickets", []) if isinstance(t, dict)] if isinstance(data, dict) else []
    done = {t.get("id") for t in tickets if t.get("status") == "done"}
    todo = [t for t in tickets if t.get("status") != "done"]
    if not todo:
        return []
    ready = [t for t in todo if all(d in done for d in t.get("deps", []) or [])]
    first = (ready or todo)[0]
    return [f"brain work: {len(todo)} open ticket(s) in docs/plan/tickets.json · next: {first.get('id')} {c.clip(str(first.get('title', '')), 70)}"]


def brain_work_lines(root: Path) -> list[str]:
    """With only the brain attached, the work is the brain itself: its open
    tickets are the position, its NEEDS_YOU.md is what waits on the owner, and
    docs/NEXT_SESSION.md is the handover."""
    out = ticket_lines(root)
    needs = st_mod.open_needs(root)
    if needs:
        out.append(f"needs owner: {len(needs)} open item(s) in NEEDS_YOU.md")
    if out and (root / "docs" / "NEXT_SESSION.md").is_file():
        out.append("handover: read docs/NEXT_SESSION.md first, then `brain plan schedule docs/plan/tickets.json`")
    return out


RADAR_EVERY_HOURS = 24
PENDING_INBOX_MAX = 8   # more inbox files than this waiting means consolidation is not happening


def radar_due(root: Path) -> bool:
    """True when no source has been checked in the last day."""
    state = c.read_json(root / "learning" / "radar" / "state.json", {}) or {}
    sources = state.get("sources", state) if isinstance(state, dict) else {}
    stamps = [v.get("last_checked", "") for v in sources.values() if isinstance(v, dict)]
    if not stamps:
        return True
    import datetime as dt
    try:
        newest = max(dt.datetime.fromisoformat(x.replace("Z", "+00:00")) for x in stamps if x)
    except ValueError:
        return True
    return (c.now() - newest).total_seconds() > RADAR_EVERY_HOURS * 3600


def learning_line(root: Path) -> str:
    """One line when the learning loop needs attention, else "": inbox files
    piling up or unreadable, a memory file near its item budget, facts overdue
    for a re-check. A healthy brain prints nothing."""
    parts: list[str] = []
    try:
        from . import learn
        cfg = c.read_json(root / "memory" / "ml_config.json", {})
        boot_cfg = cfg.get("boot") if isinstance(cfg, dict) and isinstance(cfg.get("boot"), dict) else {}
        limit = int(boot_cfg.get("pending_inbox_max", PENDING_INBOX_MAX))
        pending = learn.pending_inbox(root)
        bad = learn.inbox_unreadable(root)[0]
        if len(pending) > limit or bad:
            parts.append(f"{len(pending)} inbox file(s) waiting" + (f", {bad} unreadable line(s)" if bad else "") + ' (say "Consolidate")')
        budget = learn.DEFAULT_BUDGET
        overdue = 0
        for folder in ("memory", "owner", "playbooks"):
            for f in sorted((root / folder).glob("*.jsonl")):
                rows = c.read_jsonl(f)
                if len(rows) >= 0.9 * budget:
                    parts.append(f"{folder}/{f.name} holds {len(rows)} of {budget} items")
                overdue += sum(1 for it in rows if it.get("verified_on") and not it.get("valid_to")
                               and c.days_since(it["verified_on"]) > int(it.get("recheck_days", 90) or 90))
        if overdue:
            parts.append(f"{overdue} fact(s) overdue for a re-check (brain learn decay lists them)")
    except Exception:  # never cost the session its start
        return ""
    return "learning: " + "; ".join(parts) if parts else ""


def session_start_lines(root: Path, project: Path | None) -> list[str]:
    """Extra orientation that depends on optional modules. Every part is
    guarded: a failure here must never cost the session its start."""
    out: list[str] = []
    if project is not None:
        try:  # an earlier session that never ran `close`: record it now
            from . import ledger
            previous = ledger.mark_open(project)
            if previous:
                # This chat writes that session's record: it may commit it (push_brain_records).
                st_mod.remember_repaired(str(previous.get("session") or ""), root)
                out.append("earlier session was not closed: " + c.clip(ledger.repair_unclosed(project, previous, root), 150))
        except Exception:
            pass
    try:  # a model update or a bad lesson shows up as a shift in the numbers
        from . import mlearn
        cfg = c.read_json(root / "memory" / "ml_config.json", {}) or {}
        out += [c.clip("alarm: " + a, 180) for a in mlearn.alarms(mlearn.load(root), cfg)[:2]]
    except Exception:
        pass
    try:  # official news about the models or Claude Code, at most once a day
        if radar_due(root):
            from . import radar
            out += [c.clip("news: " + l, 220) for l in radar.due_lines(max_seconds=4, max_lines=2, trust="official", brain_root=root)]
    except Exception:
        pass
    return out


def cmd_detect(args) -> int:
    d = detect(named=args.name)
    if args.json:
        import json
        print(json.dumps(d, indent=2))
    else:
        print(f"mode: {d['mode']}" + (f" · project: {Path(d['project']).name}" if d.get("project") else ""))
        for s in d["siblings"]:
            print(f"  {Path(s['path']).name}: {s['kind']}")
    return 0


def cmd_boot(args) -> int:
    for l in boot_lines(args.request, named=args.name):
        print(l)
    return 0


def register(sub) -> None:
    p = sub.add_parser("detect", help="which project is beside the brain and in what state")
    p.add_argument("--name", help="project named by the owner, when several are attached")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_detect)
    p = sub.add_parser("boot", help="short orientation for the start of a session")
    p.add_argument("request", nargs="?", help="the owner's request, to size it and recall relevant memory")
    p.add_argument("--name")
    p.set_defaults(func=cmd_boot)
