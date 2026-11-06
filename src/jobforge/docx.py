"""Minimal, dependency-free .docx writer and reader.

A .docx is a zip of XML parts, so `zipfile` and string templates are enough,
and the runtime stays stdlib only (D-13). The output is deliberately plain:
no tables, text boxes, columns, headers, footers, or images. ATS parsers
handle headings, paragraphs, and bullet lines in reading order, and very
little else reliably.

`extract_text` reads a .docx back to plain text. That is roughly what an ATS
does, so `apply` round-trips every document through it and checks the result.
"""
from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Run:
    text: str
    bold: bool = False
    italic: bool = False
    href: str | None = None


@dataclass
class Block:
    kind: str  # "title" | "heading" | "para" | "bullet"
    runs: list[Run] = field(default_factory=list)
    align: str = "left"  # "left" | "center"

    def text(self) -> str:
        return "".join(r.text for r in self.runs)


def _esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>"""

_ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""

# Real heading styles, not just bold text: parsers use them to find section
# boundaries. Normal carries an explicit spacing rule because Word's fallback
# (8pt after every paragraph, 1.08 lines) pushes a one-page resume onto two.
_STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:docDefaults><w:rPrDefault><w:rPr>
<w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:cs="Calibri"/><w:sz w:val="21"/>
</w:rPr></w:rPrDefault></w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/>
<w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr></w:style>
<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/>
<w:basedOn w:val="Normal"/><w:pPr><w:jc w:val="center"/><w:spacing w:after="40"/></w:pPr>
<w:rPr><w:b/><w:sz w:val="32"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/>
<w:basedOn w:val="Normal"/><w:pPr><w:outlineLvl w:val="1"/><w:spacing w:before="140" w:after="40"/></w:pPr>
<w:rPr><w:b/><w:sz w:val="23"/></w:rPr></w:style>
<w:style w:type="character" w:styleId="Hyperlink"><w:name w:val="Hyperlink"/>
<w:rPr><w:color w:val="0B5FFF"/><w:u w:val="single"/></w:rPr></w:style>
</w:styles>"""

BULLET_PREFIX = "• "


def _run_xml(run: Run) -> str:
    props = []
    if run.bold:
        props.append("<w:b/>")
    if run.italic:
        props.append("<w:i/>")
    if run.href:
        props.append('<w:rStyle w:val="Hyperlink"/>')
    rpr = f"<w:rPr>{''.join(props)}</w:rPr>" if props else ""
    return f'<w:r>{rpr}<w:t xml:space="preserve">{_esc(run.text)}</w:t></w:r>'


def _para_xml(block: Block, rels: list[tuple[str, str]]) -> str:
    style = {"heading": '<w:pStyle w:val="Heading2"/>',
             "title": '<w:pStyle w:val="Title"/>'}.get(block.kind, "")
    ind = '<w:ind w:left="360" w:hanging="180"/>' if block.kind == "bullet" else ""
    align = '<w:jc w:val="center"/>' if block.align == "center" else ""
    ppr = f"<w:pPr>{style}{align}{ind}</w:pPr>" if (style or ind or align) else ""

    body = []
    if block.kind == "bullet":
        body.append(_run_xml(Run(BULLET_PREFIX)))
    for run in block.runs:
        if run.href:
            rid = f"rIdL{len(rels) + 1}"
            rels.append((rid, run.href))
            body.append(f'<w:hyperlink r:id="{rid}">{_run_xml(run)}</w:hyperlink>')
        else:
            body.append(_run_xml(run))
    return f"<w:p>{ppr}{''.join(body)}</w:p>"


def write_docx(blocks: list[Block], path: Path) -> Path:
    """Emit a .docx at `path`. Overwrites."""
    rels: list[tuple[str, str]] = []
    paras = "".join(_para_xml(b, rels) for b in blocks)
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document '
        'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f"<w:body>{paras}"
        '<w:sectPr><w:pgSz w:w="12240" w:h="15840"/>'
        '<w:pgMar w:top="720" w:right="720" w:bottom="720" w:left="720"/></w:sectPr>'
        "</w:body></w:document>"
    )
    rel_xml = "".join(
        f'<Relationship Id="{rid}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" '
        f'Target="{_esc(url)}" TargetMode="External"/>'
        for rid, url in rels
    )
    doc_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rIdStyles" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
        'Target="styles.xml"/>'
        f"{rel_xml}</Relationships>"
    )
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", _CONTENT_TYPES)
        z.writestr("_rels/.rels", _ROOT_RELS)
        z.writestr("word/document.xml", document)
        z.writestr("word/_rels/document.xml.rels", doc_rels)
        z.writestr("word/styles.xml", _STYLES)
    return path


def extract_text(path: Path) -> str:
    """Read a .docx back to plain text, one paragraph per line."""
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    xml = re.sub(r"</w:p>", "\n", xml)
    xml = re.sub(r"<[^>]+>", "", xml)
    # Unescape after stripping tags, so an escaped &lt; in the text cannot be
    # mistaken for the start of a tag.
    xml = (xml.replace("&lt;", "<").replace("&gt;", ">")
              .replace("&quot;", '"').replace("&amp;", "&"))
    return re.sub(r"\n{3,}", "\n\n", xml).strip()
