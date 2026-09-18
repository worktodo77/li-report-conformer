"""Hardening: the Word render harness caught 6 header cells rendering the wrong size that tablespec's
DIRECT-run-size check missed — their first paragraph used a non-Table-Header style (a paragraph style
overrides the Grid Table 4 firstRow size). tablespec now resolves the EFFECTIVE paragraph-style size so
that class of regression is caught in CI (no Word needed)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from conformer import tablespec   # noqa: E402


def test_effective_style_size_follows_basedon():
    styles = ('<w:styles>'
              '<w:style w:type="paragraph" w:styleId="TableData"><w:rPr><w:sz w:val="22"/></w:rPr></w:style>'
              '<w:style w:type="paragraph" w:styleId="TableHeader"><w:basedOn w:val="TableData"/>'
              '<w:rPr><w:sz w:val="20"/></w:rPr></w:style>'
              '<w:style w:type="paragraph" w:styleId="Sub"><w:basedOn w:val="TableData"/></w:style>'
              '</w:styles>')
    assert tablespec._effective_style_size(styles, 'TableHeader') == '20'
    assert tablespec._effective_style_size(styles, 'Sub') == '22'         # inherits Table Data
    assert tablespec._effective_style_size(styles, 'Missing') is None


_STYLES = ('<w:styles>'
           '<w:style w:type="paragraph" w:styleId="Heading4"><w:rPr><w:sz w:val="23"/></w:rPr></w:style>'
           '<w:style w:type="paragraph" w:styleId="TableHeader"><w:rPr><w:sz w:val="20"/></w:rPr></w:style>'
           '</w:styles>')


def _hdr_tbl(para_style):
    return ('<w:tbl><w:tblPr><w:tblStyle w:val="GridTable4"/><w:tblLook w:val="04A0" w:firstRow="1"/></w:tblPr>'
            '<w:tr><w:trPr><w:tblHeader/></w:trPr><w:tc><w:tcPr>'
            '<w:shd w:val="clear" w:color="auto" w:fill="B6DDE8"/></w:tcPr>'
            f'<w:p><w:pPr><w:pStyle w:val="{para_style}"/></w:pPr><w:r><w:t>H</w:t></w:r></w:p></w:tc></w:tr>'
            '<w:tr><w:tc><w:tcPr/><w:p><w:r><w:t>d</w:t></w:r></w:p></w:tc></w:tr></w:tbl>')


def _kinds(issues):
    return {i['kind'] for i in issues}


def test_header_style_size_flags_wrong_style():
    # header cell first paragraph is Heading4 (11.5pt) with NO direct run size -> renders wrong size
    assert 'header-style-size' in _kinds(tablespec.effective_table_issues(_hdr_tbl('Heading4'), styles_xml=_STYLES))


def test_header_style_size_not_flagged_for_table_header():
    # the house 10pt Table Header style -> no flag
    assert 'header-style-size' not in _kinds(tablespec.effective_table_issues(_hdr_tbl('TableHeader'), styles_xml=_STYLES))


def _hdr_tbl_empty(para_style):
    # a header cell whose first paragraph is EMPTY (no text) — an artifact, not a visible header
    return ('<w:tbl><w:tblPr><w:tblStyle w:val="GridTable4"/><w:tblLook w:val="04A0" w:firstRow="1"/></w:tblPr>'
            '<w:tr><w:trPr><w:tblHeader/></w:trPr><w:tc><w:tcPr>'
            '<w:shd w:val="clear" w:color="auto" w:fill="B6DDE8"/></w:tcPr>'
            f'<w:p><w:pPr><w:pStyle w:val="{para_style}"/></w:pPr></w:p></w:tc></w:tr>'
            '<w:tr><w:tc><w:tcPr/><w:p><w:r><w:t>d</w:t></w:r></w:p></w:tc></w:tr></w:tbl>')


def test_f5_visible_wrong_header_fails_empty_is_review():
    # GPT F5: a VISIBLE wrong-size header (cell has text) is a defect (fail); an EMPTY one is review only.
    visible = tablespec.effective_table_issues(_hdr_tbl('Heading4'), styles_xml=_STYLES)
    assert any(i['kind'] == 'header-style-size' and i['severity'] == 'fail' for i in visible)
    empty = tablespec.effective_table_issues(_hdr_tbl_empty('Heading4'), styles_xml=_STYLES)
    assert any(i['kind'] == 'header-style-size' and i['severity'] == 'review' for i in empty)
