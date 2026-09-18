"""Table header rows must render at the house 10pt bold (Grid Table 4). A paragraph style overrides the
table style's firstRow rPr, so header cells get a dedicated 10pt 'Table Header' paragraph style and their
conflicting direct run sizes are stripped. Regression also covers the header-marking bug: a <w:tr> that
carries attributes (w:rsidR) was missed by a bare-string replace, leaving the header unmarked and its
non-house fill uncorrected."""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from conformer.engine import Conformer   # noqa: E402


def test_table_header_style_constant_is_10pt_bold():
    s = Conformer.TABLE_HEADER_STYLE
    assert 'w:styleId="TableHeader"' in s
    assert '<w:sz w:val="20"/>' in s          # 10pt
    assert '<w:b/>' in s                       # bold


def test_ensure_table_header_style_imports_once():
    c = Conformer.__new__(Conformer)
    c.styles = '<w:styles></w:styles>'
    c.say = lambda *a, **k: None
    c._ensure_table_header_style()
    assert 'w:styleId="TableHeader"' in c.styles
    before = c.styles
    c._ensure_table_header_style()             # idempotent
    assert c.styles == before


HDR_CELL = ('<w:tc><w:tcPr><w:tcW w:w="2200" w:type="dxa"/>'
            '<w:shd w:val="clear" w:color="auto" w:fill="BDD6EE" w:themeFill="accent5" w:themeFillTint="66"/>'
            '</w:tcPr><w:p><w:pPr><w:pStyle w:val="TableData"/></w:pPr>'
            '<w:r><w:rPr><w:sz w:val="18"/><w:szCs w:val="18"/></w:rPr><w:t>Head</w:t></w:r></w:p></w:tc>')


def test_repair_header_swaps_style_strips_size_and_fixes_themefill():
    c = Conformer.__new__(Conformer)
    c._table_notes = []
    tbl = ('<w:tbl><w:tblPr><w:tblStyle w:val="GridTable4"/></w:tblPr>'
           '<w:tr w:rsidR="00AB12"><w:trPr><w:tblHeader/></w:trPr>' + HDR_CELL + '</w:tr>'
           '<w:tr><w:tc><w:tcPr/><w:p><w:r><w:t>d</w:t></w:r></w:p></w:tc></w:tr></w:tbl>')
    out, rep, _ = c._repair_stray_header_formatting(tbl, 'loc')
    hdr = re.search(r'<w:tr\b.*?</w:tr>', out, re.S).group(0)
    assert '<w:pStyle w:val="TableHeader"/>' in hdr            # 10pt bold header style
    assert '<w:pStyle w:val="TableData"/>' not in hdr
    assert '<w:sz w:val="18"/>' not in hdr                     # conflicting direct size stripped
    assert 'w:fill="B6DDE8"' in hdr and 'themeFill' not in hdr  # theme-independent concrete teal
    assert out.count('<w:pStyle w:val="TableHeader"/>') == 1    # only the header row


def _clean_conformer(items):
    c = Conformer.__new__(Conformer)
    c.items = items
    c.b0 = 0
    c.styles = '<w:styles></w:styles>'
    c.say = lambda *a, **k: None
    return c


def test_header_marking_handles_attributed_tr_row():
    # a first row carrying attributes (w:rsidR) must STILL get <w:tblHeader/>; the old bare '<w:tr>'
    # replace missed it -> header unmarked, fill/size never conformed.
    tbl = ('<w:tbl><w:tblPr><w:tblStyle w:val="TableGrid"/><w:tblLook w:val="04A0"/></w:tblPr>'
           '<w:tblGrid><w:gridCol w:w="5000"/></w:tblGrid>'
           '<w:tr w:rsidR="00AB12"><w:tc><w:tcPr><w:tcW w:w="5000" w:type="dxa"/></w:tcPr>'
           '<w:p><w:pPr><w:pStyle w:val="TableData"/></w:pPr>'
           '<w:r><w:rPr><w:sz w:val="22"/></w:rPr><w:t>H</w:t></w:r></w:p></w:tc></w:tr>'
           '<w:tr><w:tc><w:tcPr><w:tcW w:w="5000" w:type="dxa"/></w:tcPr>'
           '<w:p><w:r><w:t>d</w:t></w:r></w:p></w:tc></w:tr></w:tbl>')
    c = _clean_conformer([tbl])
    c.fix_tables()
    hdr = re.search(r'<w:tr\b.*?</w:tr>', c.items[0], re.S).group(0)
    assert '<w:tblHeader/>' in hdr                             # attributed row still marked
    assert '<w:pStyle w:val="TableHeader"/>' in hdr           # header uses the 10pt style
    assert 'w:styleId="TableHeader"' in c.styles
