"""A table whose BODY font is deliberately smaller (8-10.5pt, to fit dense data) is KEPT by default; one
class-level judgment call lets the reviewer choose to normalize all such tables to the house 11pt. Header
row (10pt Table Header) is never touched."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from conformer.engine import Conformer   # noqa: E402


def _tbl(header_sz='20', body_sz='18'):
    hdr = ('<w:tr><w:trPr><w:tblHeader/></w:trPr><w:tc><w:tcPr/><w:p><w:pPr>'
           '<w:pStyle w:val="TableHeader"/></w:pPr><w:r><w:rPr>'
           f'<w:sz w:val="{header_sz}"/></w:rPr><w:t>H</w:t></w:r></w:p></w:tc></w:tr>')
    body = ('<w:tr><w:tc><w:tcPr/><w:p><w:pPr><w:pStyle w:val="TableData"/></w:pPr>'
            f'<w:r><w:rPr><w:sz w:val="{body_sz}"/></w:rPr><w:t>d</w:t></w:r></w:p></w:tc></w:tr>')
    return f'<w:tbl><w:tblPr><w:tblStyle w:val="GridTable4"/></w:tblPr>{hdr}{body}</w:tbl>'


def test_detect_small_body():
    c = Conformer.__new__(Conformer)
    assert c._table_body_is_small(_tbl(body_sz='18')) is True    # body 9pt
    assert c._table_body_is_small(_tbl(body_sz='22')) is False   # body 11pt is not "small"


def test_normalize_strips_body_size_keeps_header():
    c = Conformer.__new__(Conformer)
    c.items = [_tbl('20', '18')]
    c.b0 = 0
    c._normalize_table_body_to_11pt(0)
    x = c.items[0]
    assert '<w:sz w:val="20"/>' in x        # header (10pt) untouched
    assert '<w:sz w:val="18"/>' not in x     # body direct size stripped -> inherits Table Data 11pt


def _pass_conformer(items):
    c = Conformer.__new__(Conformer)
    c.items = items
    c.b0 = 0
    c.decisions = None
    c.pending_judgments = []
    c._jcall_counter = 0
    c.log = []
    c.judgment = []
    c.exceptions = []
    c.verify_preservation = lambda: (True, None)
    c._snapshot = lambda: list(c.items)
    c._restore = lambda s: None
    return c


def test_offer_keeps_by_default():
    c = _pass_conformer([_tbl('20', '18')])
    c._offer_table_body_normalization()
    assert len([j for j in c.pending_judgments if j.kind == 'table-body-size']) == 1
    assert '<w:sz w:val="18"/>' in c.items[0]        # default accept = KEEP the smaller font


def test_offer_normalizes_on_change_decision():
    c = _pass_conformer([_tbl('20', '18')])
    c.decisions = {'table-body-size_1': 'change:Normalize all table bodies to 11pt'}
    c._offer_table_body_normalization()
    assert '<w:sz w:val="18"/>' not in c.items[0]     # normalized to 11pt on explicit choice
