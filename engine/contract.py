"""The project contract: create it (init), add it to an existing codebase
(adopt), check it (validate) and bring an older one up to date (migrate).

The contract is the small set of files in a project that the brain reads and
writes. Everything here is idempotent: running a command twice changes nothing
the second time, and no existing file is ever overwritten.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

from . import common as c

TEMPLATE = c.BRAIN_ROOT / "contract" / "template"
BEGIN, END = "<!-- brain:begin", "<!-- brain:end -->"
STUB_LIMIT = 2000  # bytes of always-loaded text the stub may add to a project
OLD_HANDBOOK_LIMIT = 4000  # bytes; above this an adopted project is asked to slim its handbook
FAMILIES = ("software", "data", "knowledge", "language", "operations")


# ---------------------------------------------------------------- schema
def load_schema(version: int = c.CONTRACT_VERSION, brain_root: Path | None = None) -> dict:
    return c.read_json(Path(brain_root or c.BRAIN_ROOT) / "contract" / f"v{version}.schema.json", {}) or {}


_TYPES = {"object": dict, "array": list, "string": str, "integer": int, "boolean": bool}


def check_schema(value, schema: dict, where: str = "manifest") -> list[str]:
    """Validate against the small subset of JSON Schema the contract uses
    (type, required, properties, items, enum). Unknown keys are allowed, so
    newer optional keys never break an older reader."""
    errs: list[str] = []
    t = schema.get("type")
    if t:
        py = _TYPES[t]
        if not isinstance(value, py) or (t == "integer" and isinstance(value, bool)):
            return [f"{where}: expected {t}"]
    if "enum" in schema and value not in schema["enum"]:
        errs.append(f"{where}: {value!r} is not one of {schema['enum']}")
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                errs.append(f"{where}: missing '{key}'")
        for key, sub in schema.get("properties", {}).items():
            if key in value:
                errs += check_schema(value[key], sub, f"{where}.{key}")
    if isinstance(value, list) and "items" in schema:
        for i, v in enumerate(value):
            errs += check_schema(v, schema["items"], f"{where}[{i}]")
    return errs


# ---------------------------------------------------------------- init
def slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:40] or "project"


def default_manifest(title: str, family: str, pid: str | None = None) -> dict:
    return {
        "_help": "Claude Brain project contract. Edit values, keep the keys. Commands are whatever can be run to check the work; leave empty when nothing can.",
        "contract": c.CONTRACT_VERSION,
        "project": {"id": pid or slug(title), "title": title, "created": c.today()},
        "family": family,
        "types": [],
        "stage": "intake",
        "tier": 2,
        "commands": {"setup": "", "check_fast": "", "check_full": "", "run": ""},
        "gates": [{"id": "checks", "kind": "command", "command": ""}],
        "release": {"rule": "none", "branch": "main", "live_url": ""},
        "paths": {"deliverables": [], "evidence": "docs/evidence/", "never_touch": []},
        "languages": ["en"],
        "risk": "standard",
        "privacy": {"share_lessons": "method-only"},
        "brain": {"last_seen": "", "min_contract": c.CONTRACT_VERSION},
    }


def stub_text(title: str) -> str:
    return c.read_text(TEMPLATE / "CLAUDE.stub.md").replace("{title}", title).replace("{contract}", str(c.CONTRACT_VERSION))


def _state_text(stage: str = "intake") -> str:
    return (
        "# State\n\n"
        "The single checkpoint for this project. Written by `brain checkpoint`; read by `brain boot`.\n\n"
        f"contract: {c.CONTRACT_VERSION}\nstage: {stage}\ntier: 2\nitem: none\nlast_done: none\nnext: \nblockers: none\n"
        f"session: none\nupdated: {c.now_iso()}\n\n## Notes\n\n## Log\n"
    )


def _create(path: Path, text: str, made: list[str], root: Path) -> None:
    """Create a file only if it does not exist: init never overwrites."""
    if not path.exists():
        c.write_text(path, text)
        made.append(str(path.relative_to(root)))


def ensure_stub(project: Path, title: str, made: list[str]) -> None:
    """Add the pointer block to CLAUDE.md. An existing file keeps all of its
    content: the block is put in front once and never duplicated."""
    target = project / "CLAUDE.md"
    block = stub_text(title).rstrip() + "\n"
    existing = c.read_text(target, "")
    if not target.exists():
        c.write_text(target, block)
        made.append("CLAUDE.md")
    elif BEGIN not in existing:
        c.write_text(target, block + "\n" + existing)  # the block itself says which text wins
        made.append("CLAUDE.md (pointer block added above existing content)")


def init(project: Path, title: str, family: str, manifest_overrides: dict | None = None) -> list[str]:
    """Install the contract. Returns the list of things created (empty when
    everything was already there)."""
    project = Path(project)
    made: list[str] = []
    b = project / ".brain"
    if not (b / "project.json").exists():
        m = default_manifest(title, family)
        for k, v in (manifest_overrides or {}).items():
            if isinstance(v, dict) and isinstance(m.get(k), dict):
                m[k].update(v)
            else:
                m[k] = v
        c.write_json(b / "project.json", m)
        made.append(".brain/project.json")
    title = c.load_manifest(project).get("project", {}).get("title", title)
    _create(b / "STATE.md", _state_text(), made, project)
    _create(b / "requirements.jsonl", "", made, project)
    _create(b / "PLAN.md", c.read_text(TEMPLATE / ".brain" / "PLAN.md"), made, project)
    _create(b / "DECISIONS.md", c.read_text(TEMPLATE / ".brain" / "DECISIONS.md"), made, project)
    _create(b / "memory" / "lessons.jsonl", "", made, project)
    _create(b / "ext" / "README.md", "# Project extensions\n\nSkills, agents, tools and playbook overrides that belong only to this project. They add to the brain's defaults for this project; they cannot change the contract.\n", made, project)
    _create(b / "log" / ".gitkeep", "", made, project)
    _create(b / ".gitignore", "cache/\nlog/run/\n", made, project)
    _create(project / "NEEDS_YOU.md", c.read_text(TEMPLATE / "NEEDS_YOU.md"), made, project)
    _create(project / "STATUS.md", f"# Status: {title}\n\nNothing has been built yet. Say what you want in the chat to begin.\n", made, project)
    ensure_stub(project, title, made)
    return made


# ---------------------------------------------------------------- adopt
def survey(project: Path) -> dict:
    """Read-only look at an existing codebase: guess family and commands from
    the files that declare them. Nothing is written."""
    p = Path(project)
    found: dict = {"family": "software", "types": [], "commands": {}, "signals": []}
    pkg = c.read_json(p / "package.json", None)
    if isinstance(pkg, dict):
        scripts = pkg.get("scripts", {}) if isinstance(pkg.get("scripts"), dict) else {}
        pm = "pnpm" if (p / "pnpm-lock.yaml").exists() else "yarn" if (p / "yarn.lock").exists() else "npm"
        found["signals"].append(f"package.json ({pm})")
        found["types"].append("web-app")
        found["commands"]["setup"] = f"{pm} install"
        fast = [s for s in ("lint", "typecheck") if s in scripts]
        full = [s for s in ("test", "build") if s in scripts]
        if fast:
            found["commands"]["check_fast"] = " && ".join(f"{pm} run {s}" for s in fast)
        if full:
            found["commands"]["check_full"] = " && ".join(f"{pm} run {s}" for s in full)
        if "dev" in scripts:
            found["commands"]["run"] = f"{pm} run dev"
    if (p / "pyproject.toml").exists() or (p / "requirements.txt").exists() or (p / "setup.py").exists():
        found["signals"].append("python project")
        found["types"].append("python")
        if (p / "tests").is_dir() and "check_full" not in found["commands"]:
            found["commands"]["check_full"] = "python3 -m unittest discover -s tests -t ." if not (p / "pyproject.toml").exists() or "pytest" not in c.read_text(p / "pyproject.toml") else "python3 -m pytest -q"
    if (p / "Makefile").exists():
        found["signals"].append("Makefile")
        mk = c.read_text(p / "Makefile")
        if re.search(r"^test:", mk, re.M) and "check_full" not in found["commands"]:
            found["commands"]["check_full"] = "make test"
    if (p / "vercel.json").exists() or any(p.glob("*/vercel.json")):
        found["signals"].append("vercel.json (deploys from a branch; ask whether main-on-green applies)")
    names = [f.suffix.lower() for f in p.rglob("*") if f.is_file() and ".git" not in f.parts and "node_modules" not in f.parts][:5000]
    code = sum(n in (".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".swift", ".kt", ".java") for n in names)
    prose = sum(n in (".md", ".txt", ".docx", ".tex") for n in names)
    data = sum(n in (".csv", ".ipynb", ".parquet", ".xlsx") for n in names)
    if not found["signals"]:
        found["family"] = "data" if data > max(code, prose) else "knowledge" if prose >= code else "software"
    found["counts"] = {"code": code, "prose": prose, "data": data}
    return found


def adopt(project: Path, title: str | None = None, family: str | None = None) -> tuple[dict, list[str]]:
    project = Path(project)
    s = survey(project)
    over = {"commands": s["commands"], "types": s["types"], "stage": "plan"}
    gate_cmd = s["commands"].get("check_full") or s["commands"].get("check_fast") or ""
    over["gates"] = [{"id": "checks", "kind": "command", "command": gate_cmd}]
    old_handbook = len(c.read_text(project / "CLAUDE.md").encode())
    made = init(project, title or project.name, family or s["family"], over)
    s["old_handbook_bytes"] = old_handbook
    if old_handbook > OLD_HANDBOOK_LIMIT and "Slim the old handbook" not in c.read_text(project / "NEEDS_YOU.md"):
        with open(project / "NEEDS_YOU.md", "a", encoding="utf-8") as f:
            f.write(f"\n## Slim the old handbook (a decision, no clicks)\n\n- **What:** this project's `CLAUDE.md` is about {old_handbook // 4:,} tokens and is loaded on every request and by most helpers. "
                    "Most of it can move to `.brain/ext/handbook.md`, where it is read only when needed.\n"
                    "- **How:** reply \"slim the handbook\" and it will be moved, keeping only what must always be in view.\n"
                    "- **Meanwhile:** nothing was moved or deleted; the brain's rules apply where the two disagree.\n")
    return s, made


# ---------------------------------------------------------------- validate / migrate
REQUIRED_FILES = (".brain/project.json", ".brain/STATE.md", ".brain/requirements.jsonl", ".brain/PLAN.md",
                  ".brain/DECISIONS.md", "NEEDS_YOU.md", "STATUS.md", "CLAUDE.md")


def validate(project: Path, brain_root: Path | None = None) -> list[str]:
    project = Path(project)
    errs: list[str] = []
    m = c.read_json(project / ".brain" / "project.json", None)
    if not isinstance(m, dict):
        return [".brain/project.json is missing or not valid JSON"]
    ver = m.get("contract")
    if not isinstance(ver, int):
        return ["manifest: 'contract' must be an integer"]
    if ver > c.CONTRACT_VERSION:
        return [f"stale brain: project uses contract v{ver}, this brain knows v{c.CONTRACT_VERSION}; update the brain, nothing was written"]
    if ver < c.CONTRACT_VERSION:
        errs.append(f"project is on contract v{ver}; run: brain migrate")
    schema = load_schema(ver, brain_root)
    if not schema:
        errs.append(f"no schema file for contract v{ver}")
    else:
        errs += check_schema(m, schema)
    for rel in REQUIRED_FILES:
        if not (project / rel).is_file():
            errs.append(f"missing {rel}")
    stub = c.read_text(project / "CLAUDE.md")
    if BEGIN in stub and END in stub:
        block = stub[stub.index(BEGIN): stub.index(END) + len(END)]
        if len(block.encode()) > STUB_LIMIT:
            errs.append(f"CLAUDE.md pointer block is {len(block.encode())} bytes (limit {STUB_LIMIT})")
    elif (project / "CLAUDE.md").is_file():
        errs.append("CLAUDE.md has no brain pointer block")
    for g in m.get("gates", []) if isinstance(m.get("gates"), list) else []:
        if isinstance(g, dict) and g.get("kind") == "command" and "command" not in g:
            errs.append(f"gate {g.get('id')}: kind 'command' needs a command (may be empty until known)")
    from . import req
    try:
        req.load(project)
    except req.LedgerError as e:
        errs.append(str(e))
    if c.find_secrets(c.read_text(project / ".brain" / "project.json")):
        errs.append("manifest looks like it contains a secret; use the environment's secret settings instead")
    return errs


def _load_migration(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def migrate(project: Path, target: int = c.CONTRACT_VERSION, migrations_dir: Path | None = None) -> tuple[int, list[str]]:
    """Run the chain of migrations from the project's version to ``target``.
    Returns (exit code, messages). A project newer than the brain is refused
    without writing anything."""
    project = Path(project)
    mdir = Path(migrations_dir or c.BRAIN_ROOT / "contract" / "migrations")
    m = c.load_manifest(project)
    ver = m.get("contract")
    if not isinstance(ver, int):
        return 1, ["manifest has no integer 'contract'"]
    if ver > target:
        return 3, [f"stale brain: project is v{ver}, brain is v{target}; nothing written"]
    if ver == target:
        return 0, [f"already on contract v{target}"]
    msgs: list[str] = []
    while ver < target:
        script = mdir / f"{ver}_to_{ver + 1}.py"
        if not script.is_file():
            return 1, msgs + [f"no migration script {script.name}"]
        # Keep the manifest as it was before this step, so a bad migration can
        # be undone by copying one file back.
        backup = project / ".brain" / "log" / "backup" / f"project.v{ver}.json"
        if not backup.exists():
            c.write_text(backup, c.read_text(project / ".brain" / "project.json"))
        changes = _load_migration(script).migrate(project) or []
        m = c.load_manifest(project)
        m["contract"] = ver + 1
        c.write_json(project / ".brain" / "project.json", m)
        with open(project / ".brain" / "DECISIONS.md", "a", encoding="utf-8") as f:
            f.write(f"| - | {c.today()} | Contract migrated v{ver} to v{ver + 1} | brain update | done |\n")
        msgs += [f"v{ver} -> v{ver + 1}: " + (", ".join(changes) if changes else "no file changes")]
        ver += 1
    return 0, msgs


# ---------------------------------------------------------------- cli
def cmd_init(args) -> int:
    project = Path(args.path).resolve()
    if not project.is_dir():
        print(f"not a folder: {project}")
        return 1
    if project == c.BRAIN_ROOT.resolve():
        print("refusing to install a project contract inside the brain itself")
        return 1
    if not c.is_empty_repo(project) and not c.is_managed(project) and not args.force:
        print("this folder already has content: use `brain adopt` (it surveys first and never moves existing files)")
        return 1
    over = {}
    if args.release:
        over["release"] = {"rule": args.release}
    if args.language:
        over["languages"] = args.language
    made = init(project, args.title or project.name, args.family, over)
    errs = validate(project)
    print(f"contract v{c.CONTRACT_VERSION} in {project.name}: " + (f"created {len(made)} file(s)" if made else "already complete, nothing changed"))
    for e in errs:
        print(" -", e)
    return 1 if errs else 0


def cmd_adopt(args) -> int:
    project = Path(args.path).resolve()
    if not project.is_dir():
        print(f"not a folder: {project}")
        return 1
    if args.survey:
        s = survey(project)
        print(f"survey of {project.name} (nothing written): family {s['family']}; signals: {', '.join(s['signals']) or 'none'}")
        for k, v in s["commands"].items():
            print(f"  {k}: {v}")
        return 0
    s, made = adopt(project, args.title, args.family)
    print(f"adopted {project.name}: family {c.load_manifest(project).get('family')}; added {len(made)} contract file(s); existing files untouched")
    if s.get("old_handbook_bytes", 0) > OLD_HANDBOOK_LIMIT:
        print(f"  the existing CLAUDE.md is about {s['old_handbook_bytes'] // 4:,} tokens on every request: a 'Slim the old handbook' item was added to NEEDS_YOU.md")
    for k, v in s["commands"].items():
        print(f"  inferred {k}: {v}")
    print("  next: confirm the inferred commands with `brain gate --all`, then record what the project is for in .brain/PLAN.md")
    errs = validate(project)
    for e in errs:
        print(" -", e)
    return 1 if errs else 0


def cmd_validate(args) -> int:
    project = c.resolve_project(args.project)
    if project is None:
        print("no project found")
        return 1
    errs = validate(project)
    if errs:
        print(f"{project.name}: {len(errs)} problem(s)")
        for e in errs:
            print(" -", e)
        return 3 if errs[0].startswith("stale brain") else 1
    print(f"{project.name}: contract v{c.load_manifest(project).get('contract')} valid")
    return 0


def cmd_migrate(args) -> int:
    project = c.resolve_project(args.project)
    if project is None:
        print("no project found")
        return 1
    code, msgs = migrate(project)
    for m in msgs:
        print(m)
    return code


def register(sub) -> None:
    p = sub.add_parser("init", help="install the contract in an empty project folder")
    p.add_argument("path")
    p.add_argument("--family", choices=FAMILIES, default="software")
    p.add_argument("--title")
    p.add_argument("--release", choices=("none", "main-on-green", "pr"))
    p.add_argument("--language", action="append")
    p.add_argument("--force", action="store_true", help="allow a non-empty folder")
    p.set_defaults(func=cmd_init)
    p = sub.add_parser("adopt", help="add the contract to an existing codebase without touching its files")
    p.add_argument("path")
    p.add_argument("--family", choices=FAMILIES)
    p.add_argument("--title")
    p.add_argument("--survey", action="store_true", help="only report what was found; write nothing")
    p.set_defaults(func=cmd_adopt)
    p = sub.add_parser("validate", help="check a project's contract files")
    c.add_project_arg(p)
    p.set_defaults(func=cmd_validate)
    p = sub.add_parser("migrate", help="bring a project to the current contract version")
    c.add_project_arg(p)
    p.set_defaults(func=cmd_migrate)
