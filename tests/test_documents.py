"""The .docx writer, the read-back, and the hidden-character scan (D-31)."""
import xml.etree.ElementTree as ET
import zipfile

import pytest

from jobforge.docx import BULLET_PREFIX, Block, Run, extract_text, write_docx
from jobforge.scan import clean, find_hidden, find_mixed_script

pytestmark = pytest.mark.critical


def test_round_trip_keeps_text_and_order(tmp_path):
    blocks = [Block("title", [Run("John Smith", bold=True)], align="center"),
              Block("heading", [Run("Experience")]),
              Block("para", [Run("Supervisor", bold=True), Run(" | Acme")]),
              Block("bullet", [Run("Cut overtime 25%")]),
              Block("para", [Run("Site: "), Run("example.com/x", href="https://example.com/x")])]
    path = write_docx(blocks, tmp_path / "out" / "d.docx")
    text = extract_text(path)
    assert text.splitlines() == ["John Smith", "Experience", "Supervisor | Acme",
                                 BULLET_PREFIX + "Cut overtime 25%", "Site: example.com/x"]


def test_special_characters_are_escaped_and_restored(tmp_path):
    s = 'R&D <team> "quotes" & 5 < 6'
    path = write_docx([Block("para", [Run(s)])], tmp_path / "d.docx")
    assert extract_text(path) == s


def test_every_part_is_well_formed_xml(tmp_path):
    path = write_docx([Block("para", [Run("a & b", href="https://e.com/?a=1&b=2")])],
                      tmp_path / "d.docx")
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        assert {"[Content_Types].xml", "_rels/.rels", "word/document.xml",
                "word/_rels/document.xml.rels", "word/styles.xml"} <= names
        for name in names:
            ET.fromstring(z.read(name))
        rels = z.read("word/_rels/document.xml.rels").decode()
        assert 'Target="https://e.com/?a=1&amp;b=2"' in rels


def test_no_tables_frames_or_headers(tmp_path):
    path = write_docx([Block("para", [Run("x")])], tmp_path / "d.docx")
    with zipfile.ZipFile(path) as z:
        doc = z.read("word/document.xml").decode()
    for tag in ("<w:tbl", "<w:txbxContent", "<w:headerReference", "<w:footerReference",
                "<w:drawing", "<w:cols "):
        assert tag not in doc


@pytest.mark.parametrize("ch,name", [
    ("​", "zero-width space"), ("‌", "zero-width non-joiner"),
    ("‍", "zero-width joiner"), ("﻿", "zero-width no-break space"),
    ("­", "soft hyphen"), (" ", "non-breaking space"),
    (" ", "narrow non-breaking space"), ("⁠", "word joiner"),
    ("‮", "text direction control"), ("ﬁ", "ligature glyph"),
    ("\x07", "control character"),
    # #49: any other invisible formatting character (Unicode Cf), e.g. the
    # invisible separator and the Arabic letter mark.
    ("\u2063", "invisible formatting character"), ("\u061c", "invisible formatting character"),
    ("", "private-use character"),
    ("\ud800", "lone surrogate"),  # F8 (#28): cannot be written to a file
])
def test_hidden_characters_are_found(ch, name):
    found = find_hidden(f"Manage{ch}ment")
    assert len(found) == 1 and found[0].name.startswith(name)
    assert "U+" in str(found[0])


@pytest.mark.parametrize("text,words", [
    ("used S\u0410P daily", ["S\u0410P"]),               # Latin + Cyrillic
    ("in \u0395xcel and Gr\u043ecery", ["\u0395xcel", "Gr\u043ecery"]),
    ("staff from \u041a\u0438\u0457\u0432", []),         # all Cyrillic is a real word
    ("\u03bc-law codec", []),                            # all Greek, then Latin
    ("plain café text", []),
])
def test_mixed_script_words(text, words):
    # Issue #1: a word mixing Latin with Cyrillic or Greek looks right and
    # matches nothing.
    assert [m.word for m in find_mixed_script(text)] == words


def test_mixed_script_names_the_odd_letters():
    (m,) = find_mixed_script("S\u0410P")
    assert "Cyrillic" in str(m) and "U+0410" in str(m)


def test_ordinary_text_is_clean():
    assert find_hidden("Plain text, 25% & • bullets\ttabs\nnew lines. café —") == []


def test_clean_fixes_posting_text():
    assert clean("a b​cﬁne­") == "a bcfine"


def test_italic_run_is_written_and_reads_back(tmp_path):
    # #49: the writer's italic run property.
    path = write_docx([Block("para", [Run("Plain "), Run("slanted", italic=True)])],
                      tmp_path / "i.docx")
    with zipfile.ZipFile(path) as z:
        assert "<w:i/>" in z.read("word/document.xml").decode()
    assert extract_text(path) == "Plain slanted"


def test_clean_drops_a_lone_surrogate():
    assert clean("Ware\ud800house") == "Warehouse"
