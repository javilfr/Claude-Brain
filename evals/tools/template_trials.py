#!/usr/bin/env python3
"""Prepare and score a paired template evaluation (ticket CB-203).

prepare <workdir>  one clean folder per task and arm (plainA, tpl, plainB) for
                   the dev tasks, a brief for each through `brain hr hire`
                   (`--template plain` for the plain arms), and
                   <workdir>/trials.json listing contract, brief and folder.
score <workdir>    grade every folder with `brain eval grade`, read each
                   helper's tokens from this session's transcripts, write the
                   results back to trials.json and append them to
                   evals/runs/<run>.jsonl through `brain eval record`.

Run every helper on the builder agent with the same model and effort, arms
interleaved in time, and delegate the whole batch to one coordinator agent so
the lead receives one table instead of 24 replies.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

BRAIN = Path(__file__).resolve().parents[2]
B = ["python3", str(BRAIN / "bin" / "brain")]
FAMILIES = {"software", "data", "knowledge", "language", "operations"}
ARMS = ("plainA", "tpl", "plainB")


def dev_tasks() -> list[dict]:
    return [t for t in (json.loads(p.read_text()) for p in sorted((BRAIN / "evals" / "tasks").glob("*.json")))
            if t.get("split") == "dev"]


def prepare(work: Path) -> None:
    rows = []
    for t in dev_tasks():
        for arm in ARMS:
            d = work / t["id"] / arm
            d.mkdir(parents=True, exist_ok=True)
            for f in t.get("setup", []):
                p = d / f["path"]
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(f["content"])
            cmd = B + ["hr", "hire", t["prompt"], "--why", "Evaluation trial; the result is graded automatically",
                       "--workdir", str(d), "--check", f"python3 {BRAIN}/bin/brain eval grade {t['id']} {d}", "--force"]
            if t.get("family") in FAMILIES:
                cmd += ["--family", t["family"]]
            if arm != "tpl":
                cmd += ["--template", "plain"]
            out = subprocess.run(cmd, capture_output=True, text=True, cwd=BRAIN).stdout
            grab = lambda pat: (re.search(pat, out) or [None, None])[1]  # noqa: E731
            rows.append({"task": t["id"], "arm": arm, "dir": str(d), "brief": grab(r"brief: (\S+)"),
                         "template": grab(r"template (\S+)"), "contract": grab(r"hire (h-\S+):")})
    (work / "trials.json").write_text(json.dumps(rows, indent=1))
    for i, r in enumerate(rows):
        print(i, r["task"], r["arm"], r["template"], r["contract"], r["brief"])


def score(work: Path, run: str) -> None:
    rows = json.loads((work / "trials.json").read_text())
    sid = subprocess.run(B[:1] + ["-c", "import os;print(os.environ.get('CLAUDE_CODE_SESSION_ID',''))"],
                         capture_output=True, text=True).stdout.strip()
    subs = list((Path.home() / ".claude" / "projects").glob(f"*/{sid}/subagents/agent-*.jsonl")) if sid else []
    usage = {}
    for f in subs:
        first, tok = None, 0
        for line in f.open():
            d = json.loads(line)
            m = d.get("message") or {}
            if first is None and d.get("type") == "user":
                first = str(m.get("content"))
            if d.get("type") == "assistant":
                u = m.get("usage") or {}
                tok += sum(u.get(k) or 0 for k in ("input_tokens", "cache_creation_input_tokens",
                                                   "cache_read_input_tokens", "output_tokens"))
        for r in rows:
            if r["contract"] and f"(contract {r['contract']})" in (first or ""):
                usage[r["contract"]] = tok
    out = BRAIN / "evals" / "runs" / f"{run}.jsonl"
    for r in rows:
        if r["contract"] not in usage:
            continue
        g = subprocess.run(B + ["eval", "grade", r["task"], r["dir"]], capture_output=True, text=True)
        r["passed"], r["tokens"] = int(g.returncode == 0), usage[r["contract"]]
        subprocess.run(B + ["eval", "record", str(out), "--task", r["task"], "--arm", r["arm"],
                            "--passed", str(r["passed"]), "--tokens", str(r["tokens"])], capture_output=True)
        print(r["task"], r["arm"], r["template"], r["passed"], r["tokens"])
    (work / "trials.json").write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in ("prepare", "score"):
        sys.exit(__doc__)
    work = Path(sys.argv[2]).resolve()
    prepare(work) if sys.argv[1] == "prepare" else score(work, sys.argv[3] if len(sys.argv) > 3 else "template-vs-plain")
