"""A centered display line (an equation, e.g. 'Performance Variance = ...') must NOT be turned into a
numbered body paragraph, and its centering must survive. Two mechanisms distorted it: classify() mapped a
centered Normal paragraph to Numbered Paragraph (adding a list number), and strip_direct() dropped the
direct jc=center (a paragraph style then left-/justified it)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from conformer.engine import Conformer   # noqa: E402

EQ = '<w:r><w:t>Performance Variance = Performance-Only PA Date &#8211; Beginning-of-Window PA Date</w:t></w:r>'


def test_classify_does_not_number_a_centered_display_line():
    para = ('<w:p><w:pPr><w:pStyle w:val="Normal"/><w:jc w:val="center"/>'
            '<w:ind w:left="720"/></w:pPr>' + EQ + '</w:p>')
    c = Conformer.__new__(Conformer)
    c.items = [para]
    c.b0 = 0
    c.numfmt = {}
    c.template_style_ids = set()
    c.say = lambda *a, **k: None
    c.numpr = lambda i: None                      # not a numbered paragraph
    changed = []
    c.set_style = lambda i, st: changed.append(st)
    c.classify()
    assert changed == []                          # NOT reclassified to Numbered Paragraph


def test_strip_direct_preserves_centered_alignment():
    para = ('<w:p><w:pPr><w:pStyle w:val="Normal"/><w:jc w:val="center"/>'
            '<w:ind w:left="720"/></w:pPr>' + EQ + '</w:p>')
    c = Conformer.__new__(Conformer)
    c.items = [para]
    c.b0 = 0
    c.disposition = 'clean'
    c.num = '<w:numbering></w:numbering>'
    c.styles = '<w:styles></w:styles>'
    c.say = lambda *a, **k: None
    c.strip_direct()
    assert '<w:jc w:val="center"/>' in c.items[0]  # centering preserved


def test_strip_direct_still_normalizes_noncenter_alignment():
    # a stray jc=left on body prose is NOT display intent -> it may still be normalized to the style
    para = ('<w:p><w:pPr><w:pStyle w:val="NumberedParagraph"/><w:jc w:val="left"/></w:pPr>'
            '<w:r><w:t>ordinary body text</w:t></w:r></w:p>')
    c = Conformer.__new__(Conformer)
    c.items = [para]
    c.b0 = 0
    c.disposition = 'clean'
    c.num = '<w:numbering></w:numbering>'
    c.styles = '<w:styles></w:styles>'
    c.say = lambda *a, **k: None
    c.strip_direct()
    assert '<w:jc w:val="left"/>' not in c.items[0]  # only center is treated as display intent
