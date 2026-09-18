"""P1 (§9): literal cross-reference -> REF field conversion now handles MULTI-LEVEL caption numbers
(Table 3.4.2-1), not only single-level (Table 3-1). Display-preserving (the field's cached result is the
original literal text). A multi-level Section ref is intentionally left alone (needs number simulation)."""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from conformer.engine import Conformer   # noqa: E402


def _c():
    c = Conformer.__new__(Conformer)
    c.disposition = 'clean'
    return c


def _para(text):
    return f'<w:p><w:r><w:t xml:space="preserve">{text}</w:t></w:r></w:p>'


def test_multilevel_caption_ref_becomes_field():
    c = _c()
    caps = {'Table 3.4.2-1': 'bmTbl'}
    xml = _para('see Table 3.4.2-1 for detail')
    nx, n = c._rebuild_xrefs_in(xml, caps, {})
    assert n == 1
    assert 'REF bmTbl \\h' in nx
    assert '<w:rStyle w:val="CrossReference"/>' in nx
    assert 'Table 3.4.2-1' in nx                 # display text preserved (cached field result)


def test_single_level_caption_ref_still_works():
    c = _c()
    caps = {'Figure 3-1': 'bmFig'}
    nx, n = c._rebuild_xrefs_in(_para('per Figure 3-1 above'), caps, {})
    assert n == 1 and 'REF bmFig' in nx


def test_bare_section_ref_still_works():
    c = _c()
    heads = {'5': 'bmH5'}
    nx, n = c._rebuild_xrefs_in(_para('discussed in Section 5 below'), heads and {}, heads)
    assert n == 1 and 'REF bmH5' in nx


def test_multilevel_section_ref_left_alone():
    c = _c()
    # "Section 3.4.2" needs the heading-number simulation to map to a bookmark -> not converted here
    nx, n = c._rebuild_xrefs_in(_para('see Section 3.4.2 for detail'), {}, {'3': 'bmH3'})
    assert n == 0


def test_unbookmarked_caption_ref_left_as_text():
    c = _c()
    nx, n = c._rebuild_xrefs_in(_para('see Table 9.9.9-9 now'), {}, {})   # no such target
    assert n == 0 and 'Table 9.9.9-9' in nx
