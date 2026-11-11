#!/usr/bin/env python3
"""Markdown to an ATS-friendly Word file, standard library only.

Standalone so `brain jobs init` can copy it into a job-search project as
`tools/mddocx.py`: `python3 tools/mddocx.py documents/resume.md out/resume.docx`.

Why this shape: applicant-tracking systems parse single-column documents with
real text, standard fonts and plain section headings best; tables, text
boxes, columns, headers/footers and images are where parsers lose content.
So the writer supports only what a resume or letter needs:

  # Name                 -> title line (large, bold)
  ## Section             -> section heading with a rule under it
  ### Role, Company      -> bold line; text after " | " goes right-aligned (dates)
  - bullet               -> bullet with a hanging indent
  plain line             -> paragraph (a blank line separates paragraphs)
  **bold**, *italic*, [text](url) inline; --- page break
"""
from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

FONT = "Calibri"
SIZE = 21  # half-points: 10.5 pt
MARGIN = 864  # twentieths of a point: 0.6 inch
WIDTH = 12240 - 2 * MARGIN  # usable width on US Letter

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
</Types>"""
RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
</Relationships>"""
DOC_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""
STYLES = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="{FONT}" w:hAnsi="{FONT}" w:cs="{FONT}"/><w:sz w:val="{SIZE}"/><w:szCs w:val="{SIZE}"/><w:lang w:val="en-US"/></w:rPr></w:rPrDefault>
<w:pPrDefault><w:pPr><w:spacing w:after="60" w:line="252" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:pPr><w:jc w:val="center"/><w:spacing w:after="40"/></w:pPr><w:rPr><w:b/><w:sz w:val="36"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:pPr><w:keepNext/><w:spacing w:before="200" w:after="60"/><w:pBdr><w:bottom w:val="single" w:sz="6" w:space="1" w:color="444444"/></w:pBdr><w:outlineLvl w:val="0"/></w:pPr><w:rPr><w:b/><w:caps/><w:sz w:val="23"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:pPr><w:keepNext/><w:spacing w:before="100" w:after="20"/><w:tabs><w:tab w:val="right" w:pos="{WIDTH}"/></w:tabs><w:outlineLvl w:val="1"/></w:pPr><w:rPr><w:b/></w:rPr></w:style>
</w:styles>"""

INLINE = re.compile(r"(\*\*[^*]+\*\*|\*[^*]+\*|\[[^\]]+\]\([^)]+\))")  # bold, italic, link; other brackets stay text


def runs(text: str, bold: bool = False) -> str:
    out = []
    for part in INLINE.split(text):
        if not part:
            continue
        b, i, t = bold, False, part
        if part.startswith("**") and part.endswith("**"):
            b, t = True, part[2:-2]
        elif part.startswith("*") and part.endswith("*") and len(part) > 2:
            i, t = True, part[1:-1]
        elif part.startswith("[") and re.match(r"\[([^\]]+)\]\(([^)]+)\)", part):
            m = re.match(r"\[([^\]]+)\]\(([^)]+)\)", part)
            label, url = m.group(1), m.group(2)
            t = label if label == url or url.startswith("mailto:") else f"{label} ({url})"
        rpr = ("<w:b/>" if b else "") + ("<w:i/>" if i else "")
        out.append(f'<w:r>{"<w:rPr>" + rpr + "</w:rPr>" if rpr else ""}<w:t xml:space="preserve">{escape(t)}</w:t></w:r>')
    return "".join(out)


def para(inner: str, style: str = "", ppr: str = "") -> str:
    p = (f'<w:pStyle w:val="{style}"/>' if style else "") + ppr
    return f"<w:p>{'<w:pPr>' + p + '</w:pPr>' if p else ''}{inner}</w:p>"


def body_xml(md: str) -> str:
    parts, buf = [], []

    def flush():
        if buf:
            parts.append(para(runs(" ".join(buf))))
            buf.clear()

    md = re.sub(r"<!--.*?-->", "", md, flags=re.S)  # notes to the writer, one line or many
    for raw in md.splitlines():
        line = raw.rstrip()
        s = line.strip()
        if s.startswith("<!--") or s.startswith("> "):
            continue  # notes to the writer stay out of the document
        if not s:
            flush()
            continue
        if s == "---":
            flush()
            parts.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')
        elif s.startswith("### "):
            flush()
            left, _, right = s[4:].partition(" | ")
            inner = runs(left, bold=True) + (f'<w:r><w:tab/></w:r>{runs(right, bold=False)}' if right else "")
            parts.append(para(inner, "Heading2"))
        elif s.startswith("## "):
            flush()
            parts.append(para(runs(s[3:]), "Heading1"))
        elif s.startswith("# "):
            flush()
            parts.append(para(runs(s[2:]), "Title"))
        elif re.match(r"^[-*•] ", s):
            flush()
            parts.append(para('<w:r><w:t xml:space="preserve">•</w:t></w:r><w:r><w:tab/></w:r>' + runs(s[2:].strip()),
                              ppr='<w:tabs><w:tab w:val="left" w:pos="270"/></w:tabs><w:ind w:left="270" w:hanging="270"/><w:spacing w:after="30"/>'))
        elif s.startswith("^"):  # centered line (contact details under the name)
            flush()
            parts.append(para(runs(s[1:].strip()), ppr='<w:jc w:val="center"/>'))
        else:
            buf.append(s)
    flush()
    sect = f'<w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="{MARGIN}" w:right="{MARGIN}" w:bottom="{MARGIN}" w:left="{MARGIN}" w:header="0" w:footer="0" w:gutter="0"/></w:sectPr>'
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
            + "".join(parts) + sect + "</w:body></w:document>")


def _entry(name: str) -> zipfile.ZipInfo:
    """A zip entry with a fixed date, so the same Markdown always builds the
    same bytes: an unchanged document never shows up as a change in git."""
    info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    return info


def convert(md: str, out: Path, title: str = "") -> Path:
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    core = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><cp:coreProperties '
            'xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>' + escape(title) + "</dc:title></cp:coreProperties>")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(_entry("[Content_Types].xml"), CONTENT_TYPES)
        z.writestr(_entry("_rels/.rels"), RELS)
        z.writestr(_entry("word/_rels/document.xml.rels"), DOC_RELS)
        z.writestr(_entry("word/styles.xml"), STYLES)
        z.writestr(_entry("word/document.xml"), body_xml(md))
        z.writestr(_entry("docProps/core.xml"), core)
    return out


def main(argv=None) -> int:
    a = list(sys.argv[1:] if argv is None else argv)
    if len(a) != 2:
        print("usage: mddocx.py <input.md> <output.docx>")
        return 2
    src = Path(a[0])
    md = src.read_text(encoding="utf-8")
    title = next((l[2:].strip() for l in md.splitlines() if l.startswith("# ")), src.stem)
    out = convert(md, Path(a[1]), title)
    words = len(re.findall(r"\w+", re.sub(r"<!--.*?-->", "", md, flags=re.S)))
    print(f"wrote {out} ({out.stat().st_size} bytes, about {words} words)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
