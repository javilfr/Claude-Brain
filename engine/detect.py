"""Find the project beside the brain and print a short orientation.

``boot`` replaces the start-of-session reading list. An earlier setup spent an
estimated 35,000-50,000 tokens reading six documents before doing anything;
this prints about fifteen lines.
"""
from __future__ import annotations

from pathlib import Path

from . import common as c
from . import state as st_mod

BOOT_LIMIT = 1500  # bytes


def classify(path: Path) -> str:
    if c.is_managed(path):
        return "managed"
    if c.is_empty_repo(path):
        return "empty"
    return "unmanaged"


def explicit_project(project: str | None = None, brain_root: Path | None = None) -> Path | None:
    """A project named by --project or BRAIN_PROJECT, or the git repository the
    command runs in when that is not the brain. The same precedence as every
    other command (``common.resolve_project``), so ``boot`` and ``gate`` never
    disagree about which project they act on."""
    import os
    for cand in (project, os.environ.get("BRAIN_PROJECT")):
        if cand:
            return Path(cand).expanduser().resolve()
    roots = {Path(brain_root or c.BRAIN_ROOT).resolve(), Path(c.BRAIN_ROOT).resolve()}
    cur = Path.cwd().resolve()
    for p in (cur, *cur.parents):
        if any(p == r or r in p.parents for r in roots):
            return None
        if (p / ".git").exists() or c.is_managed(p):
            return p
    return None


def detect(brain_root: Path | None = None, named: str | None = None, project: str | None = None) -> dict:
    """Decide the working mode from an explicit project, else the folders beside the brain."""
    root = Path(brain_root or c.BRAIN_ROOT)
    exp = explicit_project(project, root)
    if exp is not None and exp.is_dir():
        sibs = [(exp, classify(exp))]
        named = None
    else:
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


def boot_lines(request: str | None = None, brain_root: Path | None = None, named: str | None = None,
               project: str | None = None) -> list[str]:
    root = Path(brain_root or c.BRAIN_ROOT)
    d = detect(root, named, project)
    mode = d["mode"]
    lines = [f"brain: {root.name} · mode: {mode}" + (f" · {MODE_HELP[mode]}" if MODE_HELP.get(mode) else "")]
    proj = Path(d["project"]) if d.get("project") else None
    family = None
    if proj and c.is_managed(proj) and c.manifest_problem(proj):
        lines.append(f"project: {proj.name} · PROBLEM: {c.manifest_problem(proj)}")
    elif proj and mode in ("work", "choose", "migrate") and c.is_managed(proj):
        m, st = c.load_manifest(proj), st_mod.read_state(proj)
        family = m.get("family")
        lines.append(f"project: {proj.name} · {m.get('project', {}).get('title', '')} · family {family} · contract v{m.get('contract')} · stage {st.get('stage') or m.get('stage')}")
        lines.append(f"item: {st.get('item') or 'none'} · last done: {st.get('last_done') or 'none'}")
        if st["next_list"]:
            lines.append("next: " + "; ".join(st["next_list"]))
        if st.get("blockers") and st["blockers"] != "none":
            lines.append(f"blockers: {st['blockers']}")
        if st.get("notes"):
            lines.append("notes: " + c.clip(st["notes"], 220))
        rq, needs = st_mod.req_counts(proj), st_mod.open_needs(proj)
        rel = m.get("release", {}).get("rule", "none")
        if rq.get("broken"):
            lines.append("PROBLEM: .brain/requirements.jsonl has an unreadable line; run `brain req check` and repair it first")
        lines.append(f"requirements: {rq['done']}/{rq['total']} done, {rq['open']} open · needs owner: {len(needs)} · release: {rel}")
        warn = st_mod.lease_warning(st)
        if warn:
            lines.append("WARNING: " + warn)
        if d.get("others"):
            lines.append("also attached: " + ", ".join(d["others"]) + " (using the most recently active)")
    elif proj:
        lines.append(f"project folder: {proj.name}")
    elif d.get("others"):
        lines.append("attached: " + ", ".join(d["others"]))
    models = c.read_json(root / "memory" / "models.json", {}) or {}
    age = c.days_since(models.get("verified_on", ""))
    if age > int(models.get("recheck_days", 90)):
        lines.append(f"note: model facts were verified {age} days ago; re-check memory/models.json before relying on prices or model names")
    if mode == "brain-only":
        lines += brain_work_lines(root)
    lines += session_start_lines(root, proj if proj and c.is_managed(proj) and mode in ("work", "choose") else None)
    if request:
        try:
            from . import route
            r = route.classify(request, c.load_manifest(proj) if proj and c.is_managed(proj) else None)
            names = {0: "0 answer", 1: "1 small task", 2: "2 project", 3: "3 programme"}
            lines.append(f"size: {names.get(r['tier'], r['tier'])} · {r.get('family') or family or '-'} · {r.get('task_class', '-')} · {c.clip(r.get('reason', ''), 90)}")
            family = family or r.get("family")
            tier = r["tier"]
        except Exception:  # routing is optional at boot; never block orientation
            tier = None
        if tier != 0:
            try:
                from . import recall
                hits = recall.recall(request, family=family, k=3, budget_tokens=260, project=proj if proj and c.is_managed(proj) else None, brain_root=root)
                for h in hits:
                    lines.append(f"recall [{h['id']}] {c.clip(h['text'], 170)}")
            except Exception:
                pass
    # Keep within the byte budget: orientation must stay cheap.
    out, size = [], 0
    for l in lines:
        size += len(l.encode()) + 1
        if size > BOOT_LIMIT:
            break
        out.append(l)
    return out


