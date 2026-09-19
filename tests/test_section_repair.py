"""GPT re-review R7: fix_sections used to hard-code US-Letter portrait dimensions (12240x15840) and
Letter margins when repairing a landscape final section, so an A4 report's portrait section came out
Letter. It now derives portrait dimensions from the section's own landscape size (swap w/h, paper-size
preserving) and portrait margins from the report's prior portrait section. Fictitious content."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from conformer.engine import Conformer   # noqa: E402

_A4_PORTRAIT_SECT = ('<w:sectPr><w:pgSz w:w="11906" w:h="16838" w:code="9"/>'
                     '<w:pgMar w:top="1440" w:right="1080" w:bottom="1440" w:left="1080" '
                     'w:header="567" w:footer="567" w:gutter="0"/></w:sectPr>')
_A4_LANDSCAPE_SECT = ('<w:sectPr><w:pgSz w:w="16838" w:h="11906" w:orient="landscape" w:code="9"/>'
                      '<w:pgMar w:top="1080" w:right="1440" w:bottom="1080" w:left="1440" '
                      'w:header="720" w:footer="720" w:gutter="0"/></w:sectPr>')


def _conformer(items):
    c = Conformer.__new__(Conformer)
    c.items = list(items)
    c.b0 = 0
    c.log = []
    c.judgment = []
    return c


def test_r7_a4_landscape_section_returns_to_a4_portrait_not_letter():
    items = [
        '<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>INTRO</w:t></w:r></w:p>',
        f'<w:p><w:pPr>{_A4_PORTRAIT_SECT}</w:pPr><w:r><w:t>ends portrait</w:t></w:r></w:p>',
        '<w:p><w:r><w:t>landscape table area</w:t></w:r></w:p>',
        '<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>NEXT</w:t></w:r></w:p>',
        '<w:p><w:r><w:t>after</w:t></w:r></w:p>',
        _A4_LANDSCAPE_SECT,                       # final body section (items[-1]) is A4 landscape
    ]
    c = _conformer(items)
    c.fix_sections()
    final = c.items[-1]
    assert 'orient="landscape"' not in final                       # returned to portrait
    assert '<w:pgSz w:w="11906" w:h="16838"' in final              # A4 portrait, NOT Letter
    assert '12240' not in final and '15840' not in final           # no hard-coded Letter size
    assert 'w:header="567"' in final                               # margins taken from the prior A4 portrait
    # the landscape block is re-established on the paragraph before the resuming Heading1
    assert 'orient="landscape"' in c.items[2]


def test_r7_letter_report_still_returns_to_letter():
    letter_land = ('<w:sectPr><w:pgSz w:w="15840" w:h="12240" w:orient="landscape" w:code="9"/>'
                   '<w:pgMar w:top="1080" w:right="1440" w:bottom="1080" w:left="1440" '
                   'w:header="720" w:footer="720" w:gutter="0"/></w:sectPr>')
    letter_portrait = ('<w:sectPr><w:pgSz w:w="12240" w:h="15840" w:code="9"/>'
                       '<w:pgMar w:top="2160" w:right="1440" w:bottom="1440" w:left="1440" '
                       'w:header="1872" w:footer="720" w:gutter="0"/></w:sectPr>')
    items = [
        '<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>INTRO</w:t></w:r></w:p>',
        f'<w:p><w:pPr>{letter_portrait}</w:pPr><w:r><w:t>ends portrait</w:t></w:r></w:p>',
        '<w:p><w:r><w:t>landscape</w:t></w:r></w:p>',
        '<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>NEXT</w:t></w:r></w:p>',
        letter_land,
    ]
    c = _conformer(items)
    c.fix_sections()
    final = c.items[-1]
    assert 'orient="landscape"' not in final
    assert '<w:pgSz w:w="12240" w:h="15840"' in final              # Letter stays Letter
