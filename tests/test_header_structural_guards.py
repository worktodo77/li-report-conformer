"""GPT audit F9: structural guards for header-cell paragraph-style normalization.

`_force_header_paragraph_style` gives plain header-cell body paragraphs the 10pt Table Header style. Two
OOXML shapes must not be mishandled: (1) a paragraph carrying a DIRECT numPr is a list item — reclassifying
it would silently strip its numbering (an unauthorized reference flip), so it is left as authored; (2) a
self-closing <w:pPr/> must gain the style IN PLACE, never as a second <w:pPr> element (invalid paragraph
structure). Fictitious content."""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from conformer.engine import Conformer   # noqa: E402

fp = Conformer._force_header_paragraph_style


def _pcount(p):
    return len(re.findall(r'<w:pPr\b', p))


def test_plain_default_paragraph_gets_header_style():
    p = '<w:p><w:r><w:t>Head</w:t></w:r></w:p>'
    out = fp(p)
    assert '<w:pStyle w:val="TableHeader"/>' in out
    assert _pcount(out) == 1


def test_self_closing_ppr_does_not_duplicate():
    # F9: <w:pPr/> must become a single styled <w:pPr>...</w:pPr>, not a paragraph with two pPr children.
    p = '<w:p><w:pPr/><w:r><w:t>Head</w:t></w:r></w:p>'
    out = fp(p)
    assert _pcount(out) == 1, out
    assert '<w:pStyle w:val="TableHeader"/>' in out
    assert '<w:pPr/>' not in out


def test_body_style_paragraph_is_reclassified():
    p = '<w:p><w:pPr><w:pStyle w:val="TableData"/></w:pPr><w:r><w:t>Head</w:t></w:r></w:p>'
    out = fp(p)
    assert '<w:pStyle w:val="TableHeader"/>' in out and 'TableData' not in out


def test_numbered_paragraph_is_never_reclassified():
    # F9: a direct numPr means a numbered/bulleted list item — leave the style AND the numbering untouched
    # even though its pStyle (Normal) is otherwise a body style eligible for reclassification.
    p = ('<w:p><w:pPr><w:pStyle w:val="Normal"/>'
         '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="7"/></w:numPr></w:pPr>'
         '<w:r><w:t>a numbered item</w:t></w:r></w:p>')
    out = fp(p)
    assert out == p                                   # untouched: style kept, numbering kept
    assert '<w:numId w:val="7"/>' in out


def test_heading_paragraph_is_never_reclassified():
    p = '<w:p><w:pPr><w:pStyle w:val="Heading3"/></w:pPr><w:r><w:t>A heading</w:t></w:r></w:p>'
    assert fp(p) == p                                 # non-body deliberate style left as authored