def brain_work_lines(root: Path) -> list[str]:
    """With only the brain attached, the work is the brain itself: its open
    tickets are the position, and docs/NEXT_SESSION.md is the handover."""
    data = c.read_json(root / "docs" / "plan" / "tickets.json", {}) or {}
    tickets = [t for t in data.get("tickets", []) if isinstance(t, dict)]
    done = {t.get("id") for t in tickets if t.get("status") == "done"}
    todo = [t for t in tickets if t.get("status") != "done"]
    if not todo:
        return []
    ready = [t for t in todo if all(d in done for d in t.get("deps", []) or [])]
    first = (ready or todo)[0]
    out = [f"brain work: {len(todo)} open ticket(s) in docs/plan/tickets.json · next: {first.get('id')} {c.clip(str(first.get('title', '')), 70)}"]
    if (root / "docs" / "NEXT_SESSION.md").is_file():
        out.append("handover: read docs/NEXT_SESSION.md first, then `brain plan schedule docs/plan/tickets.json`")
    return out


RADAR_EVERY_HOURS = 24


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


def session_start_lines(root: Path, project: Path | None) -> list[str]:
    """Extra orientation that depends on optional modules. Every part is
    guarded: a failure here must never cost the session its start."""
    out: list[str] = []
    if project is not None:
        try:  # an earlier session that never ran `close`: record it now
            from . import ledger
            previous = ledger.mark_open(project)
            if previous:
                out.append("earlier session was not closed: " + c.clip(ledger.repair_unclosed(project, previous), 150))
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
    d = detect(named=args.name, project=args.project)
    if args.json:
        import json
        print(json.dumps(d, indent=2))
    else:
        print(f"mode: {d['mode']}" + (f" · project: {Path(d['project']).name}" if d.get("project") else ""))
        for s in d["siblings"]:
            print(f"  {Path(s['path']).name}: {s['kind']}")
    return 0


def cmd_boot(args) -> int:
    for l in boot_lines(args.request, named=args.name, project=args.project):
        print(l)
    return 0


def register(sub) -> None:
    p = sub.add_parser("detect", help="which project is beside the brain and in what state")
    p.add_argument("--name", help="project named by the owner, when several are attached")
    p.add_argument("--project", help="project path (default: BRAIN_PROJECT, the current repository, then the folders beside the brain)")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_detect)
    p = sub.add_parser("boot", help="short orientation for the start of a session")
    p.add_argument("request", nargs="?", help="the owner's request, to size it and recall relevant memory")
    p.add_argument("--name")
    p.add_argument("--project", help="project path (default: BRAIN_PROJECT, the current repository, then the folders beside the brain)")
    p.set_defaults(func=cmd_boot)
