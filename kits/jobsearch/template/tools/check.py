#!/usr/bin/env python3
"""The project's gate: the profile is usable, the tracker and company lists
parse, every document builds into a Word file in out/, and no document still
holds template placeholders. Exit 0 only when all of that holds."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import mddocx  # noqa: E402

PLACEHOLDERS = re.compile(r"\b(Full Name|Company|Job Title|Month Year|phone · email)\b")
TO_FILL = re.compile(r"\[(?:phone|email|linkedin[^\]]*|add [^\]]*|number[^\]]*)\]", re.I)
errors, todo = [], []

prof_path = ROOT / "profile.json"
if not prof_path.is_file():
    errors.append("profile.json is missing (copy profile.example.json)")
else:
    try:
        prof = json.loads(prof_path.read_text(encoding="utf-8"))
        if not prof.get("targets") or not all(t.get("keywords") for t in prof["targets"]):
            errors.append("profile.json: every target needs keywords")
        if not prof.get("locations"):
            errors.append("profile.json: locations is empty")
    except ValueError as e:
        errors.append(f"profile.json is not valid JSON: {e}")

for rel in ("tracker.jsonl", "data/companies.jsonl", "data/boards.jsonl", "data/matches.jsonl"):
    p = ROOT / rel
    if p.is_file():
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if line.strip():
                try:
                    json.loads(line)
                except ValueError:
                    errors.append(f"{rel}:{i} is not valid JSON")

built = 0
for md in sorted((ROOT / "documents").glob("*.md")):
    if md.name in ("outreach.md",):
        continue
    text = md.read_text(encoding="utf-8")
    template = md.name in ("resume.md", "cover-letter.md") and PLACEHOLDERS.search(re.sub(r"<!--.*?-->", "", text, flags=re.S))
    if PLACEHOLDERS.search(re.sub(r"<!--.*?-->", "", text, flags=re.S)) and not template:
        errors.append(f"documents/{md.name} still has template placeholders")
    if not template:
        gaps = TO_FILL.findall(re.sub(r"<!--.*?-->", "", text, flags=re.S))
        if gaps:
            todo.append(f"documents/{md.name}: {len(gaps)} blank(s) for you to fill, e.g. {gaps[0]}")
        mddocx.convert(text, ROOT / "out" / (md.stem + ".docx"), md.stem)
        built += 1

print(f"check: {built} document(s) built into out/; {len(errors)} problem(s)")
for e in errors:
    print(" -", e)
for t in todo:
    print(" - to fill (not an error):", t)
sys.exit(1 if errors else 0)
