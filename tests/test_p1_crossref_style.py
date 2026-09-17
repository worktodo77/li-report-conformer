"""P1 (§9): every cross-reference (REF) field's display runs carry the 'Cross Reference' character style —
applied to EXISTING fields, not only ones built from literal text. Broken references are flagged."""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from conformer.engine import Conformer   # noqa: E402


def _c():
    c = Conformer.__new__(Conformer)
    c.disposition = 'clean'
    c.audit = []
    c._log = []
    c.say = lambda kind, i, msg, cat=None: c._log.append((kind, i, msg))
    return c


def _ref_field(result, rpr=''):
    return ('<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
            '<w:r><w:instrText xml:space="preserve"> REF _Ref123 \\r \\h </w:instrText></w:r>'
            '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
            f'<w:r>{rpr}<w:t>{result}</w:t></w:r>'
            '<w:r><w:fldChar w:fldCharType="end"/></w:r>')


def test_ref_display_run_gets_crossreference_style():
    c = _c()
    x = '<w:p>' + _ref_field('3.4.2') + '</w:p>'
    nx, styled, broken = c._apply_crossref_style(x)
    assert styled == 1 and '<w:rStyle w:val="CrossReference"/>' in nx
    assert '3.4.2' in nx                       # display text unchanged


def test_run_with_existing_rpr_keeps_it_and_prepends_style():
    c = _c()
    x = '<w:p>' + _ref_field('3.4.2', rpr='<w:rPr><w:b/></w:rPr>') + '</w:p>'
    nx, styled, _ = c._apply_crossref_style(x)
    assert '<w:rPr><w:rStyle w:val="CrossReference"/><w:b/></w:rPr>' in nx


def test_pageref_and_styleref_are_not_touched():
    c = _c()
    pageref = ('<w:p><w:r><w:fldChar w:fldCharType="begin"/></w:r>'
               '<w:r><w:instrText xml:space="preserve"> PAGEREF _Ref9 \\h </w:instrText></w:r>'
               '<w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>5</w:t></w:r>'
               '<w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>')
    nx, styled, _ = c._apply_crossref_style(pageref)
    assert styled == 0 and 'CrossReference' not in nx


def test_already_styled_run_not_double_styled():
    c = _c()
    x = '<w:p>' + _ref_field('3.4.2', rpr='<w:rPr><w:rStyle w:val="CrossReference"/></w:rPr>') + '</w:p>'
    nx, styled, _ = c._apply_crossref_style(x)
    assert styled == 0 and nx.count('CrossReference') == 1


def test_broken_reference_detected():
    c = _c()
    x = '<w:p>' + _ref_field('Error! Reference source not found.') + '</w:p>'
    nx, styled, broken = c._apply_crossref_style(x)
    assert broken == 1
