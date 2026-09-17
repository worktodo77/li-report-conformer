"""P0-1: the house table style is Grid Table 4 / "LI Table" — teal header, black bold text, black grid.
These are the RED-first counterexamples for the navy->teal realignment; the OLD navy/white/grey engine
would fail them."""
import re
import zipfile
import pytest
from conformer import tablespec

NS = tablespec._NSDECLS


def _tbl(header_shd, header_run='', body_run='<w:r><w:t>x</w:t></w:r>', style='GridTable4',
         tblB='', tcB=''):
    """A minimal 2-row table: header row + one body row."""
    return (
        f'<w:tbl><w:tblPr><w:tblStyle w:val="{style}"/>{tblB}'
        '<w:tblLook w:val="04A0" w:firstRow="1"/></w:tblPr>'
        f'<w:tr><w:trPr><w:cantSplit/><w:tblHeader/></w:trPr>'
        f'<w:tc><w:tcPr>{tcB}{header_shd}</w:tcPr><w:p><w:pPr><w:jc w:val="center"/></w:pPr>{header_run}</w:p></w:tc></w:tr>'
        f'<w:tr><w:tc><w:tcPr/><w:p><w:pPr><w:jc w:val="center"/></w:pPr>{body_run}</w:p></w:tc></w:tr>'
        '</w:tbl>')


TEAL = '<w:shd w:val="clear" w:color="auto" w:fill="B6DDE8" w:themeFill="accent5" w:themeFillTint="66"/>'
TEAL_THEME_ONLY = '<w:shd w:val="clear" w:color="auto" w:themeFill="accent5" w:themeFillTint="66"/>'
NAVY = '<w:shd w:val="clear" w:color="auto" w:fill="054F8A"/>'


def _kinds(issues):
    return {i['kind'] for i in issues}


def test_teal_header_black_bold_grid_is_conformant():
    # header inherits the conditional (no direct run colour/size) -> conformant
    assert tablespec.table_conformant(_tbl(TEAL))


def test_navy_header_is_now_NONconformant():
    # the OLD engine output (navy fill) must FAIL under the teal spec
    issues = tablespec.effective_table_issues(_tbl(NAVY))
    assert 'header-fill' in _kinds(issues)
    assert not tablespec.table_conformant(_tbl(NAVY))


def test_white_header_text_is_now_wrong():
    white = '<w:r><w:rPr><w:color w:val="FFFFFF"/></w:rPr><w:t>H</w:t></w:r>'
    issues = tablespec.effective_table_issues(_tbl(TEAL, header_run=white))
    assert 'header-text' in _kinds(issues)


def test_black_header_text_is_fine():
    black = '<w:r><w:rPr><w:color w:val="auto"/></w:rPr><w:t>H</w:t></w:r>'
    issues = tablespec.effective_table_issues(_tbl(TEAL, header_run=black))
    assert 'header-text' not in _kinds(issues)


def test_theme_only_accent5_fill_is_house_not_unresolved():
    # a header carried purely as themeFill accent5 IS the house teal -> resolved, not unresolved
    issues = tablespec.effective_table_issues(_tbl(TEAL_THEME_ONLY))
    assert 'header-fill' not in _kinds(issues)
    assert 'header-fill-theme' not in _kinds(issues)


def test_wrong_style_name_fails():
    issues = tablespec.effective_table_issues(_tbl(TEAL, style='LITable'))
    assert 'style' in _kinds(issues)


def test_header_run_size_expects_10pt_not_11pt():
    # a header run at 11pt (sz 22) conflicts with the house header 10pt (sz 20)
    r22 = '<w:r><w:rPr><w:sz w:val="22"/></w:rPr><w:t>H</w:t></w:r>'
    issues = tablespec.effective_table_issues(_tbl(TEAL, header_run=r22))
    assert 'font-size' in _kinds(issues)
    r20 = '<w:r><w:rPr><w:sz w:val="20"/></w:rPr><w:t>H</w:t></w:r>'
    assert 'font-size' not in _kinds(tablespec.effective_table_issues(_tbl(TEAL, header_run=r20)))


def test_bundled_template_defines_gridtable4_correctly():
    import pathlib
    tp = pathlib.Path(__file__).resolve().parents[1] / 'src' / 'conformer' / 'assets' / 'template.dotx'
    styles = zipfile.ZipFile(tp).read('word/styles.xml').decode('utf-8')
    assert tablespec._style_defines_house_table(styles) == []


def test_grid_color_auto_black_not_grey():
    # a grey 808080 grid (the OLD spec) is no longer the house grid; black/auto is
    grey = '<w:tblBorders>' + ''.join(
        f'<w:{s} w:val="single" w:sz="4" w:color="808080"/>' for s in tablespec._GRID_SIDES) + '</w:tblBorders>'
    issues = tablespec.effective_table_issues(_tbl(TEAL, tblB=grey))
    assert 'grid-overridden' in _kinds(issues)
